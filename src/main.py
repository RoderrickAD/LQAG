import sys
import os
import datetime
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
import ctypes # WICHTIG FÜR DPI FIX

# Pfad-Fix
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- DPI FIX (DAS LÖST DAS GRAUE KASTEN PROBLEM) ---
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except: pass

# Platzhalter
cv2 = None
np = None
easyocr = None
pyautogui = None
keyboard = None
AudioEngine = None
SnippingTool = None
NpcManager = None

class App:
    def __init__(self):
        # 1. Pfade
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.root_dir = os.path.dirname(self.base_dir)
        self.debug_dir = os.path.join(self.root_dir, "debug")
        self.cache_dir = os.path.join(self.root_dir, "resources", "cache")
        self.log_file_path = os.path.join(self.debug_dir, "system.log")
        
        if not os.path.exists(self.debug_dir): os.makedirs(self.debug_dir)
        if not os.path.exists(self.cache_dir): os.makedirs(self.cache_dir)
        
        # Log Reset
        with open(self.log_file_path, "a", encoding="utf-8") as f:
            f.write(f"\n=== PROGRAMM START (V11): {datetime.datetime.now()} ===\n")

        # 2. Splash Screen (Jetzt korrekt zentriert dank DPI Fix)
        self.splash = tk.Tk()
        self.splash.overrideredirect(True)
        
        # Monitor Größe ermitteln
        ws = self.splash.winfo_screenwidth()
        hs = self.splash.winfo_screenheight()
        
        w, h = 600, 350
        x = (ws // 2) - (w // 2)
        y = (hs // 2) - (h // 2)
        
        self.splash.geometry(f'{w}x{h}+{x}+{y}')
        self.splash.configure(bg="#1a1a1a")
        
        # UI Elemente
        lbl_title = tk.Label(self.splash, text="LQAG Vorleser", bg="#1a1a1a", fg="#007acc", font=("Segoe UI", 36, "bold"))
        lbl_title.pack(pady=(50, 20))
        
        self.lbl_loading = tk.Label(self.splash, text="Lade KI...", bg="#1a1a1a", fg="#aaaaaa", font=("Segoe UI", 14))
        self.lbl_loading.pack(pady=10)
        
        style = ttk.Style()
        style.theme_use('alt')
        style.configure("green.Horizontal.TProgressbar", background='#007acc', thickness=10)
        
        self.progress_splash = ttk.Progressbar(self.splash, style="green.Horizontal.TProgressbar", mode='indeterminate', length=400)
        self.progress_splash.pack(pady=30)
        self.progress_splash.start(10)

        threading.Thread(target=self.load_heavy_stuff, daemon=True).start()
        self.splash.mainloop()

    def log(self, text):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        msg = f"[{timestamp}] {text}"
        try:
            with open(self.log_file_path, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except: pass
        if hasattr(self, 'log_box'):
            self.log_box.insert(tk.END, f">> {text}\n")
            self.log_box.see(tk.END)
        print(msg)

    def load_heavy_stuff(self):
        try:
            global cv2, np, easyocr, pyautogui, keyboard, AudioEngine, SnippingTool, NpcManager
            
            self.lbl_loading.config(text="Lade Grafik & Tools...")
            import cv2
            import numpy as np
            import pyautogui
            import easyocr
            import keyboard
            from screen_tool import SnippingTool
            from npc_manager import NpcManager
            
            self.lbl_loading.config(text="Lade KI-Stimme...")
            from audio_engine import AudioEngine

            self.lbl_loading.config(text="Starte Engines...")
            self.npc_manager = NpcManager()
            self.reader = easyocr.Reader(['de', 'en'], gpu=True)
            self.audio = AudioEngine()
            
            self.splash.after(100, self.start_main_ui)
            
        except Exception as e:
            with open(self.log_file_path, "a") as f: f.write(f"CRASH: {e}\n")
            self.splash.after(2000, self.splash.destroy)

    def start_main_ui(self):
        try:
            self.progress_splash.stop()
            self.splash.destroy()
        except: pass
        
        self.root = tk.Tk()
        self.root.title("LQAG - Vorleser")
        self.root.geometry("900x800")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#1e1e1e")
        
        self.setup_ui()
        
        # Hotkeys registrieren
        try:
            keyboard.add_hotkey('f9', self.on_f9_pressed)
            keyboard.add_hotkey('f10', self.start_learning_sequence)
            self.log("Tastatur-Kürzel aktiv (F9/F10)")
        except Exception as e:
            self.log(f"FEHLER bei Hotkeys: {e} (Bitte als Admin starten!)")
        
        self.template_tl = None
        self.template_br = None
        self.current_area = None
        self.is_scanning = False
        
        # Cache laden
        self.root.after(500, self.load_cached_templates)
        self.root.mainloop()

    def setup_ui(self):
        font_header = ("Segoe UI", 16, "bold")
        font_btn = ("Segoe UI", 12, "bold")
        font_log = ("Consolas", 11)

        lbl_info = tk.Label(self.root, text="F10: Ecken lernen  |  F9: Vorlesen",
                           bg="#1e1e1e", fg="#cccccc", font=font_header)
        lbl_info.pack(pady=20)

        btn_frame = tk.Frame(self.root, bg="#1e1e1e")
        btn_frame.pack(pady=10)
        
        self.btn_learn = tk.Button(btn_frame, text="1. Ecken lernen (F10)", 
                                   command=self.start_learning_sequence, 
                                   bg="#007acc", fg="white", font=font_btn, width=25, height=2)
        self.btn_learn.pack(side=tk.LEFT, padx=10)
        
        self.btn_read = tk.Button(btn_frame, text="2. VORLESEN (F9)", 
                                  command=self.scan_once, state=tk.DISABLED, 
                                  bg="#28a745", fg="white", font=font_btn, width=25, height=2)
        self.btn_read.pack(side=tk.LEFT, padx=10)

        ctrl_frame = tk.Frame(self.root, bg="#1e1e1e")
        ctrl_frame.pack(pady=15)
        self.btn_stop_audio = tk.Button(ctrl_frame, text="⏹ AUDIO STOPP", 
                                        command=self.stop_audio, 
                                        bg="#dc3545", fg="white", font=font_btn, width=20)
        self.btn_stop_audio.pack(side=tk.LEFT, padx=5)
        
        self.lbl_progress = tk.Label(self.root, text="Bereit.", bg="#1e1e1e", fg="white", font=("Segoe UI", 10))
        self.lbl_progress.pack()
        self.progress_read = ttk.Progressbar(self.root, orient="horizontal", length=700, mode="determinate")
        self.progress_read.pack(pady=10)

        self.log_box = tk.Text(self.root, height=20, bg="black", fg="#00ff00", font=font_log, insertbackground="white")
        self.log_box.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.lbl_target = tk.Label(self.root, text="Ziel: -", bg="#333", fg="yellow", 
                                   font=("Segoe UI", 12), bd=1, relief=tk.SUNKEN, anchor=tk.W, padx=10, pady=5)
        self.lbl_target.pack(side=tk.BOTTOM, fill=tk.X)

    # --- LOGIK ---
    def on_f9_pressed(self):
        self.log("Taste F9 erkannt!")
        self.scan_once()

    def update_progress(self, current, total):
        self.root.after(0, lambda: self._gui_update_progress(current, total))
        
    def _gui_update_progress(self, current, total):
        self.progress_read["maximum"] = total
        self.progress_read["value"] = current
        self.lbl_progress.config(text=f"Lese Satz {current} von {total}")
        if current >= total: self.lbl_progress.config(text="Fertig.")

    def preprocess_image(self, img_np):
        # 1. BGR
        img = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        
        # 2. Upscaling (3x)
        img = cv2.resize(img, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        
        # 3. Padding (Rand hinzufügen) - FIX für abgeschnittene Buchstaben!
        # Wir fügen 20 Pixel schwarzen Rand hinzu
        img = cv2.copyMakeBorder(img, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=[0, 0, 0])
        
        # 4. Graustufen & CLAHE
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        
        # 5. Schärfen
        kernel = np.array([[0, -1, 0], [-1, 5,-1], [0, -1, 0]])
        sharpened = cv2.filter2D(enhanced, -1, kernel)
        
        return sharpened

    def scan_once(self):
        if self.is_scanning: return
        if not self.current_area:
            self.log("⚠️ Kein Bereich definiert! Bitte F10 drücken.")
            return
        
        self.is_scanning = True
        self.progress_read["value"] = 0
        self.lbl_progress.config(text="Analysiere Bild...")
        threading.Thread(target=self._run_scan, daemon=True).start()

    def _run_scan(self):
        try:
            self.npc_manager.update()
            target = self.npc_manager.current_target
            voice_path = self.npc_manager.get_voice_path()
            v_name = os.path.basename(voice_path) if voice_path else "Standard"
            self.root.after(0, lambda: self.lbl_target.config(text=f"Ziel: {target} | Stimme: {v_name}"))

            # Prüfen ob Fenster noch da ist (optionales Rescan)
            # Wir nutzen hier die gespeicherten Koordinaten
            x, y, w, h = self.current_area
            
            # Screenshot machen
            screenshot = pyautogui.screenshot(region=(x, y, w, h))
            img_np = np.array(screenshot)
            
            # Bild speichern (Original)
            cv2.imwrite(os.path.join(self.debug_dir, "last_scan_raw.png"), cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR))
            
            # Bild verbessern
            processed_img = self.preprocess_image(img_np)
            cv2.imwrite(os.path.join(self.debug_dir, "last_scan_processed.png"), processed_img)
            
            # OCR
            results = self.reader.readtext(processed_img, detail=0, paragraph=True)
            
            self.log("--- ERKANNTer TEXT ---")
            for line in results:
                self.log(f"> {line}")
            self.log("----------------------")
            
            full_text = " ".join(results).strip()

            if full_text and len(full_text) > 3:
                self.log(f"Start Sprachausgabe ({len(full_text)} Zeichen)")
                if voice_path:
                    self.audio.speak(full_text, voice_path, 
                                   save_dir=self.debug_dir, 
                                   on_progress=self.update_progress)
                else:
                    self.log("⚠️ Keine Stimme zugeordnet.")
            else:
                self.log("⚠️ Kein lesbarer Text gefunden.")

        except Exception as e:
            self.log(f"Scan Fehler: {e}")
        finally:
            self.is_scanning = False

    def stop_audio(self):
        self.audio.stop()
        self.progress_read["value"] = 0
        self.lbl_progress.config(text="Abgebrochen.")
        self.log("🔇 Wiedergabe gestoppt.")

    # --- LOAD/SAVE ---
    def save_templates(self):
        if self.template_tl is not None and self.template_br is not None:
            cv2.imwrite(os.path.join(self.cache_dir, "last_tl.png"), self.template_tl)
            cv2.imwrite(os.path.join(self.cache_dir, "last_br.png"), self.template_br)
            
            # Speichere auch die Koordinaten als Backup
            try:
                coords_file = os.path.join(self.cache_dir, "coords.txt")
                with open(coords_file, "w") as f:
                    if self.current_area:
                        f.write(f"{self.current_area[0]},{self.current_area[1]},{self.current_area[2]},{self.current_area[3]}")
            except: pass
            
            self.log("💾 Konfiguration gespeichert.")

    def load_cached_templates(self):
        p_tl = os.path.join(self.cache_dir, "last_tl.png")
        p_br = os.path.join(self.cache_dir, "last_br.png")
        p_coords = os.path.join(self.cache_dir, "coords.txt")
        
        # Versuch 1: Über Bildersuche (Genauer, falls Fenster verschoben)
        if os.path.exists(p_tl) and os.path.exists(p_br):
            try:
                self.template_tl = cv2.imread(p_tl)
                self.template_br = cv2.imread(p_br)
                self.log("🔍 Suche gespeichertes Fenster...")
                found = self.scan_for_window()
                if found:
                    self.current_area = found
                    self.btn_read.config(state=tk.NORMAL)
                    self.highlight_area(*found, "blue")
                    self.log(f"✅ Fenster gefunden! (Auto-Load)")
                    return
            except: pass
            
        # Versuch 2: Über Koordinaten (Fallback, falls Bildersuche scheitert)
        if os.path.exists(p_coords):
            try:
                with open(p_coords, "r") as f:
                    data = f.read().strip().split(",")
                    self.current_area = (int(data[0]), int(data[1]), int(data[2]), int(data[3]))
                    self.btn_read.config(state=tk.NORMAL)
                    self.highlight_area(*self.current_area, "yellow")
                    self.log("⚠️ Bild nicht gefunden, nutze alte Position.")
            except: pass

    # --- LERNEN ---
    def start_learning_sequence(self):
        self.root.withdraw()
        # Warte kurz, damit UI weg ist
        time.sleep(0.2)
        SnippingTool(self.root, self._step1_finished)

    def _step1_finished(self, x, y, w, h):
        time.sleep(0.5) # Warten auf Overlay weg
        shot = pyautogui.screenshot(region=(x, y, w, h))
        self.template_tl = cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2BGR)
        
        self.root.deiconify()
        messagebox.showinfo("Schritt 2", "Jetzt UNTEN-RECHTS markieren.")
        self.root.withdraw()
        time.sleep(0.2)
        SnippingTool(self.root, self._step2_finished)

    def _step2_finished(self, x, y, w, h):
        time.sleep(0.5)
        shot = pyautogui.screenshot(region=(x, y, w, h))
        self.template_br = cv2.cvtColor(np.array(shot), cv2.COLOR_RGB2BGR)
        
        self.root.deiconify()
        self.save_templates()
        
        found = self.scan_for_window()
        if found:
            self.current_area = found
            self.btn_read.config(state=tk.NORMAL)
            self.highlight_area(*found, "green")
            self.log("🧠 Bereich erfolgreich gelernt!")
        else:
            self.log("⚠️ Fehler: Ecken bilden kein gültiges Rechteck.")

    def scan_for_window(self):
        if self.template_tl is None or self.template_br is None: return None
        try:
            screen = np.array(pyautogui.screenshot())
            screen = cv2.cvtColor(screen, cv2.COLOR_RGB2BGR)
            
            res_tl = cv2.matchTemplate(screen, self.template_tl, cv2.TM_CCOEFF_NORMED)
            _, val_tl, _, loc_tl = cv2.minMaxLoc(res_tl)
            
            res_br = cv2.matchTemplate(screen, self.template_br, cv2.TM_CCOEFF_NORMED)
            _, val_br, _, loc_br = cv2.minMaxLoc(res_br)
            
            if val_tl < 0.7 or val_br < 0.7: return None # Toleranz etwas erhöht

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
