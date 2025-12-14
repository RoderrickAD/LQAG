@echo off
cd /d "%~dp0"

:: Prüfen ob Engine da ist
if not exist "Engine\python.exe" (
    echo Engine nicht gefunden!
    pause
    exit
)

:: HIER IST DER TRICK: start "" "Engine\pythonw.exe"
:: start "" startet einen neuen Prozess
:: pythonw.exe öffnet KEIN schwarzes Fenster
start "" "Engine\pythonw.exe" "src\main.py"

exit
