import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox
import keyboard
import os
import threading
import json
import re  # Wichtig für re.escape
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
        self.filter_char = tk.StringVar(value="'") # Standard ist ' für LOTRO

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
                    # Wir laden das gespeicherte Filter-Zeichen
                    saved_filter = data.get("filter_char", "'")
                    self.filter_char.set(saved_filter)
            except Exception as e:
                logging.error(f"Fehler beim Laden der Settings: {e}")

    def save_settings(self):
        data = {
            "hotkeys": self.hotkeys,
            "filter_char": self.filter_char.get() # Wir speichern das Zeichen
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
        setup_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Setup Button
        self.btn_template = tk.Button(setup_frame, text=f"Ecken definieren ({self.hotkeys['setup']})", command=self.start_snipping, bg="#d4af37", fg="black", bd=0, padx=10)
        self.btn_template.pack(side=tk.LEFT, padx=10, pady=10)
        
        # --- NEU: FLEXIBLES TEXTFELD ---
        # Container für das Label und das Entry
        filter_box = tk.Frame(setup_frame, bg=self.style_bg)
        filter_box.pack(side=tk.LEFT, padx=20)
        
        tk.Label(filter_box, text="Begrenzungs-Zeichen:", bg=self.style_bg, fg="#cccccc", font=("Segoe UI", 8)).pack(anchor="w")
        
        # Das Eingabefeld
        self.ent_filter = tk.Entry(filter_box, textvariable=self.filter_char, width=10, bg="#1e1e1e", fg="cyan", insertbackground="white", justify="center")
        self.ent_filter.pack(anchor="w")
        # -------------------------------

        self.lbl_template_status = tk.Label(setup_frame, text="Checking...", bg=self.style_bg, fg="#aaaaaa")
        self.lbl_template_status.pack(side=tk.RIGHT, padx=10)

        # --- 2. BRIDGE ---
        bridge_group = tk.LabelFrame(self.root, text="2. Spiel Verbindung", bg=self.style_bg, fg="#aaaaaa")
        bridge_group.pack(fill=tk.X, padx=10, pady=5)
        self.lbl_plugin = tk.Label(bridge_group, text="Keine Datei gewählt", bg=self.style_bg, fg="orange", wraplength=350, justify="left")
        self.lbl_plugin.pack(side=tk.LEFT, padx=10, pady=10)
        tk.Button(bridge_group, text="Log/Plugin wählen...", command=self.select_plugin_file, bg=self.style_accent, fg=self.style_fg, bd=0).pack(side=tk.RIGHT, padx=10, pady=10)

        # --- 3. TASTEN ---
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

        # --- STATUS ---
        self.lbl_speaker = tk.Label(self.root, text="Sprecher: Unbekannt", bg=self.style_bg, fg="#00ff00", font=("Segoe UI", 11, "bold"))
        self.lbl_speaker.pack(pady=5)

        # --- STEUERUNG ---
        btn_frame = tk.Frame(self.root, bg=self.style_bg)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        tk.Button(btn_frame, text="▶ START", command=self.trigger_scan, bg=self.style_accent, fg="white", bd=0, padx=15).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="⏯ PAUSE", command=self.player.toggle_pause, bg=self.style_accent, fg="white", bd=0, padx=15).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="⏹ STOP", command=self.player.stop, bg=self.style_accent, fg="white", bd=0, padx=15).pack(side=tk.LEFT, padx=5)

        # --- LOG ---
        self.log_area = scrolledtext.ScrolledText(self.root, state='disabled', bg="#1e1e1e", fg="#00ff00", font=("Consolas", 9), height=8)
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        setup_logger(self.log_area)

    # --- LOGIC ---
    def start_snipping(self):
        self.root.iconify()
        DynamicSnipper(self.root, self.resources_path, self.on_snipping_done)

    def on_snipping_done(self, success):
        self.root.deiconify()
        if success:
            logging.info("Ecken erfolgreich gespeichert!")
            self.check_template_status()

    def check_template_status(self):
        t1 = os.path.join(self.resources_path, "template_tl.png")
        t2 = os.path.join(self.resources_path, "template_br.png")
        if os.path.exists(t1) and os.path.exists(t2):
            self.lbl_template_status.config(text="✔ Ecken definiert", fg="#00ff00")
        else:
            self.lbl_template_status.config(text="❌ Einrichtung nötig", fg="red")

    def select_plugin_file(self):
        initial = os.path.expanduser("~/Documents/The Lord of the Rings Online")
        path = filedialog.askopenfilename(initialdir=initial, title="Wähle Script.log", filetypes=[("LOTRO Log", "Script.log"), ("Alle", "*.*")])
        if path:
            self.plugin_path = path
            self.lbl_plugin.config(text=f".../{os.path.basename(path)}", fg="#00ff00")
            self.check_plugin_file_once()

    def check_plugin_file(self):
        self.check_plugin_file_once()
        self.root.after(2000, self.check_plugin_file)

    def check_plugin_file_once(self):
        if self.plugin_path:
            if self.voice_mgr.read_speaker_from_plugin(self.plugin_path):
                self.lbl_speaker.config(text=f"Sprecher: {self.voice_mgr.current_speaker}")

    def trigger_scan(self):
        if not os.path.exists(os.path.join(self.resources_path, "template_tl.png")):
            logging.error("Keine Ecken definiert! Drücke F8.")
            return
        
        voice_path = self.voice_mgr.get_voice_path()
        if not voice_path:
            logging.error("Keine Stimme gefunden.")
            return

        # --- DYNAMISCHE REGEX ERSTELLUNG ---
        # Wir holen das Zeichen aus dem Textfeld
        delimiter = self.filter_char.get().strip()
        
        if delimiter:
            # Wir speichern die Einstellung für den nächsten Start
            self.save_settings()
            
            # Sicherheits-Check: Zeichen escapen (damit z.B. ? oder * nicht crasht)
            safe_char = re.escape(delimiter)
            
            # Das Muster: Delimiter + (Alles außer Delimiter) + Delimiter
            # Beispiel für ':  '([^']*)'
            regex_pattern = f"{safe_char}([^ {safe_char}]*){safe_char}"
            
            logging.info(f"Scan ausgelöst (Filter zwischen: {delimiter})...")
        else:
            # Leer = Kein Filter
            regex_pattern = None
            logging.info("Scan ausgelöst (Kein Filter, lese alles)...")
        # -----------------------------------
        
        self.worker.run_process(self.resources_path, voice_path, self.play_audio, regex_pattern)

    def play_audio(self, p):
        self.root.after(0, lambda: self.player.play(p))

if __name__ == "__main__":
    root = tk.Tk()
    try: root.iconbitmap("resources/icon.ico")
    except: pass
    app = LQAGApp(root)
    root.mainloop()
