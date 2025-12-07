import logging
import sys
import tkinter as tk

class TextHandler(logging.Handler):
    """
    Ein spezieller Log-Handler, der Nachrichten in ein Tkinter-Textfeld schreibt.
    Er nutzt .after(), um Thread-Safe zu sein (wichtig, da der Worker in einem anderen Thread läuft).
    """
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        def append():
            if self.text_widget:
                # Schreibschutz kurz aufheben, Text rein, Schreibschutz wieder an
                self.text_widget.configure(state='normal')
                self.text_widget.insert(tk.END, msg + '\n')
                self.text_widget.see(tk.END) # Autoscroll nach unten
                self.text_widget.configure(state='disabled')
        
        # Leitet den GUI-Update-Befehl an den Haupt-Thread weiter
        try:
            self.text_widget.after(0, append)
        except Exception:
            pass # Falls das Fenster schon geschlossen wurde

def setup_logger(text_widget):
    """
    Konfiguriert das Logging-System mit 3 Ausgängen:
    1. GUI Fenster (Nur INFO, damit es übersichtlich bleibt)
    2. Konsole (DEBUG, für Entwickler)
    3. Datei 'debug_lqag.log' (DEBUG, speichert ALLES für die Fehlersuche)
    """
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG) # Wir fangen alles ab Level DEBUG auf
    
    # Vorherige Handler entfernen, falls vorhanden (verhindert doppelte Logs bei Reload)
    if logger.hasHandlers():
        logger.handlers.clear()

    # Wie soll der Log-Eintrag aussehen?
    # Beispiel: 12:30:45 - INFO - [worker] Text erkannt
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(module)s] %(message)s', datefmt='%H:%M:%S')

    # --- 1. GUI Handler (Das Fenster im Tool) ---
    gui_handler = TextHandler(text_widget)
    gui_handler.setLevel(logging.INFO) # Im Fenster zeigen wir nur wichtige Infos
    gui_handler.setFormatter(formatter)
    logger.addHandler(gui_handler)

    # --- 2. Console Handler (Das schwarze CMD Fenster, falls offen) ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG) # Hier zeigen wir alles
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # --- 3. File Handler (Die Log-Datei auf der Festplatte) ---
    # mode="w" bedeutet: Bei jedem Neustart wird die Datei überschrieben (sauberer Start)
    try:
        file_handler = logging.FileHandler("debug_lqag.log", mode="w", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG) # In der Datei speichern wir ALLES (auch technische Details)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Konnte Log-Datei nicht erstellen: {e}")
    
    return logger
