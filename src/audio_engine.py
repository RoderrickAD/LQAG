import os
import torch
import sounddevice as sd
import soundfile as sf
import threading
import queue
import re
import time
import numpy as np # Wichtig für Audio-Zusammenfügen
from TTS.api import TTS
import datetime

class AudioEngine:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        # Initialisierung
        self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(self.device)
        
        self.audio_queue = queue.Queue()
        self.is_playing = False
        self.stop_signal = False
        self.playback_thread = None
        self.progress_callback = None

    def speak(self, text, speaker_wav, save_dir=None, on_progress=None):
        if not text: return
        if not os.path.exists(speaker_wav): return

        self.stop()
        time.sleep(0.1)
        
        self.stop_signal = False
        self.is_playing = True
        self.progress_callback = on_progress

        threading.Thread(target=self._producer, args=(text, speaker_wav, save_dir), daemon=True).start()
        self.playback_thread = threading.Thread(target=self._consumer, daemon=True)
        self.playback_thread.start()

    def stop(self):
        self.stop_signal = True
        self.is_playing = False
        with self.audio_queue.mutex:
            self.audio_queue.queue.clear()
        sd.stop()

    def _producer(self, text, speaker_wav, save_dir):
        try:
            # Text reinigen
            clean_text = text.replace("\n", " ").replace("\r", "")
            clean_text = re.sub(' +', ' ', clean_text)
            
            # Splitten
            sentences = re.split(r'(?<=[.!?])\s+', clean_text)
            sentences = [s.strip() for s in sentences if len(s.strip()) > 1]
            total = len(sentences)
            
            if self.progress_callback: self.progress_callback(0, total)

            # Container für das komplette Audio
            full_audio_parts = [] 

            for i, sentence in enumerate(sentences):
                if self.stop_signal: return
                
                # Chunking für lange Sätze
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
                    
                    # 1. Zur Wiedergabe senden
                    self.audio_queue.put((data, fs, i + 1, total))
                    
                    # 2. Für das Speichern sammeln
                    full_audio_parts.append(data)
            
            # Ende Signal für Player
            self.audio_queue.put(None)
            
            # --- ALLES SPEICHERN ---
            if save_dir and full_audio_parts and not self.stop_signal:
                try:
                    # Alle Teile zusammenkleben
                    full_audio = np.concatenate(full_audio_parts)
                    
                    # Dateinamen generieren
                    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"Recording_{ts}.wav"
                    filepath = os.path.join(save_dir, filename)
                    
                    # Speichern (Samplerate ist meistens 24000 bei XTTS)
                    sf.write(filepath, full_audio, 24000)
                    print(f"💾 Audio gespeichert: {filepath}") # Landet im Log
                    
                except Exception as e:
                    print(f"Fehler beim Speichern: {e}")

        except Exception as e:
            print(f"Generator Fehler: {e}")
            self.audio_queue.put(None)

    def _consumer(self):
        while not self.stop_signal:
            try:
                try:
                    item = self.audio_queue.get(timeout=1)
                except queue.Empty: continue

                if item is None: break
                
                data, fs, cur, tot = item
                if self.stop_signal: break

                sd.play(data, samplerate=24000)
                sd.wait()
                
                if self.progress_callback:
                    self.progress_callback(cur, tot)

            except: break
        self.is_playing = False
