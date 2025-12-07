import tkinter as tk
from tkinter import scrolledtext, ttk
import keyboard
import os
import threading
from utils import setup_logger
from worker import Worker
from audio_player import AudioPlayer
import logging

class LQAGApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LQAG v1.0 - Auto Reader")
        self.root.geometry("650x450")
        
        # Modernes, neutrales Dark Theme
        self.style_bg = "#2b2b2b"       # Dunkelgrau
        self.style_fg = "#ffffff"       # Weiß
        self.style_accent = "#3a3a3a"   # Etwas helleres Grau für Elemente
        
        self.root.configure(bg=self.style_bg)

        # Komponenten initialisieren
        self.player = AudioPlayer()
        self.worker = Worker()
        
        # Layout aufbauen
        self.create_widgets()
        
        # TTS Laden im Hintergrund
        threading.Thread(target=self.worker.load_tts_model, daemon=True).start()

        # Hotkey (F9 Standard)
        self.hotkey = "F9"
        keyboard.add_hotkey(self.hotkey, self.trigger_scan)
        
        # Start-Log
        logging.info("LQAG v1.0 gestartet.")
        logging.info(f"Hotkey aktiv: {self.hotkey}")
        logging.info("Warte auf Initialisierung der KI-Modelle...")

        # Pfade
        self.template_path = "resources/template.png"
        self.ref_voice_path = "resources/reference.wav"

    def create_widgets(self):
        # Header Bereich
        header_frame = tk.Frame(self.root, bg=self.style_bg)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        
        lbl_title = tk.Label(header_frame, text="LQAG Controller", bg=self.style_bg, fg=self.style_fg, font=("Segoe UI", 12, "bold"))
        lbl_title.pack(side=tk.LEFT)

        # Button Bereich (Toolbar Style)
        btn_frame = tk.Frame(self.root, bg=self.style_bg)
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Styling der Buttons für neutralen Look
        btn_opts = {'bg': self.style_accent, 'fg': self.style_fg, 'activebackground': '#505050', 'activeforeground': 'white', 'bd': 0, 'padx': 15, 'pady': 5}

        self.btn_scan = tk.Button(btn_frame, text=f"▶ Scan ({self.hotkey})", command=self.trigger_scan, **btn_opts)
        self.btn_scan.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_pause = tk.Button(btn_frame, text="⏯ Pause / Weiter", command=self.player.toggle_pause, **btn_opts)
        self.btn_pause.pack(side=tk.LEFT, padx=5)
        
        self.btn_stop = tk.Button(btn_frame, text="⏹ Stop", command=self.player.stop, **btn_opts)
        self.btn_stop.pack(side=tk.LEFT, padx=5)

        # Log Bereich (Console Style)
        log_frame = tk.LabelFrame(self.root, text="System Log / Debug", bg=self.style_bg, fg="#aaaaaa", bd=1)
        log_frame.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        self.log_area = scrolledtext.ScrolledText(log_frame, state='disabled', bg="#1e1e1e", fg="#00ff00", font=("Consolas", 9), insertbackground="white")
        self.log_area.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
        
        # Logger verbinden
        setup_logger(self.log_area)

    def trigger_scan(self):
        if not os.path.exists(self.template_path):
            logging.error("FEHLER: 'resources/template.png' fehlt.")
            return
        if not os.path.exists(self.ref_voice_path):
            logging.error("FEHLER: 'resources/reference.wav' fehlt.")
            return

        logging.info("Scan angefordert...")
        self.worker.run_process(self.template_path, self.ref_voice_path, self.play_audio)

    def play_audio(self, file_path):
        self.root.after(0, lambda: self.player.play(file_path))

if __name__ == "__main__":
    root = tk.Tk()
    # Versuch Icon zu setzen falls vorhanden, sonst ignorieren
    try: root.iconbitmap("resources/icon.ico") 
    except: pass
    
    app = LQAGApp(root)
    root.mainloop()
