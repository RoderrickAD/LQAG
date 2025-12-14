import os
import torch
import sounddevice as sd
import soundfile as sf
import threading
import queue
import re
import time
import numpy as np
from TTS.api import TTS
import datetime
import traceback

class AudioEngine:
    def __init__(self):
        try:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        except:
            self.device = "cpu"
            
        # Wir fangen hier Fehler ab, falls TTS gar nicht laden kann
        try:
            print(f"Lade TTS auf {self.device}...")
            self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(self.device)
        except Exception as e:
            self.log_to_file(f"INIT CRASH: {e}")
            self.tts = None
        
        self.audio_queue = queue.Queue()
        self.is_playing = False
        self.is_paused = False
        self.stop_signal = False
        self.playback_thread = None
        self.progress_callback = None
        self.volume = 1.0
        
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.root_dir = os.path.dirname(self.base_dir)
        self.error_log = os.path.join(self.root_dir, "debug", "audio_error.log")

    def log_to_file(self, msg):
        try:
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            with open(self.error_log, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {msg}\n")
        except: pass

    def set_volume(self, val_0_to_100):
        try:
            vol = float(val_0_to_100) / 100.0
            self.volume = max(0.0, min(1.0, vol))
        except: pass

    def toggle_pause(self):
        if not self.is_playing: return False
        self.is_paused = not self.is_paused
        if self.is_paused: sd.stop()
        return self.is_paused

    def speak(self, text, speaker_wav, save_dir=None, on_progress=None, debug_mode=False):
        if not self.tts: 
            self.log_to_file("TTS Engine wurde nicht geladen!")
            return
        if not text: return
        
        self.stop()
        time.sleep(0.1)
        
        self.stop_signal = False
        self.is_paused = False
        self.is_playing = True
        self.progress_callback = on_progress

        threading.Thread(target=self._producer, args=(text, speaker_wav, save_dir, debug_mode), daemon=True).start()
        self.playback_thread = threading.Thread(target=self._consumer, daemon=True)
        self.playback_thread.start()

    def stop(self):
        self.stop_signal = True
        self.is_playing = False
        self.is_paused = False
        with self.audio_queue.mutex:
            self.audio_queue.queue.clear()
        sd.stop()

    def _producer(self, text, speaker_wav, save_dir, debug_mode):
        try:
            self.log_to_file(f"Start: {text[:30]}... | Voice: {os.path.basename(speaker_wav)}")
            
            clean_text = text.replace("\n", " ").replace("\r", "")
            clean_text = re.sub(' +', ' ', clean_text)
            
            sentences = re.split(r'(?<=[.!?])\s+', clean_text)
            sentences = [s.strip() for s in sentences if len(s.strip()) > 1]
            total = len(sentences)
            
            if self.progress_callback: 
                self.progress_callback(0, total, "")

            full_audio_parts = [] 

            for i, sentence in enumerate(sentences):
                if self.stop_signal: return
                
                # Chunking Logic
                chunks = [sentence]
                if len(sentence) > 230:
                    chunks = []
                    sub = re.split(r'(?<=[,;])\s+', sentence)
                    curr = ""
                    for p in sub:
                        if len(curr) + len(p) < 230: curr += p + " "
                        else: 
                            chunks.append(curr.strip())
                            curr = p + " "
                    if curr: chunks.append(curr.strip())

                for chunk in chunks:
                    if self.stop_signal: return
                    
                    # --- SICHERHEITS-CHECK VOR DEM CRASH ---
                    # 1. Ist der Text leer?
                    if not chunk or not chunk.strip():
                        self.log_to_file("Überspringe leeren Text-Chunk.")
                        continue
                    
                    # 2. Ist die Audio-Datei WIRKLICH da?
                    if not speaker_wav or not os.path.exists(speaker_wav):
                        self.log_to_file(f"CRITICAL ERROR: Stimme nicht gefunden: {speaker_wav}")
                        continue
                    
                    out_temp = "temp_gen.wav"
                    
                    try:
                        self.tts.tts_to_file(
                            text=chunk, 
                            file_path=out_temp,
                            speaker_wav=speaker_wav, 
                            language="de",
                            temperature=0.65, 
                            speed=1.05,
                            split_sentences=False
                        )
                    except Exception as e:
                        # Hier fangen wir den Fehler ab, damit der Thread NICHT stirbt!
                        self.log_to_file(f"TTS Fehler bei Chunk '{chunk[:10]}...': {e}")
                        # Wir machen einfach mit dem nächsten Chunk weiter
                        continue
                    
                    if os.path.exists(out_temp):
                        data, fs = sf.read(out_temp)
                        self.audio_queue.put((data, fs, i + 1, total, sentence))
                        if debug_mode:
                            full_audio_parts.append(data)
            
            self.audio_queue.put(None)
            self.log_to_file("Fertig generiert.")
            
            if debug_mode and save_dir and full_audio_parts and not self.stop_signal:
                try:
                    full_audio = np.concatenate(full_audio_parts)
                    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    sf.write(os.path.join(save_dir, f"Recording_{ts}.wav"), full_audio, 24000)
                except: pass

        except Exception as e:
            self.log_to_file(f"FATAL PRODUCER: {e}")
            self.log_to_file(traceback.format_exc())
            self.audio_queue.put(None)

    def _consumer(self):
        try:
            while not self.stop_signal:
                if self.is_paused:
                    time.sleep(0.1)
                    continue
                try:
                    try:
                        item = self.audio_queue.get(timeout=1)
                    except queue.Empty: continue

                    if item is None: break
                    
                    data, fs, cur, tot, text_content = item
                    
                    if self.stop_signal: break

                    if self.progress_callback:
                        self.progress_callback(cur, tot, text_content)

                    final_data = data * self.volume
                    
                    try:
                        sd.play(final_data, samplerate=24000)
                        sd.wait()
                    except Exception as e:
                        self.log_to_file(f"AUDIO PLAY ERROR: {e}")

                except Exception as e:
                    self.log_to_file(f"Consumer Loop Error: {e}")
                    break
        except Exception as e:
            self.log_to_file(f"Consumer Fatal: {e}")
        finally:
            self.is_playing = False
