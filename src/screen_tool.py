import tkinter as tk
import pyautogui

class SnippingTool:
    def __init__(self, root, callback):
        self.root = root
        self.callback = callback
        self.start_x = None
        self.start_y = None
        self.rect = None

        # Overlay Fenster erstellen
        self.top = tk.Toplevel(root)
        self.top.attributes('-fullscreen', True)
        self.top.attributes('-alpha', 0.3)
        self.top.configure(bg="black")
        self.top.attributes('-topmost', True)

        self.canvas = tk.Canvas(self.top, cursor="cross", bg="grey11")
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

    def on_button_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, 1, 1, outline='red', width=3)

    def on_move_press(self, event):
        curX, curY = (event.x, event.y)
        self.canvas.coords(self.rect, self.start_x, self.start_y, curX, curY)

    def on_button_release(self, event):
        end_x, end_y = (event.x, event.y)
        
        # Koordinaten berechnen (Links, Oben, Breite, Höhe)
        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        width = abs(end_x - self.start_x)
        height = abs(end_y - self.start_y)
        
        self.top.destroy()
        
        if width > 10 and height > 10:
            self.callback(x1, y1, width, height)
