import json
import os
import random
import re
import datetime

class NpcManager:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.root_dir = os.path.dirname(self.base_dir)
        self.assignments_path = os.path.join(self.root_dir, "resources", "voices-assignments.json")
        self.generated_dir = os.path.join(self.root_dir, "resources", "voices", "generated")
        self.npc_list_path = os.path.join(self.root_dir, "resources", "npc_lists.txt")
        self.default_target_path = os.path.join(self.root_dir, "resources", "npc_lists", "target.txt")
        
        # Debug Log Pfad
        self.debug_log_path = os.path.join(self.root_dir, "debug", "npc_gender_log.txt")
        if not os.path.exists(os.path.dirname(self.debug_log_path)):
            os.makedirs(os.path.dirname(self.debug_log_path))

        self.current_target = "Unbekannt"
        self.npc_database = self.load_npc_database()
        self.assignments = self.load_assignments()

    def log_debug(self, msg):
        """Schreibt Debug-Infos in eine Datei"""
        try:
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            with open(self.debug_log_path, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {msg}\n")
        except: pass

    def load_npc_database(self):
        db = {}
        if os.path.exists(self.npc_list_path):
            try:
                with open(self.npc_list_path, "r", encoding="utf-8") as f:
                    for line in f:
                        # Regex liest Name und Gender
                        match = re.search(r"^(.*?)\s*\[([mf])\]", line.strip())
                        if match:
                            name, gender = match.groups()
                            # WICHTIG: Wir speichern alles in KLEINBUCHSTABEN für den Vergleich
                            db[name.strip().lower()] = gender.lower()
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
        file_to_read = custom_path if (custom_path and os.path.exists(custom_path)) else self.default_target_path
        
        if os.path.exists(file_to_read):
            try:
                with open(file_to_read, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read().strip()
                    if content:
                        lines = content.splitlines()
                        last_entry = lines[-1].strip()
                        if last_entry and last_entry != self.current_target:
                            self.current_target = last_entry
                            self.log_debug(f"Neuer NPC erkannt: '{self.current_target}'")
            except: pass

    def get_voice_path(self):
        name = self.current_target
        # Vergleich in Kleinbuchstaben, damit "Gandalf" == "gandalf"
        name_lower = name.lower()
        
        # 1. Geschlecht ermitteln
        # Standard ist "m", falls nicht gefunden
        expected_gender = self.npc_database.get(name_lower, "m")
        
        self.log_debug(f"Analysiere '{name}': Erwartetes Geschlecht = {expected_gender}")

        # 2. Prüfen ob Zuweisung existiert
        if name in self.assignments:
            assigned_file = self.assignments[name]
            
            if os.path.exists(assigned_file):
                filename = os.path.basename(assigned_file).lower()
                
                # CHECK: Ist es die falsche Stimme?
                wrong_voice = False
                if expected_gender == "m" and "female_" in filename:
                    self.log_debug(f"FEHLER: '{name}' ist Mann, hat aber Frauenstimme ({filename}). Korrigiere...")
                    wrong_voice = True
                elif expected_gender == "f" and "male_" in filename:
                    self.log_debug(f"FEHLER: '{name}' ist Frau, hat aber Männerstimme ({filename}). Korrigiere...")
                    wrong_voice = True
                
                if not wrong_voice:
                    # Alles okay
                    return assigned_file
        
        # 3. Wenn wir hier sind, brauchen wir eine neue Stimme
        self.log_debug(f"Weise neue Stimme zu für '{name}'...")
        return self.auto_assign_new_voice(name, expected_gender)

    def auto_assign_new_voice(self, npc_name, gender):
        if not os.path.exists(self.generated_dir): 
            self.log_debug("FEHLER: Ordner 'generated' existiert nicht!")
            return ""
            
        all_files = [os.path.join(self.generated_dir, f) for f in os.listdir(self.generated_dir) if f.endswith(".wav")]
        
        if not all_files:
            self.log_debug("FEHLER: Keine .wav Dateien im generated Ordner gefunden!")
            return ""

        # Filtern
        males = [f for f in all_files if "male_" in os.path.basename(f).lower()]
        females = [f for f in all_files if "female_" in os.path.basename(f).lower()]
        
        self.log_debug(f"Verfügbare Stimmen: {len(males)} Männer, {len(females)} Frauen.")

        chosen = ""
        
        # Auswahl Logik
        if gender == "f":
            if females: chosen = random.choice(females)
            elif males: 
                chosen = random.choice(males)
                self.log_debug("WARNUNG: Keine Frauenstimme da, nehme Mann als Notfall.")
            else: chosen = random.choice(all_files)
        else: # Male
            if males: chosen = random.choice(males)
            elif females: 
                chosen = random.choice(females)
                self.log_debug("WARNUNG: Keine Männerstimme da, nehme Frau als Notfall.")
            else: chosen = random.choice(all_files)

        self.assignments[npc_name] = chosen
        self.save_assignments()
        self.log_debug(f"Zugewiesen: {os.path.basename(chosen)}")
        return chosen
