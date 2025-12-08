import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox
import keyboard
import os
import threading
import json
from utils import setup_logger
from worker import Worker
from audio_player import AudioPlayer
from voice_manager import VoiceManager
from snipper import DynamicSnipper
import logging

class LQAGApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LQAG v1.7 - Full Control")
        self.root.geometry("650x750") # Etwas höher für mehr Tasten
        
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

        # --- HOTKEYS LADEN ---
        # Jetzt mit F8 für Setup!
        self.hotkeys = {
            "scan": "F9",
            "pause": "F10",
            "stop": "F11",
            "setup": "F8" 
        }
        self.load_settings()

        # GUI Bauen
        self.create_widgets()
        
        # Prozesse starten
        threading.Thread(target=self.worker.load_tts_model, daemon=True).start()
        
        self.check_plugin_file()
        self.check_template_status()
        self.register_hotkeys()
        
        logging.info("LQAG bereit. Drücke F8 für Setup, F9 für Scan.")

    def load_settings(self):
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, "r") as f:
                    saved_keys = json.load(f)
                    for k in self.hotkeys:
                        if k in saved_keys:
                            self.hotkeys[k] = saved_keys[k]
            except Exception as e:
                logging.error(f"Fehler beim Laden der Settings: {e}")

    def save_settings(self):
        try:
            with open(self.settings_path, "w") as f:
                json.dump(self.hotkeys, f)
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
            
            # WICHTIG: Das Setup muss im GUI-Thread gestartet werden (after)
            keyboard.add_hotkey(self.hotkeys["setup"], lambda: self.root.after(0, self.start_snipping))
            
            logging.info(f"Keys: Setup=[{self.hotkeys['setup']}], Scan=[{self.hotkeys['scan']}], Pause=[{self.hotkeys['pause']}]")
        except Exception as e:
            logging.error(f"Fehler beim Registrieren der Hotkeys: {e}")

    def rebind_key(self, action_name, button_ref):
        button_ref.config(text="Drücke Taste...", bg="orange", fg="black")
        self.root.update()
        
        def wait_for_key():
            try:
                key = keyboard.read_hotkey(suppress=False)
                self.hotkeys[action_name] = key
                self.save_settings()
                self.root.after(0, lambda: self.finish_rebind(action_name, button_ref))
            except Exception as e:
                logging.error(f"Fehler beim Tastenlesen: {e}")

        threading.Thread(target=wait_for_key, daemon=True).start()

    def finish_rebind(self, action_name, button_ref):
        new_key = self.hotkeys[action_name]
        button_ref.config(text=new_key.upper(), bg=self.style_btn, fg="white")
        logging.info(f"Neue Taste für {action_name}: {new_key}")
        self.register_hotkeys()

    def create_widgets(self):
        # HEADER
        tk.Label(self.root, text="LQAG Controller", bg=self.style_bg, fg=self.style_fg, font=("Segoe UI", 12, "bold")).pack(pady=10)
        
        # --- SETUP ---
        setup_frame = tk.LabelFrame(self.root, text="1. Einrichtung", bg=self.style_bg, fg="#aaaaaa")
        setup_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.btn_template = tk.Button(setup_frame, text=f"Fenster-Ecken definieren ({self.hotkeys['setup']})", command=self.start_snipping, bg="#d4af37", fg="black", bd=0, padx=10)
        self.btn_template.pack(side=tk.LEFT, padx=10, pady=10)
        
        self.lbl_template_status = tk.Label(setup_frame, text="Checking...", bg=self.style_bg, fg="#aaaaaa")
        self.lbl_template_status.pack(side=tk.LEFT, pady=10)

        # --- BRIDGE ---
        bridge_group = tk.LabelFrame(self.root, text="2. LOTRO Verbindung", bg=self.style_bg, fg="#aaaaaa")
        bridge_group.pack(fill=tk.X, padx=10, pady=5)
        self.lbl_plugin = tk.Label(bridge_group, text="Keine Plugin-Datei gewählt", bg=self.style_bg, fg="orange", wraplength=350, justify="left")
        self.lbl_plugin.pack(side=tk.LEFT, padx=10, pady=10)
        tk.Button(bridge_group, text="Datei wählen...", command=self.select_plugin_file, bg=self.style_accent, fg=self.style_fg, bd=0).pack(side=tk.RIGHT, padx=10, pady=10)

        # --- TASTENBELEGUNG ---
        key_frame = tk.LabelFrame(self.root, text="3. Tastenbelegung", bg=self.style_bg, fg="#aaaaaa")
        key_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Setup Key
        tk.Label(key_frame, text="Ecken definieren:", bg=self.style_bg, fg="#cccccc").grid(row=0, column=0, padx=10, pady=2, sticky="w")
        self.btn_key_setup = tk.Button(key_frame, text=self.hotkeys["setup"], width=15, bg=self.style_btn, fg="white", bd=0,
                                      command=lambda: self.rebind_key("setup", self.btn_key_setup))
        self.btn_key_setup.grid(row=0, column=1, padx=10, pady=2)

        # Scan Key
        tk.Label(key_frame, text="Vorlesen starten:", bg=self.style_bg, fg="#cccccc").grid(row=1, column=0, padx=10, pady=2, sticky="w")
        self.btn_key_scan = tk.Button(key_frame, text=self.hotkeys["scan"], width=15, bg=self.style_btn, fg="white", bd=0,
                                      command=lambda: self.rebind_key("scan", self.btn_key_scan))
        self.btn_key_scan.grid(row=1, column=1, padx=10, pady=2)

        # Pause Key
        tk.Label(key_frame, text="Pause / Weiter:", bg=self.style_bg, fg="#cccccc").grid(row=2, column=0, padx=10, pady=2, sticky="w")
        self.btn_key_pause = tk.Button(key_frame, text=self.hotkeys["pause"], width=15, bg=self.style_btn, fg="white", bd=0,
                                       command=lambda: self.rebind_key("pause", self.btn_key_pause))
        self.btn_key_pause.grid(row=2, column=1, padx=10, pady=2)

        # Stop Key
        tk.Label(key_frame, text="Stop (Abbruch):", bg=self.style_bg, fg="#cccccc").grid(row=3, column=0, padx=10, pady=2, sticky="w")
        self.btn_key_stop = tk.Button(key_frame, text=self.hotkeys["stop"], width=15, bg=self.style_btn, fg="white", bd=0,
                                      command=lambda: self.rebind_key("stop", self.btn_key_stop))
        self.btn_key_stop.grid(row=3, column=1, padx=10, pady=2)


        # --- STATUS ---
        self.lbl_speaker = tk.Label(self.root, text="Aktueller NPC: Unbekannt", bg=self.style_bg, fg="#00ff00", font=("Segoe UI", 11, "bold"))
        self.lbl_speaker.pack(pady=5)

        # --- MANUELLE STEUERUNG ---
        btn_frame = tk.Frame(self.root, bg=self.style_bg)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Button(btn_frame, text="▶ START", command=self.trigger_scan, bg=self.style_accent, fg="white", bd=0, padx=15, pady=5).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="⏯ PAUSE", command=self.player.toggle_pause, bg=self.style_accent, fg="white", bd=0, padx=15, pady=5).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="⏹ STOP", command=self.player.stop, bg=self.style_accent, fg="white", bd=0, padx=15, pady=5).pack(side=tk.LEFT, padx=5)

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
        initial = os.path.expanduser("~/Documents/The Lord of the Rings Online/PluginData")
        path = filedialog.askopenfilename(initialdir=initial, title="Wähle LQAG_Data.plugindata", filetypes=[("Plugin Data", "*.plugindata")])
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
                self.lbl_speaker.config(text=f"Aktueller NPC: {self.voice_mgr.current_speaker}")

    def trigger_scan(self):
        if not os.path.exists(os.path.join(self.resources_path, "template_tl.png")):
            logging.error("Keine Ecken definiert! Drücke F8.")
            return
        
        voice_path = self.voice_mgr.get_voice_path()
        if not voice_path:
            logging.error("Keine Stimme gefunden.")
            return

        logging.info(f"Scan ausgelöst...")
        self.worker.run_process(self.resources_path, voice_path, self.play_audio)

    def play_audio(self, p):
        self.root.after(0, lambda: self.player.play(p))

if __name__ == "__main__":
    root = tk.Tk()
    try: root.iconbitmap("resources/icon.ico")
    except: pass
    app = LQAGApp(root)
    root.mainloop()
