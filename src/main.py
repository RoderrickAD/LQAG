import sys
import multiprocessing
import os

# --- FIX FÜR PORTABLE TKINTER ---
if sys.platform == "win32":
    # Wir suchen den Ordner, in dem python.exe liegt
    base_path = os.path.dirname(sys.executable)
    tcl_path = os.path.join(base_path, "tcl")
    
    if os.path.exists(tcl_path):
        # Wir setzen die Umgebungsvariablen manuell
        os.environ["TCL_LIBRARY"] = os.path.join(tcl_path, "tcl8.6")
        os.environ["TK_LIBRARY"] = os.path.join(tcl_path, "tk8.6")
# --------------------------------

if __name__ == "__main__":
    multiprocessing.freeze_support()
    
import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox
import os
import threading
import json
import logging
import traceback

# Wir importieren hier erst mal NUR Sachen, die sicher da sind.
# Die "gefährlichen" Imports (Worker, AudioPlayer) machen wir später im Code,
# damit wir Fehler abfangen können.

class LQAGApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LQAG v2.1 - Debug Mode")
        self.root.geometry("650x800")
        
        self.style_bg = "#2b2b2b"
        self.style_fg = "#ffffff"
        self.style_accent = "#3a3a3a"
        self.style_btn = "#505050"
        self.root.configure(bg=self.style_bg)
        
        # LOGGING SOFORT STARTEN
        self.log_area = scrolledtext.ScrolledText(self.root, state='normal', bg="#1e1e1e", fg="#00ff00", font=("Consolas", 9), height=15)
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.log("INFO", "GUI gestartet. Lade Module...")
        
        # --- SICHERER IMPORT ---
        self.modules_loaded = False
        self.worker = None
        self.player = None
        self.voice_mgr = None
        
        # Wir laden die Logik verzögert, damit wir sehen WOBEI es abstürzt
        self.root.after(100, self.safe_load_modules)

    def log(self, level, msg):
        try:
            self.log_area.insert(tk.END, f"[{level}] {msg}\n")
            self.log_area.see(tk.END)
            print(f"[{level}] {msg}")
        except: pass

    def safe_load_modules(self):
        try:
            self.log("INFO", "Importiere Utils...")
            from utils import setup_logger
            # Logger umbiegen auf unser Fenster
            setup_logger(self.log_area)
            
            self.log("INFO", "Importiere Keyboard...")
            import keyboard
            self.keyboard = keyboard

            self.log("INFO", "Importiere Snipper...")
            from snipper import DynamicSnipper
            self.SnipperClass = DynamicSnipper

            self.log("INFO", "Importiere VoiceManager...")
            from voice_manager import VoiceManager
            
            self.log("INFO", "Importiere AudioPlayer (PyAudio)...")
            from audio_player import AudioPlayer
            
            self.log("INFO", "Importiere Worker (Torch/TTS/EasyOCR) - DAS DAUERT KURZ...")
            from worker import Worker
            
            # Instanzieren
            self.player = AudioPlayer()
            self.worker = Worker()
            
            # Pfade
            self.resources_path = "resources"
            if not os.path.exists(self.resources_path): os.makedirs(self.resources_path)
            self.settings_path = os.path.join(self.resources_path, "settings.json")
            self.voice_mgr = VoiceManager(self.resources_path)
            self.plugin_path = "" 

            # GUI fertig bauen
            self.create_widgets()
            
            self.hotkeys = {
                "scan": "F9",
                "pause": "F10",
                "stop": "F11",
                "setup": "F8" 
            }
            self.filter_char = tk.StringVar(value="'")
            
            self.load_settings()
            
            # Thread starten
            self.log("INFO", "Starte TTS-Lade-Thread...")
            threading.Thread(target=self.worker.load_tts_model, daemon=True).start()
            
            self.check_plugin_file()
            self.check_template_status()
            self.register_hotkeys()
            
            self.modules_loaded = True
            self.log("SUCCESS", "Alle Module geladen! LQAG bereit.")
            
        except Exception as e:
            err_msg = traceback.format_exc()
            self.log("CRITICAL", f"FEHLER BEIM LADEN: {e}")
            self.log("CRITICAL", err_msg)
            messagebox.showerror("Start-Fehler", f"Ein Modul konnte nicht geladen werden:\n\n{e}\n\nSiehe Log-Fenster für Details.")

    def create_widgets(self):
        # Wir bauen den Rest der GUI erst wenn Imports okay sind
        # Bestehende Log Area nutzen wir weiter
        
        tk.Label(self.root, text="LQAG Controller", bg=self.style_bg, fg=self.style_fg, font=("Segoe UI", 12, "bold")).pack(pady=5)
        
        # SETUP
        setup_frame = tk.LabelFrame(self.root, text="1. Einrichtung & Filter", bg=self.style_bg, fg="#aaaaaa")
        setup_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.btn_template = tk.Button(setup_frame, text="Ecken definieren (F8)", command=self.start_snipping, bg="#d4af37", fg="black", bd=0, padx=10)
        self.btn_template.pack(side=tk.LEFT, padx=10, pady=10)
        
        filter_box = tk.Frame(setup_frame, bg=self.style_bg)
        filter_box.pack(side=tk.LEFT, padx=20)
        tk.Label(filter_box, text="Filter-Zeichen:", bg=self.style_bg, fg="#cccccc", font=("Segoe UI", 8)).pack(anchor="w")
        self.ent_filter = tk.Entry(filter_box, textvariable=self.filter_char, width=10, bg="#1e1e1e", fg="cyan", insertbackground="white", justify="center")
        self.ent_filter.pack(anchor="w")

        self.lbl_template_status = tk.Label(setup_frame, text="Checking...", bg=self.style_bg, fg="#aaaaaa")
        self.lbl_template_status.pack(side=tk.RIGHT, padx=10)

        # TASTEN
        key_frame = tk.LabelFrame(self.root, text="Steuerung", bg=self.style_bg, fg="#aaaaaa")
        key_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Button(key_frame, text="▶ START (F9)", command=self.trigger_scan, bg=self.style_btn, fg="white").pack(side=tk.LEFT, padx=5, pady=5)
        tk.Button(key_frame, text="⏯ PAUSE (F10)", command=lambda: self.player.toggle_pause(), bg=self.style_btn, fg="white").pack(side=tk.LEFT, padx=5, pady=5)
        tk.Button(key_frame, text="⏹ STOP (F11)", command=lambda: self.player.stop(), bg=self.style_btn, fg="white").pack(side=tk.LEFT, padx=5, pady=5)

    # --- RESTLICHE LOGIK ---
    def load_settings(self):
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, "r") as f:
                    data = json.load(f)
                    self.hotkeys = data.get("hotkeys", self.hotkeys)
                    self.filter_char.set(data.get("filter_char", "'"))
            except: pass

    def save_settings(self):
        data = {"hotkeys": self.hotkeys, "filter_char": self.filter_char.get()}
        try:
            with open(self.settings_path, "w") as f: json.dump(data, f)
        except: pass

    def register_hotkeys(self):
        try:
            self.keyboard.unhook_all_hotkeys()
            self.keyboard.add_hotkey(self.hotkeys["scan"], self.trigger_scan)
            self.keyboard.add_hotkey(self.hotkeys["pause"], self.player.toggle_pause)
            self.keyboard.add_hotkey(self.hotkeys["stop"], self.player.stop)
            self.keyboard.add_hotkey(self.hotkeys["setup"], lambda: self.root.after(0, self.start_snipping))
        except: pass

    def start_snipping(self):
        self.root.iconify()
        self.SnipperClass(self.root, self.resources_path, self.on_snipping_done)

    def on_snipping_done(self, success):
        self.root.deiconify()
        self.check_template_status()

    def check_template_status(self):
        t1 = os.path.join(self.resources_path, "template_tl.png")
        if os.path.exists(t1): self.lbl_template_status.config(text="✔ Ecken OK", fg="#00ff00")
        else: self.lbl_template_status.config(text="❌ Einrichtung nötig", fg="red")

    def check_plugin_file(self):
        if self.plugin_path and self.voice_mgr.read_speaker_from_plugin(self.plugin_path):
            pass # Speaker update logic hier vereinfacht
        self.root.after(2000, self.check_plugin_file)
        
    def select_plugin_file(self):
        initial = os.path.expanduser("~/Documents/The Lord of the Rings Online")
        path = filedialog.askopenfilename(initialdir=initial, title="Wähle Script.log")
        if path: self.plugin_path = path

    def trigger_scan(self):
        if not self.modules_loaded: return
        voice_path = self.voice_mgr.get_voice_path()
        if not voice_path:
            logging.error("Keine Stimme gefunden.")
            return

        try:
            import re
            delimiter = self.filter_char.get().strip()
            if delimiter:
                self.save_settings()
                safe_char = re.escape(delimiter)
                regex_pattern = f"{safe_char}(.*){safe_char}"
                logging.info(f"Scan Start (Filter: {delimiter}...{delimiter})")
            else:
                regex_pattern = None
                logging.info("Scan Start (Kein Filter)")
            
            self.worker.run_process(self.resources_path, voice_path, self.play_audio, regex_pattern)
        except Exception as e:
            logging.error(f"Scan Start Error: {e}")

    def play_audio(self, stream_gen):
        self.root.after(0, lambda: self.player.play_stream(stream_gen))
    
    def rebind_key(self, action, btn): pass # Verkürzt für Safe Mode

if __name__ == "__main__":
    multiprocessing.freeze_support() # ABSOLUT NOTWENDIG FÜR EXE
    root = tk.Tk()
    try: root.iconbitmap("resources/icon.ico")
    except: pass
    app = LQAGApp(root)
    root.mainloop()
