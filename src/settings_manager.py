import json
import os

class SettingsManager:
    def __init__(self, base_dir):
        self.filepath = os.path.join(base_dir, "resources", "settings.json")
        self.defaults = {
            "hotkey_read": "f9",
            "hotkey_learn": "f10",
            "hotkey_stop": "f8",
            "hotkey_pause": "f7",
            "debug_mode": True # Standardmäßig an, User kann es ausschalten
        }
        self.settings = self.load_settings()

    def load_settings(self):
        if not os.path.exists(self.filepath):
            return self.defaults.copy()
        try:
            with open(self.filepath, "r") as f:
                data = json.load(f)
                # Fehlende Keys auffüllen
                for k, v in self.defaults.items():
                    if k not in data:
                        data[k] = v
                return data
        except:
            return self.defaults.copy()

    def save_settings(self):
        try:
            with open(self.filepath, "w") as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Fehler beim Speichern: {e}")

    def get(self, key):
        return self.settings.get(key, self.defaults.get(key))

    def set(self, key, value):
        self.settings[key] = value
        self.save_settings()
