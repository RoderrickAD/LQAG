import sys
import os

# FIX: Add the src directory to Python's path so it can find audio_engine and screen_tool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from tkinter import ttk
import threading
import time
import easyocr
import numpy as np
import pyautogui
from audio_engine import AudioEngine
from screen_tool import SnippingTool

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("LotRO Vorleser (AI Powered)")
        self.root.geometry("500x400")
        
        # Status Variablen
        self.monitoring = False
        self.scan_area = None # (x, y, w, h)
        self.last_text = ""
        
        # 1. UI Aufbauen
        self.setup_ui()
        
        # 2. Engines im Hintergrund laden
        self.log("⏳ Lade KI-Modelle (Das dauert kurz)...")
        threading.Thread(target=self.load_engines, daemon=True).start()

    def setup_ui(self):
        # Bereich wählen Button
        btn_frame = tk.Frame(self.root, pady=10)
        btn_frame.pack()
        
        self.btn_area = tk.Button(btn_frame, text="1. Chat-Bereich auswählen", command=self.select_area, bg="#4a4a4a", fg="white")
        self.btn_area.pack(side=tk.LEFT, padx=5)
        
        self.btn_start = tk.Button(btn_frame, text="2. Start", command=self.toggle_monitoring, state=tk.DISABLED, bg="green", fg="white")
        self.btn_start.pack(side=tk.LEFT, padx=5)

        # Log Fenster
        self.log_box = tk.Text(self.root, height=15, bg="black", fg="#00ff00", font=("Consolas", 10))
        self.log_box.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Status Leiste
        self.lbl_status = tk.Label(self.root, text="Warte auf Initialisierung...", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.lbl_status.pack(side=tk.BOTTOM, fill=tk.X)

    def log(self, text):
        self.log_box.insert(tk.END, text + "\n")
        self.log_box.see(tk.END)

    def load_engines(self):
        try:
            # OCR Laden (Deutsch & Englisch)
            self.log("... Lade Texterkennung (OCR) ...")
            self.reader = easyocr.Reader(['de', 'en'], gpu=True)
            self.log("✅ OCR geladen!")
            
            # Audio Laden
            self.log("... Lade Sprach-KI (Coqui) ...")
            self.audio = AudioEngine()
            
            self.lbl_status.config(text="System bereit. Bitte Bereich wählen.")
            self.log("🚀 SYSTEM BEREIT!")
            
        except Exception as e:
            self.log(f"❌ Fehler beim Laden: {e}")

    def select_area(self):
        self.root.iconify() # Fenster minimieren
        SnippingTool(self.root, self.on_area_selected)

    def on_area_selected(self, x, y, w, h):
        self.root.deiconify() # Fenster wiederherstellen
        self.scan_area = (x, y, w, h)
        self.log(f"Bereich definiert: {x}, {y} ({w}x{h})")
        self.btn_start.config(state=tk.NORMAL)

    def toggle_monitoring(self):
        if not self.monitoring:
            self.monitoring = True
            self.btn_start.config(text="Stopp", bg="red")
            threading.Thread(target=self.monitor_loop, daemon=True).start()
        else:
            self.monitoring = False
            self.btn_start.config(text="Start", bg="green")

    def monitor_loop(self):
        self.log("👀 Überwachung gestartet...")
        while self.monitoring:
            try:
                # 1. Screenshot machen
                x, y, w, h = self.scan_area
                screenshot = pyautogui.screenshot(region=(x, y, w, h))
                image_np = np.array(screenshot)

                # 2. Text lesen
                results = self.reader.readtext(image_np, detail=0)
                full_text = " ".join(results).strip()

                # 3. Logik: Ist es neuer Text?
                if full_text and full_text != self.last_text:
                    # Filter: Ist der Text lang genug? (Rauschen vermeiden)
                    if len(full_text) > 5: 
                        self.log(f"Gelesen: {full_text}")
                        
                        # HIER SPRECHEN WIR!
                        self.audio.speak(full_text)
                        
                        self.last_text = full_text

                time.sleep(1.0) # Jede Sekunde prüfen

            except Exception as e:
                print(f"Loop Fehler: {e}")
                time.sleep(1)

# App Start
if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
