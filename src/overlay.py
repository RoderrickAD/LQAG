import tkinter as tk
from tkinter import ttk

class SubtitleOverlay:
    def __init__(self, root_ref):
        self.win = tk.Toplevel(root_ref)
        self.win.title("LQAG Overlay")
        
        # Design
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.8) # Etwas dunkler für besseren Kontrast
        self.win.configure(bg="#000000")
        
        # Position (Unten mittig)
        screen_w = self.win.winfo_screenwidth()
        screen_h = self.win.winfo_screenheight()
        w = 900
        h = 100
        x = (screen_w // 2) - (w // 2)
        y = screen_h - h - 120 
        
        self.win.geometry(f"{w}x{h}+{x}+{y}")
        
        # Sprecher Name
        self.lbl_speaker = tk.Label(self.win, text="", font=("Segoe UI", 10, "bold"), fg="#ffcc00", bg="black")
        self.lbl_speaker.pack(pady=(2, 0))
        
        # Der Text (Groß und deutlich)
        self.lbl_text = tk.Label(self.win, text="...", font=("Segoe UI", 16), fg="white", bg="black", wraplength=880)
        self.lbl_text.pack(pady=0, expand=True)
        
        # Fortschrittsbalken (ganz unten, sehr dünn)
        style = ttk.Style()
        style.theme_use('alt')
        style.configure("overlay.Horizontal.TProgressbar", background='#00ff00', thickness=5, troughcolor='black', borderwidth=0)
        
        self.progress = ttk.Progressbar(self.win, style="overlay.Horizontal.TProgressbar", mode='determinate', length=900)
        self.progress.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.visible_user_setting = False # Will der User es generell sehen?
        self.win.withdraw()
        
        # Drag & Drop
        self.win.bind("<Button-1>", self.start_move)
        self.win.bind("<B1-Motion>", self.do_move)
        self.x = 0
        self.y = 0

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.win.winfo_x() + deltax
        y = self.win.winfo_y() + deltay
        self.win.geometry(f"+{x}+{y}")

    def set_user_visible(self, state):
        self.visible_user_setting = state
        if state: self.win.deiconify()
        else: self.win.withdraw()

    def hide_temp(self):
        """Für Screenshots kurz verstecken"""
        self.win.withdraw()

    def restore(self):
        """Nach Screenshot wiederherstellen, falls User es an hat"""
        if self.visible_user_setting:
            self.win.deiconify()

    def update_content(self, speaker, current_sentence, progress_val, progress_max):
        if not self.visible_user_setting: return
        
        self.lbl_speaker.config(text=speaker)
        self.lbl_text.config(text=current_sentence)
        
        self.progress["maximum"] = progress_max
        self.progress["value"] = progress_val
        self.win.deiconify()
