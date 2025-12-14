import os
import torch
import sounddevice as sd
import soundfile as sf
import numpy as np
import threading
from TTS.api import TTS

class AudioEngine:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🔈 Lade Sprach-KI auf {self.device}...")
        
        # Wir laden das Standard-Modell (XTTS v2 ist das beste)
        self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(self.device)
        print("✅ Sprach-KI bereit!")

    def speak(self, text):
        """Liest Text vor (in einem separaten Thread, damit GUI nicht einfriert)"""
        if not text:
            return
        
        thread = threading.Thread(target=self._run_speak, args=(text,))
        thread.start()

    def _run_speak(self, text):
        try:
            # Datei temporär erstellen
            output_file = "output.wav"
            
            # Hier geschieht die Magie: Text zu Audio
            self.tts.tts_to_file(text=text, speaker="Ana Florence", language="de", file_path=output_file)
            
            # Abspielen
            data, fs = sf.read(output_file)
            sd.play(data, fs)
            sd.wait()
            
        except Exception as e:
            print(f"❌ Fehler beim Sprechen: {e}")
