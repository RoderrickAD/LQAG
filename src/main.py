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
        self.root.title("LQAG v2.0 - Golden Master")
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
        
        # Filter-Variable
        self.filter_char = tk.StringVar(value="'")

        self.load_settings()
        self.create_widgets()
        
        threading.Thread(target=self.worker.load_tts_model, daemon=True).start()
        
        self.check_plugin_file()
        self.check_template_status()
        self.register_hotkeys()
        
        logging.info("LQAG bereit. Konsole prüfen für Debug-Infos.")

    def load_settings(self):
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, "r") as f:
                    data = json.load(f)
                    self.hotkeys = data.get("hotkeys", self.hotkeys)
                    self.filter_char.set(data.get("filter_char", "'"))
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
            except: pass
        threading.Thread(target=wait_for_key, daemon=True).start()

    def finish_rebind(self, action_name, button_ref):
        new_key = self.hotkeys[action_name]
        button_ref.config(text=new_key.upper(), bg=self.style_btn, fg="white")
        self.register_hotkeys()

    def create_widgets(self):
        tk.Label(self.root, text="LQAG Controller", bg=self.style_bg, fg=self.style_fg, font=("Segoe UI", 12, "bold")).pack(pady=10)
        
        # SETUP
        setup_frame = tk.LabelFrame(self.root, text="1. Einrichtung & Filter", bg=self.style_bg, fg="#aaaaaa")
        setup_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.btn_template = tk.Button(setup_frame, text=f"Ecken definieren ({self.hotkeys['setup']})", command=self.start_snipping, bg="#d4af37", fg="black", bd=0, padx=10)
        self.btn_template.pack(side=tk.LEFT, padx=10, pady=10)
        
        filter_box = tk.Frame(setup_frame, bg=self.style_bg)
        filter_box.pack(side=tk.LEFT, padx=20)
        tk.Label(filter_box, text="Begrenzungs-Zeichen:", bg=self.style_bg, fg="#cccccc", font=("Segoe UI", 8)).pack(anchor="w")
        self.ent_filter = tk.Entry(filter_box, textvariable=self.filter_char, width=10, bg="#1e1e1e", fg="cyan", insertbackground="white", justify="center")
        self.ent_filter.pack(anchor="w")

        self.lbl_template_status = tk.Label(setup_frame, text="Checking...", bg=self.style_bg, fg="#aaaaaa")
        self.lbl_template_status.pack(side=tk.RIGHT, padx=10)

        # BRIDGE
        bridge_group = tk.LabelFrame(self.root, text="2. Spiel Verbindung", bg=self.style_bg, fg="#aaaaaa")
        bridge_group.pack(fill=tk.X, padx=10, pady=5)
        self.lbl_plugin = tk.Label(bridge_group, text="Keine Datei gewählt", bg=self.style_bg, fg="orange", wraplength=350, justify="left")
        self.lbl_plugin.pack(side=tk.LEFT, padx=10, pady=10)
        tk.Button(bridge_group, text="Log/Plugin wählen...", command=self.select_plugin_file, bg=self.style_accent, fg=self.style_fg, bd=0).pack(side=tk.RIGHT, padx=10, pady=10)

        # TASTEN
        key_frame = tk.LabelFrame(self.root, text="3. Tastenbelegung", bg=self.style_bg, fg="#aaaaaa")
        key_frame.pack(fill=tk.X, padx=10, pady=5)
        configs = [("Ecken definieren:", "setup"), ("Vorlesen starten:", "scan"), ("Pause / Weiter:", "pause"), ("Stop (Abbruch):", "stop")]
        for i, (txt, key) in enumerate(configs):
            tk.Label(key_frame, text=txt, bg=self.style_bg, fg="#cccccc").grid(row=i, column=0, padx=10, pady=2, sticky="w")
            btn = tk.Button(key_frame, text=self.hotkeys[key], width=15, bg=self.style_btn, fg="white", bd=0)
            btn.config(command=lambda k=key, b=btn: self.rebind_key(k, b))
            if key == "setup": self.btn_key_setup = btn
            elif key == "scan": self.btn_key_scan = btn
            elif key == "pause": self.btn_key_pause = btn
            elif key == "stop": self.btn_key_stop = btn
            btn.grid(row=i, column=1, padx=10, pady=2)

        # STATUS
        self.lbl_speaker = tk.Label(self.root, text="Sprecher: Unbekannt", bg=self.style_bg, fg="#00ff00", font=("Segoe UI", 11, "bold"))
