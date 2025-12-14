import sys
import os
import cv2
import numpy as np
import datetime

# Pfad-Fix
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
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
        self.root.title("LQAG - Vorleser")
        self.root.geometry("600x550")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#1e1e1e")
        
        # --- ORDNER PFADE ---
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.root_dir = os.path.dirname(self.base_dir)
        
        # Cache Ordner für das Gedächtnis (Templates)
        self.cache_dir = os.path.join(self.root_dir, "resources", "cache")
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

        # Debug Ordner (Optional)
        self.debug_dir = os.path.join(self.root_dir, "debug")
        if not os.path.exists(self.debug_dir):
            os.makedirs(self.debug_dir)
        
        # --- ZUSTAND ---
        self.is_scanning = False
        
        self.template_tl = None
        self.template_br = None
        self.current_area = None # (x, y, w, h)
        
        self.setup_ui()
        
        self.log("⏳ Starte System...")
        threading.Thread(target=self.load_engines, daemon=True).start()

    def setup_ui(self):
        # Info Text
        lbl_info = tk.Label(self.root, text="F10: Bereich lernen (wird gespeichert)\nF9: Text vorlesen (Manuell)",
                           bg="#1e1e1e", fg="#cccccc", font=("Arial", 10))
        lbl_info.pack(pady=10)

        # Buttons
        btn_frame = tk.Frame(self.root, bg="#1e1e1e")
        btn_frame.pack(pady=5)
        
        self.btn_learn = tk.Button(btn_frame, text="1. Einlernen (F10)", 
                                   command=self.learn_window_pattern, bg="#007acc", fg="white", width=20)
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

        # Log Box
        self.log_box = tk.Text(self.root, height=15, bg="black", fg="#00ff00", font=("Consolas", 9), insertbackground="white")
        self.log_box.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Status Leiste
        self.lbl_target = tk.Label(self.root, text="Ziel: -", bg="#333", fg="yellow", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.lbl_target.pack(side=tk.BOTTOM, fill=tk.X)

    def log(self, text):
        self.log_box.insert(tk.END, f">> {text}\n")
        self.log_box.see(tk.END)

    def load_engines(self):
        try:
            self.log("... Lade NPC Datenbank & Stimmen ...")
            self.npc_manager = NpcManager()
            
            self.log("... Lade Texterkennung ...")
            self.reader = easyocr.Reader(['de', 'en'], gpu=True)
            
            self.log("... Lade Audio Engine ...")
            self.audio = AudioEngine()
            
            # Hotkeys
            keyboard.add_hotkey('f9', self.scan_once)
            keyboard.add_hotkey('f10', self.learn_window_pattern)
            
            self.log("✅ SYSTEM BEREIT!")
            
            # --- GEDÄCHTNIS LADEN ---
            # Wir versuchen, die alten Templates zu laden
            self.load_cached_templates()

        except Exception as e:
            self.log(f"❌ Fehler: {e}")

    # --- SPEICHERN & LADEN (Das Gedächtnis) ---
    
    def save_templates(self):
        """Speichert die gelernten Bilder auf die Festplatte"""
        if self.template_tl is not None and self.template_br is not None:
            path_tl = os.path.join(self.cache_dir, "last_tl.png")
            path_br = os.path.join(self.cache_dir, "last_br.png")
            
            cv2.imwrite(path_tl, self.template_tl)
            cv2.imwrite(path_br, self.template_br)
            self.log("💾 Fenstermuster gespeichert.")

    def load_cached_templates(self):
        """Lädt Bilder vom letzten Mal und sucht das Fenster"""
        path_tl = os.path.join(self.cache_dir, "last_tl.png")
        path_br = os.path.join(self.cache_dir, "last_br.png")
        
        if os.path.exists(path_tl) and os.path.exists(path_br):
            self.log("📂 Altes Fenstermuster gefunden...")
            try:
                self.template_tl = cv2.imread(path_tl)
                self.template_br = cv2.imread(path_br)
                
                # Sofort suchen!
                self.log("🔍 Suche Fensterposition...")
                found = self.scan_for_window()
                if found:
                    self.current_area = found
                    self.btn_read.config(state=tk.NORMAL)
                    self.highlight_area(*found, "blue")
                    self.log(f"✅ Fenster wiedergefunden! (Bereit für F9)")
                else:
                    self.log("⚠️ Altes Fenster nicht gefunden. Bitte neu einlernen (F10).")
            except Exception as e:
                self.log(f"Fehler beim Laden: {e}")

    # --- LERNEN ---
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
                self.log("❌ Bereich zu klein!")
                return

            self.template_tl = img[0:size, 0:size]
            self.template_br = img[h_img-size:h_img, w_img-size:w_img]
            self.current_area = (x, y, w, h)
            
            # SOFORT SPEICHERN
            self.save_templates()
            
            self.btn_read.config(state=tk.NORMAL)
            self.highlight_area(x, y, w, h, "green")
            self.log("🧠 Gelernt & Gespeichert!")

        except Exception as e:
            self.log(f"Fehler: {e}")

    # --- SUCHEN ---
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
            
            w = br_x - new_x
            h = br_y - new_y
            
            return (new_x, new_y, w, h)
        except: return None

    # --- LESEN (Nur Manuell) ---
    def scan_once(self):
        if self.is_scanning: return
        
        # Falls wir noch keinen Bereich haben (z.B. nach Neustart und erfolgloser Suche)
        if not self.current_area:
            self.log("⚠️ Ich weiß nicht wo das Fenster ist. Bitte F10 drücken.")
            return

        self.is_scanning = True
        threading.Thread(target=self._run_scan, daemon=True).start()

    def _run_scan(self):
        try:
            # 1. Update NPC (Daten vom Spiel lesen)
            self.npc_manager.update()
            target = self.npc_manager.current_target
            voice_path = self.npc_manager.get_voice_path()
            voice_name = os.path.basename(voice_path) if voice_path else "Standard"
            
            # GUI Update im Main Thread
            self.root.after(0, lambda: self.lbl_target.config(text=f"Ziel: {target} | Stimme: {voice_name}"))

            # 2. Screenshot machen
            x, y, w, h = self.current_area
            
            # Kleiner Trick: Wir prüfen kurz, ob das Fenster noch da ist, 
            # indem wir schauen ob die Ecke oben links noch passt.
            # (Optional, aber sicher)
            
            screenshot = pyautogui.screenshot(region=(x, y, w, h))
            
            # DEBUG SPEICHERN
            ts = datetime.datetime.now().strftime("%H%M%S")
            screenshot.save(os.path.join(self.debug_dir, f"scan_{ts}.png"))
            
            # OCR
            image_np = np.array(screenshot)
            results = self.reader.readtext(image_np, detail=0)
            full_text = " ".join(results).strip()
            
            # LOG SPEICHERN
            with open(os.path.join(self.debug_dir, "history.txt"), "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {target}: {full_text}\n")

            if full_text and len(full_text) > 5:
                self.log(f"📖 {full_text[:50]}...")
                if voice_path:
                    self.audio.speak(full_text, voice_path)
                else:
                    self.log("⚠️ Keine Stimme vorhanden.")
            else:
                self.log("... (Kein Text erkannt)")

        except Exception as e:
            self.log(f"Scan Fehler: {e}")
        finally:
            self.is_scanning = False

    def stop_audio(self):
        self.audio.stop()
        self.log("🔇 Stopp.")

    def highlight_area(self, x, y, w, h, color="red"):
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
