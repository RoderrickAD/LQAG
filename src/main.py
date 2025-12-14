import sys
import os
import cv2
import numpy as np

# Fix für Portable Python Pfade
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
import threading
import time
import easyocr
import pyautogui
import keyboard
from audio_engine import AudioEngine
from screen_tool import SnippingTool

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Universal Game TTS (Dynamic Tracking)")
        self.root.geometry("600x500")
        self.root.attributes("-topmost", True)
        
        # --- ZUSTANDSVARIABLEN ---
        self.monitoring = False
        self.last_text = ""
        
        # Hier speichern wir die "Fingerabdrücke" des Fensters im RAM
        self.template_tl = None # Bilddaten oben-links
        self.template_br = None # Bilddaten unten-rechts
        self.current_area = None # (x, y, w, h)
        
        # Einstellungen
        self.confidence = 0.8  # Wie genau muss das Bild passen?
        self.corner_size = 30  # Wie groß ist der "Fingerabdruck" (Pixel)?

        self.setup_ui()
        
        self.log("⏳ Lade KI-Systeme...")
        threading.Thread(target=self.load_engines, daemon=True).start()

    def setup_ui(self):
        # Style
        bg_color = "#1e1e1e"
        fg_color = "#00ff00"
        self.root.configure(bg=bg_color)

        # Header Info
        lbl_info = tk.Label(self.root, text="SCHRITT 1: Ziehe einen Rahmen um das Fenster.\nSCHRITT 2: Das Tool merkt sich das Aussehen und verfolgt es.",
                           bg=bg_color, fg="white", font=("Arial", 10))
        lbl_info.pack(pady=5)

        # Buttons
        btn_frame = tk.Frame(self.root, bg=bg_color)
        btn_frame.pack(pady=10)
        
        self.btn_select = tk.Button(btn_frame, text="1. Bereich & Template lernen (F10)", 
                                   command=self.learn_window_pattern, bg="#007acc", fg="white", font=("Arial", 10, "bold"))
        self.btn_select.pack(side=tk.LEFT, padx=10)
        
        self.btn_start = tk.Button(btn_frame, text="2. Start Vorlesen (F9)", 
                                  command=self.toggle_monitoring, state=tk.DISABLED, bg="#2d2d2d", fg="white", font=("Arial", 10, "bold"))
        self.btn_start.pack(side=tk.LEFT, padx=10)

        # Log Box
        self.log_box = tk.Text(self.root, height=15, bg="black", fg=fg_color, font=("Consolas", 10), insertbackground="white")
        self.log_box.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Statusleiste
        self.lbl_status = tk.Label(self.root, text="Warte auf Engine...", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.lbl_status.pack(side=tk.BOTTOM, fill=tk.X)

    def log(self, text):
        self.log_box.insert(tk.END, f">> {text}\n")
        self.log_box.see(tk.END)

    def load_engines(self):
        try:
            self.log("... Starte OCR Engine ...")
            self.reader = easyocr.Reader(['de', 'en'], gpu=True)
            
            self.log("... Starte Audio Engine ...")
            self.audio = AudioEngine()
            
            # Hotkeys
            keyboard.add_hotkey('f9', self.toggle_monitoring)
            keyboard.add_hotkey('f10', self.learn_window_pattern)
            
            self.log("✅ SYSTEM BEREIT!")
            self.lbl_status.config(text="Bereit. Drücke F10 zum Einlernen.")

        except Exception as e:
            self.log(f"❌ Fehler: {e}")

    # --- KERN-LOGIK: LERNEN ---
    def learn_window_pattern(self):
        """Benutzer zieht Rahmen, wir speichern die Ecken als Template."""
        self.root.iconify()
        # Wir nutzen dein Snipping Tool, um den Bereich zu holen
        SnippingTool(self.root, self._process_learning)

    def _process_learning(self, x, y, w, h):
        self.root.deiconify()
        time.sleep(0.3) # Kurz warten bis Overlay weg ist
        
        try:
            # Screenshot vom gewählten Bereich machen
            screenshot = pyautogui.screenshot(region=(x, y, w, h))
            img = np.array(screenshot)
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR) # Für OpenCV konvertieren

            # Wir schneiden uns die "Ecken" aus dem Screenshot heraus
            # Top-Left Corner (TL)
            h_img, w_img, _ = img.shape
            size = self.corner_size
            
            # Sicherheitscheck: Ist der Bereich groß genug?
            if w_img < size or h_img < size:
                self.log("❌ Bereich zu klein! Muss größer als 30x30px sein.")
                return

            self.template_tl = img[0:size, 0:size] # Linke obere Ecke
            self.template_br = img[h_img-size:h_img, w_img-size:w_img] # Rechte untere Ecke
            
            self.current_area = (x, y, w, h)
            
            self.log(f"🧠 MUSTER GELERNT!")
            self.log(f"Position: {x},{y} | Größe: {w}x{h}")
            self.log("Wenn sich das Fenster bewegt, finde ich es wieder.")
            
            self.btn_start.config(state=tk.NORMAL, bg="green")
            self.highlight_area(x, y, w, h, color="green")

        except Exception as e:
            self.log(f"Lern-Fehler: {e}")

    # --- KERN-LOGIK: SUCHEN ---
    def scan_for_window(self):
        """Sucht auf dem ganzen Screen nach den gelernten Ecken."""
        if self.template_tl is None or self.template_br is None:
            return None

        try:
            # Ganzen Bildschirm fotografieren
            screen = np.array(pyautogui.screenshot())
            screen = cv2.cvtColor(screen, cv2.COLOR_RGB2BGR)

            # 1. Suche oben-links (TL)
            res_tl = cv2.matchTemplate(screen, self.template_tl, cv2.TM_CCOEFF_NORMED)
            _, max_val_tl, _, max_loc_tl = cv2.minMaxLoc(res_tl)

            # 2. Suche unten-rechts (BR)
            res_br = cv2.matchTemplate(screen, self.template_br, cv2.TM_CCOEFF_NORMED)
            _, max_val_br, _, max_loc_br = cv2.minMaxLoc(res_br)

            # Prüfen ob gut genug gefunden
            if max_val_tl < self.confidence or max_val_br < self.confidence:
                return None # Nicht gefunden

            # Neue Koordinaten berechnen
            new_x = max_loc_tl[0]
            new_y = max_loc_tl[1]
            
            # Die BR Koordinate ist der Startpunkt des BR-Templates. 
            # Wir müssen die Breite des Templates dazurechnen, um das echte Ende zu haben.
            br_x_end = max_loc_br[0] + self.corner_size
            br_y_end = max_loc_br[1] + self.corner_size
            
            new_w = br_x_end - new_x
            new_h = br_y_end - new_y
            
            return (new_x, new_y, new_w, new_h)

        except Exception:
            return None

    def highlight_area(self, x, y, w, h, color="red"):
        top = tk.Toplevel(self.root)
        top.geometry(f"{w}x{h}+{x}+{y}")
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        top.attributes("-alpha", 0.3)
        top.configure(bg=color)
        top.after(500, top.destroy)

    def toggle_monitoring(self):
        if not self.monitoring:
            if self.template_tl is None:
                self.log("⚠️ Bitte erst mit F10 einlernen!")
                return
                
            self.monitoring = True
            self.btn_start.config(text="STOPP (F9)", bg="red")
            self.log("▶ Überwachung gestartet.")
            threading.Thread(target=self.monitor_loop, daemon=True).start()
        else:
            self.monitoring = False
            self.btn_start.config(text="START (F9)", bg="green")
            self.log("⏸ Pausiert.")

    def monitor_loop(self):
        fail_count = 0
        
        while self.monitoring:
            try:
                # OPTION A: Wir nutzen die letzte bekannte Position (schnell)
                x, y, w, h = self.current_area
                
                # Wir machen einen schnellen Check: Sind die Ecken noch da?
                # (Das sparen wir uns für Performance, wir lesen einfach und wenn Text Müll ist, suchen wir neu)
                
                screenshot = pyautogui.screenshot(region=(x, y, w, h))
                image_np = np.array(screenshot)

                # Text lesen
                results = self.reader.readtext(image_np, detail=0)
                full_text = " ".join(results).strip()

                # LOGIK: Wenn wir Text finden, ist alles gut.
                if full_text:
                    fail_count = 0 # Reset
                    if full_text != self.last_text and len(full_text) > 3:
                        self.log(f"🗣️: {full_text}")
                        self.audio.speak(full_text)
                        self.last_text = full_text
                
                # LOGIK: Wenn wir LANGE keinen Text finden, hat sich das Fenster vielleicht bewegt?
                else:
                    fail_count += 1
                    if fail_count > 5: # Nach 5 Fehlversuchen (ca. 5 Sek) suchen wir das Fenster neu
                        self.log("❓ Kein Text... suche Fenster neu...")
                        found = self.scan_for_window()
                        if found:
                            self.current_area = found
                            self.log(f"✅ Fenster wiedergefunden bei {found}")
                            self.highlight_area(*found, color="blue")
                            fail_count = 0
                        else:
                            self.log("⚠️ Fenster nicht gefunden.")

                time.sleep(1.0)

            except Exception as e:
                print(f"Loop Fehler: {e}")
                time.sleep(1)

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
