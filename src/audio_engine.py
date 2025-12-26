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
import random

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

    def get_available_voices(self, api_key):
        url = "https://api.elevenlabs.io/v1/voices"
        headers = {"xi-api-key": api_key}
        try:
            response = requests.get(url, headers=headers)
            return response.json().get("voices", []) if response.status_code == 200 else []
        except: return []

    def generate_voice_library(self, settings, progress_callback=None):
        api_key = settings.get("elevenlabs_api_key")
        if not api_key: return False

        all_voices = self.get_available_voices(api_key)
        males = [v for v in all_voices if v.get("labels", {}).get("gender") == "male"]
        females = [v for v in all_voices if v.get("labels", {}).get("gender") == "female"]

        # Jeweils bis zu 5 zufällige Stimmen wählen
        selected_m = random.sample(males, min(len(males), 5))
        selected_f = random.sample(females, min(len(females), 5))
        
        targets = []
        for v in selected_m: targets.append((f"male_{v['name']}", v['voice_id']))
        for v in selected_f: targets.append((f"female_{v['name']}", v['voice_id']))

        ideal_text = ("Seid gegrüßt, Reisender! Ich habe schon viele Monde lang auf jemanden wie Euch gewartet. "
                      "Könnt Ihr das Flüstern des Windes in den alten Ruinen hören? Seid wachsam, denn die Schatten "
                      "in Mittelerde werden von Tag zu Tag länger. Aber verzagt nicht! Gemeinsam werden wir einen "
                      "Weg finden, um das Licht zurückzubringen. Sagt mir, seid Ihr bereit für dieses Abenteuer?")

        save_path = os.path.join(self.root_dir, "resources", "voices", "generated")
        if not os.path.exists(save_path): os.makedirs(save_path)

        count = 0
        for name, v_id in targets:
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{v_id}"
            headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
            data = {"text": ideal_text, "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}
            
            res = requests.post(url, json=data, headers=headers)
            if res.status_code == 200:
                with open(os.path.join(save_path, f"{name}.wav"), "wb") as f: f.write(res.content)
                count += 1
                if progress_callback: progress_callback(count, len(targets), f"Generiert: {name}")
            time.sleep(0.5)
        return count > 0

    def load_local_tts(self):
        if self.tts is None:
            self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(self.device)

    def set_volume(self, val):
        self.volume = max(0.0, min(1.0, float(val) / 100.0))

    def toggle_pause(self):
        if not self.is_playing: return False
        self.is_paused = not self.is_paused
        if self.is_paused: sd.stop()
        return self.is_paused

    def speak(self, text, speaker_ref, settings, on_progress=None):
        self.stop()
        self.stop_signal = False
        self.is_playing = True
        
        if settings.get("use_elevenlabs") and settings.get("elevenlabs_api_key"):
            target = self._producer_elevenlabs
        else:
            self.load_local_tts()
            target = self._producer_local
            
        threading.Thread(target=target, args=(text, speaker_ref, settings, on_progress), daemon=True).start()
        threading.Thread(target=self._consumer, args=(on_progress,), daemon=True).start()

    def _producer_local(self, text, speaker_wav, settings, on_progress):
        sentences = self._split(text)
        for i, s in enumerate(sentences):
            if self.stop_signal or not s.strip(): continue
            out = "temp_gen.wav"
            self.tts.tts_to_file(text=s, file_path=out, speaker_wav=speaker_wav, language="de", temperature=0.75, speed=1.0, repetition_penalty=2.0)
            self.audio_queue.put((sf.read(out)[0], 24000, i + 1, len(sentences), s))
        self.audio_queue.put(None)

    def _producer_elevenlabs(self, text, voice_id, settings, on_progress):
        sentences = self._split(text)
        for i, s in enumerate(sentences):
            if self.stop_signal: break
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
            res = requests.post(url, json={"text": s, "model_id": "eleven_multilingual_v2"}, headers={"xi-api-key": settings.get("elevenlabs_api_key")})
            if res.status_code == 200:
                with open("temp_el.mp3", "wb") as f: f.write(res.content)
                self.audio_queue.put((sf.read("temp_el.mp3")[0], 44100, i+1, len(sentences), s))
        self.audio_queue.put(None)

    def _split(self, text):
        t = text.replace("\n", " ")
        return [s.strip() for s in re.split(r'(?<=[.!?])\s+', t) if len(s.strip()) > 1]

    def _consumer(self, on_progress):
        while not self.stop_signal:
            if self.is_paused: time.sleep(0.1); continue
            try:
                item = self.audio_queue.get(timeout=1)
                if item is None: break
                data, fs, cur, tot, txt = item
                if on_progress: on_progress(cur, tot, txt)
                sd.play(data * self.volume, samplerate=fs)
                sd.wait()
            except: continue
        self.is_playing = False

    def stop(self):
        self.stop_signal = True
        sd.stop()
