import os
import glob
import json
import random
import time

class NpcManager:
    def __init__(self):
        self.npc_db = {}
        self.current_target = "Unbekannt"
        self.gender = "m" 
        
        # --- PFAD-KONFIGURATION ---
        self.src_dir = os.path.dirname(os.path.abspath(__file__))
        self.root_dir = os.path.dirname(self.src_dir)
        self.resources_dir = os.path.join(self.root_dir, "resources")
        self.cache_dir = os.path.join(self.resources_dir, "cache")
        
        # Sicherstellen, dass der Cache Ordner existiert
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            
        self.list_path = os.path.join(self.resources_dir, "npc_lists.txt")
        self.voices_dir = os.path.join(self.resources_dir, "voices")
        self.memory_file = os.path.join(self.cache_dir, "voice_assignments.json")
        
        # --- STIMMEN LADEN ---
        self.male_voices = self._load_voice_files("generic_male")
        self.female_voices = self._load_voice_files("generic_female")
        
        # --- DATENBANKEN LADEN ---
        self.load_npc_list()     # Männlich/Weiblich Liste
        self.voice_memory = self.load_voice_memory() # Wer hat welche Stimme?
        
        # --- LOG DATEI SUCHEN ---
        self.log_file = self.find_lotro_log()

    def _load_voice_files(self, subfolder):
        """Lädt alle .wav Dateien und gibt nur den Dateinamen zurück (relative Pfade sind sicherer)"""
        path = os.path.join(self.voices_dir, subfolder)
        files = glob.glob(os.path.join(path, "*.wav"))
        return sorted(files)

    def load_npc_list(self):
        if not os.path.exists(self.list_path):
            print(f"⚠️ Datei fehlt: {self.list_path}")
            return
        try:
            with open(self.list_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    if "[m]" in line:
                        self.npc_db[line.replace("[m]", "").strip()] = "male"
                    elif "[w]" in line or "[f]" in line:
                        self.npc_db[line.replace("[w]", "").replace("[f]", "").strip()] = "female"
            print(f"✅ NPC-Datenbank: {len(self.npc_db)} Einträge.")
        except Exception as e:
            print(f"❌ Fehler NPC Liste: {e}")

    # --- DAS NEUE GEDÄCHTNIS ---
    def load_voice_memory(self):
        """Lädt die gespeicherten Zuordnungen (Wer hat welche Stimme?)"""
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                print(f"🧠 Stimm-Gedächtnis geladen ({len(data)} NPCs erinnern sich).")
                return data
            except Exception as e:
                print(f"⚠️ Fehler beim Laden des Gedächtnisses: {e}")
                return {}
        return {}

    def save_voice_memory(self):
        """Speichert neue Zuordnungen"""
        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(self.voice_memory, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"❌ Konnte Gedächtnis nicht speichern: {e}")

    def find_lotro_log(self):
        user_docs = os.path.expanduser("~/Documents/The Lord of the Rings Online")
        if not os.path.exists(user_docs):
            user_docs = os.path.expanduser("~/Dokumente/The Lord of the Rings Online")
        
        log_path = os.path.join(user_docs, "Script.log")
        if os.path.exists(log_path):
            print(f"🔌 Log verbunden: {log_path}")
            return log_path
        return None

    def update(self):
        if not self.log_file or not os.path.exists(self.log_file):
            if not self.log_file: self.log_file = self.find_lotro_log()
            return

        try:
            with open(self.log_file, "r", encoding="utf-8", errors="ignore") as f:
                # Schnell ans Ende springen
                f.seek(0, 2) 
                fsize = f.tell()
                f.seek(max(fsize - 1024, 0), 0) 
                lines = f.readlines()
