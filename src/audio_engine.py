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
        
        # Sicherstellen, dass Debug-Ordner existiert
        if not os.path.exists(self.debug_dir):
            os.makedirs(self.debug_dir)

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
            self.log_to_file("Hole Stimmenliste von ElevenLabs...")
            response = requests.get(url, headers=headers, timeout=20)
            if response.status_code == 200:
                voices = response.json().get("voices", [])
                self.log_to_file(f"{len(voices)} Stimmen im Account gefunden.")
                return voices
            return []
        except Exception as e:
            self.log_to_file(f"Netzwerkfehler beim Abruf: {e}")
            return []

    def generate_voice_library(self, settings, progress_callback=None):
        api_key = settings.get("elevenlabs_api_key")
        if not api_key: return False

        all_voices = self.get_available_voices(api_key)
        if not all_voices: 
            self.log_to_file("Keine Stimmen gefunden (oder API Key falsch).")
            return False

        # Filterung
        males = [v for v in all_voices if v.get("labels", {}).get("gender") == "male"]
        females = [v for v in all_voices if v.get("labels", {}).get("gender") == "female"]
        
        targets = []
        if males or females:
            # Wir nehmen bis zu 4 Männer und 4 Frauen
            for v in random.sample(males, min(len(males), 4)): targets.append((f"male_{v['name']}", v['voice_id']))
            for v in random.sample(females, min(len(females), 4)): targets.append((f"female_{v['name']}", v['voice_id']))
        else:
            # Fallback
            self.log_to_file("Keine Gender-Labels. Nutze erste 6 Stimmen.")
            for v in all_voices[:6]: targets.append((f"neutral_{v['name']}", v['voice_id']))

        # --- DER LANGE IDEALE TEXT ---
        # Da wir den Timeout erhöhen, können wir den langen Text behalten!
        ideal_text = (
            "Seid gegrüßt, Reisender! Ich habe schon viele Monde lang auf jemanden wie Euch gewartet. "
            "Könnt Ihr das Flüstern des Windes in den alten Ruinen hören? Seid wachsam, denn die Schatten "
            "in Mittelerde werden von Tag zu Tag länger. Aber verzagt nicht! Gemeinsam werden wir einen "
            "Weg finden, um das Licht zurückzubringen. Sagt mir, seid Ihr bereit für dieses Abenteuer?"
        )

        save_path = os.path.join(self.root_dir, "resources", "voices", "generated")
        os.makedirs(save_path, exist_ok=True)

        count = 0
        self.log_to_file(f"Starte Generierung von {len(targets)} Dateien (Langzeit-Modus)...")
        
        for i, (name, v_id) in enumerate(targets):
            if self.stop_signal: break
            
            safe_name = "".join(x for x in name if x.isalnum() or x in "_-")
            if progress_callback: progress_callback(i + 1, len(targets), f"Lade (dauert lang): {safe_name}")
            
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{v_id}"
            headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
            data = {
                "text": ideal_text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
            }
            
            try:
                self.log_to_file(f"Sende Anfrage für {name}...")
                # WICHTIG: Timeout auf 120 Sekunden (2 Minuten) erhöht!
                res = requests.post(url, json=data, headers=headers, timeout=120)
                
                if res.status_code == 200:
                    with open(os.path.join(save_path, f"{safe_name}.wav"), "wb") as f:
                        f.write(res.content)
                    count += 1
                    self.log_to_file(f"Erfolg: {safe_name}.wav gespeichert.")
                else:
                    self.log_to_file(f"API Fehler {res.status_code} bei {name}: {res.text}")
            except Exception as e:
                self.log_to_file(f"Timeout/Netzwerkfehler bei {name}: {e}")
            
            # Kurze Pause für die API
            time.sleep(2.0)

        return count > 0

    def load_local_tts(self):
        if self.tts is None:
            self.log_to_file("Lade XTTS Modell...")
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
        
        # Debug Status aus Settings lesen
        debug_mode = settings.get("debug_mode", False)

        if settings.get("use_elevenlabs") and settings.get("elevenlabs_api_key"):
            target = self._producer_elevenlabs
        else:
            self.load_local_tts()
            target = self._producer_local
            
        threading.Thread(target=target, args=(text, speaker_ref, settings, on_progress, debug_mode), daemon=True).start()
        threading.Thread(target=self._consumer, args=(on_progress,), daemon=True).start()

    def _producer_local(self, text, speaker_wav, settings, on_progress, debug_mode):
        try:
            sentences = self._split(text)
            full_audio = []
            total = len(sentences)
            for i, s in enumerate(sentences):
                if self.stop_signal or not s.strip(): continue
                out = "temp_gen.wav"
                
                if not speaker_wav or not os.path.exists(speaker_wav):
                    self.log_to_file(f"FEHLER: Voice Datei fehlt: {speaker_wav}")
                    continue

                self.tts.tts_to_file(text=s, file_path=out, speaker_wav=speaker_wav, language="de", temperature=0.75, speed=1.0, repetition_penalty=2.0)
                data, fs = sf.read(out)
                self.audio_queue.put((data, 24000, i + 1, total, s))
                if debug_mode: full_audio.append(data)
            self.audio_queue.put(None)
            
            # Debug Speichern
            if debug_mode and full_audio:
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                # XTTS ist oft 24000Hz
                sf.write(os.path.join(self.debug_dir, f"Recording_{ts}.wav"), np.concatenate(full_audio), 24000)
                self.log_to_file(f"Debug Audio gespeichert: Recording_{ts}.wav")

        except Exception as e:
            self.log_to_file(f"TTS Fehler: {e}")
            self.log_to_file(traceback.format_exc())

    def _producer_elevenlabs(self, text, voice_id, settings, on_progress, debug_mode):
        sentences = self._split(text)
        api_key = settings.get("elevenlabs_api_key")
        full_audio = []
        for i, s in enumerate(sentences):
            if self.stop_signal: break
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
            try:
                # Hier auch Timeout für Streaming
                res = requests.post(url, json={"text": s, "model_id": "eleven_multilingual_v2"}, headers={"xi-api-key": api_key}, timeout=30)
                if res.status_code == 200:
                    with open("temp_el.mp3", "wb") as f: f.write(res.content)
                    data, fs = sf.read("temp_el.mp3")
                    self.audio_queue.put((data, fs, i+1, len(sentences), s))
                    if debug_mode: full_audio.append(data)
            except: pass
        self.audio_queue.put(None)
        
        # Debug Speichern
        if debug_mode and full_audio:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            # ElevenLabs ist meist 44100Hz
            sf.write(os.path.join(self.debug_dir, f"Recording_{ts}.wav"), np.concatenate(full_audio), 44100)
            self.log_to_file(f"Debug Audio gespeichert: Recording_{ts}.wav")


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
