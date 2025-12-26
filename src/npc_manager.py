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
        self.target_path = os.path.join(self.root_dir, "resources", "npc_lists", "target.txt")
        
        self.current_target = "Unbekannt"
        self.npc_database = self.load_npc_database()
        self.assignments = self.load_assignments()

    def load_npc_database(self):
        """Lädt die Liste mit Namen[m/f] Zuordnungen"""
        db = {}
        if os.path.exists(self.npc_list_path):
            try:
                with open(self.npc_list_path, "r", encoding="utf-8") as f:
                    for line in f:
                        # Extrahiert Name und Geschlecht, z.B. "Aerona[f]" -> "Aerona", "f"
                        match = re.search(r"^(.*)\[([mf])\]", line.strip())
                        if match:
                            name, gender = match.groups()
                            db[name.strip()] = gender
            except Exception as e:
                print(f"Fehler beim Laden der NPC-Liste: {e}")
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

    def update(self):
        if os.path.exists(self.target_path):
            try:
                with open(self.target_path, "r", encoding="utf-8") as f:
                    self.current_target = f.read().strip() or "Unbekannt"
            except: pass

    def get_voice_path(self):
        name = self.current_target
        if name in self.assignments:
            path = self.assignments[name]
            if os.path.exists(path): return path
        return self.auto_assign_new_voice(name)

    def auto_assign_new_voice(self, npc_name):
        if not os.path.exists(self.generated_dir): return ""
        all_files = [os.path.join(self.generated_dir, f) for f in os.listdir(self.generated_dir) if f.endswith(".wav")]
        if not all_files: return ""

        # Geschlecht aus Datenbank abrufen 
        gender = self.npc_database.get(npc_name, "m") # Standard "m", falls unbekannt
        
        males = [f for f in all_files if "male_" in os.path.basename(f).lower()]
        females = [f for f in all_files if "female_" in os.path.basename(f).lower()]

        if gender == "f" and females:
            chosen = random.choice(females)
        elif males:
            chosen = random.choice(males)
        else:
            chosen = random.choice(all_files)

        self.assignments[npc_name] = chosen
        self.save_assignments()
        return chosen

    def assign_voice(self, npc_name, voice_path):
        self.assignments[npc_name] = voice_path
        self.save_assignments()
