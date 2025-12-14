import os
import torch
import sounddevice as sd
import soundfile as sf
import threading
import re # Für das Aufteilen von Sätzen
from TTS.api import TTS

class AudioEngine:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🔈 Lade XTTS Sprach-KI auf {self.device}...")
        self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(self.device)
        print("✅ Audio-Engine bereit!")
        self.is_playing = False
        self.stop_signal = False

    def speak(self, text, speaker_wav):
        if not text: return
        if not speaker_wav or not os.path.exists(speaker_wav):
            print(f"⚠️ FEHLER: Stimmen-Datei fehlt: {speaker_wav}")
            return

        # Alte Wiedergabe stoppen
        self.stop()
        self.stop_signal = False
        
        # Neuen Thread starten
        threading.Thread(target=self._run_speak_splitted, args=(text, speaker_wav)).start()

    def stop(self):
        """Sendet Signal zum Stoppen."""
        self.stop_signal = True
        if self.is_playing:
            sd.stop()
            self.is_playing = False

    def _run_speak_splitted(self, text, speaker_wav):
        """Zerlegt Text in Sätze und spielt sie nacheinander."""
        try:
            # 1. Text säubern und in Sätze splitten
            # Wir splitten bei . ! ? und behalten das Satzzeichen
            sentences = re.split(r'(?<=[.!?]) +', text)
            
            for sentence in sentences:
                if self.stop_signal: 
                    break # Abbruch durch User
                
                sentence = sentence.strip()
                if len(sentence) < 2: continue # Leere Schnipsel überspringen
                
                # Wenn ein Satz IMMER NOCH zu lang ist (>200 Zeichen), müssen wir ihn hart teilen
                if len(sentence) > 200:
                    chunks = [sentence[i:i+200] for i in range(0, len(sentence), 200)]
                else:
                    chunks = [sentence]

                for chunk in chunks:
                    if self.stop_signal: break
                    self._play_single_chunk(chunk, speaker_wav)

        except Exception as e:
            print(f"❌ Audio-Fehler: {e}")
            self.is_playing = False

    def _play_single_chunk(self, text_chunk, speaker_wav):
        """Generiert und spielt ein einzelnes Stück Audio."""
        try:
            output_file = "temp_output.wav"
            
            # Generieren
            self.tts.tts_to_file(
                text=text_chunk, 
                file_path=output_file,
                speaker_wav=speaker_wav, 
                language="de"
            )
            
            if self.stop_signal: return

            # Abspielen
            data, fs = sf.read(output_file)
            self.is_playing = True
            sd.play(data, fs)
            sd.wait() # Warten bis fertig gesprochen
            self.is_playing = False
            
        except Exception as e:
            print(f"❌ Chunk Fehler: {e}")
