import tkinter as tk
from PIL import Image, ImageTk, ImageEnhance # Pillow für Bildbearbeitung
import pyautogui
import os
import time

class DynamicSnipper(tk.Toplevel):
    def __init__(self, parent, resources_path, on_complete):
        super().__init__(parent)
        self.withdraw() # Erstmal unsichtbar
        self.parent = parent
        self.resources_path = resources_path
        self.on_complete = on_complete
        
        # Setup Variablen
        self.step = 1 # 1 = Top-Left, 2 = Bottom-Right
        self.start_x = None
        self.start_y = None
        self.rect = None
        self.current_rect_coords = None

        # 1. SCREENSHOT MACHEN (Vom hellen Spiel)
        # Wir verstecken das Hauptfenster kurz
        self.parent.iconify() 
        self.parent.update()
        time.sleep(0.3) # Kurz warten bis Animation fertig
        
        try:
            # Screenshot machen
            self.original_image = pyautogui.screenshot()
            
            # Für die Anzeige im Editor dunkeln wir das Bild etwas ab (visueller Effekt),
            # damit man den Auswahlrahmen besser sieht.
            # Das Template wird später aber vom ORIGINAL (hellen) Bild ausgeschnitten.
            enhancer = ImageEnhance.Brightness(self.original_image)
            self.dark_image = enhancer.enhance(0.5) # 50% Helligkeit für den Hintergrund
            
            self.tk_image = ImageTk.PhotoImage(self.dark_image)
            
        except Exception as e:
            print(f"Screenshot Fehler: {e}")
            self.close(False)
            return

        # 2. FENSTER AUFBAUEN (Vollbild mit Screenshot)
        self.attributes('-fullscreen', True)
        self.attributes('-topmost', True)
        self.configure(cursor="cross")

        self.canvas = tk.Canvas(self, cursor="cross", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Screenshot als Hintergrund setzen
        self.canvas.create_image(0, 0, image=self.tk_image, anchor="nw")

        # Anleitung
        self.lbl_info = tk.Label(self, text="", fg="white", bg="#333333", font=("Segoe UI", 14, "bold"), padx=10, pady=5)
        self.lbl_info.place(relx=0.5, rely=0.1, anchor="n")
        
        self.update_instruction()

        # Events
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Escape>", lambda e: self.close(False))
        self.bind("<Return>", lambda e: self.confirm_selection()) # Enter zum Bestätigen

        self.deiconify() # Jetzt anzeigen

    def update_instruction(self):
        if self.step == 1:
            self.lbl_info.config(text="SCHRITT 1/2: Markiere den Anker OBEN LINKS (z.B. Ring-Icon)", bg="#b81b1b") # Rot
        else:
            self.lbl_info.config(text="SCHRITT 2/2: Markiere den Anker UNTEN RECHTS (z.B. 'Annehmen'-Button)", bg="#0057b8") # Blau

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        
        # Altes Rechteck löschen
        if self.rect: self.canvas.delete(self.rect)
        
        color = "red" if self.step == 1 else "cyan"
        # Wir zeichnen den Rahmen
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline=color, width=2)

    def on_drag(self, event):
        if self.rect:
            self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def on_release(self, event):
        # Koordinaten speichern
        x1, y1 = min(self.start_x, event.x), min(self.start_y, event.y)
        x2, y2 = max(self.start_x, event.x), max(self.start_y, event.y)
        
        # Speichern für Bestätigung
        self.current_rect_coords = (x1, y1, x2-x1, y2-y1)
        
        # Automatisch weiter nach kurzem Loslassen? 
        # Besser: Wir machen es direkt, wie beim Windows Snipping Tool
        self.confirm_selection()

    def confirm_selection(self):
        if not self.current_rect_coords: return
        
        x, y, w, h = self.current_rect_coords
        if w < 5 or h < 5: return # Zu klein (nur ein Klick)

        try:
            # WICHTIG: Wir schneiden vom ORIGINALEN (hellen) Bild aus!
            crop = self.original_image.crop((x, y, x+w, y+h))
            
            if self.step == 1:
                path = os.path.join(self.resources_path, "template_tl.png")
                crop.save(path)
                
                # Weiter zu Schritt 2
                self.step = 2
                self.canvas.delete(self.rect)
                self.current_rect_coords = None
                self.update_instruction()
                
            elif self.step == 2:
                path = os.path.join(self.resources_path, "template_br.png")
                crop.save(path)
                
                # Fertig
                self.close(True)
                
        except Exception as e:
            print(f"Fehler beim Speichern: {e}")
            self.close(False)

    def close(self, success=False):
        self.parent.deiconify() # Hauptfenster wiederherstellen
        self.destroy()
        if self.on_complete:
            self.on_complete(success)
