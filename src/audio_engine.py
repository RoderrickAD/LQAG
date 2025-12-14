import os
import torch
import sounddevice as sd
import soundfile as sf
import threading
import queue
import re
import time
from TTS.api import TTS

class AudioEngine:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🔈 Lade XTTS Sprach-KI auf {self.device}...")
        
        # XTTS laden
        self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(self.device)
        print("✅ Audio-Engine bereit (Streaming Modus)!")
        
        # Warteschlange für Audio-Schnipsel
        self.audio_queue = queue.Queue()
        self.is_playing = False
        self.stop_signal = False
        self.playback_thread = None

    def speak(self, text, speaker_wav):
        """Startet den Prozess: Generator füllt die Queue, Player leert sie."""
        if not text: return
        if not os.path.exists(speaker_wav):
            print(f"⚠️ Stimme fehlt: {speaker_wav}")
            return

        # 1. Alles Alte stoppen
        self.stop()
        time.sleep(0.1) # Kurz warten bis alles ruhig ist
        
        self.stop_signal = False
        self.is_playing = True

        # 2. Generator-Thread starten (Der "Koch", der Audio zubereitet)
        threading.Thread(target=self._producer, args=(text, speaker_wav), daemon=True).start()
        
        # 3. Player-Thread starten (Der "Kellner", der serviert)
        self.playback_thread = threading.Thread(target=self._consumer, daemon=True)
        self.playback_thread.start()

    def stop(self):
        """Bricht alles sofort ab."""
        self.stop_signal = True
        self.is_playing = False
        
        # Queue leeren, damit nichts Altes mehr nachkommt
        with self.audio_queue.mutex:
            self.audio_queue.queue.clear()
            
        sd.stop()

    def _producer(self, text, speaker_wav):
        """Zerlegt Text und generiert Audio im Hintergrund."""
        try:
            # Text in Sätze zerlegen (bei Punkt, Ausrufezeichen, Fragezeichen)
            # Dieser Regex behält das Satzzeichen am Ende des Satzes
            sentences = re.split(r'(?<=[.!?])\s+', text)

            for sentence in sentences:
                if self.stop_signal: return
                
                clean_text = sentence.strip()
                if len(clean_text) < 2: continue
                
                # Falls ein Satz immer noch riesig ist, hart teilen
                chunks = [clean_text]
                if len(clean_text) > 200:
                    chunks = [clean_text[i:i+200] for i in range(0, len(clean_text), 200)]

                for chunk in chunks:
                    if self.stop_signal: return
                    
                    # Generieren (blockiert nur diesen Thread, nicht den Player!)
                    output_path = "temp_gen.wav"
                    self.tts.tts_to_file(
                        text=chunk, 
                        file_path=output_path,
                        speaker_wav=speaker_wav, 
                        language="de"
                    )
                    
                    # Daten in den Speicher laden
                    data, fs = sf.read(output_path)
                    
                    # In die Warteschlange schieben
                    self.audio_queue.put((data, fs))
            
            # Signal, dass wir fertig sind
            self.audio_queue.put(None)

        except Exception as e:
            print(f"❌ Generator Fehler: {e}")
            self.audio_queue.put(None)

    def _consumer(self):
        """Liest aus der Warteschlange und spielt ab."""
        while not self.stop_signal:
            try:
                # Warten auf das nächste Audio-Stück (max 1 Sekunde warten, dann prüfen ob stop)
                try:
                    item = self.audio_queue.get(timeout=1)
                except queue.Empty:
                    continue

                if item is None: # Generator sagt "Bin fertig"
                    break
                
                data, fs = item
                
                if self.stop_signal: break

                # Abspielen (blockiert diesen Thread, bis Audio zu Ende ist)
                sd.play(data, fs)
                sd.wait()

            except Exception as e:
                print(f"❌ Player Fehler: {e}")
                break
        
        self.is_playing = False
