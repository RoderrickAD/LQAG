import sys
import os
import datetime
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
import ctypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
SubtitleOverlay = None # <-- NEU

class App:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.root_dir = os.path.dirname(self.base_dir)
        self.debug_dir = os.path.join(self.root_dir, "debug")
        self.cache_dir = os.path.join(self.root_dir, "resources", "cache")
        self.log_file_path = os.path.join(self.debug_dir, "system.log")
        
        if not os.path.exists(self.debug_dir): os.makedirs(self.debug_dir)
        if not os.path.exists(self.cache_dir): os.makedirs(self.cache_dir)
        
        with open(self.log_file_path, "a", encoding="utf-8") as f:
            f.write(f"\n=== START V16: {datetime.datetime.now()} ===\n")

        self.splash = tk.Tk()
        self.splash.overrideredirect(True)
        w, h = 600, 350
        ws = self.splash.winfo_screenwidth()
        hs = self.splash.winfo_screenheight()
        x = (ws // 2) - (w // 2)
        y = (hs // 2) - (h // 2)
        self.splash.geometry(f'{w}x{h}+{x}+{y}')
        self.splash.configure(bg="#1a1a1a")
        
        tk.Label(self.splash, text="LQAG Vorleser", bg="#1a1a1a", fg="#007acc", font=("Segoe UI", 36, "bold")).pack(pady=(50, 20))
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
        try:
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            msg = f"[{timestamp}] {text}"
            with open(self.log_file_path, "a", encoding="utf-8") as f: f.write(msg + "\n")
            if hasattr(self, 'log_box'):
                self.log_box.insert(tk.END, f">> {text}\n")
                self.log_box.see(tk.END)
            print(msg)
        except: pass

    def load_heavy_stuff(self):
        try:
            global cv2, np, easyocr, pyautogui, keyboard, AudioEngine, SnippingTool, NpcManager, SubtitleOverlay
            
            self.lbl_loading.config(text="Lade Grafik & Tools...")
            import cv2
            import numpy as np
            import pyautogui
            import easyocr
            import keyboard
            from screen_tool import SnippingTool
            from npc_manager import NpcManager
            from overlay import SubtitleOverlay # <-- NEU
            
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
        self.root.geometry("900x850") # Etwas höher für neue Controls
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#1e1e1e")
        
        # Overlay initialisieren
        self.overlay = SubtitleOverlay(self.root)
        
        self.setup_ui()
        
        try:
            keyboard.add_hotkey('f9', self.on_f9_pressed)
            keyboard.add_hotkey('f10', self.start_learning_sequence)
            self.log("Tastatur-Kürzel aktiv (F9/F10)")
        except Exception as e:
            self.log(f"FEHLER Hotkeys: {e}")
        
        self.template_tl = None
        self.template_br = None
        self.current_area = None
        self.is_scanning = False
        
        self.root.after(500, self.load_cached_templates)
        self.root.mainloop()

    def setup_ui(self):
        font_header = ("Segoe UI", 16, "bold")
        font_btn = ("Segoe UI", 12, "bold")
        font_log = ("Consolas", 11)

        lbl_info = tk.Label(self.root, text="F10: Ecken lernen  |  F9: Suchen & Vorlesen",
                           bg="#1e1e1e", fg="#cccccc", font=font_header)
        lbl_info.pack(pady=15)

        # Buttons
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

        # --- CONTROLS (Volume & Overlay) ---
        ctrl_frame = tk.Frame(self.root, bg="#1e1e1e")
        ctrl_frame.pack(pady=10)

        # Volume Slider
        lbl_vol = tk.Label(ctrl_frame, text="Lautstärke:", bg="#1e1e1e", fg="white", font=("Segoe UI", 11))
        lbl_vol.pack(side=tk.LEFT, padx=5)
        
        self.scale_vol = tk.Scale(ctrl_frame, from_=0, to=100, orient=tk.HORIZONTAL, 
                                  bg="#1e1e1e", fg="white", highlightthickness=0, 
                                  command=self.update_volume)
        self.scale_vol.set(100) # Standard 100%
        self.scale_vol.pack(side=tk.LEFT, padx=5)

        # Overlay Checkbox
        self.chk_overlay_var = tk.BooleanVar(value=False)
        self.chk_overlay = tk.Checkbutton(ctrl_frame, text="Overlay anzeigen", variable=self.chk_overlay_var,
                                          bg="#1e1e1e", fg="white", selectcolor="#333", font=("Segoe UI", 11),
                                          command=self.toggle_overlay)
        self.chk_overlay.pack(side=tk.LEFT, padx=20)

        # Stop Button
        self.btn_stop_audio = tk.Button(ctrl_frame, text="STOPP", 
                                        command=self.stop_audio, 
                                        bg="#dc3545", fg="white", font=("Segoe UI", 10, "bold"), width=10)
        self.btn_stop_audio.pack(side=tk.LEFT, padx=5)
        
        # Progress
        self.lbl_progress = tk.Label(self.root, text="Bereit.", bg="#1e1e1e", fg="white", font=("Segoe UI", 10))
        self.lbl_progress.pack()
        self.progress_read = ttk.Progressbar(self.root, orient="horizontal", length=700, mode="determinate")
        self.progress_read.pack(pady=10)

        # Log
        self.log_box = tk.Text(self.root, height=20, bg="black", fg="#00ff00", font=font_log, insertbackground="white")
        self.log_box.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.lbl_target = tk.Label(self.root, text="Ziel: -", bg="#333", fg="yellow", 
                                   font=("Segoe UI", 12), bd=1, relief=tk.SUNKEN, anchor=tk.W, padx=10, pady=5)
        self.lbl_target.pack(side=tk.BOTTOM, fill=tk.X)

    # --- NEUE FUNKTIONEN ---
    def update_volume(self, val):
        if self.audio:
            self.audio.set_volume(val)

    def toggle_overlay(self):
        if self.chk_overlay_var.get():
            self.overlay.show()
            self.log("Overlay aktiviert.")
        else:
            self.overlay.hide()
            self.log("Overlay deaktiviert.")

    # --- BESTEHENDE LOGIK ---
    def on_f9_pressed(self):
        self.scan_once()

    def update_progress(self, current, total):
        self.root.after(0, lambda: self._gui_update_progress(current, total))
        
    def _gui_update_progress(self, current, total):
        self.progress_read["maximum"] = total
        self.progress_read["value"] = current
        self.lbl_progress.config(text=f"Lese Satz {current} von {total}")
        if current >= total: self.lbl_progress.config(text="Fertig.")

    def preprocess_image(self, img_np):
        img = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        img = cv2.resize(img, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        # Rand
        img = cv2.copyMakeBorder(img, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=[0, 0, 0])
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Anti-Ghosting
        _, img = cv2.threshold(img, 90, 255, cv2.THRESH_TOZERO)
        
        # Neu: Ganz leichtes Blur, hilft gegen Rauschen bei scharfen Fonts
        img = cv2.GaussianBlur(img, (3, 3), 0)
        
        return img

    def scan_once(self):
        if self.is_scanning: return
        if self.template_tl is None:
            self.log("⚠️ Bitte F10 drücken.")
            return
        
        self.is_scanning = True
        self.progress_read["value"] = 0
        self.lbl_progress.config(text="Suche...")
        threading.Thread(target=self._run_scan, daemon=True).start()

    def _run_scan(self):
        try:
            self.npc_manager.update()
            target = self.npc_manager.current_target
            voice_path = self.npc_manager.get_voice_path()
            v_name = os.path.basename(voice_path) if voice_path else "Standard"
            self.root.after(0, lambda: self.lbl_target.config(text=f"Ziel: {target} | Stimme: {v_name}"))

            found_area = self.scan_for_window()
            
            if found_area:
                self.current_area = found_area
                self.log(f"🔍 Fenster gefunden bei: {found_area}")
                self.highlight_area(*found_area, "green")
            else:
                self.log("❌ Fenster optisch nicht gefunden.")
                self.is_scanning = False
                return

            x, y, w, h = self.current_area
            screenshot = pyautogui.screenshot(region=(x, y, w, h))
            img_np = np.array(screenshot)
            
            cv2.imwrite(os.path.join(self.debug_dir, "last_scan_raw.png"), cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR))
            
            processed_img = self.preprocess_image(img_np)
            cv2.imwrite(os.path.join(self.debug_dir, "last_scan_processed.png"), processed_img)
            
            results = self.reader.readtext(processed_img, detail=0, paragraph=True)
            
            self.log("--- TEXT ---")
            for line in results: self.log(f"> {line}")
            self.log("------------")
            
            full_text = " ".join(results).strip()

            if full_text and len(full_text) > 3:
                self.log(f"📖 Text erkannt ({len(full_text)} Zeichen)")
                
                # --- OVERLAY UPDATE ---
                if self.chk_overlay_var.get():
                    self.root.after(0, lambda: self.overlay.update_text(target, full_text))
                
                if voice_path:
                    self.audio.speak(full_text, voice_path, 
                                   save_dir=self.debug_dir, 
                                   on_progress=self.update_progress)
                else:
                    self.log("⚠️ Keine Stimme.")
            else:
                self.log("⚠️ Kein Text erkannt.")

        except Exception as e:
            self.log(f"Scan Fehler: {e}")
        finally:
            self.is_scanning = False

    def stop_audio(self):
        self.audio.stop()
        self.progress_read["value"] = 0
        self.lbl_progress.config(text="Abgebrochen.")
        self.log("🔇 Gestoppt.")

    def save_templates(self):
        if self.template_tl is not None and self.template_br is not None:
            cv2.imwrite(os.path.join(self.cache_dir, "last_tl.png"), self.template_tl)
            cv2.imwrite(os.path.join(self.cache_dir, "last_br.png"), self.template_br)
            self.log("💾 Templates gespeichert.")

    def load_cached_templates(self):
        p_tl = os.path.join(self.cache_dir, "last_tl.png")
        p_br = os.path.join(self.cache_dir, "last_br.png")
        if os.path.exists(p_tl) and os.path.exists(p_br):
            try:
                self.template_tl = cv2.imread(p_tl)
                self.template_br = cv2.imread(p_br)
                self.btn_read.config(state=tk.NORMAL)
                self.log("✅ Templates geladen.")
            except: 
                self.log("⚠️ Fehler beim Laden.")
        else:
            self.log("ℹ️ Keine Templates. F10 drücken.")

    def start_learning_sequence(self):
        self.root.withdraw()
        time.sleep(0.2)
        SnippingTool(self.root, self._step1_finished)

    def _step1_finished(self, x, y, w, h):
        time.sleep(0.5)
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
            self.log("🧠 Bereich gelernt!")
        else:
            self.log("⚠️ Fehler: Ecken nicht gefunden.")

    def scan_for_window(self):
        if self.template_tl is None or self.template_br is None: return None
        try:
            screen = np.array(pyautogui.screenshot())
            screen = cv2.cvtColor(screen, cv2.COLOR_RGB2BGR)
            res_tl = cv2.matchTemplate(screen, self.template_tl, cv2.TM_CCOEFF_NORMED)
            _, val_tl, _, loc_tl = cv2.minMaxLoc(res_tl)
            res_br = cv2.matchTemplate(screen, self.template_br, cv2.TM_CCOEFF_NORMED)
            _, val_br, _, loc_br = cv2.minMaxLoc(res_br)
            if val_tl < 0.7 or val_br < 0.7: return None
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
