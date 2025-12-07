import tkinter as tk
from tkinter import scrolledtext, filedialog
import keyboard
import os
import threading
from utils import setup_logger
from worker import Worker
from audio_player import AudioPlayer
from voice_manager import VoiceManager  # Importieren!
import logging

class LQAGApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LQAG v1.2 - Auto-Speaker Detect")
        self.root.geometry("650x550")
        
        self.style_bg = "#2b2b2b"
        self.style_fg = "#ffffff"
        self.style_accent = "#3a3a3a"
        self.root.configure(bg=self.style_bg)

        # Pfade
        self.template_path = "resources/template.png"
        self.voices_dir = "resources/voices"
        
        # Komponenten
        self.player = AudioPlayer()
        self.worker = Worker()
        self.voice_mgr = VoiceManager(self.voices_dir)
        
        # Plugin Datei Pfad (Standardmäßig leer)
        self.plugin_path = "" 

        self.create_widgets()

        # Threads & Hotkeys
        threading.Thread(target=self.worker.load_tts_model, daemon=True).start()
        self.hotkey = "F9"
        keyboard.add_hotkey(self.hotkey, self.trigger_scan)
        
        # Starte den Datei-Watcher Loop
        self.check_plugin_file()

    def create_widgets(self):
        # Header
        tk.Label(self.root, text="LQAG Controller", bg=self.style_bg, fg=self.style_fg, font=("Segoe UI", 12, "bold")).pack(pady=10)

        # --- BRIDGE BEREICH ---
        bridge_frame = tk.LabelFrame(self.root, text="LOTRO Plugin Bridge (.plugindata)", bg=self.style_bg, fg="#aaaaaa")
        bridge_frame.pack(fill=tk.X, padx=10, pady=5)

        self.lbl_plugin = tk.Label(bridge_frame, text="Keine Datei ausgewählt", bg=self.style_bg, fg="yellow", wraplength=500)
        self.lbl_plugin.pack(side=tk.LEFT, padx=5, pady=5)
        
        tk.Button(bridge_frame, text="Datei wählen...", command=self.select_plugin_file, bg=self.style_accent, fg=self.style_fg, bd=0).pack(side=tk.RIGHT, padx=5, pady=5)
        # ----------------------

        # Aktueller Sprecher Anzeige
        self.lbl_speaker = tk.Label(self.root, text="Aktueller Sprecher: Unbekannt", bg=self.style_bg, fg="#00ff00", font=("Segoe UI", 10))
        self.lbl_speaker.pack(pady=5)

        # Buttons
        btn_frame = tk.Frame(self.root, bg=self.style_bg)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        btn_opts = {'bg': self.style_accent, 'fg': self.style_fg, 'bd': 0, 'padx': 15, 'pady': 5}
        
        tk.Button(btn_frame, text=f"▶ Scan ({self.hotkey})", command=self.trigger_scan, **btn_opts).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="⏹ Stop", command=self.player.stop, **btn_opts).pack(side=tk.LEFT, padx=5)

        # Log
        self.log_area = scrolledtext.ScrolledText(self.root, state='disabled', bg="#1e1e1e", fg="#00ff00", font=("Consolas", 9), height=10)
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        setup_logger(self.log_area)

    def select_plugin_file(self):
        # LOTRO speichert Plugins meist in Documents/The Lord of the Rings Online/PluginData/...
        path = filedialog.askopenfilename(title="Wähle die .plugindata Datei", filetypes=[("Plugin Data", "*.plugindata"), ("All Files", "*.*")])
        if path:
            self.plugin_path = path
            self.lbl_plugin.config(text=f"...{os.path.basename(path)}")
            logging.info(f"Bridge aktiviert: Überwache {os.path.basename(path)}")

    def check_plugin_file(self):
        """Überprüft alle 2 Sekunden, ob das Plugin den Sprecher geändert hat"""
        if self.plugin_path:
            has_changed = self.voice_mgr.read_speaker_from_plugin(self.plugin_path)
            if has_changed:
                self.lbl_speaker.config(text=f"Aktueller Sprecher: {self.voice_mgr.current_speaker}")
        
        # Loop
        self.root.after(2000, self.check_plugin_file)

    def trigger_scan(self):
        # 1. Hole den Pfad zur WAV basierend auf dem aktuellen Sprecher
        voice_path = self.voice_mgr.get_voice_path()
        
        if not os.path.exists(voice_path):
            logging.warning(f"Stimme '{voice_path}' nicht gefunden. Nutze Default.")
            # Suche nach _default.wav
            voice_path = os.path.join(self.voices_dir, "_default.wav")

        logging.info(f"Scan für Sprecher: {self.voice_mgr.current_speaker}")
        self.worker.run_process(self.template_path, voice_path, self.play_audio)

    def play_audio(self, file_path):
        self.root.after(0, lambda: self.player.play(file_path))

if __name__ == "__main__":
    root = tk.Tk()
    app = LQAGApp(root)
    root.mainloop()
