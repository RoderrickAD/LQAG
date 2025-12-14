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

# --- DESIGN KONSTANTEN ---
COLORS = {
    "bg": "#1e1e1e",           # Haupt-Hintergrund
    "panel": "#252526",        # Panels/Tabs
    "fg": "#ffffff",           # Text
    "accent": "#007acc",       # Blau
    "success": "#28a745",      # Grün
    "warning": "#ffc107",      # Gelb
    "danger": "#dc3545",       # Rot
    "text_bg": "#1a1a1a",      # Textfeld
    "border": "#3e3e42"
}

FONT_BIG = ("Segoe UI", 14, "bold")
FONT_NORM = ("Segoe UI", 11)
FONT_MONO = ("Consolas", 10)

# Platzhalter
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
        
        with open(self.log_file_path, "a", encoding="utf-8") as f:
            f.write(f"\n=== START V19 (Tabs): {datetime.datetime.now()} ===\n")

        # --- SPLASH SCREEN ---
        self.splash = tk.Tk()
        self.splash.overrideredirect(True)
        w, h = 600, 350
        try:
            ws = self.splash.winfo_screenwidth()
            hs = self.splash.winfo_screenheight()
        except: ws, hs = 1920, 1080
        x = (ws // 2) - (w // 2)
        y = (hs // 2) - (h // 2)
        self.splash.geometry(f'{w}x{h}+{x}+{y}')
        self.splash.configure(bg=COLORS["bg"])
        
        tk.Label(self.splash, text="LQAG Vorleser", bg=COLORS["bg"], fg=COLORS["accent"], font=("Segoe UI", 36, "bold")).pack(pady=(50, 20))
        self.lbl_loading = tk.Label(self.splash, text="Lade KI...", bg=COLORS["bg"], fg="#aaaaaa", font=("Segoe UI", 14))
        self.lbl_loading.pack(pady=10)
        
        style = ttk.Style()
        style.theme_use('alt')
        style.configure("green.Horizontal.TProgressbar", background=COLORS["accent"], thickness=10, troughcolor=COLORS["panel"], borderwidth=0)
        
        self.progress_splash = ttk.Progressbar(self.splash, style="green.Horizontal.TProgressbar", mode='indeterminate', length=400)
        self.progress_splash.pack(pady=30)
        self.progress_splash.start(10)

        threading.Thread(target=self.load_heavy_stuff, daemon=True).start()
        self.splash.mainloop()

    # --- LOGGING ---
    def log_user(self, text):
        """Zeigt Info im Status-Bereich der GUI an"""
        if hasattr(self, 'lbl_status'):
            self.lbl_status.config(text=text)
        try:
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            with open(self.log_file_path, "a", encoding="utf-8") as f: 
                f.write(f"[{ts}] INFO: {text}\n")
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
            
            self.lbl_loading.config(text="Lade KI-Stimme...")
            from audio_engine import AudioEngine

            self.lbl_loading.config(text="Initialisiere...")
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
        self.root.geometry("1000x850")
        self.root.configure(bg=COLORS["bg"])
        
        # Styles für Tabs
        style = ttk.Style()
        style.theme_use('alt')
        style.configure('TNotebook', background=COLORS["bg"], borderwidth=0)
        style.configure('TNotebook.Tab', background=COLORS["panel"], foreground="white", padding=[20, 10], font=FONT_NORM)
        style.map('TNotebook.Tab', background=[('selected', COLORS["accent"])])

        self.setup_ui()
        
        # Hotkeys
        self.root.after(100, self.register_hotkeys)
        
        self.template_tl = None
        self.template_br = None
        self.current_area = None
        self.is_scanning = False
        
        self.root.after(500, self.load_cached_templates)
        self.root.mainloop()

    # --- UI SETUP MIT TABS ---
    def setup_ui(self):
        # Notebook (Tab Container)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Vorlesen
        self.tab_main = tk.Frame(self.notebook, bg=COLORS["bg"])
        self.notebook.add(self.tab_main, text="   Vorlesen   ")
        
        # Tab 2: Einstellungen
        self.tab_settings = tk.Frame(self.notebook, bg=COLORS["bg"])
        self.notebook.add(self.tab_settings, text="   Einstellungen   ")

        # Inhalt aufbauen
        self.setup_tab_main()
        self.setup_tab_settings()

    def setup_tab_main(self):
        # Padding Container
        container = tk.Frame(self.tab_main, bg=COLORS["bg"])
        container.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)

        # 1. Info & Status
        info_frame = tk.Frame(container, bg=COLORS["bg"])
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.lbl_status = tk.Label(info_frame, text="System bereit.", bg=COLORS["bg"], fg="#aaaaaa", font=FONT_NORM)
        self.lbl_status.pack(side=tk.LEFT)
        
        self.lbl_target = tk.Label(info_frame, text="-", bg=COLORS["panel"], fg=COLORS["accent"], padx=10)
        self.lbl_target.pack(side=tk.RIGHT)

        # 2. Text Box (Groß)
        self.txt_display = tk.Text(container, bg=COLORS["text_bg"], fg="#eeeeee", font=("Segoe UI", 12),
                                   relief="flat", highlightthickness=1, highlightbackground=COLORS["border"],
                                   padx=20, pady=20, wrap=tk.WORD, height=15)
        self.txt_display.pack(fill=tk.BOTH, expand=True)
        self.txt_display.tag_configure("speaker", foreground=COLORS["accent"], font=("Segoe UI", 12, "bold"))

        # 3. Progress Bar (Jetzt sichtbar!)
        self.progress_read = ttk.Progressbar(container, style="green.Horizontal.TProgressbar", mode="determinate")
        self.progress_read.pack(fill=tk.X, pady=(15, 5))
        
        self.lbl_progress_text = tk.Label(container, text="0/0", bg=COLORS["bg"], fg="#666")
        self.lbl_progress_text.pack(anchor="e")

        # 4. Buttons (Footer)
        # WICHTIG: Kein festes 'height' im Frame, damit Buttons sichtbar bleiben
        footer = tk.Frame(container, bg=COLORS["bg"], pady=20)
        footer.pack(fill=tk.X, side=tk.BOTTOM)

        # Links: Hauptaktionen
        self.btn_learn = tk.Button(footer, text="Ecken lernen", command=self.start_learning_sequence,
                                   bg=COLORS["panel"], fg="white", font=FONT_BIG, relief="flat", padx=20, pady=10)
        self.btn_learn.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_read = tk.Button(footer, text="VORLESEN", command=self.scan_once, state=tk.DISABLED,
                                  bg=COLORS["success"], fg="white", font=FONT_BIG, relief="flat", padx=20, pady=10)
        self.btn_read.pack(side=tk.LEFT, padx=10)

        # Rechts: Audio Steuerung
        self.btn_stop = tk.Button(footer, text="⏹ STOPP", command=self.stop_audio,
                                  bg=COLORS["danger"], fg="white", font=FONT_BIG, relief="flat", padx=15, pady=10)
        self.btn_stop.pack(side=tk.RIGHT, padx=5)

        self.btn_pause = tk.Button(footer, text="⏸", command=self.toggle_pause,
                                   bg=COLORS["warning"], fg="black", font=FONT_BIG, relief="flat", padx=15, pady=10)
        self.btn_pause.pack(side=tk.RIGHT, padx=5)

    def setup_tab_settings(self):
        container = tk.Frame(self.tab_settings, bg=COLORS["bg"])
        container.pack(fill=tk.BOTH, expand=True, padx=50, pady=40)

        # 1. Hotkeys Section
        tk.Label(container, text="Tastenbelegung", bg=COLORS["bg"], fg="white", font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 20))

        self.binder_frame = tk.Frame(container, bg=COLORS["bg"])
        self.binder_frame.pack(fill=tk.X)
        
        self.create_binder("Vorlesen starten:", "hotkey_read")
        self.create_binder("Ecken lernen:", "hotkey_learn")
        self.create_binder("Wiedergabe stoppen:", "hotkey_stop")
        self.create_binder("Pause / Weiter:", "hotkey_pause")

        tk.Frame(container, bg=COLORS["border"], height=1).pack(fill=tk.X, pady=30)

        # 2. Audio Section
        tk.Label(container, text="Audio", bg=COLORS["bg"], fg="white", font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 20))
        
        vol_frame = tk.Frame(container, bg=COLORS["bg"])
        vol_frame.pack(fill=tk.X, anchor="w")
        
        tk.Label(vol_frame, text="Lautstärke:", bg=COLORS["bg"], fg="#ccc", font=FONT_NORM, width=20, anchor="w").pack(side=tk.LEFT)
        self.scale_vol = tk.Scale(vol_frame, from_=0, to=100, orient=tk.HORIZONTAL, 
                                  bg=COLORS["bg"], fg="white", highlightthickness=0, 
                                  length=300, command=self.update_volume)
        self.scale_vol.set(100)
        self.scale_vol.pack(side=tk.LEFT)

        tk.Frame(container, bg=COLORS["border"], height=1).pack(fill=tk.X, pady=30)

        # 3. System Section
        tk.Label(container, text="System", bg=COLORS["bg"], fg="white", font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 20))
        
        self.chk_debug_var = tk.BooleanVar(value=self.settings_mgr.get("debug_mode"))
        chk = tk.Checkbutton(container, text="Debug-Modus (Bilder & Audio speichern zur Fehleranalyse)", 
                             variable=self.chk_debug_var, command=self.toggle_debug,
                             bg=COLORS["bg"], fg="#ccc", selectcolor=COLORS["bg"], 
                             activebackground=COLORS["bg"], activeforeground="white", font=FONT_NORM)
        chk.pack(anchor="w")

    def create_binder(self, label_text, key_name):
        f = tk.Frame(self.binder_frame, bg=COLORS["bg"])
        f.pack(fill=tk.X, pady=5)
        
        tk.Label(f, text=label_text, bg=COLORS["bg"], fg="#ccc", font=FONT_NORM, width=20, anchor="w").pack(side=tk.LEFT)
        
        current_key = self.settings_mgr.get(key_name).upper()
        btn = tk.Button(f, text=current_key, bg=COLORS["panel"], fg="white", width=15, relief="flat")
        btn.pack(side=tk.LEFT, padx=10)
        
        def on_click():
            btn.config(text="Drücken...", bg=COLORS["accent"])
            self.root.focus()
            
            def on_key(e):
                new_key = e.name
                self.settings_mgr.set(key_name, new_key)
                btn.config(text=new_key.upper(), bg=COLORS["panel"])
                keyboard.unhook(on_key)
                self.register_hotkeys()
                
            keyboard.on_press(on_key, suppress=True)

        btn.config(command=on_click)

    # --- LOGIK ---
    def register_hotkeys(self):
        try:
            # FIX: Hier war der Fehler. Wir nutzen try-except, falls unhook fehlschlägt.
            try:
                keyboard.unhook_all()
            except AttributeError:
                pass # Ignorieren beim ersten Start oder Bibliotheks-Fehler
            except Exception:
                pass

            hk_read = self.settings_mgr.get("hotkey_read")
            hk_learn = self.settings_mgr.get("hotkey_learn")
            hk_stop = self.settings_mgr.get("hotkey_stop")
            hk_pause = self.settings_mgr.get("hotkey_pause")
            
            keyboard.add_hotkey(hk_read, self.scan_once)
            keyboard.add_hotkey(hk_learn, self.start_learning_sequence)
            keyboard.add_hotkey(hk_stop, self.stop_audio)
            keyboard.add_hotkey(hk_pause, self.toggle_pause)
            
            # Buttons Text aktualisieren
            self.btn_read.config(text=f"VORLESEN ({hk_read.upper()})")
            self.btn_learn.config(text=f"Ecken lernen ({hk_learn.upper()})")
            
            self.log_user("Hotkeys aktualisiert.")
            
        except Exception as e:
            print(f"Hotkey Error: {e}") # Nur in Konsole, nicht GUI blockieren

    def toggle_debug(self):
        val = self.chk_debug_var.get()
        self.settings_mgr.set("debug_mode", val)

    def toggle_pause(self):
        is_paused = self.audio.toggle_pause()
        if is_paused:
            self.btn_pause.config(bg=COLORS["success"], text="▶")
            self.log_user("Pausiert")
        else:
            self.btn_pause.config(bg=COLORS["warning"], text="⏸")
            self.log_user("Wiedergabe läuft")

    def update_volume(self, val):
        if self.audio: self.audio.set_volume(val)

    def update_progress(self, current, total, text_sentence=""):
        self.root.after(0, lambda: self._gui_update_progress(current, total, text_sentence))
        
    def _gui_update_progress(self, current, total, text_sentence):
        self.progress_read["maximum"] = total
        self.progress_read["value"] = current
        self.lbl_progress_text.config(text=f"{current} / {total}")
        
        if current >= total:
            self.lbl_status.config(text="Fertig.")
            self.progress_read["value"] = 0

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
            self.log_user("Keine Ecken gelernt! Bitte Einstellungen prüfen.")
            # Automatisch zum Tab springen? Nein, lieber User Hinweis geben.
            return
        
        self.is_scanning = True
        self.progress_read["value"] = 0
        self.lbl_status.config(text="Suche Fenster...")
        threading.Thread(target=self._run_scan, daemon=True).start()

    def _run_scan(self):
        debug = self.settings_mgr.get("debug_mode")
        try:
            self.npc_manager.update()
            target = self.npc_manager.current_target
            voice_path = self.npc_manager.get_voice_path()
            v_name = os.path.basename(voice_path) if voice_path else "Standard"
            
            self.root.after(0, lambda: self.lbl_target.config(text=f"{target}"))

            # Hide Main Window
            self.root.after(0, self.root.withdraw)
            time.sleep(0.2)

            found_area = self.scan_for_window()
            
            if not found_area:
                self.log_user("Fenster nicht gefunden.")
                self.root.after(0, self.root.deiconify)
                self.is_scanning = False
                return

            self.current_area = found_area
            x, y, w, h = self.current_area
            screenshot = pyautogui.screenshot(region=(x, y, w, h))
            img_np = np.array(screenshot)
            
            # Show Main Window
            self.root.after(0, self.root.deiconify)
            self.highlight_area(*found_area, COLORS["success"])

            if debug:
                cv2.imwrite(os.path.join(self.debug_dir, "last_scan_raw.png"), cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR))
            
            processed_img = self.preprocess_image(img_np)
            if debug:
                cv2.imwrite(os.path.join(self.debug_dir, "last_scan_processed.png"), processed_img)
            
            results = self.reader.readtext(processed_img, detail=0, paragraph=True)
            
            full_text_raw = " ".join(results).strip()
            display_text = "\n\n".join(results) 

            if full_text_raw and len(full_text_raw) > 3:
                self.log_user(f"Text erkannt ({len(full_text_raw)} Zeichen).")
                self.root.after(0, lambda: self.display_result(target, display_text))

                if voice_path:
                    self.audio.speak(full_text_raw, voice_path, 
                                   save_dir=self.debug_dir, 
                                   on_progress=self.update_progress,
                                   debug_mode=debug)
                else:
                    self.log_user("Keine Stimme gefunden.")
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
        self.btn_pause.config(text="⏸", bg=COLORS["warning"])

    def save_templates(self):
        if self.template_tl is not None and self.template_br is not None:
            cv2.imwrite(os.path.join(self.cache_dir, "last_tl.png"), self.template_tl)
            cv2.imwrite(os.path.join(self.cache_dir, "last_br.png"), self.template_br)
            self.log_user("Ecken gespeichert.")

    def load_cached_templates(self):
        p_tl = os.path.join(self.cache_dir, "last_tl.png")
        p_br = os.path.join(self.cache_dir, "last_br.png")
        if os.path.exists(p_tl) and os.path.exists(p_br):
            try:
                self.template_tl = cv2.imread(p_tl)
                self.template_br = cv2.imread(p_br)
                self.btn_read.config(state=tk.NORMAL)
                self.log_user("Bereit.")
            except: pass

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
            self.highlight_area(*found, COLORS["success"])
            self.log_user("Bereich gelernt!")
        else:
            self.log_user("Fehler: Ecken nicht gefunden.")

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

    def highlight_area(self, x, y, w, h, color):
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
