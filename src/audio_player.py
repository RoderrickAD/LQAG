import pygame
import os
import logging

class AudioPlayer:
    def __init__(self):
        pygame.mixer.init()
        self.is_paused = False

    def play(self, file_path):
        if not os.path.exists(file_path): return
        self.stop()
        try:
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            logging.info(">> Wiedergabe gestartet.")
            self.is_paused = False
        except Exception as e:
            logging.error(f"Audio Fehler: {e}")

    def toggle_pause(self):
        if pygame.mixer.music.get_busy() or self.is_paused:
            if self.is_paused:
                pygame.mixer.music.unpause()
                self.is_paused = False
            else:
                pygame.mixer.music.pause()
                self.is_paused = True

    def stop(self):
        pygame.mixer.music.stop()
        self.is_paused = False
