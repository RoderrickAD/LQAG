import threading
import logging
import time
import sys

# Wir versuchen den Import sicher zu machen
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError as e:
    PYAUDIO_AVAILABLE = False
    logging.critical(f"CRITICAL: PyAudio konnte nicht importiert werden: {e}")
except Exception as e:
    PYAUDIO_AVAILABLE = False
    logging.critical(f"CRITICAL: Schwerer Fehler beim Laden von PyAudio: {e}")

class AudioPlayer:
    def __init__(self):
        self.p = None
        self.stream = None
        self.is_playing = False
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()

        if not PYAUDIO_AVAILABLE:
            logging.error("ABBRUCH: Audio-System nicht verfügbar (PyAudio fehlt).")
            return

        try:
            logging.info("Initialisiere PyAudio System...")
            self.p = pyaudio.PyAudio()
            
            # Diagnose: Welche Geräte sehen wir?
            info = self.p.get_host_api_info_by_index(0)
            numdevices = info.get('deviceCount')
            logging.info(f"Audio-System bereit. Gefundene Geräte: {numdevices}")
            
        except Exception as e:
            logging.critical(f"FEHLER bei PyAudio Init: {e}")
            self.p = None

    def play_stream(self, audio_generator):
        if self.p is None:
            logging.error("Kann nicht abspielen: Audio-System ist tot.")
            # Wir konsumieren den Generator trotzdem, damit der Worker nicht blockiert
            for _ in audio_generator: pass 
            return

        self.stop()
        thread = threading.Thread(target=self._stream_worker, args=(audio_generator,))
        thread.start()

    def _stream_worker(self, generator):
        self.is_playing = True
        self.stop_event.clear()
        self.pause_event.set()
        
        try:
            logging.info(">> Audio-Stream öffnet Kanal...")
            
            self.stream = self.p.open(
                format=pyaudio.paFloat32,
                channels=1,
                rate=24000,
                output=True
            )
            
            logging.info(">> Stream läuft. Warte auf Daten...")
            chunk_count = 0

            for chunk in generator:
                if self.stop_event.is_set(): break
                self.pause_event.wait() 

                if chunk is not None and len(chunk) > 0:
                    self.stream.write(chunk.tobytes())
                    chunk_count += 1
            
            logging.info(f"<< Stream beendet. {chunk_count} Chunks abgespielt.")

        except Exception as e:
            logging.error(f"Fehler im Audio-Stream: {e}")
            logging.error("Traceback:", exc_info=True)
        finally:
            self.is_playing = False
            if self.stream:
                try:
                    self.stream.stop_stream()
                    self.stream.close()
                except: pass
