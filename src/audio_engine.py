import os
import requests
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
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tts = None
        
        self.audio_queue = queue.Queue()
        self.is_playing = False
        self.is_paused = False
        self.stop_signal = False
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

    def load_local_tts(self):
        if self.tts is None:
            try:
                self.log_to_file(f"Lade lokales XTTS auf {self.device}...")
                self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(self.device)
            except Exception as e:
                self.log_to_file(f"XTTS Load Error: {e}")

    def speak(self, text, speaker_ref, settings, save_dir=None, on_progress=None):
        if not text: return
        self.stop()
        time.sleep(0.1)
        
        self.stop_signal = False
        self.is_playing = True
        
        # Wechsle Modus basierend auf Einstellungen
        if settings.get("use_elevenlabs") and settings.get("elevenlabs_api_key"):
            target_func = self._producer_elevenlabs
        else:
            self.load_local_tts()
            target_func = self._producer_local
            
        threading.Thread(target=target_func, args=(text, speaker_ref, settings, save_dir, on_progress), daemon=True).start()
        self.playback_thread = threading.Thread(target=self._consumer, args=(on_progress,), daemon=True)
        self.playback_thread.start()

    def _producer_local(self, text, speaker_wav, settings, save_dir, on_progress):
        try:
            sentences = self._clean_and_split(text)
            total = len(sentences)
            for i, sentence in enumerate(sentences):
                if self.stop_signal: return
                if not sentence.strip(): continue [cite: 4]
                
                out_temp = "temp_gen.wav"
                self.tts.tts_to_file(
                    text=sentence, file_path=out_temp, speaker_wav=speaker_wav, language="de",
                    temperature=0.75, speed=1.0, repetition_penalty=2.0,
                    top_p=0.85, top_k=50 # Qualitäts-Parameter aus V15
                )
                data, fs = sf.read(out_temp)
                self.audio_queue.put((data, fs, i + 1, total, sentence))
            self.audio_queue.put(None)
        except Exception as e:
            self.log_to_file(f"Local Gen Error: {e}")

    def _producer_elevenlabs(self, text, voice_id, settings, save_dir, on_progress):
        try:
            api_key = settings.get("elevenlabs_api_key")
            sentences = self._clean_and_split(text)
            total = len(sentences)
            
            for i, sentence in enumerate(sentences):
                if self.stop_signal: return
                
                url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
                headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
                data = {
                    "text": sentence, 
                    "model_id": "eleven_multilingual_v2", 
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
                }
                
                response = requests.post(url, json=data, headers=headers)
                if response.status_code == 200:
                    with open("temp_el.mp3", "wb") as f:
                        f.write(response.content)
                    data_audio, fs = sf.read("temp_el.mp3")
                    self.audio_queue.put((data_audio, fs, i + 1, total, sentence))
                else:
                    self.log_to_file(f"ElevenLabs API Error: {response.text}")
            self.audio_queue.put(None)
        except Exception as e:
            self.log_to_file(f"ElevenLabs Gen Error: {e}")

    def _clean_and_split(self, text):
        clean = text.replace("\n", " ").replace("\r", "")
        clean = re.sub(' +', ' ', clean)
        return [s.strip() for s in re.split(r'(?<=[.!?])\s+', clean) if len(s.strip()) > 1]

    def _consumer(self, on_progress):
        while not self.stop_signal:
            if self.is_paused:
                time.sleep(0.1)
                continue
            try:
                item = self.audio_queue.get(timeout=1)
                if item is None: break
                data, fs, cur, tot, text = item
                if on_progress: on_progress(cur, tot, text)
                sd.play(data * self.volume, samplerate=fs)
                sd.wait()
            except queue.Empty: continue
        self.is_playing = False

    def stop(self):
        self.stop_signal = True
        sd.stop()
