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
import traceback
import json

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
        self.voice_map_path = os.path.join(self.root_dir, "resources", "voices", "generated", "voice_map.json")
        os.makedirs(self.debug_dir, exist_ok=True)

    def log_to_file(self, msg):
        try:
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            with open(self.error_log, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {msg}\n")
        except: pass

    def load_voice_map(self):
        if os.path.exists(self.voice_map_path):
            try:
                with open(self.voice_map_path, "r") as f: return json.load(f)
            except: return {}
        return {}

    def save_voice_map(self, data):
        try:
            with open(self.voice_map_path, "w") as f: json.dump(data, f, indent=4)
        except: pass

    # --- SMARTE REQUEST FUNKTION (KEY ROTATION) ---
    def _make_elevenlabs_request(self, method, url, json_data, settings, timeout=20):
        """Probiert alle Keys nacheinander durch, wenn einer failt (401/429)"""
        keys = settings.get("elevenlabs_api_keys", [])
        if not keys: return None
        
        for key in keys:
            headers = {"xi-api-key": key, "Content-Type": "application/json"}
            try:
                if method == "GET":
                    res = requests.get(url, headers=headers, timeout=timeout)
                else:
                    res = requests.post(url, json=json_data, headers=headers, timeout=timeout)
                
                # Wenn erfolgreich: Fertig!
                if res.status_code == 200:
                    return res
                
                # Wenn Quota leer (401 Unauthorized oder 429 Too Many Requests)
                if res.status_code in [401, 402, 429]:
                    self.log_to_file(f"Key {key[:5]}... leer/fehlerhaft ({res.status_code}). Versuche nächsten...")
                    continue # Nächster Key in der Schleife
                
                # Bei anderen Fehlern (500 etc) abbrechen
                return res
            except: 
                continue # Bei Netzwerkfehler nächsten Key probieren
        
        return None # Alle Keys gescheitert

    # --- GENERATOR ---
    def generate_voice_library(self, settings, progress_callback=None):
        # Nutzt jetzt die Smart Request Funktion für GET
        res = self._make_elevenlabs_request("GET", "https://api.elevenlabs.io/v1/voices", None, settings)
        all_voices = res.json().get("voices", []) if res and res.status_code == 200 else []
        
        if not all_voices: return False

        males = [v for v in all_voices if v.get("labels", {}).get("gender") == "male"]
        females = [v for v in all_voices if v.get("labels", {}).get("gender") == "female"]
        targets = []
        if males or females:
            for v in random.sample(males, min(len(males), 4)): targets.append((f"male_{v['name']}", v['voice_id']))
            for v in random.sample(females, min(len(females), 4)): targets.append((f"female_{v['name']}", v['voice_id']))
        else:
            for v in all_voices[:6]: targets.append((f"neutral_{v['name']}", v['voice_id']))

        ideal_text = (
            "Seid gegrüßt, Reisender! Ich habe schon viele Monde lang auf jemanden wie Euch gewartet. "
            "Könnt Ihr das Flüstern des Windes in den alten Ruinen hören? Seid wachsam, denn die Schatten "
            "in Mittelerde werden von Tag zu Tag länger. Aber verzagt nicht! Gemeinsam werden wir einen "
            "Weg finden, um das Licht zurückzubringen. Sagt mir, seid Ihr bereit für dieses Abenteuer?"
        )
        
        save_path = os.path.join(self.root_dir, "resources", "voices", "generated")
        os.makedirs(save_path, exist_ok=True)
        voice_map = self.load_voice_map()
        count = 0
        
        for i, (name, v_id) in enumerate(targets):
            if self.stop_signal: break
            safe_name = "".join(x for x in name if x.isalnum() or x in "_-")
            filename = f"{safe_name}.wav"
            if progress_callback: progress_callback(i + 1, len(targets), f"Lade (Lang): {safe_name}")
            
            # Nutzt jetzt die Smart Request Funktion für POST
            data = {"text": ideal_text, "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}
            res = self._make_elevenlabs_request("POST", f"https://api.elevenlabs.io/v1/text-to-speech/{v_id}", data, settings, timeout=120)
            
            if res and res.status_code == 200:
                with open(os.path.join(save_path, filename), "wb") as f: f.write(res.content)
                voice_map[filename] = v_id
                count += 1
            time.sleep(1.0)
            
        self.save_voice_map(voice_map)
        return count > 0

    # --- HYBRID ENGINE ---
    def load_local_tts(self):
        if self.tts is None:
            self.log_to_file("Lade lokales XTTS Modell...")
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
        
        debug_mode = settings.get("debug_mode", False)
        # Check ob Cloud aktiviert ist UND Keys vorhanden sind
        use_el = settings.get("use_elevenlabs") and settings.get("elevenlabs_api_keys")
        
        voice_id = None
        voice_map = self.load_voice_map()
        if speaker_ref and os.path.basename(speaker_ref) in voice_map:
            voice_id = voice_map[os.path.basename(speaker_ref)]
        elif speaker_ref and not os.path.exists(speaker_ref) and len(speaker_ref) > 10:
            voice_id = speaker_ref

        if use_el and voice_id:
            threading.Thread(target=self._producer_hybrid, args=(text, voice_id, speaker_ref, settings, on_progress, debug_mode), daemon=True).start()
        else:
            self.load_local_tts()
            threading.Thread(target=self._producer_local, args=(text, speaker_ref, settings, on_progress, debug_mode), daemon=True).start()
            
        threading.Thread(target=self._consumer, args=(on_progress,), daemon=True).start()

    def _producer_hybrid(self, text, voice_id, local_path, settings, on_progress, debug_mode):
        sentences = self._split(text)
        for i, s in enumerate(sentences):
            if self.stop_signal: break
            success = False
            
            # 1. Cloud Versuch (mit Key Rotation)
            data = {"text": s, "model_id": "eleven_multilingual_v2"}
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
            
            # Streaming ist schwer mit Rotation, wir nutzen hier normalen Request für Sicherheit
            # (oder man baut Rotation für Stream, aber das ist komplexer. Hier "einfach" full download pro Satz)
            res = self._make_elevenlabs_request("POST", url, data, settings, timeout=20)
            
            if res and res.status_code == 200:
                with open("temp_el.mp3", "wb") as f: f.write(res.content)
                data_audio, fs = sf.read("temp_el.mp3")
                self.audio_queue.put((data_audio, fs, i+1, len(sentences), s))
                success = True
            
            # 2. Local Fallback
            if not success:
                if local_path and os.path.exists(local_path):
                    self.load_local_tts()
                    self._generate_local_chunk(s, local_path, i, len(sentences), debug_mode)
        
        self.audio_queue.put(None)

    def _producer_local(self, text, speaker_wav, settings, on_progress, debug_mode):
        sentences = self._split(text)
        for i, s in enumerate(sentences):
            if self.stop_signal: break
            self._generate_local_chunk(s, speaker_wav, i, len(sentences), debug_mode)
        self.audio_queue.put(None)

    def _generate_local_chunk(self, text, speaker_wav, index, total, debug_mode):
        if not text.strip(): return
        try:
            out = "temp_gen.wav"
            self.tts.tts_to_file(text=text, file_path=out, speaker_wav=speaker_wav, language="de", temperature=0.75, speed=1.0, repetition_penalty=2.0)
            data, fs = sf.read(out)
            self.audio_queue.put((data, 24000, index + 1, total, text))
            if debug_mode:
                 pass 
        except: pass

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
        with self.audio_queue.mutex: self.audio_queue.queue.clear()
