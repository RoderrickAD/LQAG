@echo off
title LQAG Vorleser
cls

REM =======================================================
REM WICHTIG: In das Verzeichnis der BAT-Datei wechseln!
REM =======================================================
cd /d "%~dp0"

echo Arbeitsverzeichnis ist: %CD%
echo.

REM 1. Prüfen ob Python überhaupt da ist
echo Pruefe auf Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [FEHLER] Python wurde nicht gefunden!
    echo Bitte installiere Python von python.org und setze den Haken bei "Add to PATH".
    echo.
    pause
    exit /b
)

REM 2. Virtuelle Umgebung (venv) prüfen
if not exist "venv" (
    echo.
    echo [ERST-INSTALLATION]
    echo Erstelle isolierte Python-Umgebung (venv)...
    python -m venv venv
    
    if not exist "venv\Scripts\activate.bat" (
        echo [FEHLER] Venv konnte nicht erstellt werden.
        pause
        exit /b
    )
    
    echo Aktiviere Umgebung...
    call venv\Scripts\activate.bat
    
    echo.
    echo Installiere Bibliotheken (das dauert kurz)...
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    
    echo.
    echo Installation fertig.
) else (
    echo Starte Umgebung...
    call venv\Scripts\activate.bat
)

REM 3. Programm starten
echo.
echo Starte LQAG Vorleser...
echo ------------------------------------------

REM Prüfen ob die Main-Datei existiert
if not exist "src\main.py" (
    echo [FEHLER] Konnte 'src\main.py' nicht finden!
    echo Bin im Ordner: %CD%
    echo Bitte Neu-Installieren.
    pause
    exit /b
)

python src/main.py

REM 4. Falls das Programm abstürzt, Fenster offen lassen
if %errorlevel% neq 0 (
    echo.
    echo ------------------------------------------
    echo Das Programm wurde unerwartet beendet.
    echo Siehe Fehlermeldung oben.
)

echo.
echo Programm beendet. Druecke eine Taste zum Schliessen.
pause
