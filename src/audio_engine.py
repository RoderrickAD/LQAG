import os
import torch
import sounddevice as sd
import soundfile as sf
import threading
from TTS.api import TTS

class AudioEngine:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🔈 Lade Sprach-KI auf {self.device}...")
        
        # XTTS v2 laden
        self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(self.device)
        print("✅ Sprach-KI bereit!")

    def speak(self, text):
        if not text: return
        threading.Thread(target=self._run_speak, args=(text,)).start()

    def _run_speak(self, text):
        try:
            output_file = "output.wav"
            # Sprechen (Ana Florence klingt sehr gut für Fantasy)
            self.tts.tts_to_file(text=text, speaker="Ana Florence", language="de", file_path=output_file)
            
            data, fs = sf.read(output_file)
            sd.play(data, fs)
            sd.wait()
        except Exception as e:
            print(f"❌ Fehler: {e}")
