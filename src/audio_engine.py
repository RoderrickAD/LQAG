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
        
        # Sicherstellen, dass das Debug-Verzeichnis existiert
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
            self.log_to_file("Verbinde mit ElevenLabs API für Stimmenliste...")
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                voices = response.json().get("voices", [])
                self.log_to_file(f"API Erfolg: {len(voices)} Stimmen insgesamt gefunden.")
                return voices
            else:
                self.log_to_file(f"API Fehler beim Abruf: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            self.log_to_file(f"Netzwerkfehler: {e}")
            return []

    def generate_voice_library(self, settings, progress_callback=None):
        api_key = settings.get("elevenlabs_api_key")
        if not api_key:
            self.log_to_file("Fehler: Kein API-Key vorhanden.")
            return False

        all_voices = self.get_available_voices(api_key)
        if not all_voices:
            self.log_to_file("Abbruch: Keine Stimmen vom Server erhalten.")
            return False

        # --- VERBESSERTE FILTER-LOGIK (FALLBACK) ---
        males = [v for v in all_voices if v.get("labels", {}).get("gender") == "male"]
        females = [v for v in all_voices if v.get("labels", {}).get("gender") == "female"]
        
        self.log_to_file(f"Gefiltert: {len(males)} männlich, {len(females)} weiblich nach Labels.")

        targets = []
        
        # Wenn wir Labels haben, nutzen wir diese
        if males or females:
            selected_m = random.sample(males, min(len(males), 4))
            selected_f = random.sample(females, min(len(females), 4))
            for v in selected_m: targets.append((f"male_{v['name']}", v['voice_id']))
            for v in selected_f: targets.append((f"female_{v['name']}", v['voice_id']))
        else:
            # FALLBACK: Wenn keine Labels existieren, nehmen wir einfach die ersten 6 Stimmen
            self.log_to_file("Keine Gender-Labels gefunden. Nutze Fallback (erste 6 Stimmen).")
            for v in all_voices[:6]:
                # Wir versuchen am Namen zu raten oder nutzen 'neutral'
                targets.append((f"neutral_{v['name']}", v['voice_id']))

        if not targets:
            self.log_to_file("Abbruch: Keine Ziel-Stimmen definiert.")
            return False

        ideal_text = (
            "Seid gegrüßt, Reisender! Ich habe schon viele Monde lang auf jemanden wie Euch gewartet. "
            "Könnt Ihr das Flüstern des Windes in den alten Ruinen hören? Seid wachsam, denn die Schatten "
            "in Mittelerde werden von Tag zu Tag länger. Aber verzagt nicht! Gemeinsam werden wir einen "
            "Weg finden, um das Licht zurückzubringen. Sagt mir, seid Ihr bereit für dieses Abenteuer?"
        )

        save_path = os.path.join(self.root_dir, "resources", "voices", "generated")
        if not os.path.exists(save_path): 
            os.makedirs(save_path)

        self.log_to_file(f"Starte Generierung für {len(targets)} Stimmen...")
        
        count = 0
        for i, (name, v_id) in enumerate(targets):
            if self.stop_signal: break
            
            self.log_to_file(f"Verarbeite ({i+1}/{len(targets)}): {name}")
            
            # UI Update (Damit im Tab Vorlesen was passiert)
            if progress_callback:
                progress_callback(i + 1, len(targets), f"Generiere: {name}")

            url = f"https://api.elevenlabs.io/v1/text-to-speech/{v_id}"
            headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
            data = {
                "text": ideal_text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
            }
            
            try:
                res = requests.post(url, json=data, headers=headers, timeout=30)
                if res.status_code == 200:
                    safe_name = "".join(x for x in name if x.isalnum() or x in "_-")
                    with open(os.path.join(save_path, f"{safe_name}.wav"), "wb") as f:
                        f.write(res.content)
                    count += 1
                    self.log_to_file(f"Datei gespeichert: {safe_name}.wav")
                else:
                    self.log_to_file(f"Fehler bei {name}: {res.status_code} - {res.text}")
            except Exception as e:
                self.log_to_file(f"Exception bei {name}: {e}")
            
            time.sleep(0.8) # API Schutzpause

        self.log_to_file(f"Bibliothek-Vorgang abgeschlossen. {count} Stimmen erstellt.")
        return count > 0

    # --- DER REST BLEIBT GLEICH ---
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
        api_key = settings.get("elevenlabs_api_key")
        for i, s in enumerate(sentences):
            if self.stop_signal: break
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
            try:
                res = requests.post(url, json={"text": s, "model_id": "eleven_multilingual_v2"}, headers={"xi-api-key": api_key}, timeout=15)
                if res.status_code == 200:
                    with open("temp_el.mp3", "wb") as f: f.write(res.content)
                    self.audio_queue.put((sf.read("temp_el.mp3")[0], 44100, i+1, len(sentences), s))
            except: pass
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
