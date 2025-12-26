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
        self.debug_dir = os.path.join(self.root_dir, "debug")
        self.error_log = os.path.join(self.debug_dir, "audio_error.log")

    def log_to_file(self, msg):
        try:
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            with open(self.error_log, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {msg}\n")
        except: pass

    def get_available_voices(self, api_key):
        url = "https://api.elevenlabs.io/v1/voices"
        try:
            res = requests.get(url, headers={"xi-api-key": api_key}, timeout=10)
            return res.json().get("voices", []) if res.status_code == 200 else []
        except: return []

    def generate_voice_library(self, settings, progress_callback=None):
        api_key = settings.get("elevenlabs_api_key")
        all_voices = self.get_available_voices(api_key)
        if not all_voices: return False
        
        males = [v for v in all_voices if v.get("labels", {}).get("gender") == "male"]
        females = [v for v in all_voices if v.get("labels", {}).get("gender") == "female"]
        targets = []
        if males or females:
            for v in random.sample(males, min(len(males), 4)): targets.append((f"male_{v['name']}", v['voice_id']))
            for v in random.sample(females, min(len(females), 4)): targets.append((f"female_{v['name']}", v['voice_id']))
        else:
            for v in all_voices[:6]: targets.append((f"neutral_{v['name']}", v['voice_id']))
        
        text = "Seid gegrüßt, Reisender! Ich habe schon viele Monde lang auf jemanden wie Euch gewartet."
        save_p = os.path.join(self.root_dir, "resources", "voices", "generated")
        os.makedirs(save_p, exist_ok=True)

        for i, (name, v_id) in enumerate(targets):
            if self.stop_signal: break
            if progress_callback: progress_callback(i + 1, len(targets), f"Generiere: {name}")
            try:
                res = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{v_id}", 
                                    json={"text": text, "model_id": "eleven_multilingual_v2"}, 
                                    headers={"xi-api-key": api_key}, timeout=30)
                if res.status_code == 200:
                    with open(os.path.join(save_p, f"{name}.wav"), "wb") as f: f.write(res.content)
            except: pass
            time.sleep(0.5)
        return True

    def speak(self, text, speaker_ref, settings, on_progress=None):
        self.stop()
        self.stop_signal = False
        self.is_playing = True
        debug = settings.get("debug_mode", False)
        
        if settings.get("use_elevenlabs") and settings.get("elevenlabs_api_key"):
            target = self._producer_elevenlabs
        else:
            if self.tts is None: self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(self.device)
            target = self._producer_local
        threading.Thread(target=target, args=(text, speaker_ref, settings, on_progress, debug), daemon=True).start()
        threading.Thread(target=self._consumer, args=(on_progress,), daemon=True).start()

    def _producer_local(self, text, speaker_wav, settings, on_progress, debug):
        sentences = self._split(text)
        full_audio = []
        for i, s in enumerate(sentences):
            if self.stop_signal or not s.strip(): continue
            out = "temp_gen.wav"
            self.tts.tts_to_file(text=s, file_path=out, speaker_wav=speaker_wav, language="de", temperature=0.75, speed=1.0, repetition_penalty=2.0)
            data, fs = sf.read(out)
            self.audio_queue.put((data, 24000, i + 1, len(sentences), s))
            if debug: full_audio.append(data)
        self.audio_queue.put(None)
        if debug and full_audio:
            sf.write(os.path.join(self.debug_dir, f"Recording_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"), np.concatenate(full_audio), 24000)

    def _producer_elevenlabs(self, text, voice_id, settings, on_progress, debug):
        sentences = self._split(text)
        full_audio = []
        for i, s in enumerate(sentences):
            if self.stop_signal: break
            try:
                res = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream", 
                                    json={"text": s, "model_id": "eleven_multilingual_v2"}, 
                                    headers={"xi-api-key": settings.get("elevenlabs_api_key")}, timeout=15)
                if res.status_code == 200:
                    with open("temp_el.mp3", "wb") as f: f.write(res.content)
                    data, fs = sf.read("temp_el.mp3")
                    self.audio_queue.put((data, fs, i+1, len(sentences), s))
                    if debug: full_audio.append(data)
            except: pass
        self.audio_queue.put(None)
        if debug and full_audio:
            sf.write(os.path.join(self.debug_dir, f"Rec_{datetime.datetime.now().strftime('%H%M%S')}.wav"), np.concatenate(full_audio), 44100)

    def _split(self, text):
        return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.replace("\n", " ")) if len(s.strip()) > 1]

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
        with self.audio_queue.mutex: self.audio_queue.queue.clear()

    def set_volume(self, val):
        self.volume = max(0.0, min(1.0, float(val) / 100.0))

    def toggle_pause(self):
        if not self.is_playing: return False
        self.is_paused = not self.is_paused
        if self.is_paused: sd.stop()
        return self.is_paused
