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
    "bg": "#1e1e1e",           # Dunkler Hintergrund (VS Code Style)
    "fg": "#ffffff",           # Weißer Text
    "accent": "#007acc",       # Blau (Buttons, Highlights)
    "accent_hover": "#0098ff", 
    "success": "#28a745",      # Grün
    "warning": "#ffc107",      # Gelb/Orange
    "danger": "#dc3545",       # Rot
    "panel": "#252526",        # Etwas hellerer Hintergrund für Panels
    "text_bg": "#1a1a1a",      # Sehr dunkler Hintergrund für Textbox
    "border": "#3e3e42"
}

FONT_H1 = ("Segoe UI", 20, "bold")
FONT_H2 = ("Segoe UI", 12, "bold")
FONT_TEXT = ("Segoe UI", 11)
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
        
        # Log File Init
        with open(self.log_file_path, "a", encoding="utf-8") as f:
            f.write(f"\n=== START V18 (Clean UI): {datetime.datetime.now()} ===\n")

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

    # --- LOGGING HELPER ---
    def log_debug(self, text):
        """Schreibt NUR ins Logfile, wenn Debug an ist."""
        if self.settings_mgr.get("debug_mode"):
            try:
                ts = datetime.datetime.now().strftime("%H:%M:%S")
                with open(self.log_file_path, "a", encoding="utf-8") as f: 
                    f.write(f"[{ts}] DEBUG: {text}\n")
            except: pass

    def log_user(self, text):
        """Zeigt Info im Status-Bereich der GUI an"""
        self.lbl_status.config(text=text)
        # Auch ins Logfile
        try:
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            with open(self.log_file_path, "a", encoding="utf-8") as f: 
                f.write(f"[{ts}] INFO: {text}\n")
        except: pass

    def load_heavy_stuff(self):
        try:
            global cv2, np, easyocr, pyautogui, keyboard, AudioEngine, SnippingTool, NpcManager, SettingsManager
            
            self.lbl_loading.config(text="Lade Grafik & Tools...")
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
        self.root.geometry("1000x800")
        self.root.configure(bg=COLORS["bg"])
        
        self.setup_ui()
        self.register_hotkeys()
        
        self.template_tl = None
        self.template_br = None
        self.current_area = None
        self.is_scanning = False
        
        self.root.after(500, self.load_cached_templates)
        self.root.mainloop()

    def register_hotkeys(self):
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
            
            # Buttons aktualisieren
            self.btn_learn.config(text=f"Ecken lernen ({hk_learn.upper()})")
            self.btn_read.config(text=f"VORLESEN ({hk_read.upper()})")
            
        except Exception as e:
            self.log_user(f"Fehler Hotkeys: {e}")

    # --- MODERN UI SETUP ---
    def setup_ui(self):
        # Header Bar
        header = tk.Frame(self.root, bg=COLORS["panel"], height=60)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        tk.Label(header, text="LQAG Vorleser", bg=COLORS["panel"], fg=COLORS["accent"], font=("Segoe UI", 18, "bold")).pack(side=tk.LEFT, padx=20)
        
        btn_settings = tk.Button(header, text="⚙ Einstellungen", command=self.open_settings_window,
                                 bg=COLORS["bg"], fg="white", relief="flat", font=("Segoe UI", 10))
        btn_settings.pack(side=tk.RIGHT, padx=20)

        # Main Content Area
        content = tk.Frame(self.root, bg=COLORS["bg"])
        content.pack(fill=tk.BOTH, expand=True, padx=40, pady=20)

        # Status Line (Info für User)
        self.lbl_status = tk.Label(content, text="Bereit.", bg=COLORS["bg"], fg="#aaaaaa", font=("Segoe UI", 12))
        self.lbl_status.pack(pady=(0, 10), anchor="w")

        # Text Display Box (Schön & Sauber)
        self.txt_display = tk.Text(content, bg=COLORS["text_bg"], fg="#eeeeee", font=("Segoe UI", 12),
                                   relief="flat", highlightthickness=1, highlightbackground=COLORS["border"],
                                   padx=20, pady=20, wrap=tk.WORD)
        self.txt_display.pack(fill=tk.BOTH, expand=True)
        # Tag für Überschriften/Namen
        self.txt_display.tag_configure("speaker", foreground=COLORS["accent"], font=("Segoe UI", 12, "bold"))

        # Progress Bar
        self.progress_read = ttk.Progressbar(content, style="green.Horizontal.TProgressbar", mode="determinate")
        self.progress_read.pack(fill=tk.X, pady=(20, 5))
        
        self.lbl_progress_text = tk.Label(content, text="", bg=COLORS["bg"], fg="#888888", font=("Segoe UI", 9))
        self.lbl_progress_text.pack(anchor="e")

        # Controls Footer
        footer = tk.Frame(self.root, bg=COLORS["panel"], height=100)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        
        # Left: Main Actions
        frame_actions = tk.Frame(footer, bg=COLORS["panel"])
        frame_actions.pack(side=tk.LEFT, padx=30, pady=20)

        self.btn_learn = tk.Button(frame_actions, text="Lernen", command=self.start_learning_sequence,
                                   bg=COLORS["accent"], fg="white", font=FONT_H2, relief="flat", width=20)
        self.btn_learn.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_read = tk.Button(frame_actions, text="LESEN", command=self.scan_once, state=tk.DISABLED,
                                  bg=COLORS["success"], fg="white", font=FONT_H2, relief="flat", width=20)
        self.btn_read.pack(side=tk.LEFT)

        # Center: Audio Controls
        frame_audio = tk.Frame(footer, bg=COLORS["panel"])
        frame_audio.pack(side=tk.LEFT, padx=30)

        self.btn_pause = tk.Button(frame_audio, text="⏸", command=self.toggle_pause,
                                   bg=COLORS["warning"], fg="black", font=("Segoe UI", 14), relief="flat", width=4)
        self.btn_pause.pack(side=tk.LEFT, padx=5)

        self.btn_stop = tk.Button(frame_audio, text="⏹", command=self.stop_audio,
                                  bg=COLORS["danger"], fg="white", font=("Segoe UI", 14), relief="flat", width=4)
        self.btn_stop.pack(side=tk.LEFT, padx=5)

        # Volume Slider
        frame_vol = tk.Frame(frame_audio, bg=COLORS["panel"])
        frame_vol.pack(side=tk.LEFT, padx=15)
        tk.Label(frame_vol, text="Vol", bg=COLORS["panel"], fg="#aaa").pack()
        self.scale_vol = tk.Scale(frame_vol, from_=0, to=100, orient=tk.HORIZONTAL, bg=COLORS["panel"], fg="white", 
                                  highlightthickness=0, length=100, command=self.update_volume)
        self.scale_vol.set(100)
        self.scale_vol.pack()

        # Right: Target Info
        self.lbl_target = tk.Label(footer, text="-", bg=COLORS["panel"], fg=COLORS["accent"], font=("Segoe UI", 10, "bold"))
        self.lbl_target.pack(side=tk.RIGHT, padx=30)


    # --- SETTINGS WINDOW ---
    def open_settings_window(self):
        sw = tk.Toplevel(self.root)
        sw.title("Einstellungen")
        sw.geometry("450x500")
        sw.configure(bg=COLORS["panel"])
        sw.attributes("-topmost", True)

        tk.Label(sw, text="Tastenbelegung", bg=COLORS["panel"], fg="white", font=FONT_H2).pack(pady=15)

        def create_binder(label_text, setting_key):
            f = tk.Frame(sw, bg=COLORS["panel"])
            f.pack(pady=5, fill=tk.X, padx=30)
            tk.Label(f, text=label_text, bg=COLORS["panel"], fg="#ccc", width=20, anchor="w").pack(side=tk.LEFT)
            
            curr = self.settings_mgr.get(setting_key)
            btn = tk.Button(f, text=curr.upper(), bg=COLORS["bg"], fg="white", width=12, relief="flat")
            btn.pack(side=tk.RIGHT)
            
            def on_click():
                btn.config(text="Drücken...", bg=COLORS["accent"])
                sw.focus()
                def on_key(e):
                    self.settings_mgr.set(setting_key, e.name)
                    btn.config(text=e.name.upper(), bg=COLORS["bg"])
                    keyboard.unhook(on_key)
                    self.register_hotkeys()
                keyboard.on_press(on_key, suppress=True)
            btn.config(command=on_click)

        create_binder("Vorlesen:", "hotkey_read")
        create_binder("Lernen:", "hotkey_learn")
        create_binder("Stoppen:", "hotkey_stop")
        create_binder("Pause:", "hotkey_pause")

        tk.Frame(sw, bg="#444", height=1).pack(fill=tk.X, padx=20, pady=20)

        # Debug Checkbox
        tk.Label(sw, text="Entwickler-Optionen", bg=COLORS["panel"], fg="white", font=FONT_H2).pack(pady=5)
        
        chk_debug_var = tk.BooleanVar(value=self.settings_mgr.get("debug_mode"))
        def toggle_debug():
            val = chk_debug_var.get()
            self.settings_mgr.set("debug_mode", val)
            
        chk = tk.Checkbutton(sw, text="Debug-Modus (Dateien speichern)", variable=chk_debug_var, 
                             bg=COLORS["panel"], fg="#ccc", selectcolor=COLORS["bg"], 
                             activebackground=COLORS["panel"], activeforeground="white",
                             command=toggle_debug)
        chk.pack(pady=10)


    # --- LOGIK ---
    def toggle_pause(self):
        is_paused = self.audio.toggle_pause()
        if is_paused:
            self.btn_pause.config(bg=COLORS["success"], text="▶")
            self.log_user("⏸ Pausiert")
        else:
            self.btn_pause.config(bg=COLORS["warning"], text="⏸")
            self.log_user("▶ Läuft")

    def update_volume(self, val):
        if self.audio: self.audio.set_volume(val)

    def update_progress(self, current, total, text_sentence=""):
        self.root.after(0, lambda: self._gui_update_progress(current, total, text_sentence))
        
    def _gui_update_progress(self, current, total, text_sentence):
        self.progress_read["maximum"] = total
        self.progress_read["value"] = current
        self.lbl_progress_text.config(text=f"Satz {current}/{total}")
        
        # Aktuellen Satz hervorheben (im Textfeld suchen)
        # Fürs erste scrollen wir einfach zum Ende
        self.txt_display.see(tk.END)
        
        if current >= total:
            self.lbl_status.config(text="Fertig gelesen.")
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
            self.log_user("Keine Ecken gelernt! Bitte Taste drücken.")
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
            
            self.root.after(0, lambda: self.lbl_target.config(text=f"{target} ({v_name})"))

            # Hide Main Window for Screenshot
            self.root.after(0, self.root.withdraw)
            time.sleep(0.2)

            found_area = self.scan_for_window()
            
            if not found_area:
                self.log_user("❌ Fenster nicht gefunden")
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

            # Save Raw if Debug
            if debug:
                cv2.imwrite(os.path.join(self.debug_dir, "last_scan_raw.png"), cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR))
            
            processed_img = self.preprocess_image(img_np)
            if debug:
                cv2.imwrite(os.path.join(self.debug_dir, "last_scan_processed.png"), processed_img)
            
            results = self.reader.readtext(processed_img, detail=0, paragraph=True)
            
            # Formatierten Text bauen
            full_text_raw = " ".join(results).strip()
            # Zeilenumbrüche für die Anzeige verschönern (optional)
            display_text = "\n\n".join(results) 

            if full_text_raw and len(full_text_raw) > 3:
                self.log_user(f"Text erkannt ({len(full_text_raw)} Zeichen). Generiere Audio...")
                
                # Textbox updaten
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
            if debug: self.log_debug(f"Scan Exception: {e}")
            self.root.after(0, self.root.deiconify)
        finally:
            self.is_scanning = False

    def display_result(self, speaker, text):
        """Zeigt den Text schön in der großen Box an"""
        self.txt_display.delete("1.0", tk.END)
        self.txt_display.insert(tk.END, f"{speaker}:\n", "speaker")
        self.txt_display.insert(tk.END, text)

    def stop_audio(self):
        self.audio.stop()
        self.progress_read["value"] = 0
        self.lbl_status.config(text="Abgebrochen.")
        self.btn_pause.config(text="⏸", bg=COLORS["warning"])
        self.log_user("Gestoppt.")

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
                self.log_user("Bereit zum Vorlesen.")
            except: pass
        else:
            self.log_user("Bitte Ecken einlernen.")

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
