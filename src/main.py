import sys
import os
import cv2
import numpy as np

# Fix für Portable Python: Stelle sicher, dass Module im src-Ordner gefunden werden
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
import threading
import time
import easyocr
import pyautogui
import keyboard
from audio_engine import AudioEngine
from screen_tool import SnippingTool
from npc_manager import NpcManager  # <-- Unser neuer Manager

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("LQAG - Voice Cloning Edition")
        self.root.geometry("600x520")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#1e1e1e")
        
        # --- ZUSTANDSVARIABLEN ---
        self.monitoring = False
        self.last_text = ""
        
        # Template Matching (für das Finden des Fensters)
        self.template_tl = None
        self.template_br = None
        self.current_area = None # (x, y, w, h)
        
        self.setup_ui()
        
        self.log("⏳ Lade Systeme...")
        threading.Thread(target=self.load_engines, daemon=True).start()

    def setup_ui(self):
        # Header Info
        lbl_info = tk.Label(self.root, text="SCHRITT 1: F10 drücken & Quest-Text markieren.\nSCHRITT 2: F9 drücken zum Starten.\nDas Tool wählt automatisch die passende Stimme!",
                           bg="#1e1e1e", fg="white", font=("Arial", 10))
        lbl_info.pack(pady=10)

        # Buttons
        btn_frame = tk.Frame(self.root, bg="#1e1e1e")
        btn_frame.pack(pady=5)
        
        self.btn_select = tk.Button(btn_frame, text="1. Bereich lernen (F10)", 
                                   command=self.learn_window_pattern, bg="#007acc", fg="white", font=("Arial", 10, "bold"))
        self.btn_select.pack(side=tk.LEFT, padx=10)
        
        self.btn_start = tk.Button(btn_frame, text="2. Start (F9)", 
                                  command=self.toggle_monitoring, state=tk.DISABLED, bg="#2d2d2d", fg="white", font=("Arial", 10, "bold"))
        self.btn_start.pack(side=tk.LEFT, padx=10)

        # Log Box
        self.log_box = tk.Text(self.root, height=15, bg="black", fg="#00ff00", font=("Consolas", 10), insertbackground="white")
        self.log_box.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Statusleiste (Zeigt aktuelles Ziel an)
        self.lbl_target = tk.Label(self.root, text="Ziel: Unbekannt", bg="#333", fg="yellow", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.lbl_target.pack(side=tk.BOTTOM, fill=tk.X)

    def log(self, text):
        self.log_box.insert(tk.END, f">> {text}\n")
        self.log_box.see(tk.END)

    def load_engines(self):
        try:
            self.log("... Lade NPC Datenbank ...")
            self.npc_manager = NpcManager() # <-- Lädt deine Listen & Stimmen
            
            self.log("... Lade OCR (Textlesen) ...")
            self.reader = easyocr.Reader(['de', 'en'], gpu=True)
            
            self.log("... Lade Audio Engine ...")
            self.audio = AudioEngine()
            
            # Hotkeys
            keyboard.add_hotkey('f9', self.toggle_monitoring)
            keyboard.add_hotkey('f10', self.learn_window_pattern)
            
            self.log("✅ SYSTEM BEREIT!")
            self.btn_select.config(state=tk.NORMAL)

        except Exception as e:
            self.log(f"❌ Kritischer Ladefehler: {e}")

    # --- LERN-LOGIK (Fenster erkennen) ---
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

            h_img, w_img, _ = img.shape
            size = 30 # Größe der Ecken
            
            if w_img < size or h_img < size:
                self.log("❌ Bereich zu klein!")
                return

            self.template_tl = img[0:size, 0:size]
            self.template_br = img[h_img-size:h_img, w_img-size:w_img]
            self.current_area = (x, y, w, h)
            
            self.log(f"🧠 Bereich gelernt ({w}x{h})")
            self.btn_start.config(state=tk.NORMAL, bg="green")
            self.highlight_area(x, y, w, h, "green")

        except Exception as e:
            self.log(f"Fehler: {e}")

    # --- SUCH-LOGIK (Wenn Fenster verschoben wird) ---
    def scan_for_window(self):
        if self.template_tl is None: return None
        try:
            screen = np.array(pyautogui.screenshot())
            screen = cv2.cvtColor(screen, cv2.COLOR_RGB2BGR)

            res_tl = cv2.matchTemplate(screen, self.template_tl, cv2.TM_CCOEFF_NORMED)
            _, max_val_tl, _, max_loc_tl = cv2.minMaxLoc(res_tl)

            res_br = cv2.matchTemplate(screen, self.template_br, cv2.TM_CCOEFF_NORMED)
            _, max_val_br, _, max_loc_br = cv2.minMaxLoc(res_br)

            if max_val_tl < 0.8 or max_val_br < 0.8: return None

            new_x, new_y = max_loc_tl
            br_x = max_loc_br[0] + 30
            br_y = max_loc_br[1] + 30
            
            return (new_x, new_y, br_x - new_x, br_y - new_y)
        except: return None

    def highlight_area(self, x, y, w, h, color="red"):
        top = tk.Toplevel(self.root)
        top.geometry(f"{w}x{h}+{x}+{y}")
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        top.attributes("-alpha", 0.3)
        top.configure(bg=color)
        top.after(500, top.destroy)

    # --- HAUPT-LOOP ---
    def toggle_monitoring(self):
        if not self.monitoring:
            if self.template_tl is None:
                self.log("⚠️ Bitte erst F10 drücken!")
                return
            self.monitoring = True
            self.btn_start.config(text="STOPP (F9)", bg="red")
            threading.Thread(target=self.monitor_loop, daemon=True).start()
        else:
            self.monitoring = False
            self.btn_start.config(text="START (F9)", bg="green")

    def monitor_loop(self):
        fail_count = 0
        while self.monitoring:
            try:
                # 1. PLUGIN CHECK: Wer ist das Ziel?
                self.npc_manager.update()
                
                # GUI Update (Ziel anzeigen)
                target_name = self.npc_manager.current_target
                voice_path = self.npc_manager.get_voice_path()
                voice_name = os.path.basename(voice_path) if voice_path else "KEINE"
                
                self.lbl_target.config(text=f"Ziel: {target_name} | Stimme: {voice_name}")

                # 2. SCREENSHOT & OCR
                x, y, w, h = self.current_area
                screenshot = pyautogui.screenshot(region=(x, y, w, h))
                image_np = np.array(screenshot)
                
                results = self.reader.readtext(image_np, detail=0)
                full_text = " ".join(results).strip()

                if full_text:
                    fail_count = 0
                    # Nur sprechen, wenn neuer Text da ist
                    if full_text != self.last_text and len(full_text) > 3:
                        
                        self.log(f"🗣️ {target_name}: {full_text[:30]}...")
                        
                        # HIER IST DIE MAGIE: Wir übergeben die Datei an die Audio-Engine!
                        if voice_path:
                            self.audio.speak(full_text, voice_path)
                        else:
                            self.log("⚠️ Fehler: Keine Stimmen-Datei gefunden!")
                        
                        self.last_text = full_text
                else:
                    # Fenster verloren? Suchen!
                    fail_count += 1
                    if fail_count > 5:
                        found = self.scan_for_window()
                        if found:
                            self.current_area = found
                            self.highlight_area(*found, "blue")
                            fail_count = 0

                time.sleep(0.5)

            except Exception as e:
                print(f"Loop Fehler: {e}")
                time.sleep(1)

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
