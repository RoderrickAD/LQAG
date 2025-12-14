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
        print("✅ Audio-Engine bereit (HQ Streaming)!")
        
        self.audio_queue = queue.Queue()
        self.is_playing = False
        self.stop_signal = False
        self.playback_thread = None
        self.progress_callback = None # Funktion zum Updaten des Balkens

    def speak(self, text, speaker_wav, on_progress=None):
        """
        on_progress: Eine Funktion, die aufgerufen wird, wenn ein Satz fertig ist.
                     Signatur: callback(current, total)
        """
        if not text: return
        if not os.path.exists(speaker_wav):
            print(f"⚠️ Stimme fehlt: {speaker_wav}")
            return

        self.stop()
        time.sleep(0.1)
        
        self.stop_signal = False
        self.is_playing = True
        self.progress_callback = on_progress

        # Threads starten
        threading.Thread(target=self._producer, args=(text, speaker_wav), daemon=True).start()
        self.playback_thread = threading.Thread(target=self._consumer, daemon=True)
        self.playback_thread.start()

    def stop(self):
        self.stop_signal = True
        self.is_playing = False
        with self.audio_queue.mutex:
            self.audio_queue.queue.clear()
        sd.stop()

    def _producer(self, text, speaker_wav):
        try:
            # Besserer Splitter (behält Satzzeichen)
            sentences = re.split(r'(?<=[.!?])\s+', text)
            sentences = [s for s in sentences if len(s.strip()) > 1]
            total_sentences = len(sentences)
            
            # Melden, wie viele Sätze wir haben
            if self.progress_callback:
                self.progress_callback(0, total_sentences)

            for i, sentence in enumerate(sentences):
                if self.stop_signal: return
                
                # Maximale Länge pro Happen begrenzen
                chunks = [sentence]
                if len(sentence) > 250:
                    chunks = [sentence[i:i+250] for i in range(0, len(sentence), 250)]

                for chunk in chunks:
                    if self.stop_signal: return
                    
                    output_path = "temp_gen.wav"
                    
                    # --- QUALITÄTS UPDATE ---
                    # temperature=0.7: Weniger "Kreativität", stabileres Sprechen (weniger Lallen)
                    # speed=1.1: Ein Hauch schneller wirkt oft natürlicher
                    self.tts.tts_to_file(
                        text=chunk, 
                        file_path=output_path,
                        speaker_wav=speaker_wav, 
                        language="de",
                        temperature=0.7, 
                        speed=1.1,
                        split_sentences=False 
                    )
                    
                    data, fs = sf.read(output_path)
                    # Wir packen auch den Index dazu, damit der Balken weiß, wo wir sind
                    self.audio_queue.put((data, fs, i + 1, total_sentences))
            
            self.audio_queue.put(None)

        except Exception as e:
            print(f"❌ Generator Fehler: {e}")
            self.audio_queue.put(None)

    def _consumer(self):
        while not self.stop_signal:
            try:
                try:
                    item = self.audio_queue.get(timeout=1)
                except queue.Empty:
                    continue

                if item is None: break
                
                data, fs, current_idx, total = item
                
                if self.stop_signal: break

                # --- QUALITÄTS FIX: Samplerate erzwingen ---
                # XTTS ist meistens 24000. Falls sounddevice was anderes denkt, zwingen wir es.
                sd.play(data, samplerate=24000)
                sd.wait()
                
                # Fortschrittsbalken updaten
                if self.progress_callback and not self.stop_signal:
                    self.progress_callback(current_idx, total)

            except Exception as e:
                print(f"❌ Player Fehler: {e}")
                break
        
        self.is_playing = False
