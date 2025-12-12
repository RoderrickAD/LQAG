import tkinter as tk
from PIL import Image, ImageTk, ImageEnhance
import pyautogui
import os
import time

class DynamicSnipper(tk.Toplevel):
    def __init__(self, parent, resources_path, on_complete):
        super().__init__(parent)
        self.withdraw()
        self.parent = parent
        self.resources_path = resources_path
        self.on_complete = on_complete
        self.step = 1
        self.start_x = None
        self.start_y = None
        self.rect = None
        self.current_rect_coords = None

        # FREEZE
        self.parent.iconify() 
        self.parent.update()
        time.sleep(0.3)
        
        try:
            self.original_image = pyautogui.screenshot()
            enhancer = ImageEnhance.Brightness(self.original_image)
            self.dark_image = enhancer.enhance(0.5)
            self.tk_image = ImageTk.PhotoImage(self.dark_image)
        except:
            self.close(False)
            return

        self.attributes('-fullscreen', True)
        self.attributes('-topmost', True)
        self.configure(cursor="cross")

        self.canvas = tk.Canvas(self, cursor="cross", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.create_image(0, 0, image=self.tk_image, anchor="nw")

        self.lbl_info = tk.Label(self, text="", fg="white", bg="#333333", font=("Arial", 14, "bold"), padx=10)
        self.lbl_info.place(relx=0.5, rely=0.1, anchor="n")
        self.update_instruction()

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Escape>", lambda e: self.close(False))
        self.bind("<Return>", lambda e: self.confirm_selection())
        self.deiconify()

    def update_instruction(self):
        if self.step == 1: self.lbl_info.config(text="SCHRITT 1/2: Oben Links (Icon)", bg="red")
        else: self.lbl_info.config(text="SCHRITT 2/2: Unten Rechts (Button)", bg="blue")

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect: self.canvas.delete(self.rect)
        color = "red" if self.step == 1 else "cyan"
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline=color, width=2)

    def on_drag(self, event):
        if self.rect: self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def on_release(self, event):
        x1, y1 = min(self.start_x, event.x), min(self.start_y, event.y)
        x2, y2 = max(self.start_x, event.x), max(self.start_y, event.y)
        self.current_rect_coords = (x1, y1, x2-x1, y2-y1)
        self.confirm_selection()

    def confirm_selection(self):
        if not self.current_rect_coords: return
        x, y, w, h = self.current_rect_coords
        if w < 5: return

        try:
            crop = self.original_image.crop((x, y, x+w, y+h))
            if self.step == 1:
                crop.save(os.path.join(self.resources_path, "template_tl.png"))
                self.step = 2
                self.canvas.delete(self.rect)
                self.current_rect_coords = None
                self.update_instruction()
            elif self.step == 2:
                crop.save(os.path.join(self.resources_path, "template_br.png"))
                self.close(True)
        except: self.close(False)

    def close(self, success=False):
        self.parent.deiconify()
        self.destroy()
        if self.on_complete: self.on_complete(success)
