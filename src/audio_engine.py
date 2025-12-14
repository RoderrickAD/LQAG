import os
import torch
import sounddevice as sd
import soundfile as sf
import threading
from TTS.api import TTS

class AudioEngine:
    def __init__(self):
        # Prüfung, ob Grafikkarte (CUDA) verfügbar ist
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🔈 Lade XTTS Sprach-KI auf {self.device}...")
        
        # Das Modell wird geladen (XTTS v2 ist der Standard für Voice Cloning)
        self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(self.device)
        print("✅ Audio-Engine bereit!")

    def speak(self, text, speaker_wav):
        """
        Liest Text vor.
        :param text: Der Text zum Lesen.
        :param speaker_wav: Pfad zur .wav Datei, deren Stimme imitiert werden soll.
        """
        if not text:
            return
        
        # Sicherheitscheck: Existiert die Stimm-Datei?
        if not speaker_wav or not os.path.exists(speaker_wav):
            print(f"⚠️ FEHLER: Stimmen-Datei nicht gefunden: {speaker_wav}")
            # Optional: Hier könnte man eine Notfall-Stimme definieren
            return

        # Startet das Sprechen in einem eigenen Thread, damit das Fenster nicht einfriert
        threading.Thread(target=self._run_speak, args=(text, speaker_wav)).start()

    def _run_speak(self, text, speaker_wav):
        try:
            output_file = "output.wav"
            
            # HIER passiert das Voice Cloning:
            # Wir geben dem Modell den Text UND die Audio-Datei des Sprechers
            self.tts.tts_to_file(
                text=text, 
                file_path=output_file,
                speaker_wav=speaker_wav, 
                language="de"
            )
            
            # Abspielen der generierten Datei
            data, fs = sf.read(output_file)
            sd.play(data, fs)
            sd.wait()
            
        except Exception as e:
            print(f"❌ Audio-Fehler: {e}")
