import sys
import os
import datetime
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk, filedialog # filedialog hinzugefügt
import ctypes
import numpy as np
import cv2
import pyautogui
import keyboard
import easyocr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except: pass

COLORS = {"bg": "#1e1e1e", "panel": "#252526", "fg": "#ffffff", "accent": "#007acc", "success": "#28a745", "warning": "#ffc107", "danger": "#dc3545", "text_bg": "#1a1a1a", "border": "#3e3e42"}
FONT_BIG = ("Segoe UI", 14, "bold")
FONT_NORM = ("Segoe UI", 11)

class App:
    def __init__(self):
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.debug_dir = os.path.join(self.root_dir, "debug")
        self.cache_dir = os.path.join(self.root_dir, "resources", "cache")
        os.makedirs(self.debug_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)

        from npc_manager import NpcManager
        from settings_manager import SettingsManager
        from audio_engine import AudioEngine
        from screen_tool import SnippingTool
        self.npc_manager = NpcManager()
        self.settings_mgr = SettingsManager(self.root_dir)
        self.audio = AudioEngine()
        self.reader = easyocr.Reader(['de', 'en'], gpu=True)
        self.SnippingTool = SnippingTool
        
        self.root = tk.Tk()
        self.root.title("LQAG Vorleser V25")
        self.root.geometry("1000x900")
        self.root.configure(bg=COLORS["bg"])
        
        style = ttk.Style()
        style.theme_use('alt')
        style.configure('TNotebook', background=COLORS["bg"], borderwidth=0)
        style.configure('TNotebook.Tab', background=COLORS["panel"], foreground="white", padding=[20, 10], font=FONT_NORM)
        style.map('TNotebook.Tab', background=[('selected', COLORS["accent"])])
        style.configure("green.Horizontal.TProgressbar", background=COLORS["accent"], thickness=10, troughcolor=COLORS["panel"], borderwidth=0)

        self.setup_ui()
        self.register_hotkeys()
        self.is_scanning = False
        self.template_tl = None
        
        self.root.after(500, self.load_cached_templates)
        self.root.mainloop()

    def setup_ui(self):
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill=tk.BOTH, expand=True)
        self.tab1 = tk.Frame(self.nb, bg=COLORS["bg"]); self.nb.add(self.tab1, text=" Vorlesen ")
        self.tab2 = tk.Frame(self.nb, bg=COLORS["bg"]); self.nb.add(self.tab2, text=" Einstellungen ")
        self.setup_tab_main()
        self.setup_tab_settings()

    def setup_tab_main(self):
        c = tk.Frame(self.tab1, bg=COLORS["bg"]); c.pack(fill=tk.BOTH, expand=True, padx=30, pady=20)
        f1 = tk.Frame(c, bg=COLORS["bg"]); f1.pack(fill=tk.X, pady=(0, 10))
        self.lbl_status = tk.Label(f1, text="Bereit.", bg=COLORS["bg"], fg="#aaa", font=FONT_NORM); self.lbl_status.pack(side=tk.LEFT)
        self.lbl_target = tk.Label(f1, text="-", bg=COLORS["panel"], fg=COLORS["accent"], padx=10); self.lbl_target.pack(side=tk.RIGHT)
        self.txt = tk.Text(c, bg=COLORS["text_bg"], fg="#eee", font=("Segoe UI", 12), relief="flat", highlightthickness=1, highlightbackground=COLORS["border"], padx=20, pady=20, wrap=tk.WORD, height=18); self.txt.pack(fill=tk.BOTH, expand=True)
        self.txt.tag_configure("speaker", foreground=COLORS["accent"], font=("Segoe UI", 12, "bold"))
        self.pb = ttk.Progressbar(c, style="green.Horizontal.TProgressbar", mode="determinate"); self.pb.pack(fill=tk.X, pady=(15, 5))
        self.lbl_pb = tk.Label(c, text="0 / 0", bg=COLORS["bg"], fg="#666"); self.lbl_pb.pack(anchor="e")
        bt = tk.Frame(c, bg=COLORS["bg"], pady=20); bt.pack(fill=tk.X, side=tk.BOTTOM)
        self.btn_l = tk.Button(bt, text="Lernen", command=self.start_learning_sequence, bg=COLORS["panel"], fg="white", font=FONT_BIG, relief="flat", padx=20, pady=10); self.btn_l.pack(side=tk.LEFT, padx=(0, 10))
        self.btn_r = tk.Button(bt, text="VORLESEN", command=self.scan_once, state=tk.DISABLED, bg=COLORS["success"], fg="white", font=FONT_BIG, relief="flat", padx=20, pady=10); self.btn_r.pack(side=tk.LEFT)
        tk.Button(bt, text="⏹", command=self.stop_audio, bg=COLORS["danger"], fg="white", font=FONT_BIG, relief="flat", padx=15, pady=10).pack(side=tk.RIGHT, padx=5)
        self.btn_p = tk.Button(bt, text="⏸", command=self.toggle_pause, bg=COLORS["warning"], fg="black", font=FONT_BIG, relief="flat", padx=15, pady=10); self.btn_p.pack(side=tk.RIGHT, padx=5)

    def setup_tab_settings(self):
        c = tk.Frame(self.tab2, bg=COLORS["bg"]); c.pack(fill=tk.BOTH, expand=True, padx=50, pady=30)
        
        # --- PLUGINS DATEI WAHL ---
        tk.Label(c, text="Plugin Datei (target.txt):", bg=COLORS["bg"], fg="white", font=FONT_NORM).pack(anchor="w", pady=(0, 5))
        f_plug = tk.Frame(c, bg=COLORS["bg"]); f_plug.pack(fill=tk.X, pady=(0, 20))
        self.ent_plug = tk.Entry(f_plug, bg=COLORS["text_bg"], fg="#aaa", relief="flat"); 
        self.ent_plug.insert(0, self.settings_mgr.get("plugin_target_path")); self.ent_plug.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(f_plug, text="Durchsuchen...", command=self.choose_plugin_file, bg=COLORS["panel"], fg="white").pack(side=tk.LEFT, padx=5)
        
        tk.Frame(c, bg=COLORS["border"], height=1).pack(fill=tk.X, pady=10)

        self.create_binder(c, "Vorlesen:", "hotkey_read")
        self.create_binder(c, "Lernen:", "hotkey_learn")
        self.create_binder(c, "Stoppen:", "hotkey_stop")
        self.create_binder(c, "Pause:", "hotkey_pause")
        
        tk.Frame(c, bg=COLORS["border"], height=1).pack(fill=tk.X, pady=25)
        
        self.chk_el = tk.BooleanVar(value=self.settings_mgr.get("use_elevenlabs"))
        tk.Checkbutton(c, text="ElevenLabs nutzen", variable=self.chk_el, command=lambda: self.settings_mgr.set("use_elevenlabs", self.chk_el.get()), bg=COLORS["bg"], fg="#ccc", selectcolor=COLORS["bg"]).pack(anchor="w")
        
        api_f = tk.Frame(c, bg=COLORS["bg"]); api_f.pack(fill=tk.X, pady=10)
        tk.Label(api_f, text="API Key:", bg=COLORS["bg"], fg="#888").pack(side=tk.LEFT)
        self.ent_api = tk.Entry(api_f, bg=COLORS["text_bg"], fg="white", relief="flat"); self.ent_api.insert(0, self.settings_mgr.get("elevenlabs_api_key")); self.ent_api.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Button(api_f, text="Save", command=lambda: self.settings_mgr.set("elevenlabs_api_key", self.ent_api.get()), bg=COLORS["accent"], fg="white").pack(side=tk.LEFT)
        
        tk.Button(c, text="🚀 Bibliothek dynamisch aufbauen", command=self.start_library_generation, bg=COLORS["success"], fg="white", pady=10).pack(fill=tk.X, pady=20)
        
        self.chk_db = tk.BooleanVar(value=self.settings_mgr.get("debug_mode"))
        tk.Checkbutton(c, text="Debug-Modus (Bilder/Text speichern)", variable=self.chk_db, command=lambda: self.settings_mgr.set("debug_mode", self.chk_db.get()), bg=COLORS["bg"], fg="#ccc", selectcolor=COLORS["bg"]).pack(anchor="w")
        
        vol_f = tk.Frame(c, bg=COLORS["bg"]); vol_f.pack(fill=tk.X, pady=10)
        tk.Label(vol_f, text="Vol:", bg=COLORS["bg"], fg="#ccc").pack(side=tk.LEFT)
        s = tk.Scale(vol_f, from_=0, to=100, orient=tk.HORIZONTAL, bg=COLORS["bg"], fg="white", command=self.audio.set_volume); s.set(100); s.pack(side=tk.LEFT, padx=10)

    def choose_plugin_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text Dateien", "*.txt"), ("Alle Dateien", "*.*")])
        if file_path:
            self.settings_mgr.set("plugin_target_path", file_path)
            self.ent_plug.delete(0, tk.END)
            self.ent_plug.insert(0, file_path)

    def create_binder(self, parent, label, key):
        f = tk.Frame(parent, bg=COLORS["bg"]); f.pack(fill=tk.X, pady=3)
        tk.Label(f, text=label, bg=COLORS["bg"], fg="#ccc", width=15, anchor="w").pack(side=tk.LEFT)
        b = tk.Button(f, text=self.settings_mgr.get(key).upper(), bg=COLORS["panel"], fg="white", width=12, relief="flat"); b.pack(side=tk.LEFT, padx=10)
        def click():
            b.config(text="...", bg=COLORS["accent"])
            def press(e):
                self.settings_mgr.set(key, e.name); b.config(text=e.name.upper(), bg=COLORS["panel"]); keyboard.unhook(press); self.register_hotkeys()
            keyboard.on_press(press, suppress=True)
        b.config(command=click)

    def register_hotkeys(self):
        try:
            try: keyboard.unhook_all()
            except: pass
            keyboard.add_hotkey(self.settings_mgr.get("hotkey_read"), self.scan_once)
            keyboard.add_hotkey(self.settings_mgr.get("hotkey_learn"), self.start_learning_sequence)
            keyboard.add_hotkey(self.settings_mgr.get("hotkey_stop"), self.stop_audio)
            keyboard.add_hotkey(self.settings_mgr.get("hotkey_pause"), self.toggle_pause)
            self.btn_r.config(text=f"VORLESEN ({self.settings_mgr.get('hotkey_read').upper()})")
            self.btn_l.config(text=f"Lernen ({self.settings_mgr.get('hotkey_learn').upper()})")
        except: pass

    def start_library_generation(self):
        threading.Thread(target=self._run_lib, daemon=True).start()
    def _run_lib(self):
        self.audio.generate_voice_library(self.settings_mgr.get_all(), self.update_progress)
        self.lbl_status.config(text="Bibliothek fertig!")

    def scan_once(self):
        if self.is_scanning or self.template_tl is None: return
        self.is_scanning = True; threading.Thread(target=self._run_scan, daemon=True).start()
        
    def _run_scan(self):
        db = self.settings_mgr.get("debug_mode")
        plug_path = self.settings_mgr.get("plugin_target_path")
        
        try:
            # HIER WIRD JETZT DER PFAD ÜBERGEBEN
            self.npc_manager.update(plug_path)
            
            target = self.npc_manager.current_target; v_ref = self.npc_manager.get_voice_path()
            self.root.after(0, lambda: self.lbl_target.config(text=target))
            self.root.after(0, self.root.withdraw); time.sleep(0.3); area = self.scan_for_window(); self.root.after(0, self.root.deiconify)
            if not area: self.is_scanning = False; return
            img = np.array(pyautogui.screenshot(region=area))
            if db: cv2.imwrite(os.path.join(self.debug_dir, "last_scan_raw.jpg"), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
            proc = cv2.threshold(cv2.cvtColor(cv2.resize(cv2.cvtColor(img, cv2.COLOR_RGB2BGR), None, fx=3, fy=3), cv2.COLOR_BGR2GRAY), 90, 255, cv2.THRESH_TOZERO)[1]
            if db: cv2.imwrite(os.path.join(self.debug_dir, "last_scan_processed.jpg"), proc)
            txt = " ".join(self.reader.readtext(proc, detail=0, paragraph=True)).strip()
            if db: 
                with open(os.path.join(self.debug_dir, "last_recognized_text.txt"), "w", encoding="utf-8") as f: f.write(txt)
            if len(txt) > 3:
                self.root.after(0, lambda: self.display_result(target, txt))
                self.audio.speak(txt, v_ref, self.settings_mgr.get_all(), on_progress=self.update_progress)
        except: pass
        finally: self.is_scanning = False

    def display_result(self, speaker, text):
        self.txt.delete("1.0", tk.END); self.txt.insert(tk.END, f"{speaker}:\n", "speaker"); self.txt.insert(tk.END, text)
    def update_progress(self, cur, tot, txt=""):
        self.root.after(0, lambda: self._gui_up(cur, tot))
    def _gui_up(self, cur, tot):
        self.pb["maximum"] = tot; self.pb["value"] = cur; self.lbl_pb.config(text=f"{cur} / {tot}")
        if cur >= tot: self.lbl_status.config(text="Audio wurde Erstellt."); self.pb["value"] = 0
    def stop_audio(self): self.audio.stop(); self.pb["value"] = 0; self.lbl_status.config(text="Abgebrochen.")
    def toggle_pause(self): 
        p = self.audio.toggle_pause(); self.btn_p.config(bg=COLORS["success"] if p else COLORS["warning"], text="▶" if p else "⏸")
    def start_learning_sequence(self):
        self.root.withdraw(); time.sleep(0.2); self.SnippingTool(self.root, self._step1)
    def _step1(self, x, y, w, h):
        self.template_tl = cv2.cvtColor(np.array(pyautogui.screenshot(region=(x, y, w, h))), cv2.COLOR_RGB2BGR)
        self.root.deiconify(); messagebox.showinfo("2", "UNTEN-RECHTS"); self.root.withdraw(); self.SnippingTool(self.root, self._step2)
    def _step2(self, x, y, w, h):
        self.template_br = cv2.cvtColor(np.array(pyautogui.screenshot(region=(x, y, w, h))), cv2.COLOR_RGB2BGR)
        self.root.deiconify(); cv2.imwrite(os.path.join(self.cache_dir, "last_tl.png"), self.template_tl); cv2.imwrite(os.path.join(self.cache_dir, "last_br.png"), self.template_br)
        if self.scan_for_window(): self.btn_r.config(state=tk.NORMAL); self.lbl_status.config(text="Gelernt!")
    def load_cached_templates(self):
        p = os.path.join(self.cache_dir, "last_tl.png")
        if os.path.exists(p): self.template_tl = cv2.imread(p); self.template_br = cv2.imread(os.path.join(self.cache_dir, "last_br.png")); self.btn_r.config(state=tk.NORMAL); self.lbl_status.config(text="Bereit.")
    def scan_for_window(self):
        if self.template_tl is None: return None
        scr = cv2.cvtColor(np.array(pyautogui.screenshot()), cv2.COLOR_RGB2BGR)
        tl = cv2.minMaxLoc(cv2.matchTemplate(scr, self.template_tl, cv2.TM_CCOEFF_NORMED))[3]
        br = cv2.minMaxLoc(cv2.matchTemplate(scr, self.template_br, cv2.TM_CCOEFF_NORMED))[3]
        return (tl[0], tl[1], (br[0] + self.template_br.shape[1]) - tl[0], (br[1] + self.template_br.shape[0]) - tl[1])

if __name__ == "__main__": App()
