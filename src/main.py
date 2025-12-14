import sys
import os
import time
import threading

# --- GUI TEST (Tkinter) ---
try:
    import tkinter as tk
    from tkinter import messagebox
    TK_OK = True
except ImportError as e:
    TK_OK = False
    TK_ERR = str(e)

if not TK_OK:
    print("CRITICAL: TKINTER FEHLT! Transplantation gescheitert.")
    print(f"Fehler: {TK_ERR}")
    input("Drücke Enter...")
    sys.exit()

# --- APP START ---
class TestApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LQAG Engine V3 - System Check")
        self.root.geometry("600x400")
        self.root.configure(bg="black")
        
        self.log_box = tk.Text(root, bg="#101010", fg="#00ff00", font=("Consolas", 10))
        self.log_box.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.log("System gestartet. Prüfe Module...")
        
        # Test starten (verzögert, damit GUI erst lädt)
        self.root.after(100, self.run_checks)

    def log(self, text):
        self.log_box.insert(tk.END, text + "\n")
        self.log_box.see(tk.END)
        self.root.update()

    def run_checks(self):
        # 1. Keyboard
        try:
            import keyboard
            self.log("[OK] Keyboard Modul geladen.")
        except ImportError:
            self.log("[FAIL] Keyboard fehlt!")

        # 2. PyTorch
        try:
            self.log("Lade PyTorch (CPU/GPU)...")
            import torch
            v = torch.__version__
            cuda = torch.cuda.is_available()
            self.log(f"[OK] PyTorch {v} geladen.")
            self.log(f"     -> GPU Verfügbar: {cuda}")
        except ImportError:
            self.log("[FAIL] PyTorch fehlt!")

        # 3. TTS (Der Endgegner)
        try:
            self.log("Lade TTS (Das dauert kurz)...")
            from TTS.api import TTS
            self.log("[OK] TTS Engine erfolgreich importiert!")
            self.log("-------------------------------------")
            self.log("✅ SYSTEM BEREIT! WIR KÖNNEN LOSLEGEN.")
            self.log("-------------------------------------")
        except Exception as e:
            self.log(f"[FAIL] TTS Fehler: {e}")

# Start
root = tk.Tk()
app = TestApp(root)
root.mainloop()
