import os
import torch
import sounddevice as sd
import soundfile as sf
import threading
from TTS.api import TTS

class AudioEngine:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🔈 Lade XTTS Sprach-KI auf {self.device}...")
        self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(self.device)
        print("✅ Audio-Engine bereit!")
        self.is_playing = False

    def speak(self, text, speaker_wav):
        if not text: return
        if not speaker_wav or not os.path.exists(speaker_wav):
            print(f"⚠️ FEHLER: Stimmen-Datei fehlt: {speaker_wav}")
            return

        # Falls schon was läuft: Stoppen!
        self.stop()
        
        # Neuen Thread starten
        threading.Thread(target=self._run_speak, args=(text, speaker_wav)).start()

    def stop(self):
        """Stoppt die aktuelle Wiedergabe sofort."""
        if self.is_playing:
            sd.stop()
            self.is_playing = False

    def _run_speak(self, text, speaker_wav):
        try:
            output_file = "output.wav"
            
            # 1. Generieren (Dauert kurz)
            self.tts.tts_to_file(
                text=text, 
                file_path=output_file,
                speaker_wav=speaker_wav, 
                language="de"
            )
            
            # 2. Abspielen
            data, fs = sf.read(output_file)
            self.is_playing = True
            sd.play(data, fs)
            sd.wait() # Wartet bis fertig
            self.is_playing = False
            
        except Exception as e:
            print(f"❌ Audio-Fehler: {e}")
            self.is_playing = False
