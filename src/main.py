import sys
import os
import datetime
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
import ctypes

# Pfad-Fix für lokale Module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# DPI Awareness für scharfe Screenshots auf 4K/Skalierten Monitoren
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except: pass

# --- DESIGN KONSTANTEN ---
COLORS = {
    "bg": "#1e1e1e",           
    "panel": "#252526",        
    "fg": "#ffffff",           
    "accent": "#007acc",       
    "success": "#28a745",      
    "warning": "#ffc107",      
    "danger": "#dc3545",       
    "text_bg": "#1a1a1a",      
    "border": "#3e3e42"
}

FONT_BIG = ("Segoe UI", 14, "bold")
FONT_NORM = ("Segoe UI", 11)

# Platzhalter für Lazy Loading
cv2 = None
np = None
easyocr = None
pyautogui = None
keyboard = None
AudioEngine = None
SnippingTool = None
NpcManager = None
SettingsManager = None

class App:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.root_dir = os.path.dirname(self.base_dir)
        self.debug_dir = os.path.join(self.root_dir, "debug")
        self.cache_dir = os.path.join(self.root_dir, "resources", "cache")
        self.log_file_path = os.path.join(self.debug_dir, "system.log")
        
        if not os.path.exists(self.debug_dir): os.makedirs(self.debug_dir)
        if not os.path.exists(self.cache_dir): os.makedirs(self.cache_dir)
        
        # Initialer Log-Eintrag [cite: 5]
        with open(self.log_file_path, "a", encoding="utf-8") as f:
            f.write(f"\n=== START V20 (Hybrid): {datetime.datetime.now()} ===\n")

        # --- SPLASH SCREEN ---
        self.splash = tk.Tk()
        self.splash.overrideredirect(True)
        w, h = 600, 350
        ws = self.splash.winfo_screenwidth()
        hs = self.splash.winfo_screenheight()
        x = (ws // 2) - (w // 2)
        y = (hs // 2) - (h // 2)
        self.splash.geometry(f'{w}x{h}+{x}+{y}')
        self.splash.configure(bg=COLORS["bg"])
        
        tk.Label(self.splash, text="LQAG Vorleser", bg=COLORS["bg"], fg=COLORS["accent"], font=("Segoe UI", 36, "bold")).pack(pady=(50, 20))
        self.lbl_loading = tk.Label(self.splash, text="Lade KI-Systeme...", bg=COLORS["bg"], fg="#aaaaaa", font=("Segoe UI", 14))
        self.lbl_loading.pack(pady=10)
        
        style = ttk.Style()
        style.theme_use('alt')
        style.configure("green.Horizontal.TProgressbar", background=COLORS["accent"], thickness=10, troughcolor=COLORS["panel"], borderwidth=0)
        
        self.progress_splash = ttk.Progressbar(self.splash, style="green.Horizontal.TProgressbar", mode='indeterminate', length=400)
        self.progress_splash.pack(pady=30)
        self.progress_splash.start(10)

        threading.Thread(target=self.load_heavy_stuff, daemon=True).start()
        self.splash.mainloop()

    def log_user(self, text):
        """Aktualisiert den Status-Text für den Benutzer [cite: 6]"""
        if hasattr(self, 'lbl_status'):
            self.lbl_status.config(text=text)
        try:
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            with open(self.log_file_path, "a", encoding="utf-8") as f: 
                f.write(f"[{ts}] {text}\n")
        except: pass

    def load_heavy_stuff(self):
        try:
            global cv2, np, easyocr, pyautogui, keyboard, AudioEngine, SnippingTool, NpcManager, SettingsManager
            
            self.lbl_loading.config(text="Lade Bibliotheken...")
            import cv2
            import numpy as np
            import pyautogui
            import easyocr
            import keyboard
            from screen_tool import SnippingTool
            from npc_manager import NpcManager
            from settings_manager import SettingsManager
            from audio_engine import AudioEngine

            self.npc_manager = NpcManager()
            self.reader = easyocr.Reader(['de', 'en'], gpu=True)
            self.audio = AudioEngine()
            self.settings_mgr = SettingsManager(self.root_dir)
            
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
        self.root.geometry("1000x900")
        self.root.configure(bg=COLORS["bg"])
        
        style = ttk.Style()
        style.theme_use('alt')
        style.configure('TNotebook', background=COLORS["bg"], borderwidth=0)
        style.configure('TNotebook.Tab', background=COLORS["panel"], foreground="white", padding=[20, 10], font=FONT_NORM)
        style.map('TNotebook.Tab', background=[('selected', COLORS["accent"])])

        self.setup_ui()
        self.root.after(100, self.register_hotkeys)
        
        self.template_tl = None
        self.template_br = None
        self.current_area = None
        self.is_scanning = False
        
        self.root.after(500, self.load_cached_templates)
        self.root.mainloop()

    def setup_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.tab_main = tk.Frame(self.notebook, bg=COLORS["bg"])
        self.notebook.add(self.tab_main, text="   Vorlesen   ")
        
        self.tab_settings = tk.Frame(self.notebook, bg=COLORS["bg"])
        self.notebook.add(self.tab_settings, text="   Einstellungen   ")

        self.setup_tab_main()
        self.setup_tab_settings()

    def setup_tab_main(self):
        container = tk.Frame(self.tab_main, bg=COLORS["bg"])
        container.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)

        status_frame = tk.Frame(container, bg=COLORS["bg"])
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.lbl_status = tk.Label(status_frame, text="Bereit.", bg=COLORS["bg"], fg="#aaaaaa", font=FONT_NORM)
        self.lbl_status.pack(side=tk.LEFT)
        
        self.lbl_target = tk.Label(status_frame, text="-", bg=COLORS["panel"], fg=COLORS["accent"], font=FONT_NORM, padx=10)
        self.lbl_target.pack(side=tk.RIGHT)

        self.txt_display = tk.Text(container, bg=COLORS["text_bg"], fg="#eeeeee", font=("Segoe UI", 12),
                                   relief="flat", highlightthickness=1, highlightbackground=COLORS["border"],
                                   padx=20, pady=20, wrap=tk.WORD, height=18)
        self.txt_display.pack(fill=tk.BOTH, expand=True)
        self.txt_display.tag_configure("speaker", foreground=COLORS["accent"], font=("Segoe UI", 12, "bold"))

        self.progress_read = ttk.Progressbar(container, style="green.Horizontal.TProgressbar", mode="determinate")
        self.progress_read.pack(fill=tk.X, pady=(15, 5))
        
        self.lbl_progress_text = tk.Label(container, text="0 / 0", bg=COLORS["bg"], fg="#666")
        self.lbl_progress_text.pack(anchor="e")

        footer = tk.Frame(container, bg=COLORS["bg"], pady=20)
        footer.pack(fill=tk.X, side=tk.BOTTOM)

        self.btn_learn = tk.Button(footer, text="Ecken lernen", command=self.start_learning_sequence,
                                   bg=COLORS["panel"], fg="white", font=FONT_BIG, relief="flat", padx=20, pady=10)
        self.btn_learn.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_read = tk.Button(footer, text="VORLESEN", command=self.scan_once, state=tk.DISABLED,
                                  bg=COLORS["success"], fg="white", font=FONT_BIG, relief="flat", padx=20, pady=10)
        self.btn_read.pack(side=tk.LEFT, padx=10)

        self.btn_stop = tk.Button(footer, text="⏹", command=self.stop_audio,
                                  bg=COLORS["danger"], fg="white", font=FONT_BIG, relief="flat", padx=15, pady=10)
        self.btn_stop.pack(side=tk.RIGHT, padx=5)

        self.btn_pause = tk.Button(footer, text="⏸", command=self.toggle_pause,
                                   bg=COLORS["warning"], fg="black", font=FONT_BIG, relief="flat", padx=15, pady=10)
        self.btn_pause.pack(side=tk.RIGHT, padx=5)

    def setup_tab_settings(self):
        container = tk.Frame(self.tab_settings, bg=COLORS["bg"])
        container.pack(fill=tk.BOTH, expand=True, padx=50, pady=30)

        # Hotkeys
        tk.Label(container, text="Tastenbelegung", bg=COLORS["bg"], fg="white", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 15))
        self.binder_frame = tk.Frame(container, bg=COLORS["bg"])
        self.binder_frame.pack(fill=tk.X)
        self.create_binder("Vorlesen:", "hotkey_read")
        self.create_binder("Lernen:", "hotkey_learn")
        self.create_binder("Stoppen:", "hotkey_stop")
        self.create_binder("Pause:", "hotkey_pause")

        tk.Frame(container, bg=COLORS["border"], height=1).pack(fill=tk.X, pady=25)

        # ElevenLabs Integration
        tk.Label(container, text="ElevenLabs (Cloud Audio)", bg=COLORS["bg"], fg="white", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 15))
        
        self.chk_el_var = tk.BooleanVar(value=self.settings_mgr.get("use_elevenlabs"))
        tk.Checkbutton(container, text="ElevenLabs nutzen", variable=self.chk_el_var,
                       command=lambda: self.settings_mgr.set("use_elevenlabs", self.chk_el_var.get()),
                       bg=COLORS["bg"], fg="#ccc", selectcolor=COLORS["bg"], activebackground=COLORS["bg"], font=FONT_NORM).pack(anchor="w")
        
        api_frame = tk.Frame(container, bg=COLORS["bg"])
        api_frame.pack(fill=tk.X, pady=10)
        tk.Label(api_frame, text="API Key:", bg=COLORS["bg"], fg="#888", width=10, anchor="w").pack(side=tk.LEFT)
        self.ent_api_key = tk.Entry(api_frame, bg=COLORS["text_bg"], fg="white", relief="flat", highlightthickness=1, highlightbackground=COLORS["border"])
        self.ent_api_key.insert(0, self.settings_mgr.get("elevenlabs_api_key"))
        self.ent_api_key.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        tk.Button(api_frame, text="Speichern", command=self.save_api_key, bg=COLORS["accent"], fg="white", relief="flat", padx=10).pack(side=tk.LEFT)

        tk.Frame(container, bg=COLORS["border"], height=1).pack(fill=tk.X, pady=25)

        # Audio & Debug
        tk.Label(container, text="System & Audio", bg=COLORS["bg"], fg="white", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 15))
        
        vol_frame = tk.Frame(container, bg=COLORS["bg"])
        vol_frame.pack(fill=tk.X)
        tk.Label(vol_frame, text="Lautstärke:", bg=COLORS["bg"], fg="#ccc", width=15, anchor="w").pack(side=tk.LEFT)
        self.scale_vol = tk.Scale(vol_frame, from_=0, to=100, orient=tk.HORIZONTAL, bg=COLORS["bg"], fg="white", highlightthickness=0, length=250, command=self.update_volume)
        self.scale_vol.set(100)
        self.scale_vol.pack(side=tk.LEFT)

        self.chk_debug_var = tk.BooleanVar(value=self.settings_mgr.get("debug_mode"))
        tk.Checkbutton(container, text="Debug-Modus (Dateien speichern)", variable=self.chk_debug_var,
                       command=lambda: self.settings_mgr.set("debug_mode", self.chk_debug_var.get()),
                       bg=COLORS["bg"], fg="#ccc", selectcolor=COLORS["bg"], font=FONT_NORM).pack(anchor="w", pady=20)

    def create_binder(self, label_text, key_name):
        f = tk.Frame(self.binder_frame, bg=COLORS["bg"])
        f.pack(fill=tk.X, pady=3)
        tk.Label(f, text=label_text, bg=COLORS["bg"], fg="#ccc", font=FONT_NORM, width=15, anchor="w").pack(side=tk.LEFT)
        curr = self.settings_mgr.get(key_name).upper()
        btn = tk.Button(f, text=curr, bg=COLORS["panel"], fg="white", width=12, relief="flat")
        btn.pack(side=tk.LEFT, padx=10)
        def on_click():
            btn.config(text="...", bg=COLORS["accent"])
            def on_key(e):
                self.settings_mgr.set(key_name, e.name)
                btn.config(text=e.name.upper(), bg=COLORS["panel"])
                keyboard.unhook(on_key)
                self.register_hotkeys()
            keyboard.on_press(on_key, suppress=True)
        btn.config(command=on_click)

    # --- LOGIK ---
    def save_api_key(self):
        self.settings_mgr.set("elevenlabs_api_key", self.ent_api_key.get())
        self.log_user("API Key gespeichert.")

    def register_hotkeys(self):
        try:
            try: keyboard.unhook_all()
            except: pass
            keyboard.add_hotkey(self.settings_mgr.get("hotkey_read"), self.scan_once)
            keyboard.add_hotkey(self.settings_mgr.get("hotkey_learn"), self.start_learning_sequence)
            keyboard.add_hotkey(self.settings_mgr.get("hotkey_stop"), self.stop_audio)
            keyboard.add_hotkey(self.settings_mgr.get("hotkey_pause"), self.toggle_pause)
            self.btn_read.config(text=f"VORLESEN ({self.settings_mgr.get('hotkey_read').upper()})")
            self.btn_learn.config(text=f"Lernen ({self.settings_mgr.get('hotkey_learn').upper()})")
        except: pass

    def toggle_pause(self):
        is_paused = self.audio.toggle_pause()
        self.btn_pause.config(bg=COLORS["success"] if is_paused else COLORS["warning"], text="▶" if is_paused else "⏸")
        self.log_user("Pausiert" if is_paused else "Läuft")

    def update_volume(self, val):
        if self.audio: self.audio.set_volume(val)

    def update_progress(self, current, total, text_sentence=""):
        self.root.after(0, lambda: self._gui_update_progress(current, total, text_sentence))
        
    def _gui_update_progress(self, current, total, text_sentence):
        self.progress_read["maximum"] = total
        self.progress_read["value"] = current
        self.lbl_progress_text.config(text=f"{current} / {total}")
        if current >= total: 
            self.lbl_status.config(text="Audio wurde Erstellt.") # Benutzer-Wunsch Logik
            self.progress_read["value"] = 0

    def scan_once(self):
        if self.is_scanning or not self.template_tl is not None: 
            if not self.template_tl: self.log_user("Bitte zuerst Ecken lernen.")
            return
        self.is_scanning = True
        self.lbl_status.config(text="Suche Fenster...")
        threading.Thread(target=self._run_scan, daemon=True).start()

    def _run_scan(self):
        debug = self.settings_mgr.get("debug_mode")
        try:
            self.npc_manager.update()
            target = self.npc_manager.current_target
            voice_ref = self.npc_manager.get_voice_path()
            self.root.after(0, lambda: self.lbl_target.config(text=target))
            
            self.root.after(0, self.root.withdraw)
            time.sleep(0.3)
            found_area = self.scan_for_window()
            self.root.after(0, self.root.deiconify)

            if not found_area:
                self.log_user("Fenster nicht gefunden.")
                self.is_scanning = False
                return

            self.current_area = found_area
            screenshot = pyautogui.screenshot(region=self.current_area)
            img_np = np.array(screenshot)
            self.highlight_area(*found_area, COLORS["success"])

            # Bildbearbeitung [cite: 10]
            img = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            img = cv2.resize(img, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            _, processed = cv2.threshold(gray, 90, 255, cv2.THRESH_TOZERO)
            
            if debug: cv2.imwrite(os.path.join(self.debug_dir, "last_scan_processed.jpg"), processed)
            
            results = self.reader.readtext(processed, detail=0, paragraph=True)
            full_text = " ".join(results).strip()

            if full_text and len(full_text) > 3:
                self.log_user("Text erkannt. Generiere Audio...") # Benutzer-Wunsch Logik
                self.root.after(0, lambda: self.display_result(target, "\n\n".join(results)))
                self.audio.speak(full_text, voice_ref, self.settings_mgr.get_all(), save_dir=self.debug_dir, on_progress=self.update_progress)
            else:
                self.log_user("Kein Text erkannt.")
        except Exception as e:
            self.log_user(f"Fehler: {e}")
            self.root.after(0, self.root.deiconify)
        finally:
            self.is_scanning = False

    def display_result(self, speaker, text):
        self.txt_display.delete("1.0", tk.END)
        self.txt_display.insert(tk.END, f"{speaker}:\n", "speaker")
        self.txt_display.insert(tk.END, text)

    def stop_audio(self):
        self.audio.stop()
        self.progress_read["value"] = 0
        self.lbl_status.config(text="Abgebrochen.")

    def save_templates(self):
        if self.template_tl is not None:
            cv2.imwrite(os.path.join(self.cache_dir, "last_tl.png"), self.template_tl)
            cv2.imwrite(os.path.join(self.cache_dir, "last_br.png"), self.template_br)

    def load_cached_templates(self):
        p_tl = os.path.join(self.cache_dir, "last_tl.png")
        if os.path.exists(p_tl):
            self.template_tl = cv2.imread(p_tl)
            self.template_br = cv2.imread(os.path.join(self.cache_dir, "last_br.png"))
            self.btn_read.config(state=tk.NORMAL)
            self.log_user("Bereit.")

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
            self.highlight_area(*found, COLORS["success"])
            self.log_user("Bereich gelernt!")

    def scan_for_window(self):
        if self.template_tl is None: return None
        try:
            screen = cv2.cvtColor(np.array(pyautogui.screenshot()), cv2.COLOR_RGB2BGR)
            res_tl = cv2.matchTemplate(screen, self.template_tl, cv2.TM_CCOEFF_NORMED)
            _, val_tl, _, loc_tl = cv2.minMaxLoc(res_tl)
            res_br = cv2.matchTemplate(screen, self.template_br, cv2.TM_CCOEFF_NORMED)
            _, val_br, _, loc_br = cv2.minMaxLoc(res_br)
            if val_tl < 0.7 or val_br < 0.7: return None
            return (loc_tl[0], loc_tl[1], (loc_br[0] + self.template_br.shape[1]) - loc_tl[0], (loc_br[1] + self.template_br.shape[0]) - loc_tl[1])
        except: return None

    def highlight_area(self, x, y, w, h, color):
        top = tk.Toplevel(self.root)
        top.geometry(f"{w}x{h}+{x}+{y}")
        top.overrideredirect(True)
        top.attributes("-topmost", True, "-alpha", 0.3)
        top.configure(bg=color)
        top.after(1000, top.destroy)

if __name__ == "__main__":
    App()
