import os
import logging
import re
import random
import json

class VoiceManager:
    def __init__(self, resources_path):
        self.resources_path = os.path.abspath(resources_path)
        self.voices_path = os.path.join(self.resources_path, "voices")
        self.npc_list_path = os.path.join(self.resources_path, "npc_lists.txt")
        self.memory_path = os.path.join(self.resources_path, "voice_assignments.json")
        
        self.current_speaker = "Unbekannt"
        
        # Pools
        self.specific_voices = {} # Name -> Dateipfad
        self.male_pool = []       # Liste von Pfaden
        self.female_pool = []     # Liste von Pfaden
        
        # Datenbanken
        self.gender_db = {}       # Name -> "m" oder "f"
        self.assignments = {}     # Name -> Dateipfad (Das Gedächtnis)

        # Initialisierung
        self.load_gender_database()
        self.load_voices()
        self.load_assignments()

    def load_gender_database(self):
        """Liest die npc_lists.txt ein: Name[m] oder Name[f]"""
        if not os.path.exists(self.npc_list_path):
            logging.warning(f"Keine NPC-Liste gefunden unter: {self.npc_list_path}")
            return

        try:
            with open(self.npc_list_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    
                    # Suche nach [m] oder [f] am Ende
                    match = re.search(r"^(.*?)\[([mf])\]$", line)
                    if match:
                        name = match.group(1).strip().lower()
                        gender = match.group(2)
                        self.gender_db[name] = gender
            
            logging.info(f"Geschlechter-Datenbank geladen: {len(self.gender_db)} NPCs bekannt.")
        except Exception as e:
            logging.error(f"Fehler beim Laden der NPC-Liste: {e}")

    def load_voices(self):
        """Lädt Stimmen aus den Unterordnern specific, generic_male, generic_female"""
        # 1. SPECIFIC (Vorrang)
        spec_path = os.path.join(self.voices_path, "specific")
        if os.path.exists(spec_path):
            for file in os.listdir(spec_path):
                if file.lower().endswith(".wav"):
                    name = os.path.splitext(file)[0].lower()
                    self.specific_voices[name] = os.path.join(spec_path, file)

        # 2. GENERIC MALE
        male_path = os.path.join(self.voices_path, "generic_male")
        if os.path.exists(male_path):
            for file in os.listdir(male_path):
                if file.lower().endswith(".wav"):
                    self.male_pool.append(os.path.join(male_path, file))

        # 3. GENERIC FEMALE
        female_path = os.path.join(self.voices_path, "generic_female")
        if os.path.exists(female_path):
            for file in os.listdir(female_path):
                if file.lower().endswith(".wav"):
                    self.female_pool.append(os.path.join(female_path, file))

        logging.info(f"Stimmen: {len(self.specific_voices)} Spezifisch | {len(self.male_pool)} Männer | {len(self.female_pool)} Frauen")

    def load_assignments(self):
        """Lädt das Gedächtnis (wer hat welche Stimme)"""
        if os.path.exists(self.memory_path):
            try:
                with open(self.memory_path, "r", encoding="utf-8") as f:
                    self.assignments = json.load(f)
            except:
                self.assignments = {}

    def save_assignments(self):
        """Speichert das Gedächtnis"""
        try:
            with open(self.memory_path, "w", encoding="utf-8") as f:
                json.dump(self.assignments, f, indent=4)
        except Exception as e:
            logging.error(f"Konnte Zuordnungen nicht speichern: {e}")

    def read_speaker_from_plugin(self, filepath):
        try:
            if not os.path.exists(filepath): return False

            # Script.log
            if filepath.endswith(".log"):
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    if lines:
                        self.current_speaker = lines[-1].strip()
                        return True
            # .plugindata
            else:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    match = re.search(r'\["Name"\]\s*=\s*"(.*?)"', content)
                    if not match: match = re.search(r'<Name>(.*?)</Name>', content)
                    if match:
                        self.current_speaker = match.group(1)
                        return True
        except: pass
        return False

    def get_voice_path(self):
        name = self.current_speaker
        name_key = name.lower()
        
        # 1. PRÜFUNG: Gibt es eine SPEZIFISCHE Datei? (Gandalf.wav) -> HÖCHSTE PRIORITÄT
        if name_key in self.specific_voices:
            logging.info(f"Spezifische Stimme gefunden: {name}")
            return self.specific_voices[name_key]

        # 2. PRÜFUNG: Haben wir dem NPC schon mal eine Stimme zugewiesen? (Gedächtnis)
        if name_key in self.assignments:
            assigned_path = self.assignments[name_key]
            # Prüfen, ob die Datei noch existiert
            if os.path.exists(assigned_path):
                logging.info(f"Bekannter NPC '{name}'. Nutze zugewiesene Stimme.")
                return assigned_path

        # 3. NEUE ZUWEISUNG: Wir müssen eine Stimme aussuchen
        chosen_voice = None
        
        # A. Geschlecht prüfen in der Liste
        gender = self.gender_db.get(name_key, "unknown")
        
        if gender == "f":
            if self.female_pool:
                chosen_voice = random.choice(self.female_pool)
                logging.info(f"NPC '{name}' ist WEIBLICH (Liste). Wähle Frauenstimme.")
            else:
                logging.warning("Keine Frauenstimmen verfügbar!")
                
        elif gender == "m":
            if self.male_pool:
                chosen_voice = random.choice(self.male_pool)
                logging.info(f"NPC '{name}' ist MÄNNLICH (Liste). Wähle Männerstimme.")
            else:
                logging.warning("Keine Männerstimmen verfügbar!")
                
        else:
            # B. Unbekanntes Geschlecht -> Raten oder Zufall
            logging.info(f"NPC '{name}' nicht in der Liste. Rate...")
            # Einfache Heuristik für Endungen
            if name_key.endswith("a") or name_key.endswith("ien") or name_key.endswith("wen"):
                pool = self.female_pool if self.female_pool else self.male_pool
            else:
                pool = self.male_pool if self.male_pool else self.female_pool
            
            if pool:
                chosen_voice = random.choice(pool)

        # 4. SPEICHERN
        if chosen_voice:
            self.assignments[name_key] = chosen_voice
            self.save_assignments() # Gedächtnis auf Festplatte schreiben
            return chosen_voice
            
        return None
