import tkinter as tk
import pyautogui
import os

class DynamicSnipper(tk.Toplevel):
    def __init__(self, parent, resources_path, on_complete):
        super().__init__(parent)
        self.withdraw()
        self.parent = parent
        self.resources_path = resources_path
        self.on_complete = on_complete
        
        # Setup Variablen
        self.step = 1 # 1 = Top-Left, 2 = Bottom-Right
        
        # UI Setup (Vollbild, Transparent)
        self.attributes('-fullscreen', True)
        self.attributes('-alpha', 0.3)
        self.configure(bg='black', cursor="cross")
        
        self.canvas = tk.Canvas(self, cursor="cross", bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Anleitungstext
        self.lbl_info = tk.Label(self, text="", fg="white", font=("Arial", 14, "bold"))
        self.lbl_info.place(relx=0.5, rely=0.1, anchor="n")
        
        self.update_instruction()

        # Maus Events
        self.start_x = None
        self.start_y = None
        self.rect = None

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Escape>", lambda e: self.close())

        self.deiconify()

    def update_instruction(self):
        if self.step == 1:
            self.lbl_info.config(text="SCHRITT 1/2: Markiere die OBERE LINKE Ecke (Anker)", bg="red")
        else:
            self.lbl_info.config(text="SCHRITT 2/2: Markiere die UNTERE RECHTE Ecke (Ende)", bg="blue")

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect: self.canvas.delete(self.rect)
        color = "red" if self.step == 1 else "cyan"
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline=color, width=2)

    def on_drag(self, event):
        if self.rect:
            self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def on_release(self, event):
        x1, y1 = min(self.start_x, event.x), min(self.start_y, event.y)
        x2, y2 = max(self.start_x, event.x), max(self.start_y, event.y)
        w, h = x2 - x1, y2 - y1

        if w < 10 or h < 10: return

        if self.step == 1:
            # Speichere Top-Left Template
            path = os.path.join(self.resources_path, "template_tl.png")
            pyautogui.screenshot(region=(x1, y1, w, h)).save(path)
            
            # Weiter zu Schritt 2
            self.step = 2
            self.canvas.delete(self.rect)
            self.update_instruction()
            
        elif self.step == 2:
            # Speichere Bottom-Right Template
            path = os.path.join(self.resources_path, "template_br.png")
            pyautogui.screenshot(region=(x1, y1, w, h)).save(path)
            
            self.close(True)

    def close(self, success=False):
        self.destroy()
        if self.on_complete:
            self.on_complete(success)
