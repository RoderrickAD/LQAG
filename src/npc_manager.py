import json
import os
import random
import re

class NpcManager:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.root_dir = os.path.dirname(self.base_dir)
        self.assignments_path = os.path.join(self.root_dir, "resources", "voices-assignments.json")
        self.generated_dir = os.path.join(self.root_dir, "resources", "voices", "generated")
        self.npc_list_path = os.path.join(self.root_dir, "resources", "npc_lists.txt")
        
        # Standard-Pfad
        self.default_target_path = os.path.join(self.root_dir, "resources", "npc_lists", "target.txt")
        
        self.current_target = "Unbekannt"
        self.npc_database = self.load_npc_database()
        self.assignments = self.load_assignments()

    def load_npc_database(self):
        db = {}
        if os.path.exists(self.npc_list_path):
            try:
                with open(self.npc_list_path, "r", encoding="utf-8") as f:
                    for line in f:
                        # Verbesserte Regex: Erlaubt Leerzeichen vor der Klammer "Name [m]"
                        match = re.search(r"^(.*?)\s*\[([mf])\]", line.strip())
                        if match:
                            name, gender = match.groups()
                            db[name.strip()] = gender
            except: pass
        return db

    def load_assignments(self):
        if os.path.exists(self.assignments_path):
            try:
                with open(self.assignments_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except: return {}
        return {}

    def save_assignments(self):
        try:
            with open(self.assignments_path, "w", encoding="utf-8") as f:
                json.dump(self.assignments, f, indent=4, ensure_ascii=False)
        except: pass

    def update(self, custom_path=""):
        """Liest die Datei und nimmt NUR die letzte Zeile"""
        file_to_read = custom_path if (custom_path and os.path.exists(custom_path)) else self.default_target_path
        
        if os.path.exists(file_to_read):
            try:
                with open(file_to_read, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read().strip()
                    if content:
                        lines = content.splitlines()
                        last_entry = lines[-1].strip()
                        if last_entry:
                            self.current_target = last_entry
            except: pass

    def get_voice_path(self):
        name = self.current_target
        
        # Welches Geschlecht erwarten wir? (Standard: male)
        expected_gender = self.npc_database.get(name, "m")

        # Prüfen, ob eine Zuweisung existiert
        if name in self.assignments:
            assigned_file = self.assignments[name]
            
            # --- DER FIX: GENDER CHECK ---
            # Wenn Datei existiert, prüfen wir, ob das Geschlecht stimmt
            if os.path.exists(assigned_file):
                filename = os.path.basename(assigned_file).lower()
                
                # Wenn NPC männlich ist, aber Datei "female_" heißt -> NEU ZUWEISEN!
                if expected_gender == "m" and "female_" in filename:
                    return self.auto_assign_new_voice(name)
                
                # Wenn NPC weiblich ist, aber Datei "male_" heißt -> NEU ZUWEISEN!
                if expected_gender == "f" and "male_" in filename:
                    return self.auto_assign_new_voice(name)
                    
                # Alles gut, behalte die Stimme
                return assigned_file
        
        # Keine Zuweisung oder Datei fehlt -> Neu machen
        return self.auto_assign_new_voice(name)

    def auto_assign_new_voice(self, npc_name):
        if not os.path.exists(self.generated_dir): return ""
        all_files = [os.path.join(self.generated_dir, f) for f in os.listdir(self.generated_dir) if f.endswith(".wav")]
        if not all_files: return ""

        gender = self.npc_database.get(npc_name, "m")
        
        # Listen filtern
        males = [f for f in all_files if "male_" in os.path.basename(f).lower()]
        females = [f for f in all_files if "female_" in os.path.basename(f).lower()]

        chosen = ""
        
        # Logik: Versuche passendes Geschlecht zu finden
        if gender == "f":
            if females: chosen = random.choice(females)
            elif males: chosen = random.choice(males) # Notfall: Mann
            else: chosen = random.choice(all_files)
        else: # Male
            if males: chosen = random.choice(males)
            elif females: chosen = random.choice(females) # Notfall: Frau
            else: chosen = random.choice(all_files)

        self.assignments[npc_name] = chosen
        self.save_assignments()
        return chosen
