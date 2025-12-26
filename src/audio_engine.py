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

    # --- MAP VERWALTUNG ---
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

    # --- GENERATOR MIT MAP-SUPPORT ---
    def get_available_voices(self, api_key):
        try:
            res = requests.get("https://api.elevenlabs.io/v1/voices", headers={"xi-api-key": api_key}, timeout=20)
            return res.json().get("voices", []) if res.status_code == 200 else []
        except: return []

    def generate_voice_library(self, settings, progress_callback=None):
        api_key = settings.get("elevenlabs_api_key")
        if not api_key: return False
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

        ideal_text = "Seid gegrüßt! Die Schatten werden länger, doch wir werden das Licht zurückbringen. Seid Ihr bereit?"
        save_path = os.path.join(self.root_dir, "resources", "voices", "generated")
        os.makedirs(save_path, exist_ok=True)
        
        # Map laden oder neu erstellen
        voice_map = self.load_voice_map()
        count = 0
        
        for i, (name, v_id) in enumerate(targets):
            if self.stop_signal: break
            safe_name = "".join(x for x in name if x.isalnum() or x in "_-")
            filename = f"{safe_name}.wav"
            
            if progress_callback: progress_callback(i + 1, len(targets), f"Lade: {safe_name}")
            
            try:
                res = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{v_id}", 
                                    json={"text": ideal_text, "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}, 
                                    headers={"xi-api-key": api_key, "Content-Type": "application/json"}, timeout=120)
                
                if res.status_code == 200:
                    with open(os.path.join(save_path, filename), "wb") as f: f.write(res.content)
                    voice_map[filename] = v_id # ID speichern!
                    count += 1
                else:
                    self.log_to_file(f"Fehler {res.status_code} bei {name}")
            except Exception as e:
                self.log_to_file(f"Timeout/Fehler bei {name}: {e}")
            time.sleep(1.5)
            
        self.save_voice_map(voice_map) # Map speichern
        return count > 0

    # --- HYBRID ENGINE ---
    def load_local_tts(self):
        if self.tts is None:
            self.log_to_file("Lade lokales XTTS Modell (Fallback)...")
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
        use_el = settings.get("use_elevenlabs") and settings.get("elevenlabs_api_key")
        
        # ID ermitteln
        voice_id = None
        voice_map = self.load_voice_map()
        
        # Fall 1: speaker_ref ist ein Pfad (z.B. generated/male_Josh.wav)
        if speaker_ref and os.path.basename(speaker_ref) in voice_map:
            voice_id = voice_map[os.path.basename(speaker_ref)]
        # Fall 2: speaker_ref ist bereits eine ID (manuell eingetragen)
        elif speaker_ref and not os.path.exists(speaker_ref) and len(speaker_ref) > 10:
            voice_id = speaker_ref

        # Strategie wählen
        if use_el and voice_id:
            # Cloud First mit Fallback
            threading.Thread(target=self._producer_hybrid, args=(text, voice_id, speaker_ref, settings, on_progress, debug_mode), daemon=True).start()
        else:
            # Nur Lokal
            self.load_local_tts()
            threading.Thread(target=self._producer_local, args=(text, speaker_ref, settings, on_progress, debug_mode), daemon=True).start()
            
        threading.Thread(target=self._consumer, args=(on_progress,), daemon=True).start()

    def _producer_hybrid(self, text, voice_id, local_path, settings, on_progress, debug_mode):
        sentences = self._split(text)
        api_key = settings.get("elevenlabs_api_key")
        
        for i, s in enumerate(sentences):
            if self.stop_signal: break
            success = False
            
            # 1. VERSUCH: CLOUD
            try:
                # self.log_to_file(f"Versuche Cloud für Satz {i+1}...") 
                url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
                res = requests.post(url, json={"text": s, "model_id": "eleven_multilingual_v2"}, headers={"xi-api-key": api_key}, timeout=10)
                
                if res.status_code == 200:
                    with open("temp_el.mp3", "wb") as f: f.write(res.content)
                    data, fs = sf.read("temp_el.mp3")
                    self.audio_queue.put((data, fs, i+1, len(sentences), s))
                    success = True
                else:
                    self.log_to_file(f"Cloud Fehler {res.status_code}. Wechsle zu Lokal.")
            except Exception as e:
                self.log_to_file(f"Cloud Exception: {e}. Wechsle zu Lokal.")

            # 2. FALLBACK: LOKAL (wenn Cloud fehlschlug)
            if not success:
                if local_path and os.path.exists(local_path):
                    self.load_local_tts()
                    self._generate_local_chunk(s, local_path, i, len(sentences), debug_mode)
                else:
                    self.log_to_file("Kritisch: Cloud fehlgeschlagen und keine lokale Datei vorhanden.")
        
        self.audio_queue.put(None)

    def _producer_local(self, text, speaker_wav, settings, on_progress, debug_mode):
        sentences = self._split(text)
        for i, s in enumerate(sentences):
            if self.stop_signal: break
            self._generate_local_chunk(s, speaker_wav, i, len(sentences), debug_mode)
        self.audio_queue.put(None)

    def _generate_local_chunk(self, text, speaker_wav, index, total, debug_mode):
        """Hilfsfunktion für lokale Generierung"""
        if not text.strip(): return
        try:
            out = "temp_gen.wav"
            self.tts.tts_to_file(text=text, file_path=out, speaker_wav=speaker_wav, language="de", temperature=0.75, speed=1.0, repetition_penalty=2.0)
            data, fs = sf.read(out)
            self.audio_queue.put((data, 24000, index + 1, total, text))
            if debug_mode:
                 # Optional: hier speichern wenn nötig
                 pass
        except Exception as e:
            self.log_to_file(f"Local TTS Fail: {e}")

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
