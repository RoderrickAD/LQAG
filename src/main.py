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
SubtitleOverlay = None
SettingsManager = None # <-- NEU

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
            f.write(f"\n=== START V17 (Settings): {datetime.datetime.now()} ===\n")

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
        self.lbl_loading = tk.Label(self.splash, text="Lade System...", bg="#1a1a1a", fg="#aaaaaa", font=("Segoe UI", 14))
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
            global cv2, np, easyocr, pyautogui, keyboard, AudioEngine, SnippingTool, NpcManager, SubtitleOverlay, SettingsManager
            
            self.lbl_loading.config(text="Lade Grafik & Tools...")
            import cv2
            import numpy as np
            import pyautogui
            import easyocr
            import keyboard
            from screen_tool import SnippingTool
            from npc_manager import NpcManager
            from overlay import SubtitleOverlay
            from settings_manager import SettingsManager # <-- NEU
            
            self.lbl_loading.config(text="Lade KI-Stimme...")
            from audio_engine import AudioEngine

            self.lbl_loading.config(text="Initialisiere...")
            self.npc_manager = NpcManager()
            self.reader = easyocr.Reader(['de', 'en'], gpu=True)
            self.audio = AudioEngine()
            self.settings_mgr = SettingsManager(self.root_dir) # Settings laden
            
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
        self.root.geometry("900x880")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#1e1e1e")
        
        self.overlay = SubtitleOverlay(self.root)
        self.setup_ui()
        self.register_hotkeys() # Hotkeys anwenden
        
        self.template_tl = None
        self.template_br = None
        self.current_area = None
        self.is_scanning = False
        
        self.root.after(500, self.load_cached_templates)
        self.root.mainloop()

    def register_hotkeys(self):
        """Liest Settings und registriert Hotkeys"""
        try:
            keyboard.unhook_all_hotkeys()
            
            hk_read = self.settings_mgr.get("hotkey_read")
            hk_learn = self.settings_mgr.get("hotkey_learn")
            hk_stop = self.settings_mgr.get("hotkey_stop")
            hk_pause = self.settings_mgr.get("hotkey_pause")
            
            keyboard.add_hotkey(hk_read, self.scan_once)
            keyboard.add_hotkey(hk_learn, self.start_learning_sequence)
            keyboard.add_hotkey(hk_stop, self.stop_audio)
            keyboard.add_hotkey(hk_pause, self.toggle_pause)
            
            self.log(f"Hotkeys aktiv: Lesen={hk_read}, Lernen={hk_learn}, Stop={hk_stop}, Pause={hk_pause}")
            
            # Button Labels updaten
            self.btn_learn.config(text=f"1. Ecken lernen ({hk_learn})")
            self.btn_read.config(text=f"2. VORLESEN ({hk_read})")
            
        except Exception as e:
            self.log(f"Fehler bei Hotkeys: {e}")

    def setup_ui(self):
        font_header = ("Segoe UI", 16, "bold")
        font_btn = ("Segoe UI", 12, "bold")
        
        # Oben: Settings Button
        top_bar = tk.Frame(self.root, bg="#1e1e1e")
        top_bar.pack(fill=tk.X, padx=10, pady=5)
        
        btn_settings = tk.Button(top_bar, text="⚙ Tastenbelegung", command=self.open_settings_window,
                                 bg="#444", fg="white", font=("Segoe UI", 9))
        btn_settings.pack(side=tk.RIGHT)

        lbl_info = tk.Label(self.root, text="LQAG Steuerung",
                           bg="#1e1e1e", fg="#cccccc", font=font_header)
        lbl_info.pack(pady=10)

        # Main Buttons
        btn_frame = tk.Frame(self.root, bg="#1e1e1e")
        btn_frame.pack(pady=10)
        
        self.btn_learn = tk.Button(btn_frame, text="1. Ecken lernen", 
                                   command=self.start_learning_sequence, 
                                   bg="#007acc", fg="white", font=font_btn, width=25, height=2)
        self.btn_learn.pack(side=tk.LEFT, padx=10)
        
        self.btn_read = tk.Button(btn_frame, text="2. VORLESEN", 
                                  command=self.scan_once, state=tk.DISABLED, 
                                  bg="#28a745", fg="white", font=font_btn, width=25, height=2)
        self.btn_read.pack(side=tk.LEFT, padx=10)

        # Audio Controls
        ctrl_frame = tk.Frame(self.root, bg="#1e1e1e")
        ctrl_frame.pack(pady=10)
        
        tk.Label(ctrl_frame, text="Vol:", bg="#1e1e1e", fg="white").pack(side=tk.LEFT)
        self.scale_vol = tk.Scale(ctrl_frame, from_=0, to=100, orient=tk.HORIZONTAL, 
                                  bg="#1e1e1e", fg="white", command=self.update_volume)
        self.scale_vol.set(100)
        self.scale_vol.pack(side=tk.LEFT, padx=5)

        self.chk_overlay_var = tk.BooleanVar(value=False)
        self.chk_overlay = tk.Checkbutton(ctrl_frame, text="Overlay", variable=self.chk_overlay_var,
                                          bg="#1e1e1e", fg="white", selectcolor="#333",
                                          command=self.toggle_overlay)
        self.chk_overlay.pack(side=tk.LEFT, padx=15)

        self.btn_pause = tk.Button(ctrl_frame, text="PAUSE", command=self.toggle_pause,
                                   bg="#ffc107", fg="black", font=("Segoe UI", 9, "bold"), width=8)
        self.btn_pause.pack(side=tk.LEFT, padx=5)

        self.btn_stop = tk.Button(ctrl_frame, text="STOPP", command=self.stop_audio,
                                  bg="#dc3545", fg="white", font=("Segoe UI", 9, "bold"), width=8)
        self.btn_stop.pack(side=tk.LEFT, padx=5)

        # Progress
        self.lbl_progress = tk.Label(self.root, text="Bereit.", bg="#1e1e1e", fg="white", font=("Segoe UI", 10))
        self.lbl_progress.pack()
        self.progress_read = ttk.Progressbar(self.root, orient="horizontal", length=700, mode="determinate")
        self.progress_read.pack(pady=10)

        # Log
        self.log_box = tk.Text(self.root, height=20, bg="black", fg="#00ff00", font=("Consolas", 10), insertbackground="white")
        self.log_box.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.lbl_target = tk.Label(self.root, text="Ziel: -", bg="#333", fg="yellow", 
                                   font=("Segoe UI", 12), bd=1, relief=tk.SUNKEN, anchor=tk.W, padx=10, pady=5)
        self.lbl_target.pack(side=tk.BOTTOM, fill=tk.X)

    # --- EINSTELLUNGEN FENSTER ---
    def open_settings_window(self):
        sw = tk.Toplevel(self.root)
        sw.title("Tastenbelegung ändern")
        sw.geometry("400x350")
        sw.configure(bg="#333")
        sw.attributes("-topmost", True)

        def create_binder(label_text, setting_key):
            f = tk.Frame(sw, bg="#333")
            f.pack(pady=5, fill=tk.X, padx=20)
            tk.Label(f, text=label_text, bg="#333", fg="white", width=20, anchor="w").pack(side=tk.LEFT)
            
            current_key = self.settings_mgr.get(setting_key)
            btn = tk.Button(f, text=current_key, bg="#555", fg="white", width=15)
            btn.pack(side=tk.RIGHT)
            
            def on_click():
                btn.config(text="Drücke Taste...", bg="orange")
                sw.focus()
                
                def on_key(e):
                    new_key = e.name
                    self.settings_mgr.set(setting_key, new_key)
                    btn.config(text=new_key, bg="#555")
                    keyboard.unhook(on_key) # Listener entfernen
                    self.register_hotkeys() # Sofort anwenden
                    
                keyboard.on_press(on_key, suppress=True) # Einen Tastendruck abfangen

            btn.config(command=on_click)

        tk.Label(sw, text="Klicke auf einen Button und\ndrücke dann die neue Taste.", bg="#333", fg="#aaa").pack(pady=15)
        
        create_binder("Vorlesen:", "hotkey_read")
        create_binder("Ecken lernen:", "hotkey_learn")
        create_binder("Stoppen:", "hotkey_stop")
        create_binder("Pause/Weiter:", "hotkey_pause")

    # --- LOGIK ---
    def toggle_pause(self):
        is_paused = self.audio.toggle_pause()
        if is_paused:
            self.btn_pause.config(text="WEITER", bg="#28a745")
            self.log("⏸ Pausiert.")
        else:
            self.btn_pause.config(text="PAUSE", bg="#ffc107")
            self.log("▶ Weiter.")

    def update_volume(self, val):
        if self.audio: self.audio.set_volume(val)

    def toggle_overlay(self):
        self.overlay.set_user_visible(self.chk_overlay_var.get())

    def update_progress(self, current, total, text_sentence=""):
        self.root.after(0, lambda: self._gui_update_progress(current, total, text_sentence))
        
    def _gui_update_progress(self, current, total, text_sentence):
        self.progress_read["maximum"] = total
        self.progress_read["value"] = current
        self.lbl_progress.config(text=f"Satz {current}/{total}: {text_sentence[:60]}...")
        if current >= total: self.lbl_progress.config(text="Fertig.")
        
        # Overlay updaten!
        target = self.npc_manager.current_target
        self.overlay.update_content(target, text_sentence, current, total)

    def preprocess_image(self, img_np):
        img = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        img = cv2.resize(img, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        img = cv2.copyMakeBorder(img, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=[0, 0, 0])
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, img = cv2.threshold(img, 90, 255, cv2.THRESH_TOZERO)
        return img

    def scan_once(self):
        if self.is_scanning: return
        if self.template_tl is None:
            self.log("⚠️ Keine Templates.")
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

            # --- OVERLAY & WINDOW HIDE (Wichtig!) ---
            self.root.after(0, self.root.withdraw)
            self.root.after(0, self.overlay.hide_temp) # Overlay auch weg!
            time.sleep(0.3)

            found_area = self.scan_for_window()
            
            if not found_area:
                self.log("❌ Fenster nicht gefunden.")
                self.root.after(0, self.root.deiconify)
                self.root.after(0, self.overlay.restore) # Overlay wieder da
                self.is_scanning = False
                return

            self.current_area = found_area
            self.log(f"🔍 Gefunden: {found_area}")
            
            x, y, w, h = self.current_area
            screenshot = pyautogui.screenshot(region=(x, y, w, h))
            img_np = np.array(screenshot)
            
            # --- WIEDER ANZEIGEN ---
            self.root.after(0, self.root.deiconify)
            self.root.after(0, self.overlay.restore) # Overlay wieder da
            self.highlight_area(*found_area, "green")

            cv2.imwrite(os.path.join(self.debug_dir, "last_scan_raw.png"), cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR))
            processed_img = self.preprocess_image(img_np)
            cv2.imwrite(os.path.join(self.debug_dir, "last_scan_processed.png"), processed_img)
            
            results = self.reader.readtext(processed_img, detail=0, paragraph=True)
            full_text = " ".join(results).strip()

            self.log(f"📖 Text: {full_text[:50]}...")

            if full_text and len(full_text) > 3:
                if voice_path:
                    self.audio.speak(full_text, voice_path, 
                                   save_dir=self.debug_dir, 
                                   on_progress=self.update_progress)
                else:
                    self.log("⚠️ Keine Stimme.")
            else:
                self.log("⚠️ Kein Text.")

        except Exception as e:
            self.log(f"Fehler: {e}")
            self.root.after(0, self.root.deiconify)
            self.root.after(0, self.overlay.restore)
        finally:
            self.is_scanning = False
    
    # ... Rest der Funktionen (stop_audio, save_templates, etc.) bleiben gleich ...
    def stop_audio(self):
        self.audio.stop()
        self.progress_read["value"] = 0
        self.lbl_progress.config(text="Abgebrochen.")
        self.btn_pause.config(text="PAUSE", bg="#ffc107") # Reset Pause Button
        self.log("🔇 Stop.")

    def save_templates(self):
        if self.template_tl is not None and self.template_br is not None:
            cv2.imwrite(os.path.join(self.cache_dir, "last_tl.png"), self.template_tl)
            cv2.imwrite(os.path.join(self.cache_dir, "last_br.png"), self.template_br)
            self.log("💾 Gespeichert.")

    def load_cached_templates(self):
        p_tl = os.path.join(self.cache_dir, "last_tl.png")
        p_br = os.path.join(self.cache_dir, "last_br.png")
        if os.path.exists(p_tl) and os.path.exists(p_br):
            try:
                self.template_tl = cv2.imread(p_tl)
                self.template_br = cv2.imread(p_br)
                self.btn_read.config(state=tk.NORMAL)
                self.log("✅ Templates geladen.")
            except: pass

    def start_learning_sequence(self):
        self.root.withdraw()
        self.overlay.hide_temp() # Sicherstellen dass Overlay weg ist beim Lernen
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
        self.overlay.restore()
        self.save_templates()
        found = self.scan_for_window()
        if found:
            self.current_area = found
            self.btn_read.config(state=tk.NORMAL)
            self.highlight_area(*found, "green")
            self.log("🧠 Gelernt!")

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
