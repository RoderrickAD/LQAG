import tkinter as tk
from tkinter import scrolledtext, filedialog
import keyboard
import os
import threading
from utils import setup_logger
from worker import Worker
from audio_player import AudioPlayer
from voice_manager import VoiceManager
from snipper import DynamicSnipper # <--- NEUER IMPORT
import logging

class LQAGApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LQAG v1.5 - Dynamic Window Support")
        self.root.geometry("650x600")
        
        self.style_bg = "#2b2b2b"
        self.style_fg = "#ffffff"
        self.style_accent = "#3a3a3a"
        self.root.configure(bg=self.style_bg)

        self.resources_path = "resources"
        if not os.path.exists(self.resources_path): os.makedirs(self.resources_path)
        
        self.player = AudioPlayer()
        self.worker = Worker()
        self.voice_mgr = VoiceManager(self.resources_path)
        self.plugin_path = "" 

        self.create_widgets()
        threading.Thread(target=self.worker.load_tts_model, daemon=True).start()
        
        self.hotkey = "F9"
        keyboard.add_hotkey(self.hotkey, self.trigger_scan)
        self.check_plugin_file()
        
        self.check_template_status()

    def create_widgets(self):
        # ... (Header Code wie vorher) ...
        # Nur der Setup Bereich ändert sich leicht im Text:
        
        # --- SETUP ---
        setup_frame = tk.LabelFrame(self.root, text="Einrichtung", bg=self.style_bg, fg="#aaaaaa")
        setup_frame.pack(fill=tk.X, padx=10, pady=5)

        self.btn_template = tk.Button(setup_frame, text="1. Fenster-Ecken definieren", command=self.start_snipping, bg="#d4af37", fg="black", bd=0, padx=10)
        self.btn_template.pack(side=tk.LEFT, padx=10, pady=10)
        
        self.lbl_template_status = tk.Label(setup_frame, text="❌ Fehlt", bg=self.style_bg, fg="red")
        self.lbl_template_status.pack(side=tk.LEFT, pady=10)
        
        # ... (Restlicher Code für Bridge, Controls, Log bleibt identisch wie v1.4) ...
        # (Ich kürze hier ab, damit du nicht alles neu kopieren musst, der Rest ist gleich)
        # Hier nur die wichtigen geänderten Funktionen:

        # --- BRIDGE ---
        bridge_group = tk.LabelFrame(self.root, text="2. LOTRO Verbindung", bg=self.style_bg, fg="#aaaaaa", bd=1)
        bridge_group.pack(fill=tk.X, padx=10, pady=5)
        self.lbl_plugin = tk.Label(bridge_group, text="Keine Plugin-Datei gewählt", bg=self.style_bg, fg="orange", wraplength=350, justify="left")
        self.lbl_plugin.pack(side=tk.LEFT, padx=10, pady=10)
        tk.Button(bridge_group, text="Datei wählen...", command=self.select_plugin_file, bg=self.style_accent, fg=self.style_fg, bd=0).pack(side=tk.RIGHT, padx=10, pady=10)

        # --- STATUS ---
        self.lbl_speaker = tk.Label(self.root, text="Aktueller NPC: Unbekannt", bg=self.style_bg, fg="#00ff00", font=("Segoe UI", 11, "bold"))
        self.lbl_speaker.pack(pady=5)

        # --- CONTROLS ---
        btn_frame = tk.Frame(self.root, bg=self.style_bg)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        btn_opts = {'bg': self.style_accent, 'fg': self.style_fg, 'bd': 0, 'padx': 20, 'pady': 8}
        self.btn_scan = tk.Button(btn_frame, text=f"▶ SCAN ({self.hotkey})", command=self.trigger_scan, **btn_opts)
        self.btn_scan.pack(side=tk.LEFT, padx=(0, 5))
        tk.Button(btn_frame, text="⏯ Pause", command=self.player.toggle_pause, **btn_opts).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="⏹ Stop", command=self.player.stop, **btn_opts).pack(side=tk.LEFT, padx=5)

        # --- LOG ---
        self.log_area = scrolledtext.ScrolledText(self.root, state='disabled', bg="#1e1e1e", fg="#00ff00", font=("Consolas", 9), height=8)
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        setup_logger(self.log_area)


    def start_snipping(self):
        self.root.iconify()
        DynamicSnipper(self.root, self.resources_path, self.on_snipping_done)

    def on_snipping_done(self, success):
        self.root.deiconify()
        if success:
            logging.info("Ecken erfolgreich gespeichert!")
            self.check_template_status()

    def check_template_status(self):
        # Wir prüfen jetzt auf beide Dateien
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
        # Check ob Ecken da sind
        t1 = os.path.join(self.resources_path, "template_tl.png")
        if not os.path.exists(t1):
            logging.error("KEINE DEFINITION! Bitte klicke erst auf 'Fenster-Ecken definieren'.")
            return
        
        voice_path = self.voice_mgr.get_voice_path()
        if not voice_path:
            logging.error("Keine Stimme gefunden.")
            return

        # Wir übergeben jetzt den Ordner Pfad, nicht mehr das Bild
        self.worker.run_process(self.resources_path, voice_path, self.play_audio)

    def play_audio(self, p):
        self.root.after(0, lambda: self.player.play(p))

if __name__ == "__main__":
    root = tk.Tk()
    try: root.iconbitmap("resources/icon.ico")
    except: pass
    app = LQAGApp(root)
    root.mainloop()
