import os
import logging
import random

class VoiceManager:
    def __init__(self, base_path):
        self.base_path = base_path
        
        # Pfade definieren
        self.path_specific = os.path.join(base_path, "voices", "specific")
        self.path_male = os.path.join(base_path, "voices", "generic_male")
        self.path_female = os.path.join(base_path, "voices", "generic_female")
        self.file_db = os.path.join(base_path, "npc_list.txt")

        self.current_speaker = "Unbekannt"
        
        # Datenbank für Geschlechter: {'Name': 'm', 'Name2': 'f'}
        self.gender_map = {} 
        self.load_gender_db()

        # Cache für generische Dateien (damit wir nicht ständig die Festplatte scannen)
        self.generic_m_files = self._scan_folder(self.path_male)
        self.generic_f_files = self._scan_folder(self.path_female)

    def _scan_folder(self, folder):
        """Hilfsfunktion: Listet alle WAVs in einem Ordner auf"""
        if not os.path.exists(folder):
            os.makedirs(folder) # Erstellt Ordner falls er fehlt
            return []
        return [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith('.wav')]

    def load_gender_db(self):
        """Liest die Datei mit Format: Name[m] oder Name[f]"""
        if not os.path.exists(self.file_db):
            logging.warning(f"Keine NPC-Liste gefunden unter: {self.file_db}")
            return

        count = 0
        try:
            with open(self.file_db, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    
                    # Format Parsen
                    if "[m]" in line:
                        name = line.replace("[m]", "").strip()
                        self.gender_map[name] = "m"
                        count += 1
                    elif "[f]" in line:
                        name = line.replace("[f]", "").strip()
                        self.gender_map[name] = "f"
                        count += 1
            logging.info(f"NPC-Datenbank geladen: {count} Einträge gefunden.")
        except Exception as e:
            logging.error(f"Fehler beim Laden der NPC-Liste: {e}")

    def get_voice_path(self, speaker_name=None):
        if not speaker_name:
            speaker_name = self.current_speaker

        # Namen bereinigen für Dateisystem (keine Doppelpunkte etc.)
        safe_name = "".join([c for c in speaker_name if c.isalnum() or c in (' ', '-', '_')]).strip()
        
        # 1. PRÜFUNG: Gibt es eine spezielle Datei für diesen NPC?
        # Wir suchen in voices/specific/Name.wav
        specific_file = os.path.join(self.path_specific, f"{safe_name}.wav")
        if os.path.exists(specific_file):
            logging.info(f"Spezifische Stimme gefunden für: {speaker_name}")
            return specific_file

        # 2. PRÜFUNG: Geschlecht bestimmen
        # Wir schauen in die geladene Liste
        gender = self.gender_map.get(speaker_name, "unknown") # Default ist unknown

        target_pool = []
        
        if gender == "m":
            target_pool = self.generic_m_files
            logging.info(f"Geschlecht erkannt: MÄNNLICH ({speaker_name})")
        elif gender == "f":
            target_pool = self.generic_f_files
            logging.info(f"Geschlecht erkannt: WEIBLICH ({speaker_name})")
        else:
            # Wenn unbekannt, werfen wir beide Pools zusammen oder nehmen Männer (im Zweifel oft passender bei Orks/Zwergen)
            target_pool = self.generic_m_files + self.generic_f_files
            logging.info(f"Geschlecht unbekannt für '{speaker_name}'. Wähle zufällig.")

        # 3. ZUFALLSWAHL
        if target_pool:
            chosen_voice = random.choice(target_pool)
            # Nur den Dateinamen loggen, nicht den ganzen Pfad, der Übersicht halber
            logging.info(f"-> Zufällige Stimme gewählt: {os.path.basename(chosen_voice)}")
            return chosen_voice
        else:
            logging.error("Keine generischen Stimmen gefunden! Bitte WAVs in generic_male/female legen.")
            return None

    def read_speaker_from_plugin(self, plugindata_path):
        """(Dieser Teil bleibt gleich wie vorher, aber ich füge ihn der Vollständigkeit halber ein)"""
        if not os.path.exists(plugindata_path):
            return False
        try:
            with open(plugindata_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if '["Target"]' in content:
                part = content.split('["Target"]')[1]
                start = part.find('"')
                end = part.find('"', start + 1)
                if start != -1 and end != -1:
                    clean_name = part[start+1 : end]
                    if clean_name and clean_name != self.current_speaker:
                        self.current_speaker = clean_name
                        logging.info(f"🔁 Neuer NPC: {self.current_speaker}")
                        return True
        except: pass
        return False
