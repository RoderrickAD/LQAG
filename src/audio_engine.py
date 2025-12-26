import os
import requests # Für ElevenLabs API
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
        
        # Initialisierungspfade
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.root_dir = os.path.dirname(self.base_dir)
        self.error_log = os.path.join(self.root_dir, "debug", "audio_error.log")
        
        # Audio Queue & Flags
        self.audio_queue = queue.Queue()
        self.is_playing = False
        self.is_paused = False
        self.stop_signal = False
        self.volume = 1.0

    def log_to_file(self, msg):
        try:
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            with open(self.error_log, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {msg}\n")
        except: pass

    def load_local_tts(self):
        """Lädt XTTS nur bei Bedarf, um RAM zu sparen"""
        if self.tts is None:
            try:
                self.log_to_file(f"Lade lokales XTTS auf {self.device}...")
                self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(self.device)
            except Exception as e:
                self.log_to_file(f"XTTS Load Error: {e}")

    def speak(self, text, speaker_wav, settings, save_dir=None, on_progress=None):
        if not text: return
        self.stop()
        time.sleep(0.1)
        
        self.stop_signal = False
        self.is_playing = True
        
        # Entscheidung: ElevenLabs oder Lokal
        if settings.get("use_elevenlabs") and settings.get("elevenlabs_api_key"):
            target_func = self._producer_elevenlabs
        else:
            self.load_local_tts()
            target_func = self._producer_local
            
        threading.Thread(target=target_func, args=(text, speaker_wav, settings, save_dir, on_progress), daemon=True).start()
        threading.Thread(target=self._consumer, args=(on_progress,), daemon=True).start()

    def _producer_local(self, text, speaker_wav, settings, save_dir, on_progress):
        # ... (Deine bisherige XTTS Logik mit den Qualitäts-Fixes aus V15) ...
        try:
            sentences = self._clean_and_split(text)
            total = len(sentences)
            for i, sentence in enumerate(sentences):
                if self.stop_signal: return
                if not sentence.strip(): continue # Fix für ValueError [cite: 2, 4]
                
                out_temp = "temp_gen.wav"
                self.tts.tts_to_file(
                    text=sentence, file_path=out_temp, speaker_wav=speaker_wav, language="de",
                    temperature=0.75, speed=1.0, repetition_penalty=2.0
                )
                data, fs = sf.read(out_temp)
                self.audio_queue.put((data, fs, i + 1, total, sentence))
            self.audio_queue.put(None)
        except Exception as e:
            self.log_to_file(f"Local Gen Error: {e}")

    def _producer_elevenlabs(self, text, speaker_wav, settings, save_dir, on_progress):
        """API Anbindung für ElevenLabs"""
        try:
            api_key = settings.get("elevenlabs_api_key")
            # Wir nehmen an, dass 'speaker_wav' hier eine Voice-ID oder ein Pfad zu einem Voice-Mapping ist
            voice_id = "21m00Tcm4TlvDq8ikWAM" # Standard 'Rachel', müsste dynamisch sein
            
            sentences = self._clean_and_split(text)
            total = len(sentences)
            
            for i, sentence in enumerate(sentences):
                if self.stop_signal: return
                
                url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
                headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
                data = {"text": sentence, "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}
                
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
        clean_text = text.replace("\n", " ").replace("\r", "")
        clean_text = re.sub(' +', ' ', clean_text)
        sentences = re.split(r'(?<=[.!?])\s+', clean_text)
        return [s.strip() for s in sentences if len(s.strip()) > 1]

    def _consumer(self, on_progress):
        while not self.stop_signal:
            if self.is_paused:
                time.sleep(0.1)
                continue
            item = self.audio_queue.get()
            if item is None: break
            data, fs, cur, tot, text = item
            if on_progress: on_progress(cur, tot, text)
            sd.play(data * self.volume, samplerate=fs)
            sd.wait()
        self.is_playing = False

    def stop(self):
        self.stop_signal = True
        sd.stop()
