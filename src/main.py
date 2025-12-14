import sys
import os
import cv2
import numpy as np
import datetime

# Pfad-Fix
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from tkinter import messagebox
import threading
import time
import easyocr
import pyautogui
import keyboard
from audio_engine import AudioEngine
from screen_tool import SnippingTool
from npc_manager import NpcManager

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("LQAG - Vorleser (Präzise)")
        self.root.geometry("600x550")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#1e1e1e")
        
        # --- ORDNER PFADE ---
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.root_dir = os.path.dirname(self.base_dir)
        
        # Cache & Debug
        self.cache_dir = os.path.join(self.root_dir, "resources", "cache")
        if not os.path.exists(self.cache_dir): os.makedirs(self.cache_dir)

        self.debug_dir = os.path.join(self.root_dir, "debug")
        if not os.path.exists(self.debug_dir): os.makedirs(self.debug_dir)
        
        # --- ZUSTAND ---
        self.is_scanning = False
        
        self.template_tl = None # Bild Oben-Links
        self.template_br = None # Bild Unten-Rechts
        self.current_area = None # (x, y, w, h)
        
        self.setup_ui()
        
        self.log("⏳ Starte System...")
        threading.Thread(target=self.load_engines, daemon=True).start()

    def setup_ui(self):
        lbl_info = tk.Label(self.root, text="F10: Ecken manuell lernen (2 Schritte)\nF9: Text vorlesen",
                           bg="#1e1e1e", fg="#cccccc", font=("Arial", 10))
        lbl_info.pack(pady=10)

        # Buttons
        btn_frame = tk.Frame(self.root, bg="#1e1e1e")
        btn_frame.pack(pady=5)
        
        self.btn_learn = tk.Button(btn_frame, text="1. Ecken lernen (F10)", 
                                   command=self.start_learning_sequence, bg="#007acc", fg="white", width=20)
        self.btn_learn.pack(side=tk.LEFT, padx=5)
        
        self.btn_read = tk.Button(btn_frame, text="2. VORLESEN (F9)", 
                                  command=self.scan_once, state=tk.DISABLED, bg="#28a745", fg="white", width=20)
        self.btn_read.pack(side=tk.LEFT, padx=5)

        # Audio Control
        ctrl_frame = tk.Frame(self.root, bg="#1e1e1e")
        ctrl_frame.pack(pady=10)
        self.btn_stop_audio = tk.Button(ctrl_frame, text="⏹ Audio Stopp", 
                                        command=self.stop_audio, bg="#dc3545", fg="white", font=("Arial", 9, "bold"))
        self.btn_stop_audio.pack(side=tk.LEFT, padx=5)

        # Log
        self.log_box = tk.Text(self.root, height=15, bg="black", fg="#00ff00", font=("Consolas", 9), insertbackground="white")
        self.log_box.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Status
        self.lbl_target = tk.Label(self.root, text="Ziel: -", bg="#333", fg="yellow", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.lbl_target.pack(side=tk.BOTTOM, fill=tk.X)

    def log(self, text):
        self.log_box.insert(tk.END, f">> {text}\n")
        self.log_box.see(tk.END)

    def load_engines(self):
        try:
            self.log("... Lade NPC Datenbank ...")
            self.npc_manager = NpcManager()
            self.log("... Lade OCR ...")
            self.reader = easyocr.Reader(['de', 'en'], gpu=True)
            self.log("... Lade Audio Engine ...")
            self.audio = AudioEngine()
            
            keyboard.add_hotkey('f9', self.scan_once)
            keyboard.add_hotkey('f10', self.start_learning_sequence)
            
            self.log("✅ SYSTEM BEREIT!")
            self.load_cached_templates()

        except Exception as e:
            self.log(f"❌ Fehler: {e}")

    # --- SAVE / LOAD TEMPLATES ---
    def save_templates(self):
        if self.template_tl is not None and self.template_br is not None:
            cv2.imwrite(os.path
