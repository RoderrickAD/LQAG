import os
import logging

class VoiceManager:
    def __init__(self, voices_dir):
        self.voices_dir = voices_dir
        self.current_speaker = "Unbekannt"
        self.default_voice = "_default.wav"

    def get_voice_path(self, speaker_name=None):
        """
        Sucht nach einer WAV-Datei, die genau so heißt wie der Sprecher.
        Bsp: Sprecher "Gandalf" -> sucht "Gandalf.wav"
        """
        if not speaker_name:
            speaker_name = self.current_speaker

        # Bereinige den Namen (Windows Dateisystem mag keine Sonderzeichen)
        safe_name = "".join([c for c in speaker_name if c.isalnum() or c in (' ', '-', '_')]).strip()
        
        target_file = os.path.join(self.voices_dir, f"{safe_name}.wav")

        if os.path.exists(target_file):
            return target_file
        else:
            # Fallback auf Standard
            return os.path.join(self.voices_dir, self.default_voice)

def read_speaker_from_plugin(self, plugindata_path):
        """
        Liest die von LOTRO erzeugte .plugindata Datei.
        Format ist meist: return { ["Target"] = "Name" };
        """
        if not os.path.exists(plugindata_path):
            return False

        try:
            # Datei öffnen (UTF-8 ist wichtig für Umlaute im Namen)
            with open(plugindata_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                
            # Wir suchen einfach nach dem String innerhalb der Anführungszeichen nach dem Gleichheitszeichen
            # Quick & Dirty Parsing für Lua Table: ["Target"] = "NAME"
            if '["Target"]' in content:
                # Alles nach '["Target"]' holen
                part = content.split('["Target"]')[1]
                # Das erste was in Anführungszeichen steht, ist der Name
                start_quote = part.find('"')
                end_quote = part.find('"', start_quote + 1)
                
                if start_quote != -1 and end_quote != -1:
                    clean_name = part[start_quote+1 : end_quote]
                    
                    if clean_name and clean_name != self.current_speaker:
                        self.current_speaker = clean_name
                        logging.info(f"🔁 Neuer NPC erkannt: {self.current_speaker}")
                        return True
                        
        except Exception as e:
            # Fehler ignorieren, passiert manchmal wenn LOTRO gerade schreibt
            pass
            
        return False
