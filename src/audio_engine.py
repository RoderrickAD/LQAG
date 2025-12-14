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

class AudioEngine:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(self.device)
        
        self.audio_queue = queue.Queue()
        self.is_playing = False
        self.is_paused = False # NEU
        self.stop_signal = False
        self.playback_thread = None
        self.progress_callback = None
        self.volume = 1.0

    def set_volume(self, val_0_to_100):
        try:
            vol = float(val_0_to_100) / 100.0
            self.volume = max(0.0, min(1.0, vol))
        except: pass

    def toggle_pause(self):
        """Schaltet Pause an/aus"""
        if not self.is_playing: return False
        self.is_paused = not self.is_paused
        # Wenn wir pausieren, stoppen wir den aktuellen Sound sofort
        if self.is_paused:
            sd.stop()
        return self.is_paused

    def speak(self, text, speaker_wav, save_dir=None, on_progress=None):
        if not text: return
        self.stop()
        time.sleep(0.1)
        
        self.stop_signal = False
        self.is_paused = False
        self.is_playing = True
        self.progress_callback = on_progress

        threading.Thread(target=self._producer, args=(text, speaker_wav, save_dir), daemon=True).start()
        self.playback_thread = threading.Thread(target=self._consumer, daemon=True)
        self.playback_thread.start()

    def stop(self):
        self.stop_signal = True
        self.is_playing = False
        self.is_paused = False
        with self.audio_queue.mutex:
            self.audio_queue.queue.clear()
        sd.stop()

    def _producer(self, text, speaker_wav, save_dir):
        # ... (Identisch wie vorher, keine Änderungen nötig) ...
        try:
            clean_text = text.replace("\n", " ").replace("\r", "")
            clean_text = re.sub(' +', ' ', clean_text)
            
            # Splitten am Satzende (.!?)
            sentences = re.split(r'(?<=[.!?])\s+', clean_text)
            sentences = [s.strip() for s in sentences if len(s.strip()) > 1]
            total = len(sentences)
            
            # Initiale Meldung an GUI (Satz 0 von X)
            if self.progress_callback: 
                # Wir übergeben jetzt den TEXT des Satzes mit!
                self.progress_callback(0, total, "")

            full_audio_parts = [] 

            for i, sentence in enumerate(sentences):
                if self.stop_signal: return
                
                # Chunking Logic (wie vorher)
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
                    
                    out_temp = "temp_gen.wav"
                    self.tts.tts_to_file(
                        text=chunk, 
                        file_path=out_temp,
                        speaker_wav=speaker_wav, 
                        language="de",
                        temperature=0.65, 
                        speed=1.05,
                        split_sentences=False
                    )
                    
                    data, fs = sf.read(out_temp)
                    
                    # WICHTIG: Wir senden jetzt den SATZ-TEXT mit in die Queue
                    self.audio_queue.put((data, fs, i + 1, total, sentence))
                    
                    full_audio_parts.append(data)
            
            self.audio_queue.put(None)
            
            if save_dir and full_audio_parts and not self.stop_signal:
                try:
                    full_audio = np.concatenate(full_audio_parts)
                    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    sf.write(os.path.join(save_dir, f"Recording_{ts}.wav"), full_audio, 24000)
                except: pass

        except Exception as e:
            print(f"Gen Error: {e}")
            self.audio_queue.put(None)

    def _consumer(self):
        while not self.stop_signal:
            # 1. PAUSE CHECK
            if self.is_paused:
                time.sleep(0.1)
                continue

            try:
                try:
                    item = self.audio_queue.get(timeout=1)
                except queue.Empty: continue

                if item is None: break
                
                # Entpacken (jetzt mit text_content)
                data, fs, cur, tot, text_content = item
                
                if self.stop_signal: break

                # GUI Update VOR dem Abspielen (damit Text synchron erscheint)
                if self.progress_callback:
                    self.progress_callback(cur, tot, text_content)

                final_data = data * self.volume
                sd.play(final_data, samplerate=24000)
                sd.wait() # Wartet bis Audio fertig ist

            except: break
        self.is_playing = False
