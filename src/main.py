import tkinter as tk
from tkinter import scrolledtext, filedialog, ttk
import keyboard
import os
import threading
from utils import setup_logger
from worker import Worker
from audio_player import AudioPlayer
from voice_manager import VoiceManager
import logging

class LQAGApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LQAG v1.3 - Smart Speaker Controller")
        self.root.geometry("650x550")
        
        # Design Einstellungen (Neutral Dark Mode)
        self.style_bg = "#2b2b2b"
        self.style_fg = "#ffffff"
        self.style_accent = "#3a3a3a"
        self.root.configure(bg=self.style_bg)

        # 1. PFADE DEFINIEREN
        # Wir zeigen auf den Haupt-Resource-Ordner, der Manager kümmert sich um den Rest
        self.resources_path = "resources"
        self.template_path = os.path.join(self.resources_path, "template.png")
        
        # 2. KOMPONENTEN INITIALISIEREN
        self.player = AudioPlayer()
        self.worker = Worker()
        
        # Der VoiceManager bekommt den Pfad zum 'resources' Ordner
        # Er sucht dort selbst nach 'voices/specific', 'voices/generic_male' usw.
        self.voice_mgr = VoiceManager(self.resources_path)
        
        self.plugin_path = "" # Pfad zur .plugindata Datei

        # 3. GUI BAUEN
        self.create_widgets()

        # 4. HINTERGRUND PROZESSE STARTEN
        # KI-Modell laden (dauert etwas, daher im Thread)
        threading.Thread(target=self.worker.load_tts_model, daemon=True).start()
        
        # Hotkey setzen (Standard F9)
        self.hotkey = "F9"
        keyboard.add_hotkey(self.hotkey, self.trigger_scan)
        
        # Startet den Loop, der die Plugin-Datei überwacht
        self.check_plugin_file()
        
        logging.info("LQAG v1.3 gestartet.")
        logging.info("Bitte LOTRO Plugin-Datei (.plugindata) auswählen.")

    def create_widgets(self):
        # --- HEADER ---
        header_frame = tk.Frame(self.root, bg=self.style_bg)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        tk.Label(header_frame, text="LQAG Controller", bg=self.style_bg, fg=self.style_fg, font=("Segoe UI", 12, "bold")).pack(side=tk.LEFT)
        
        # --- BRIDGE BEREICH (Verbindung zum Spiel) ---
        bridge_group = tk.LabelFrame(self.root, text="LOTRO Verbindung", bg=self.style_bg, fg="#aaaaaa", bd=1)
        bridge_group.pack(fill=tk.X, padx=10, pady=5)

        # Dateipfad Anzeige
        self.lbl_plugin = tk.Label(bridge_group, text="Keine Plugin-Datei ausgewählt!", bg=self.style_bg, fg="orange", wraplength=450, justify="left")
        self.lbl_plugin.pack(side=tk.LEFT, padx=10, pady=10)
        
        # Button zum Auswählen
        btn_select = tk.Button(bridge_group, text="Datei wählen...", command=self.select_plugin_file, bg=self.style_accent, fg=self.style_fg, bd=0, padx=10)
        btn_select.pack(side=tk.RIGHT, padx=10, pady=10)

        # --- STATUS ANZEIGE ---
        status_frame = tk.Frame(self.root, bg=self.style_bg)
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Zeigt den erkannten NPC Namen an
        self.lbl_speaker = tk.Label(status_frame, text="Aktueller NPC: Unbekannt", bg=self.style_bg, fg="#00ff00", font=("Segoe UI", 11, "bold"))
        self.lbl_speaker.pack(pady=5)

        # --- STEUERUNG ---
        btn_frame = tk.Frame(self.root, bg=self.style_bg)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)

        # Styles für Buttons
        btn_opts = {'bg': self.style_accent, 'fg': self.style_fg, 'activebackground': '#505050', 'activeforeground': 'white', 'bd': 0, 'padx': 20, 'pady': 8}

        self.btn_scan = tk.Button(btn_frame, text=f"▶ SCAN ({self.hotkey})", command=self.trigger_scan, **btn_opts)
        self.btn_scan.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_pause = tk.Button(btn_frame, text="⏯ Pause", command=self.player.toggle_pause, **btn_opts)
        self.btn_pause.pack(side=tk.LEFT, padx=5)
        
        self.btn_stop = tk.Button(btn_frame, text="⏹ Stop", command=self.player.stop, **btn_opts)
        self.btn_stop.pack(side=tk.LEFT, padx=5)

        # --- LOG / DEBUG ---
        log_frame = tk.LabelFrame(self.root, text="System Log", bg=self.style_bg, fg="#aaaaaa", bd=1)
        log_frame.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        self.log_area = scrolledtext.ScrolledText(log_frame, state='disabled', bg="#1e1e1e", fg="#00ff00", font=("Consolas", 9), height=10)
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Log verbinden
        setup_logger(self.log_area)

    def select_plugin_file(self):
        # Standardpfad für LOTRO Plugins vorschlagen
        initial_dir = os.path.expanduser("~/Documents/The Lord of the Rings Online/PluginData")
        
        path = filedialog.askopenfilename(
            initialdir=initial_dir,
            title="Wähle die .plugindata Datei (z.B. LQAG_Data.plugindata)",
            filetypes=[("Plugin Data", "*.plugindata"), ("All Files", "*.*")]
        )
        
        if path:
            self.plugin_path = path
            filename = os.path.basename(path)
            self.lbl_plugin.config(text=f".../{filename}", fg="#00ff00")
            logging.info(f"Überwache Plugin-Datei: {filename}")
            # Einmal sofort prüfen
            self.check_plugin_file_once()

    def check_plugin_file(self):
        """Regelmäßiger Loop (alle 2 Sekunden)"""
        self.check_plugin_file_once()
        self.root.after(2000, self.check_plugin_file)

    def check_plugin_file_once(self):
        """Liest die Datei und aktualisiert das UI, falls sich der Name geändert hat"""
        if self.plugin_path:
            has_changed = self.voice_mgr.read_speaker_from_plugin(self.plugin_path)
            if has_changed:
                speaker = self.voice_mgr.current_speaker
                # Info update im UI
                self.lbl_speaker.config(text=f"Aktueller NPC: {speaker}")
                
                # Optional: Hier könnte man schon anzeigen, welches Geschlecht erkannt wurde
                gender = self.voice_mgr.gender_map.get(speaker, "?")
                logging.info(f"UI Update: Sprecher ist '{speaker}' (Gender: {gender})")

    def trigger_scan(self):
        # 1. Template prüfen
        if not os.path.exists(self.template_path):
            logging.error(f"FEHLER: Template nicht gefunden: {self.template_path}")
            return

        # 2. Automatische Stimmenwahl über den Manager
        # (Der Manager weiß durch den Loop oben schon, wer der Speaker ist)
        voice_path = self.voice_mgr.get_voice_path()
        
        if not voice_path:
            logging.error("ABBRUCH: Keine Stimme gefunden (Weder spezifisch noch generisch).")
            return

        # Nur zur Info loggen (Dateiname reicht)
        voice_name = os.path.basename(voice_path)
        logging.info(f"Starte TTS mit Stimme: {voice_name}")

        # 3. Worker starten
        self.worker.run_process(self.template_path, voice_path, self.play_audio)

    def play_audio(self, file_path):
        # Wird vom Worker aufgerufen, wenn Audio fertig ist
        self.root.after(0, lambda: self.player.play(file_path))

if __name__ == "__main__":
    root = tk.Tk()
    # Icon laden falls vorhanden (optional)
    try: root.iconbitmap("resources/icon.ico")
    except: pass
    
    app = LQAGApp(root)
    root.mainloop()
