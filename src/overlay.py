import tkinter as tk

class SubtitleOverlay:
    def __init__(self, root_ref):
        # Eigenes Toplevel Fenster
        self.win = tk.Toplevel(root_ref)
        self.win.title("LQAG Overlay")
        
        # Design: Rahmenlos, Immer oben, Halb-Transparent
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.75) # 75% Sichtbarkeit
        self.win.configure(bg="black")
        
        # Größe und Position (Unten mittig standardmäßig)
        screen_w = self.win.winfo_screenwidth()
        screen_h = self.win.winfo_screenheight()
        w = 800
        h = 120
        x = (screen_w // 2) - (w // 2)
        y = screen_h - h - 150 # Etwas über der Taskleiste
        
        self.win.geometry(f"{w}x{h}+{x}+{y}")
        
        # Inhalt
        self.lbl_speaker = tk.Label(self.win, text="", font=("Segoe UI", 12, "bold"), fg="#ffcc00", bg="black")
        self.lbl_speaker.pack(pady=(5, 0))
        
        self.lbl_text = tk.Label(self.win, text="Warte auf Text...", font=("Segoe UI", 14), fg="white", bg="black", wraplength=780)
        self.lbl_text.pack(pady=5)
        
        # Startzustand: Versteckt
        self.visible = False
        self.win.withdraw()
        
        # Drag & Drop Logik (damit man es verschieben kann)
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

    def show(self):
        self.visible = True
        self.win.deiconify()

    def hide(self):
        self.visible = False
        self.win.withdraw()

    def update_text(self, speaker, text):
        if not self.visible: return
        self.lbl_speaker.config(text=speaker)
        self.lbl_text.config(text=text)
        self.win.deiconify() # Sicherstellen dass es da ist
