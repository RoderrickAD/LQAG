LQAG - Lokaler Quest Audio Generator
Version 1.3
----------------------------

Vielen Dank, dass du LQAG nutzt!

WAS IST LQAG?
LQAG steht für "Lokaler Quest Audio Generator".
Es ist ein KI-gestütztes Tool, das Texte vom Bildschirm erkennt und mit hochwertigen Stimmen vorliest.
Aktueller Status: Diese Version ist speziell für "The Lord of the Rings Online" (LOTRO) konfiguriert und optimiert. Unterstützung für weitere Spiele ist für die Zukunft geplant.

--- INSTALLATION (LOTRO MODUL) ---

SCHRITT A: Das Plugin installieren
Damit LQAG weiß, wer gerade spricht, benötigt es eine kleine Brücke zum Spiel.
1. Öffne den Ordner "LQAG_Plugin" aus diesem Zip-Paket.
2. Kopiere den darin enthaltenen Ordner "LQAG" (nicht die Datei, den ganzen Ordner!) nach:
   Dokumente\The Lord of the Rings Online\Plugins\
   (Falls der Ordner "Plugins" nicht existiert, erstelle ihn einfach).

SCHRITT B: Das Tool starten
1. Starte die Datei "LQAG.exe".
2. Es kann beim ersten Start kurz dauern (ca. 10-20 Sekunden), bis das KI-Modell im Hintergrund geladen ist.

--- EINRICHTUNG IM SPIEL ---

1. Starte LOTRO und logge dich ein.
2. Tippe in den Chat: /plugins load LQAG
   (Es sollte eine grüne Meldung erscheinen: "Reporter geladen").
3. Klicke einen NPC an (z.B. Gandalf), damit das Plugin Daten schreibt.
4. Gehe zurück zum LQAG-Tool (Windows).
5. Klicke auf "Datei wählen..." und navigiere zu:
   Dokumente\The Lord of the Rings Online\PluginData\<DEIN_ACCOUNT>\AllServers\LQAG_Data.plugindata
   
   HINWEIS: Diese Datei wird vom Spiel erst erstellt, nachdem du das Plugin geladen und den ersten NPC angeklickt hast!

--- BENUTZUNG ---

1. Öffne ein Quest-Fenster im Spiel.
2. Drücke F9 (Standard-Hotkey).
3. Das Tool liest den Text vor.
4. Mit dem Pause-Knopf im Tool kannst du die Sprachausgabe anhalten wie bei einem Video.

--- EIGENE STIMMEN HINZUFÜGEN ---

Das System ordnet Stimmen automatisch zu. Du kannst den Ordner "resources/voices" bearbeiten:

- "specific": Hier kommen Stimmen rein, die exakt so heißen wie der NPC (z.B. 'Gandalf.wav').
- "generic_male": Wirf hier verschiedene Männerstimmen rein. LQAG wählt zufällig eine aus, wenn kein spezieller NPC erkannt wird.
- "generic_female": Das Gleiche für Frauenstimmen.

Viel Spaß beim Spielen!
