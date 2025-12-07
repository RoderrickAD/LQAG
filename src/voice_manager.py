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
        LOTRO speichert Daten oft als Lua-Code: return "Gandalf"
        """
        if not os.path.exists(plugindata_path):
            return

        try:
            with open(plugindata_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                
            # Einfaches Parsen: Wir nehmen an, der Name steht im Text
            # Oft steht in der Datei: return "Name"
            if "return" in content:
                # Entferne 'return', Anführungszeichen und Leerzeichen
                clean_name = content.replace("return", "").replace('"', '').replace("'", "").strip()
                
                if clean_name and clean_name != self.current_speaker:
                    self.current_speaker = clean_name
                    logging.info(f"🔁 Neuer Sprecher erkannt: {self.current_speaker}")
                    return True # Sprecher hat sich geändert
        except Exception as e:
            logging.error(f"Fehler beim Lesen der Plugin-Daten: {e}")
            
        return False
