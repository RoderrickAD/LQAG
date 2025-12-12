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
        
        self.specific_voices = {}
        self.male_pool = []
        self.female_pool = []
        self.gender_db = {}
        self.assignments = {}

        self.load_gender_database()
        self.load_voices()
        self.load_assignments()

    def load_gender_database(self):
        if not os.path.exists(self.npc_list_path): return
        try:
            with open(self.npc_list_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    match = re.search(r"^(.*?)\[([mf])\]$", line.strip())
                    if match:
                        self.gender_db[match.group(1).strip().lower()] = match.group(2)
        except: pass

    def load_voices(self):
        # Specific
        spec_path = os.path.join(self.voices_path, "specific")
        if os.path.exists(spec_path):
            for f in os.listdir(spec_path):
                if f.endswith(".wav"): self.specific_voices[os.path.splitext(f)[0].lower()] = os.path.join(spec_path, f)
        # Generic Male
        m_path = os.path.join(self.voices_path, "generic_male")
        if os.path.exists(m_path):
            for f in os.listdir(m_path):
                if f.endswith(".wav"): self.male_pool.append(os.path.join(m_path, f))
        # Generic Female
        f_path = os.path.join(self.voices_path, "generic_female")
        if os.path.exists(f_path):
            for f in os.listdir(f_path):
                if f.endswith(".wav"): self.female_pool.append(os.path.join(f_path, f))
        
        logging.info(f"Stimmen: {len(self.specific_voices)} Spezifisch | {len(self.male_pool)} M | {len(self.female_pool)} F")

    def load_assignments(self):
        if os.path.exists(self.memory_path):
            try:
                with open(self.memory_path, "r", encoding="utf-8") as f: self.assignments = json.load(f)
            except: self.assignments = {}

    def save_assignments(self):
        try:
            with open(self.memory_path, "w", encoding="utf-8") as f: json.dump(self.assignments, f, indent=4)
        except: pass

    def read_speaker_from_plugin(self, filepath):
        try:
            if not os.path.exists(filepath): return False
            if filepath.endswith(".log"):
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    if lines:
                        self.current_speaker = lines[-1].strip()
                        return True
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
        name_key = self.current_speaker.lower()
        
        if name_key in self.specific_voices:
            logging.info(f"Spezifische Stimme: {name_key}")
            return self.specific_voices[name_key]

        if name_key in self.assignments and os.path.exists(self.assignments[name_key]):
            logging.info(f"Bekannt (Gedächtnis): {self.current_speaker}")
            return self.assignments[name_key]

        gender = self.gender_db.get(name_key, "unknown")
        chosen = None
        
        if gender == "f" and self.female_pool: chosen = random.choice(self.female_pool)
        elif gender == "m" and self.male_pool: chosen = random.choice(self.male_pool)
        else:
            # Fallback
            if name_key.endswith("a") or name_key.endswith("ien"): pool = self.female_pool
            else: pool = self.male_pool
            if not pool: pool = self.female_pool + self.male_pool
            if pool: chosen = random.choice(pool)

        if chosen:
            self.assignments[name_key] = chosen
            self.save_assignments()
            return chosen
            
        return None
