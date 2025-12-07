import tkinter as tk
import pyautogui
import os

class SnippingTool(tk.Toplevel):
    def __init__(self, parent, save_path, on_complete):
        super().__init__(parent)
        self.withdraw() # Erstmal verstecken
        self.parent = parent
        self.save_path = save_path
        self.on_complete = on_complete
        
        # Vollbild über alle Monitore
        self.attributes('-fullscreen', True)
        self.attributes('-alpha', 0.3) # 30% Transparenz (Dunkel)
        self.configure(bg='black')
        self.configure(cursor="cross")

        # Canvas zum Zeichnen des Rechtecks
        self.canvas = tk.Canvas(self, cursor="cross", bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Variablen für Maus-Position
        self.start_x = None
        self.start_y = None
        self.rect = None

        # Events binden
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        
        # Escape zum Abbrechen
        self.bind("<Escape>", lambda e: self.close())

        self.deiconify() # Jetzt anzeigen

    def on_button_press(self, event):
        # Startpunkt speichern
        self.start_x = event.x
        self.start_y = event.y
        # Altes Rechteck löschen falls vorhanden
        if self.rect:
            self.canvas.delete(self.rect)
        # Rotes Auswahl-Rechteck erstellen
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='red', width=2)

    def on_move_press(self, event):
        # Rechteck Größe aktualisieren während man zieht
        if self.rect:
            self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def on_button_release(self, event):
        # Koordinaten berechnen
        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)
        
        width = x2 - x1
        height = y2 - y1

        # Wenn die Auswahl zu klein war (z.B. nur ein Klick), abbrechen
        if width < 10 or height < 10:
            self.close()
            return

        # Fenster kurz verstecken, damit es nicht auf dem Screenshot ist
        self.withdraw()
        self.parent.update() # GUI Update erzwingen

        # Screenshot machen
        try:
            screenshot = pyautogui.screenshot(region=(x1, y1, width, height))
            screenshot.save(self.save_path)
            print(f"Template gespeichert: {self.save_path}")
            if self.on_complete:
                self.on_complete(True)
        except Exception as e:
            print(f"Fehler beim Snipping: {e}")
            if self.on_complete:
                self.on_complete(False)
        
        self.destroy()

    def close(self):
        self.destroy()
        if self.on_complete:
            self.on_complete(False)
