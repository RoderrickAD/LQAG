import sys
import os
import cv2
import numpy as np
import datetime # Für Zeitstempel in den Logs

# Fix für Portable Python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from tkinter import messagebox
import threading
import time
import easyocr
import pyautogui
import keyboard
from audio_engine import AudioEngine
from screen_tool import SnippingTool
from npc_manager import NpcManager

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("LQAG - Debug & Control Edition")
        self.root.geometry("650x600")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#1e1e1e")
        
        # --- ORDNER STRUKTUR ---
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.debug_dir = os.path.join(self.base_dir, "..", "debug")
        if not os.path.exists(self.debug_dir):
            os.makedirs(self.debug_dir)
            print(f"📁 Debug-Ordner erstellt: {self.debug_dir}")
        
        # --- ZUSTAND ---
        self.auto_mode = False  # Standard: Manuell
        self.is_scanning = False
        
        self.template_tl = None
        self.template_br = None
        self.current_area = None # (x, y, w, h)
        
        self.setup_ui()
        
        self.log("⏳ Initialisiere Systeme...")
        threading.Thread(target=self.load_engines, daemon=True).start()

    def setup_ui(self):
        # Info
        lbl_info = tk.Label(self.root, text="F10: Bereich lernen | F9: JETZT lesen\nDebug-Daten werden im Ordner 'debug' gespeichert.",
                           bg="#1e1e1e", fg="#cccccc", font=("Arial", 9))
        lbl_info.pack(pady=5)

        # Buttons Reihe 1
        btn_frame = tk.Frame(self.root, bg="#1e1e1e")
        btn_frame.pack(pady=5)
        
        self.btn_learn = tk.Button(btn_frame, text="1. Einlernen (F10)", 
                                   command=self.learn_window_pattern, bg="#007acc", fg="white", width=20)
        self.btn_learn.pack(side=tk.LEFT, padx=5)
        
        self.btn_read = tk.Button(btn_frame, text="2. JETZT LESEN (F9)", 
                                  command=self.scan_once, state=tk.DISABLED, bg="#28a745", fg="white", width=20)
        self.btn_read.pack(side=tk.LEFT, padx=5)

        # Buttons Reihe 2 (Audio & Auto)
        ctrl_frame = tk.Frame(self.root, bg="#1e1e1e")
        ctrl_frame.pack(pady=5)

        self.btn_stop_audio = tk.Button(ctrl_frame, text="⏹ Audio Stopp", 
                                        command=self.stop_audio, bg="#dc3545", fg="white")
        self.btn_stop_audio.pack(side=tk.LEFT, padx=5)

        self.chk_auto_var = tk.BooleanVar()
        self.chk_auto = tk.Checkbutton(ctrl_frame, text="Auto-Modus (Loop)", variable=self.chk_auto_var, 
                                       bg="#1e1e1e", fg="white", selectcolor="black", command=self.toggle_auto)
        self.chk_auto.pack(side=tk.LEFT, padx=10)

        # Log Box
        self.log_box = tk.Text(self.root, height=20, bg="black", fg="#00ff00", font=("Consolas", 9), insertbackground="white")
        self.log_box.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Status
        self.lbl_target = tk.Label(self.root, text="Ziel: -", bg="#333", fg="yellow", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.lbl_target.pack(side=tk.BOTTOM, fill=tk.X)

    def log(self, text):
        self.log_box.insert(tk.END, f">> {text}\n")
        self.log_box.see(tk.END)

    def load_engines(self):
        try:
            self.npc_manager = NpcManager()
            self.reader = easyocr.Reader(['de', 'en'], gpu=True)
            self.audio = AudioEngine()
            
            keyboard.add_hotkey('f9', self.scan_once)
            keyboard.add_hotkey('f10', self.learn_window_pattern)
            
            self.log("✅ BEREIT! Drücke F10 zum Einlernen.")

        except Exception as e:
            self.log(f"❌ Fehler: {e}")

    # --- LERNEN & DEBUGGEN ---
    def learn_window_pattern(self):
        self.root.iconify()
        SnippingTool(self.root, self._process_learning)

    def _process_learning(self, x, y, w, h):
        self.root.deiconify()
        time.sleep(0.3)
        try:
            screenshot = pyautogui.screenshot(region=(x, y, w, h))
            img = np.array(screenshot)
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

            size = 30
            h_img, w_img, _ = img.shape
            if w_img < size or h_img < size:
                self.log("❌ Zu klein!")
                return

            self.template_tl = img[0:size, 0:size]
            self.template_br = img[h_img-size:h_img, w_img-size:w_img]
            self.current_area = (x, y, w, h)
            
            # DEBUG: Templates speichern
            cv2.imwrite(os.path.join(self.debug_dir, "template_oben_links.png"), self.template_tl)
            cv2.imwrite(os.path.join(self.debug_dir, "template_unten_rechts.png"), self.template_br)
            self.log(f"📝 Templates gespeichert in 'debug/'")
            
            self.btn_read.config(state=tk.NORMAL)
            self.highlight_area(x, y, w, h, "green")

        except Exception as e:
            self.log(f"Fehler: {e}")

    # --- LESEN (MANUELL ODER AUTO) ---
    def scan_once(self):
        """Liest genau EINMAL den Bereich."""
        if self.is_scanning or not self.current_area: return
        self.is_scanning = True
        
        threading.Thread(target=self._run_scan, daemon=True).start()

    def toggle_auto(self):
        """Schaltet den Loop an/aus."""
        if self.chk_auto_var.get():
            self.log("🔄 Auto-Modus AKTIV (Scannt alle 2s)")
            self.auto_loop()
        else:
            self.log("🛑 Auto-Modus AUS (Nur F9)")

    def auto_loop(self):
        if not self.chk_auto_var.get(): return
        self.scan_once()
        # Ruft sich selbst in 2 Sekunden wieder auf
        self.root.after(2000, self.auto_loop)

    def _run_scan(self):
        try:
            # 1. Update NPC
            self.npc_manager.update()
            target = self.npc_manager.current_target
            voice_path = self.npc_manager.get_voice_path()
            voice_name = os.path.basename(voice_path) if voice_path else "Standard"
            
            self.root.after(0, lambda: self.lbl_target.config(text=f"Ziel: {target} | Stimme: {voice_name}"))

            # 2. Prüfen, ob Fenster noch da ist (Template Match)
            # Wir suchen erst, wenn wir unsicher sind, oder wir vertrauen der Position
            # Für Debugging machen wir einfach den Screenshot an der gemerkten Position
            
            x, y, w, h = self.current_area
            screenshot = pyautogui.screenshot(region=(x, y, w, h))
            
            # DEBUG: Screenshot speichern
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            debug_img_path = os.path.join(self.debug_dir, f"scan_{timestamp}.png")
            screenshot.save(debug_img_path)
            
            # OCR
            image_np = np.array(screenshot)
            results = self.reader.readtext(image_np, detail=0)
            full_text = " ".join(results).strip()
            
            # DEBUG: Text speichern
            debug_txt_path = os.path.join(self.debug_dir, "scan_log.txt")
            with open(debug_txt_path, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {target}: {full_text}\n----------------\n")

            if full_text and len(full_text) > 5:
                self.log(f"📖 Gelesen: {full_text[:40]}...")
                self.log(f"💾 (Gespeichert in debug/scan_{timestamp}.png)")
                
                if voice_path:
                    self.audio.speak(full_text, voice_path)
                else:
                    self.log("⚠️ Keine Stimme gefunden!")
            else:
                self.log("... kein Text erkannt oder zu kurz.")

        except Exception as e:
            self.log(f"Scan Fehler: {e}")
        finally:
            self.is_scanning = False

    def stop_audio(self):
        self.audio.stop()
        self.log("🔇 Audio gestoppt.")

    def highlight_area(self, x, y, w, h, color="red"):
        # Zeichnet kurz einen Rahmen
        try:
            top = tk.Toplevel(self.root)
            top.geometry(f"{w}x{h}+{x}+{y}")
            top.overrideredirect(True)
            top.attributes("-topmost", True)
            top.attributes("-alpha", 0.3)
            top.configure(bg=color)
            top.after(500, top.destroy)
        except: pass

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
