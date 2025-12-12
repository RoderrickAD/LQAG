import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox
import keyboard
import os
import threading
import json
import re
from utils import setup_logger
from worker import Worker
from audio_player import AudioPlayer
from voice_manager import VoiceManager
from snipper import DynamicSnipper
import logging

class LQAGApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LQAG v1.9 - Universal")
        self.root.geometry("650x800")
        
        self.style_bg = "#2b2b2b"
        self.style_fg = "#ffffff"
        self.style_accent = "#3a3a3a"
        self.style_btn = "#505050"
        self.root.configure(bg=self.style_bg)

        # Pfade
        self.resources_path = "resources"
        if not os.path.exists(self.resources_path): os.makedirs(self.resources_path)
        self.settings_path = os.path.join(self.resources_path, "settings.json")
        
        # Komponenten
        self.player = AudioPlayer()
        self.worker = Worker()
        self.voice_mgr = VoiceManager(self.resources_path)
        self.plugin_path = "" 

        # Hotkeys
        self.hotkeys = {
            "scan": "F9",
            "pause": "F10",
            "stop": "F11",
            "setup": "F8" 
        }
        
        # Filter-Variable für das Textfeld
        self.filter_char = tk.StringVar(value="'")

        self.load_settings()
        self.create_widgets()
        
        threading.Thread(target=self.worker.load_tts_model, daemon=True).start()
        
        self.check_plugin_file()
        self.check_template_status()
        self.register_hotkeys()
        
        logging.info("LQAG bereit. Gib dein Begrenzungs-Zeichen oben ein (oder lass es leer).")

    def load_settings(self):
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, "r") as f:
                    data = json.load(f)
                    self.hotkeys = data.get("hotkeys", self.hotkeys)
                    saved_filter = data.get("filter_char", "'")
                    self.filter_char.set(saved_filter)
            except Exception as e:
                logging.error(f"Fehler beim Laden der Settings: {e}")

    def save_settings(self):
        data = {
            "hotkeys": self.hotkeys,
            "filter_char": self.filter_char.get()
        }
        try:
            with open(self.settings_path, "w") as f:
                json.dump(data, f)
            logging.info("Einstellungen gespeichert.")
        except Exception as e:
            logging.error(f"Fehler beim Speichern: {e}")

    def register_hotkeys(self):
        try:
            keyboard.unhook_all_hotkeys()
        except: pass
        try:
            keyboard.add_hotkey(self.hotkeys["scan"], self.trigger_scan)
            keyboard.add_hotkey(self.hotkeys["pause"], self.player.toggle_pause)
            keyboard.add_hotkey(self.hotkeys["stop"], self.player.stop)
            keyboard.add_hotkey(self.hotkeys["setup"], lambda: self.root.after(0, self.start_snipping))
        except Exception as e:
            logging.error(f"Hotkey Fehler: {e}")

    def rebind_key(self, action_name, button_ref):
        button_ref.config(text="Drücke Taste...", bg="orange", fg="black")
        self.root.update()
        def wait_for_key():
            try:
                key = keyboard.read_hotkey(suppress=False)
                self.hotkeys[action_name] = key
                self.save_settings()
                self.root.after(0, lambda: self.finish_rebind(action_name, button_ref))
            except Exception: pass
        threading.Thread(target=wait_for_key, daemon=True).start()

    def finish_rebind(self, action_name, button_ref):
        new_key = self.hotkeys[action_name]
        button_ref.config(text=new_key.upper(), bg=self.style_btn, fg="white")
        self.register_hotkeys()

    def create_widgets(self):
        tk.Label(self.root, text="LQAG Controller", bg=self.style_bg, fg=self.style_fg, font=("Segoe UI", 12, "bold")).pack(pady=10)
        
        # --- 1. SETUP & FILTER ---
        setup_frame = tk.LabelFrame(self.root, text="1. Einrichtung & Filter", bg=self.style_bg, fg="#aaaaaa")
        setup_frame.pack(fill=
