@echo off
title LQAG Vorleser - System Check...
echo Pruefe Systemumgebung...

REM 1. Prüfen ob Python installiert ist
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo FEHLER: Python wurde nicht gefunden!
    echo Bitte installiere Python von python.org (Haken bei "Add to PATH" setzen).
    pause
    exit
)

REM 2. Prüfen ob die virtuelle Umgebung (venv) existiert
if not exist "venv" (
    echo.
    echo ========================================================
    echo ERSTER START - Richte Umgebung ein...
    echo Das kann einige Minuten dauern (Download von KI-Modellen).
    echo Bitte warten...
    echo ========================================================
    echo.
    
    REM Venv erstellen
    python -m venv venv
    
    REM Bibliotheken installieren
    call venv\Scripts\activate
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    
    echo.
    echo Installation abgeschlossen! Starte Programm...
) else (
    call venv\Scripts\activate
)

REM 3. Programm starten
cls
echo Starte LQAG Vorleser...
python src/main.py
pause
