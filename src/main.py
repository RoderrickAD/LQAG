import sys
import os
import cv2
import numpy as np
import datetime

# Pfad-Fix
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
        self.root.title("LQAG - Vorleser (Präzise)")
        self.root.geometry("600x550")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#1e1e1e")
        
        # --- ORDNER PFADE ---
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.root_dir = os.path.dirname(self.base_dir)
        
        # Cache & Debug
        self.cache_dir = os.path.join(self.root_dir, "resources", "cache")
        if not os.path.exists(self.cache_dir): os.makedirs(self.cache_dir)

        self.debug_dir = os.path.join(self.root_dir, "debug")
        if not os.path.exists(self.debug_dir): os.makedirs(self.debug_dir)
        
        # --- ZUSTAND ---
        self.is_scanning = False
        
        self.template_tl = None # Bild Oben-Links
        self.template_br = None # Bild Unten-Rechts
        self.current_area = None # (x, y, w, h)
        
        self.setup_ui()
        
        self.log("⏳ Starte System...")
        threading.Thread(target=self.load_engines, daemon=True).start()

    def setup_ui(self):
        lbl_info = tk.Label(self.root, text="F10: Ecken manuell lernen (2 Schritte)\nF9: Text vorlesen",
                           bg="#1e1e1e", fg="#cccccc", font=("Arial", 10))
        lbl_info.pack(pady=10)

        # Buttons
        btn_frame = tk.Frame(self.root, bg="#1e1e1e")
        btn_frame.pack(pady=5)
        
        self.btn_learn = tk.Button(btn_frame, text="1. Ecken lernen (F10)", 
                                   command=self.start_learning_sequence, bg="#007acc", fg="white", width=20)
        self.btn_learn.pack(side=tk.LEFT, padx=5)
        
        self.btn_read = tk.Button(btn_frame, text="2. VORLESEN (F9)", 
                                  command=self.scan_once, state=tk.DISABLED, bg="#28a745", fg="white", width=20)
        self.btn_read.pack(side=tk.LEFT, padx=5)

        # Audio Control
        ctrl_frame = tk.Frame(self.root, bg="#1e1e1e")
        ctrl_frame.pack(pady=10)
        self.btn_stop_audio = tk.Button(ctrl_frame, text="⏹ Audio Stopp", 
                                        command=self.stop_audio, bg="#dc3545", fg="white", font=("Arial", 9, "bold"))
        self.btn_stop_audio.pack(side=tk.LEFT, padx=5)

        # Log
        self.log_box = tk.Text(self.root, height=15, bg="black", fg="#00ff00", font=("Consolas", 9), insertbackground="white")
        self.log_box.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Status
        self.lbl_target = tk.Label(self.root, text="Ziel: -", bg="#333", fg="yellow", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.lbl_target.pack(side=tk.BOTTOM, fill=tk.X)

    def log(self, text):
        self.log_box.insert(tk.END, f">> {text}\n")
        self.log_box.see(tk.END)

    def load_engines(self):
        try:
            self.log("... Lade NPC Datenbank ...")
            self.npc_manager = NpcManager()
            self.log("... Lade OCR ...")
            self.reader = easyocr.Reader(['de', 'en'], gpu=True)
            self.log("... Lade Audio Engine ...")
            self.audio = AudioEngine()
            
            keyboard.add_hotkey('f9', self.scan_once)
            keyboard.add_hotkey('f10', self.start_learning_sequence)
            
            self.log("✅ SYSTEM BEREIT!")
            self.load_cached_templates()

        except Exception as e:
            self.log(f"❌ Fehler: {e}")

    # --- SAVE / LOAD TEMPLATES ---
    def save_templates(self):
        if self.template_tl is not None and self.template_br is not None:
            cv2.imwrite(os.path.join(self.cache_dir, "last_tl.png"), self.template_tl)
            cv2.imwrite(os.path.join(self.cache_dir, "last_br.png"), self.template_br)
            self.log("💾 Ecken gespeichert.")

    def load_cached_templates(self):
        p_tl = os.path.join(self.cache_dir, "last_tl.png")
        p_br = os.path.join(self.cache_dir, "last_br.png")
        
        if os.path.exists(p_tl) and os.path.exists(p_br):
            self.log("📂 Alte Ecken gefunden. Suche Fenster...")
            try:
                self.template_tl = cv2.imread(p_tl)
                self.template_br = cv2.imread(p_br)
                found = self.scan_for_window()
                if found:
                    self.current_area = found
                    self.btn_read.config(state=tk.NORMAL)
                    self.highlight_area(*found, "blue")
                    self.log(f"✅ Fenster wiedergefunden!")
                else:
                    self.log("⚠️ Altes Fenster nicht gefunden. (F10 drücken)")
            except Exception as e:
                self.log(f"Ladefehler: {e}")

    # --- NEUER LERN-PROZESS (2 SCHRITTE) ---
    def start_learning_sequence(self):
        self.log("SCHRITT 1: Markiere die Ecke OBEN-LINKS")
        messagebox.showinfo("Schritt 1", "Ziehe jetzt einen Rahmen um die Ecke OBEN-LINKS.")
        self.root.iconify()
        SnippingTool(self.root, self._step1_finished)

    def _step1_finished(self, x, y, w, h):
        time.sleep(0.3)
        shot = pyautogui.screenshot(region=(x, y, w, h))
        self.template_tl = cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2BGR)
        
        self.log("✅ Oben-Links gelernt.")
        self.root.deiconify()
        self.root.after(500, self.start_step2)

    def start_step2(self):
        self.log("SCHRITT 2: Markiere die Ecke UNTEN-RECHTS")
        messagebox.showinfo("Schritt 2", "Ziehe jetzt einen Rahmen um die Ecke UNTEN-RECHTS.")
        self.root.iconify()
        SnippingTool(self.root, self._step2_finished)

    def _step2_finished(self, x, y, w, h):
        self.root.deiconify()
        time.sleep(0.3)
        shot = pyautogui.screenshot(region=(x, y, w, h))
        self.template_br = cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2BGR)
        
        self.log("✅ Unten-Rechts gelernt.")
        self.save_templates()
        
        found = self.scan_for_window()
        if found:
            self.current_area = found
            self.btn_read.config(state=tk.NORMAL)
            self.highlight_area(*found, "green")
            self.log("🧠 Fenster erfolgreich definiert!")
        else:
            self.log("⚠️ Fehler: Konnte Bereich zwischen den Ecken nicht berechnen.")

    # --- SUCH-LOGIK ---
    def scan_for_window(self):
        if self.template_tl is None or self.template_br is None: return None
        try:
            screen = np.array(pyautogui.screenshot())
            screen = cv2.cvtColor(screen, cv2.COLOR_RGB2BGR)

            # Suche TL
            res_tl = cv2.matchTemplate(screen, self.template_tl, cv2.TM_CCOEFF_NORMED)
            _, val_tl, _, loc_tl = cv2.minMaxLoc(res_tl)
            
            # Suche BR
            res_br = cv2.matchTemplate(screen, self.template_br, cv2.TM_CCOEFF_NORMED)
            _, val_br, _, loc_br = cv2.minMaxLoc(res_br)

            if val_tl < 0.8 or val_br < 0.8: return None

            # Bereich berechnen
            x_start = loc_tl[0]
            y_start = loc_tl[1]
            
            h_br, w_br, _ = self.template_br.shape
            x_end = loc_br[0] + w_br
            y_end = loc_br[1] + h_br
            
            w = x_end - x_start
            h = y_end - y_start
            
            if w < 10 or h < 10: return None
            
            return (x_start, y_start, w, h)
        except: return None

    # --- LESEN ---
    def scan_once(self):
        if self.is_scanning: return
        if not self.current_area:
            self.log("⚠️ Kein Bereich gelernt. F10 drücken.")
            return

        self.is_scanning = True
        threading.Thread(target=self._run_scan, daemon=True).start()

    def _run_scan(self):
        try:
            # 1. Update NPC
            self.npc_manager.update()
            target = self.npc_manager.current_target
            voice_path = self.npc_manager.get_voice_path()
            v_name = os.path.basename(voice_path) if voice_path else "Standard"
            
            self.root.after(0, lambda: self.lbl_target.config(text=f"Ziel: {target} | Stimme: {v_name}"))

            # 2. Screenshot
            x, y, w, h = self.current_area
            screenshot = pyautogui.screenshot(region=(x, y, w, h))
            
            ts = datetime.datetime.now().strftime("%H%M%S")
            screenshot.save(os.path.join(self.debug_dir, f"scan_{ts}.png"))
            
            # 3. OCR (Textlesen)
            image_np = np.array(screenshot)
            results = self.reader.readtext(image_np, detail=0)
            
            # HIER WAR DER FEHLER - JETZT KORRIGIERT:
            full_text = " ".join(results).strip()
            
            # 4. Sprechen
            if full_text and len(full_text) > 5:
                self.log(f"📖 {full_text[:60]}...")
                if voice_path:
                    # Hier wird der Text jetzt an die neue "Split"-Funktion übergeben
                    self.audio.speak(full_text, voice_path)
                else:
                    self.log("⚠️ Keine Stimme gefunden.")
            else:
                self.log("... (Kein Text/Zu kurz)")

        except Exception as e:
            self.log(f"Scan Fehler: {e}")
        finally:
            self.is_scanning = False

    def stop_audio(self):
        self.audio.stop()
        self.log("🔇 Abgebrochen.")

    def highlight_area(self, x, y, w, h, color="red"):
        try:
            top = tk.Toplevel(self.root)
            top.geometry(f"{w}x{h}+{x}+{y}")
            top.overrideredirect(True)
            top.attributes("-topmost", True)
            top.attributes("-alpha", 0.3)
            top.configure(bg=color)
            top.after(1000, top.destroy)
        except: pass

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
