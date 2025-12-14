import os
import glob
import hashlib

class NpcManager:
    def __init__(self):
        self.npc_db = {}
        self.current_target = "Unbekannt"
        self.gender = "m" 
        
        # --- PFAD-KONFIGURATION ---
        # Wir sind in LQAG/src/ und wollen nach LQAG/resources/
        self.src_dir = os.path.dirname(os.path.abspath(__file__))
        self.root_dir = os.path.dirname(self.src_dir)
        self.resources_dir = os.path.join(self.root_dir, "resources")
        
        self.list_path = os.path.join(self.resources_dir, "npc_lists.txt")
        self.voices_dir = os.path.join(self.resources_dir, "voices")
        
        # --- STIMMEN LADEN ---
        # Wir laden alle .wav Dateien aus den entsprechenden Unterordnern
        self.male_voices = self._load_voice_files("generic_male")
        self.female_voices = self._load_voice_files("generic_female")
        
        # --- DATENBANK LADEN ---
        self.load_npc_list()
        
        # --- PLUGIN SUCHEN ---
        self.plugin_file = self.find_plugin_data()

    def _load_voice_files(self, subfolder):
        """Lädt alle .wav Dateien aus resources/voices/subfolder"""
        path = os.path.join(self.voices_dir, subfolder)
        files = glob.glob(os.path.join(path, "*.wav"))
        
        # Falls keine Dateien da sind, Warnung ausgeben
        if not files:
            print(f"⚠️ WARNUNG: Keine Stimmen in '{subfolder}' gefunden!")
            print(f"   (Gesucht in: {path})")
        else:
            print(f"   In '{subfolder}' geladen: {len(files)} Stimmen.")
            
        return sorted(files) # Sortieren für konsistente Reihenfolge

    def load_npc_list(self):
        """Liest die npc_lists.txt aus dem resources Ordner"""
        if not os.path.exists(self.list_path):
            print(f"⚠️ FEHLER: Datei nicht gefunden: {self.list_path}")
            return

        print(f"📖 Lade NPC-Liste aus: {self.list_path}")
        count = 0
        try:
            with open(self.list_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    
                    # Parsing Logik für [m], [w] und [f]
                    if "[m]" in line:
                        name = line.replace("[m]", "").strip()
                        self.npc_db[name] = "male"
                        count += 1
                    elif "[w]" in line or "[f]" in line:
                        name = line.replace("[w]", "").replace("[f]", "").strip()
                        self.npc_db[name] = "female"
                        count += 1
                        
            print(f"✅ Datenbank bereit: {count} NPCs bekannt.")
            
        except Exception as e:
            print(f"❌ Fehler beim Lesen der Liste: {e}")

    def find_plugin_data(self):
        """Sucht die .plugindata Datei vom LotRO Plugin"""
        user_docs = os.path.expanduser("~/Documents/The Lord of the Rings Online/PluginData")
        if not os.path.exists(user_docs):
            # Fallback für deutsche Windows Versionen, falls Pfad anders
            user_docs = os.path.expanduser("~/Dokumente/The Lord of the Rings Online/PluginData")

        for root, dirs, files in os.walk(user_docs):
            if "LQAG_Data.plugindata" in files:
                path = os.path.join(root, "LQAG_Data.plugindata")
                print(f"🔌 Plugin-Verbindung hergestellt: {path}")
                return path
        
        print("⚠️ Plugin-Datei 'LQAG_Data.plugindata' noch nicht gefunden.")
        return None

    def update(self):
        """Wird regelmäßig aufgerufen, um das Ziel zu prüfen"""
        if not self.plugin_file or not os.path.exists(self.plugin_file):
            # Vielleicht ist die Datei jetzt da? (Erster Start des Spiels)
            if not self.plugin_file:
                self.plugin_file = self.find_plugin_data()
            return

        try:
            # Wir lesen die Lua-Datei
            with open(self.plugin_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Suche nach ["Target"] = "Name"
            if '["Target"]' in content:
                start = content.find('["Target"] = "') + 14
                end = content.find('"', start)
                if start > 13 and end > start:
                    name = content[start:end]
                    
                    if name != self.current_target and name != "":
                        self.current_target = name
                        self.determine_gender(name)
                        # Debug Ausgabe
                        v_path = self.get_voice_path()
                        v_name = os.path.basename(v_path) if v_path else "KEINE"
                        print(f"🎯 Ziel: '{name}' ({self.gender}) -> Stimme: {v_name}")

        except Exception:
            pass # Lese-Fehler ignorieren (Datei wird gerade vom Spiel geschrieben)

    def determine_gender(self, name):
        """Ermittelt Geschlecht aus Datenbank oder rät"""
        # 1. Datenbank prüfen
        if name in self.npc_db:
            self.gender = self.npc_db[name]
        else:
            # Fallback: Standard ist männlich, falls unbekannt
            self.gender = "male" 

    def get_voice_path(self):
        """Wählt die korrekte .wav Datei aus"""
        name = self.current_target
        
        # 1. SPECIFIC CHECK: Haben wir eine spezielle Datei für diesen Namen?
        # Wir suchen in resources/voices/specific/Name.wav
        specific_path = os.path.join(self.voices_dir, "specific", f"{name}.wav")
        if os.path.exists(specific_path):
            return specific_path

        # 2. GENERIC POOL: Wähle Männlich oder Weiblich
        pool = self.female_voices if self.gender == "female" else self.male_voices
        
        if not pool:
            return None # Keine Stimmen vorhanden
            
        # 3. KONSISTENTE AUSWAHL
        # Der Hash des Namens sorgt dafür, dass "Otto" immer Stimme 3 bekommt,
        # auch nach einem Neustart.
        name_hash = int(hashlib.sha256(name.encode('utf-8')).hexdigest(), 16)
        voice_index = name_hash % len(pool)
        
        return pool[voice_index]
