import os
import glob
import hashlib
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
        
        self.list_path = os.path.join(self.resources_dir, "npc_lists.txt")
        self.voices_dir = os.path.join(self.resources_dir, "voices")
        
        # --- STIMMEN LADEN ---
        self.male_voices = self._load_voice_files("generic_male")
        self.female_voices = self._load_voice_files("generic_female")
        
        # --- DATENBANK LADEN ---
        self.load_npc_list()
        
        # --- LOG DATEI SUCHEN ---
        self.log_file = self.find_lotro_log()

    def _load_voice_files(self, subfolder):
        """Lädt alle .wav Dateien aus resources/voices/subfolder"""
        path = os.path.join(self.voices_dir, subfolder)
        files = glob.glob(os.path.join(path, "*.wav"))
        return sorted(files)

    def load_npc_list(self):
        """Liest die npc_lists.txt"""
        if not os.path.exists(self.list_path):
            print(f"⚠️ FEHLER: Datei nicht gefunden: {self.list_path}")
            return

        try:
            with open(self.list_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    
                    if "[m]" in line:
                        name = line.replace("[m]", "").strip()
                        self.npc_db[name] = "male"
                    elif "[w]" in line or "[f]" in line:
                        name = line.replace("[w]", "").replace("[f]", "").strip()
                        self.npc_db[name] = "female"
            print(f"✅ Datenbank bereit: {len(self.npc_db)} NPCs geladen.")
            
        except Exception as e:
            print(f"❌ Fehler beim Lesen der Liste: {e}")

    def find_lotro_log(self):
        """Sucht die Script.log Datei im LotRO Dokumente Ordner"""
        # Standardpfad: Dokumente/The Lord of the Rings Online/Script.log
        user_docs = os.path.expanduser("~/Documents/The Lord of the Rings Online")
        if not os.path.exists(user_docs):
            user_docs = os.path.expanduser("~/Dokumente/The Lord of the Rings Online")

        log_path = os.path.join(user_docs, "Script.log")
        
        if os.path.exists(log_path):
            print(f"🔌 Log-Datei gefunden: {log_path}")
            return log_path
        
        print(f"⚠️ Script.log nicht gefunden in: {user_docs}")
        return None

    def update(self):
        """Liest die letzte Zeile der Script.log"""
        if not self.log_file or not os.path.exists(self.log_file):
            if not self.log_file:
                self.log_file = self.find_lotro_log()
            return

        try:
            # Datei öffnen und Zeilen lesen
            # errors='ignore' ist wichtig, falls LotRO seltsame Zeichen schreibt
            with open(self.log_file, "r", encoding="utf-8", errors="ignore") as f:
                # Wir gehen ans Ende der Datei, um nicht MBs an Daten zu lesen
                # (Einfache Methode: readlines() der letzten paar Bytes)
                # Aber für den Anfang reicht readlines(), da Script.log selten riesig wird
                lines = f.readlines()
                
            if lines:
                # Nimm die letzte nicht-leere Zeile
                last_line = ""
                for line in reversed(lines):
                    line = line.strip()
                    if line:
                        last_line = line
                        break
                
                # Check: Ist es eine Fehlermeldung? (Die wollen wir nicht als Namen)
                if "Main.lua" in last_line or "attempt to index" in last_line:
                    return 

                # Wenn sich der Name geändert hat
                if last_line and last_line != self.current_target:
                    self.current_target = last_line
                    self.determine_gender(self.current_target)
                    
                    # Debug Ausgabe
                    v_path = self.get_voice_path()
                    v_name = os.path.basename(v_path) if v_path else "KEINE"
                    print(f"🎯 Ziel erkannt: '{self.current_target}' ({self.gender}) -> Stimme: {v_name}")

        except Exception:
            pass 

    def determine_gender(self, name):
        """Ermittelt Geschlecht aus Datenbank oder rät"""
        if name in self.npc_db:
            self.gender = self.npc_db[name]
        else:
            self.gender = "male" 

    def get_voice_path(self):
        """Wählt die korrekte .wav Datei aus"""
        name = self.current_target
        
        # 1. SPECIFIC
        specific_path = os.path.join(self.voices_dir, "specific", f"{name}.wav")
        if os.path.exists(specific_path):
            return specific_path

        # 2. GENERIC POOL
        pool = self.female_voices if self.gender == "female" else self.male_voices
        
        if not pool:
            return None 
            
        # 3. KONSISTENTE AUSWAHL
        name_hash = int(hashlib.sha256(name.encode('utf-8')).hexdigest(), 16)
        voice_index = name_hash % len(pool)
        
        return pool[voice_index]
