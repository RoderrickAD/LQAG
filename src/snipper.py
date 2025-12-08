import tkinter as tk
import pyautogui
import os
import time  # WICHTIG: Für die kurze Wartezeit

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
        self.attributes('-alpha', 0.3) # Hier ist die Abdunkelung (30% sichtbar)
        self.configure(bg='black', cursor="cross")
        self.attributes('-topmost', True) # Immer im Vordergrund
        
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
            self.lbl_info.config(text="SCHRITT 1/2: Markiere ein eindeutiges Merkmal OBEN LINKS (z.B. Icon/Verzierung)", bg="red")
        else:
            self.lbl_info.config(text="SCHRITT 2/2: Markiere ein Merkmal UNTEN RECHTS (z.B. Button)", bg="blue")

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

        # --- DER FIX: Overlay kurz ausblenden! ---
        self.withdraw()             # Fenster verstecken
        self.parent.update()        # GUI Update erzwingen
        time.sleep(0.3)             # 300ms warten, bis das Spiel wieder hell ist
        # ----------------------------------------

        try:
            if self.step == 1:
                path = os.path.join(self.resources_path, "template_tl.png")
                # Screenshot vom HELLEN Bildschirm machen
                pyautogui.screenshot(region=(x1, y1, w, h)).save(path)
                
                # Overlay wieder anzeigen für Schritt 2
                self.deiconify()
                self.step = 2
                self.canvas.delete(self.rect)
                self.update_instruction()
                
            elif self.step == 2:
                path = os.path.join(self.resources_path, "template_br.png")
                # Screenshot vom HELLEN Bildschirm machen
                pyautogui.screenshot(region=(x1, y1, w, h)).save(path)
                
                self.close(True)
        except Exception as e:
            print(f"Fehler beim Snipping: {e}")
            self.close(False)

    def close(self, success=False):
        self.destroy()
        if self.on_complete:
            self.on_complete(success)
