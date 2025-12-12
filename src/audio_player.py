import threading
import logging
import time
import sys

try:
    import pyaudio
    import numpy as np
    PYAUDIO_AVAILABLE = True
except ImportError as e:
    PYAUDIO_AVAILABLE = False
    logging.critical(f"PyAudio fehlt: {e}")
except Exception as e:
    PYAUDIO_AVAILABLE = False
    logging.critical(f"Fehler: {e}")

class AudioPlayer:
    def __init__(self):
        self.p = None
        self.stream = None
        self.is_playing = False
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()

        if not PYAUDIO_AVAILABLE:
            logging.error("Kein Audio-System.")
            return

        try:
            self.p = pyaudio.PyAudio()
            # Test Init
            self.p.get_host_api_info_by_index(0)
            logging.info("Audio-System bereit.")
        except Exception as e:
            logging.critical(f"Audio Init Fehler: {e}")
            self.p = None

    def play_stream(self, audio_generator):
        if self.p is None:
            logging.error("Player nicht bereit.")
            for _ in audio_generator: pass # Leeren
            return

        self.stop()
        thread = threading.Thread(target=self._stream_worker, args=(audio_generator,))
        thread.start()

    def _stream_worker(self, generator):
        self.is_playing = True
        self.stop_event.clear()
        self.pause_event.set()
        
        try:
            logging.info(">> Stream Start.")
            self.stream = self.p.open(
                format=pyaudio.paFloat32,
                channels=1,
                rate=24000,
                output=True
            )

            for chunk in generator:
                if self.stop_event.is_set(): break
                self.pause_event.wait() 
                if chunk is not None and len(chunk) > 0:
                    self.stream.write(chunk.tobytes())
            
            logging.info("<< Stream Ende.")

        except Exception as e:
            logging.error(f"Stream Fehler: {e}")
        finally:
            self.is_playing = False
            if self.stream:
                try:
                    self.stream.stop_stream()
                    self.stream.close()
                except: pass

    def stop(self):
        if self.is_playing:
            self.stop_event.set()

    def toggle_pause(self):
        if self.pause_event.is_set():
            self.pause_event.clear()
        else:
            self.pause_event.set()
