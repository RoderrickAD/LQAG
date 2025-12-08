import os
import logging
import re

class VoiceManager:
    def __init__(self, resources_path):
        self.resources_path = resources_path
        self.voices_path = os.path.join(resources_path, "voices")
        self.current_speaker = "Unbekannt"
        
        # Mapping: NPC-Name -> Dateiname der Stimme
        self.speaker_map = {}
        
        if not os.path.exists(self.voices_path):
            os.makedirs(self.voices_path)
            
        self.refresh_voice_list()

    def refresh_voice_list(self):
        """Scanne den voices Ordner nach WAV Dateien"""
        self.speaker_map = {}
        try:
            for file in os.listdir(self.voices_path):
                if file.lower().endswith(".wav"):
                    # Dateiname: "Gandalf.wav" -> Speaker: "Gandalf"
                    name = os.path.splitext(file)[0]
                    self.speaker_map[name.lower()] = os.path.join(self.voices_path, file)
        except Exception as e:
            logging.error(f"Fehler beim Laden der Stimmen: {e}")

    def read_speaker_from_plugin(self, filepath):
        """
        Liest den aktuellen NPC-Namen.
        Unterstützt jetzt:
        1. Script.log (Liest die letzte Zeile)
        2. .plugindata (Liest XML/Lua Struktur)
        """
        try:
            if not os.path.exists(filepath):
                return False

            # --- LOGIK FÜR SCRIPT.LOG ---
            if filepath.endswith(".log"):
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    if lines:
                        # Die letzte Zeile holen und aufräumen (Leerzeichen/Umbruch weg)
                        last_line = lines[-1].strip()
                        if last_line:
                            # Manchmal steht Zeitstempel davor, wir nehmen die ganze Zeile als Name
                            # oder filtern, falls nötig. Für jetzt: Roher Text.
                            self.current_speaker = last_line
                            return True
                return False
            
            # --- ALTE LOGIK FÜR .PLUGINDATA ---
            else:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    
                    # Suche nach dem Namen im Lua/XML Format
                    # Muster: ["Name"] = "Gandalf"  ODER  <Name>Gandalf</Name>
                    match = re.search(r'\["Name"\]\s*=\s*"(.*?)"', content)
                    if not match:
                         match = re.search(r'<Name>(.*?)</Name>', content)
                    
                    if match:
                        self.current_speaker = match.group(1)
                        return True
                        
        except Exception as e:
            logging.error(f"Fehler beim Lesen der Datei: {e}")
            
        return False

    def get_voice_path(self):
        """
        Gibt den Pfad zur WAV-Datei für den aktuellen Sprecher zurück.
        Wenn keine spezielle Stimme da ist, wähle eine zufällige (oder Standard).
        """
        name_key = self.current_speaker.lower()
        
        # 1. Volltreffer? (z.B. "Gandalf" gefunden)
        if name_key in self.speaker_map:
            logging.info(f"Stimme gefunden für '{self.current_speaker}': {os.path.basename(self.speaker_map[name_key])}")
            return self.speaker_map[name_key]
        
        # 2. Teil-Treffer? (z.B. "Ork-Krieger" -> Nutze "Ork.wav")
        for key, path in self.speaker_map.items():
            if key in name_key:
                logging.info(f"Ähnliche Stimme gefunden ({key}) für '{self.current_speaker}'")
                return path

        # 3. Fallback: Zufällige Stimme aus dem Ordner nehmen
        # (Damit es nicht immer gleich klingt, wenn wir den NPC nicht kennen)
        import random
        all_voices = list(self.speaker_map.values())
        if all_voices:
            logging.info(f"Geschlecht unbekannt für '{self.current_speaker}'. Wähle zufällig.")
            chosen = random.choice(all_voices)
            logging.info(f"-> Zufällige Stimme gewählt: {os.path.basename(chosen)}")
            return chosen
            
        logging.warning("Keine Stimmen im 'resources/voices' Ordner gefunden!")
        return None
