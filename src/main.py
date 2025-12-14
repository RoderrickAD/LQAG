import sys
import os
import cv2
import numpy as np
import datetime
import threading
import time

# Pfad-Fix
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from tkinter import messagebox, ttk
import easyocr
import pyautogui
import keyboard
from audio_engine import AudioEngine
from screen_tool import SnippingTool
from npc_manager import NpcManager

# --- LOGGER KLASSE (Leitet Konsole in Datei um) ---
class Logger(object):
    def __init__(self, filename="debug/system.log"):
        self.terminal = sys.stdout
        self.log = open(filename, "a", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message) # Weiterhin in Konsole (falls offen)
        self.log.write(message)
        self.log.flush()

    def flush(self):
        self.terminal.flush()
        self.log.flush()

# --- HAUPT APP ---
class App:
    def __init__(self):
        # 1. Logger aktivieren
        if not os.path.exists("debug"): os.makedirs("debug")
        sys.stdout = Logger()
        sys.stderr = sys.stdout
        print(f"=== NEUER START: {datetime.datetime.now()} ===")

        # 2. Splash Screen erstellen (Ladebildschirm)
        self.splash = tk.Tk()
        self.splash.overrideredirect(True) # Kein Fensterrahmen
        # Zentrieren
        w, h = 400, 150
        ws = self.splash.winfo_screenwidth()
        hs = self.splash.winfo_screenheight()
        x = (ws/2) - (w/2)
        y = (hs/2) - (h/2)
        self.splash.geometry('%dx%d+%d+%d' % (w, h, x, y))
        self.splash.configure(bg="#222")
        
        lbl = tk.Label(self.splash, text="LQAG Vorleser", bg="#222", fg="#007acc", font=("Arial", 20, "bold"))
        lbl.pack(pady=20)
        
        self.lbl_loading = tk.Label(self.splash, text="Lade KI-Modelle... (Das dauert kurz)", bg="#222", fg="white")
        self.lbl_loading.pack()
        
        # Ladebalken (Indeterminate)
        self.progress_splash = ttk.Progressbar(self.splash, mode='indeterminate')
        self.progress_splash.pack(fill=tk.X, padx=20, pady=20)
        self.progress_splash.start(10)

        # 3. Engines im Hintergrund laden
        threading.Thread(target=self.load_engines, daemon=True).start()
        
        # Splash Loop starten
        self.splash.mainloop()

    def load_engines(self):
        """Lädt alles Schwere im Hintergrund"""
        try:
            self.base_dir = os.path.dirname(os.path.abspath(__file__))
            self.root_dir = os.path.dirname(self.base_dir)
            self.cache_dir = os.path.join(self.root_dir, "resources", "cache")
            self.debug_dir = os.path.join(self.root_dir, "debug")
            if not os.path.exists(self.cache_dir): os.makedirs(self.cache_dir)

            self.npc_manager = NpcManager()
            self.reader = easyocr.Reader(['de', 'en'], gpu=True)
            self.audio = AudioEngine()
            
            # Wenn fertig, Splash schließen und Main UI öffnen
            self.splash.after(0, self.start_main_ui)
            
        except Exception as e:
            print(f"CRASH BEIM LADEN: {e}")
            self.splash.destroy()

    def start_main_ui(self):
        """Baut das Hauptfenster auf, nachdem geladen wurde"""
        self.splash.destroy()
        
        self.root = tk.Tk()
        self.root.title("LQAG - Vorleser")
        self.root.geometry("600x600")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#1e1e1e")
        
        # UI Aufbau
        self.setup_ui()
        
        # Hotkeys
        keyboard.add_hotkey('f9', self.scan_once)
        keyboard.add_hotkey('f10', self.start_learning_sequence)
        
        # Cache laden
        self.template_tl = None
        self.template_br = None
        self.current_area = None
        self.is_scanning = False
        
        self.load_cached_templates()
        
        self.root.mainloop()

    def setup_ui(self):
        # Header
        lbl_info = tk.Label(self.root, text="F10: Ecken lernen | F9: Vorlesen",
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

        # Audio Stop
        ctrl_frame = tk.Frame(self.root, bg="#1e1e1e")
        ctrl_frame.pack(pady=10)
        self.btn_stop_audio = tk.Button(ctrl_frame, text="⏹ STOPP", 
                                        command=self.stop_audio, bg="#dc3545", fg="white", font=("Arial", 9, "bold"))
        self.btn_stop_audio.pack(side=tk.LEFT, padx=5)
        
        # Fortschrittsbalken (Lesefortschritt)
        self.lbl_progress = tk.Label(self.root, text="", bg="#1e1e1e", fg="white", font=("Arial", 8))
        self.lbl_progress.pack()
        
        self.progress_read = ttk.Progressbar(self.root, orient="horizontal", length=500, mode="determinate")
        self.progress_read.pack(pady=5)

        # Log Box
        self.log_box = tk.Text(self.root, height=15, bg="black", fg="#00ff00", font=("Consolas", 9), insertbackground="white")
        self.log_box.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Target Status
        self.lbl_target = tk.Label(self.root, text="Ziel: -", bg="#333", fg="yellow", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.lbl_target.pack(side=tk.BOTTOM, fill=tk.X)

    def log(self, text):
        self.log_box.insert(tk.END, f">> {text}\n")
        self.log_box.see(tk.END)
        print(text) # Schreibt auch in die Log-Datei via Logger

    # --- AUDIO CALLBACK ---
    def update_progress(self, current, total):
        """Wird von AudioEngine aufgerufen"""
        # Da dies aus einem anderen Thread kommt, nutzen wir root.after
        self.root.after(0, lambda: self._gui_update_progress(current, total))
        
    def _gui_update_progress(self, current, total):
        self.progress_read["maximum"] = total
        self.progress_read["value"] = current
        self.lbl_progress.config(text=f"Lese Satz {current} von {total}")
        if current >= total:
            self.lbl_progress.config(text="Fertig.")

    # --- IMAGE PRE-PROCESSING (Das verbessert die Erkennung!) ---
    def preprocess_image(self, img_np):
        # 1. Konvertiere zu OpenCV Format
        img = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        
        # 2. Vergrößern (Upscaling) - Faktor 2 oder 3
        # Das macht kleine Schrift "fetter" und lesbarer
        img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        
        # 3. Graustufen
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 4. Optional: Kontrast erhöhen (Threshold)
        # Wir nutzen Otsu's Binarization, das findet automatisch den besten Wert
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        return binary

    # --- SCANNING ---
    def scan_once(self):
        if self.is_scanning or not self.current_area: return
        self.is_scanning = True
        self.progress_read["value"] = 0
        threading.Thread(target=self._run_scan, daemon=True).start()

    def _run_scan(self):
        try:
            self.npc_manager.update()
            target = self.npc_manager.current_target
            voice_path = self.npc_manager.get_voice_path()
            v_name = os.path.basename(voice_path) if voice_path else "Standard"
            self.root.after(0, lambda: self.lbl_target.config(text=f"Ziel: {target} | Stimme: {v_name}"))

            x, y, w, h = self.current_area
            screenshot = pyautogui.screenshot(region=(x, y, w, h))
            img_np = np.array(screenshot)
            
            # --- NEU: Bild verbessern ---
            processed_img = self.preprocess_image(img_np)
            
            # Debug speichern (damit du siehst, was die KI sieht)
            cv2.imwrite(os.path.join(self.debug_dir, "last_scan_processed.png"), processed_img)
            
            # OCR auf verbessertem Bild
            results = self.reader.readtext(processed_img, detail=0)
            full_text = " ".join(results).strip()

            if full_text and len(full_text) > 3:
                self.log(f"📖 {full_text[:50]}...")
                if voice_path:
                    # Callback übergeben!
                    self.audio.speak(full_text, voice_path, on_progress=self.update_progress)
                else:
                    self.log("⚠️ Keine Stimme.")
            else:
                self.log("... (Nichts erkannt)")

        except Exception as e:
            self.log(f"Fehler: {e}")
        finally:
            self.is_scanning = False

    def stop_audio(self):
        self.audio.stop()
        self.progress_read["value"] = 0
        self.lbl_progress.config(text="Abgebrochen.")
        self.log("🔇 Stopp.")

    # --- LERNEN & TEMPLATES (Gleich wie vorher, nur gekürzt für Übersicht) ---
    def save_templates(self):
        if self.template_tl is not None and self.template_br is not None:
            cv2.imwrite(os.path.join(self.cache_dir, "last_tl.png"), self.template_tl)
            cv2.imwrite(os.path.join(self.cache_dir, "last_br.png"), self.template_br)
            self.log("💾 Ecken gespeichert.")

    def load_cached_templates(self):
        p_tl = os.path.join(self.cache_dir, "last_tl.png")
        p_br = os.path.join(self.cache_dir, "last_br.png")
        if os.path.exists(p_tl) and os.path.exists(p_br):
            try:
                self.template_tl = cv2.imread(p_tl)
                self.template_br = cv2.imread(p_br)
                found = self.scan_for_window()
                if found:
                    self.current_area = found
                    self.btn_read.config(state=tk.NORMAL)
                    self.highlight_area(*found, "blue")
                    self.log(f"✅ Fenster gefunden!")
            except: pass

    def start_learning_sequence(self):
        self.root.iconify()
        SnippingTool(self.root, self._step1_finished)

    def _step1_finished(self, x, y, w, h):
        time.sleep(0.3)
        shot = pyautogui.screenshot(region=(x, y, w, h))
        self.template_tl = cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2BGR)
        self.root.deiconify()
        messagebox.showinfo("Schritt 2", "Jetzt UNTEN-RECHTS markieren.")
        self.root.iconify()
        SnippingTool(self.root, self._step2_finished)

    def _step2_finished(self, x, y, w, h):
        self.root.deiconify()
        time.sleep(0.3)
        shot = pyautogui.screenshot(region=(x, y, w, h))
        self.template_br = cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2BGR)
        self.save_templates()
        found = self.scan_for_window()
        if found:
            self.current_area = found
            self.btn_read.config(state=tk.NORMAL)
            self.highlight_area(*found, "green")

    def scan_for_window(self):
        if self.template_tl is None or self.template_br is None: return None
        try:
            screen = np.array(pyautogui.screenshot())
            screen = cv2.cvtColor(screen, cv2.COLOR_RGB2BGR)
            res_tl = cv2.matchTemplate(screen, self.template_tl, cv2.TM_CCOEFF_NORMED)
            _, val_tl, _, loc_tl = cv2.minMaxLoc(res_tl)
            res_br = cv2.matchTemplate(screen, self.template_br, cv2.TM_CCOEFF_NORMED)
            _, val_br, _, loc_br = cv2.minMaxLoc(res_br)
            if val_tl < 0.8 or val_br < 0.8: return None
            h_br, w_br, _ = self.template_br.shape
            w = (loc_br[0] + w_br) - loc_tl[0]
            h = (loc_br[1] + h_br) - loc_tl[1]
            if w < 10 or h < 10: return None
            return (loc_tl[0], loc_tl[1], w, h)
        except: return None

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
    App()
