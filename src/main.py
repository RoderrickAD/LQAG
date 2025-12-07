import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox
import keyboard
import os
import threading
from utils import setup_logger
from worker import Worker
from audio_player import AudioPlayer
from voice_manager import VoiceManager
from snipper import SnippingTool # <--- NEU IMPORTIEREN
import logging

class LQAGApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LQAG v1.4 - mit Setup Tool")
        self.root.geometry("650x600") # Etwas größer
        
        self.style_bg = "#2b2b2b"
        self.style_fg = "#ffffff"
        self.style_accent = "#3a3a3a"
        self.root.configure(bg=self.style_bg)

        # Pfade
        self.resources_path = "resources"
        if not os.path.exists(self.resources_path):
            os.makedirs(self.resources_path)

        self.template_path = os.path.join(self.resources_path, "template.png")
        
        self.player = AudioPlayer()
        self.worker = Worker()
        self.voice_mgr = VoiceManager(self.resources_path)
        self.plugin_path = "" 

        self.create_widgets()

        threading.Thread(target=self.worker.load_tts_model, daemon=True).start()
        
        self.hotkey = "F9"
        keyboard.add_hotkey(self.hotkey, self.trigger_scan)
        self.check_plugin_file()
        
        logging.info("LQAG bereit.")
        self.check_template_status() # Prüft beim Start ob Template da ist

    def create_widgets(self):
        # Header
        tk.Label(self.root, text="LQAG Controller", bg=self.style_bg, fg=self.style_fg, font=("Segoe UI", 12, "bold")).pack(pady=10)
        
        # --- SETUP BEREICH (NEU) ---
        setup_frame = tk.LabelFrame(self.root, text="Einrichtung & Setup", bg=self.style_bg, fg="#aaaaaa", bd=1)
        setup_frame.pack(fill=tk.X, padx=10, pady=5)

        # Template Button
        self.btn_template = tk.Button(setup_frame, text="1. Bildausschnitt wählen (Template)", command=self.start_snipping, bg="#d4af37", fg="black", bd=0, padx=10)
        self.btn_template.pack(side=tk.LEFT, padx=10, pady=10)
        
        self.lbl_template_status = tk.Label(setup_frame, text="❌ Fehlt", bg=self.style_bg, fg="red")
        self.lbl_template_status.pack(side=tk.LEFT, pady=10)

        # --- BRIDGE BEREICH ---
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
        # Fenster minimieren, damit man das Spiel sieht
        self.root.iconify() 
        # Snipping Tool starten
        SnippingTool(self.root, self.template_path, self.on_snipping_done)

    def on_snipping_done(self, success):
        self.root.deiconify() # Fenster wiederherstellen
        if success:
            logging.info("Neues Template erfolgreich gespeichert!")
            self.check_template_status()
        else:
            logging.warning("Template-Erstellung abgebrochen.")

    def check_template_status(self):
        if os.path.exists(self.template_path):
            self.lbl_template_status.config(text="✔ OK", fg="#00ff00")
        else:
            self.lbl_template_status.config(text="❌ Fehlt", fg="red")

    # --- Restliche Funktionen bleiben gleich ---
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
        if not os.path.exists(self.template_path):
            logging.error("KEIN TEMPLATE! Bitte klicke erst auf 'Bildausschnitt wählen'.")
            return
        
        voice_path = self.voice_mgr.get_voice_path()
        if not voice_path:
            logging.error("Keine Stimme gefunden.")
            return

        self.worker.run_process(self.template_path, voice_path, self.play_audio)

    def play_audio(self, p):
        self.root.after(0, lambda: self.player.play(p))

if __name__ == "__main__":
    root = tk.Tk()
    try: root.iconbitmap("resources/icon.ico")
    except: pass
    app = LQAGApp(root)
    root.mainloop()
