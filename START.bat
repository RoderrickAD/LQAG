@echo off
cd /d "%~dp0"
title LQAG Starter

:: 1. Sicherheitscheck: Ist die Engine überhaupt da?
if not exist "Engine\pythonw.exe" (
    cls
    color 0C
    echo ========================================================
    echo [FEHLER] Die Engine wurde nicht gefunden!
    echo ========================================================
    echo Es fehlt der Ordner "Engine" oder die Datei "pythonw.exe".
    echo Bitte stelle sicher, dass du alles korrekt entpackt hast.
    echo.
    pause
    exit
)

:: 2. Starten (Versteckt)
:: 'start' oeffnet einen neuen Prozess.
:: 'pythonw.exe' (statt python.exe) unterdrueckt das schwarze Fenster.
echo Starte Vorleser...
start "" "Engine\pythonw.exe" "src\main.py"

:: 3. Dieses Fenster schliessen
exit
