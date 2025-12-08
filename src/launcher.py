import tkinter as tk
from tkinter import ttk, messagebox
import os
import requests
import zipfile
import threading
import subprocess
import sys

# --- KONFIGURATION ---
# Hier trägst du später den Link zu deiner riesigen ZIP-Datei ein
# (z.B. von Google Drive, Dropbox oder GitHub Release)
DOWNLOAD_URL = "https://DEIN_LINK_ZUR_RIESIGEN_DATEI/core_files.zip"
ZIP_FILENAME = "lqag_core.zip"
MAIN_EXE_NAME = "LQAG_Internal.exe" # So heißt das eigentliche Programm später

class LauncherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LQAG Launcher")
        self.root.geometry("400x250")
        self.root.configure(bg="#2b2b2b")
        
        # Style
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TProgressbar", thickness=20, troughcolor='#1e1e1e', background='#d4af37')
        
        # GUI Elemente
        tk.Label(root, text="LQAG Setup", bg="#2b2b2b", fg="white", font=("Segoe UI", 16, "bold")).pack(pady=20)
        
        self.status_label = tk.Label(root, text="Prüfe Installation...", bg="#2b2b2b", fg="#cccccc")
        self.status_label.pack(pady=5)
        
        self.progress = ttk.Progressbar(root, orient="horizontal", length=300, mode="determinate")
        self.progress.pack(pady=20)
        
        self.btn_action = tk.Button(root, text="Starten", command=self.check_and_run, bg="#d4af37", fg="black", bd=0, padx=20, pady=10)
        self.btn_action.pack(pady=10)

        # Automatisch prüfen beim Start
        self.root.after(1000, self.check_and_run)

    def check_and_run(self):
        # Prüfen, ob das Hauptprogramm schon da ist (im Unterordner 'core')
        core_path = os.path.join(os.getcwd(), "core")
        exe_path = os.path.join(core_path, MAIN_EXE_NAME)
        
        if os.path.exists(exe_path):
            self.status_label.config(text="Starte LQAG...")
            self.progress['value'] = 100
            # Starten
            subprocess.Popen([exe_path])
            self.root.destroy() # Launcher schließen
        else:
            self.status_label.config(text="Hauptdateien fehlen. Download erforderlich.")
            self.btn_action.config(text="Download starten (ca. 3GB)", command=self.start_download)

    def start_download(self):
        self.btn_action.config(state="disabled")
        threading.Thread(target=self.download_worker, daemon=True).start()

    def download_worker(self):
        try:
            # 1. DOWNLOAD
            self.update_status("Lade Core-Dateien herunter...")
            response = requests.get(DOWNLOAD_URL, stream=True)
            total_size = int(response.headers.get('content-length', 0))
            
            with open(ZIP_FILENAME, 'wb') as f:
                downloaded = 0
                for data in response.iter_content(chunk_size=4096):
                    downloaded += len(data)
                    f.write(data)
                    # Fortschritt berechnen
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        self.update_progress(percent)
            
            # 2. ENTPACKEN
            self.update_status("Entpacke Dateien (das dauert kurz)...")
            self.update_progress(0) # Reset Bar
            
            with zipfile.ZipFile(ZIP_FILENAME, 'r') as zip_ref:
                file_list = zip_ref.namelist()
                total_files = len(file_list)
                for i, file in enumerate(file_list):
                    zip_ref.extract(file, "core")
                    self.update_progress((i / total_files) * 100)

            # 3. AUFRÄUMEN
            self.update_status("Räume auf...")
            os.remove(ZIP_FILENAME)
            
            # 4. FERTIG
            self.update_status("Installation fertig!")
            self.root.after(1000, self.check_and_run)

        except Exception as e:
            self.update_status(f"Fehler: {str(e)}")
            self.root.after(0, lambda: self.btn_action.config(state="normal", text="Erneut versuchen"))

    def update_status(self, text):
        self.root.after(0, lambda: self.status_label.config(text=text))

    def update_progress(self, val):
        self.root.after(0, lambda: self.progress.configure(value=val))

if __name__ == "__main__":
    root = tk.Tk()
    try: root.iconbitmap("resources/icon.ico")
    except: pass
    app = LauncherApp(root)
    root.mainloop()
