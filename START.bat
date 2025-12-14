@echo off
cd /d "%~dp0"
title LQAG - LotRO Audio Guide
color 0B

echo ===================================================
echo      LOTRO AUDIO GUIDE (Powered by Engine V11)
echo ===================================================
echo.

:: 1. Sicherheits-Check: Ist der Motor da?
if not exist "Engine\python.exe" (
    color 0C
    echo [FEHLER] Der Ordner "Engine" fehlt!
    echo.
    echo Bitte lade die "LQAG_Engine_V11.zip" von GitHub herunter
    echo und entpacke sie genau hier, sodass der Ordner "Engine" sichtbar ist.
    echo.
    pause
    exit
)

:: 2. Starten
echo [INFO] Starte System...
echo [INFO] Lade Python Umgebung...
echo.
echo HINWEIS: Das schwarze Fenster muss offen bleiben!
echo.

"Engine\python.exe" "src\main.py"

:: 3. Fehler-Fangnetz (Falls es abstürzt)
if %ERRORLEVEL% NEQ 0 (
    color 0C
    echo.
    echo ===================================================
    echo   KRITISCHER FEHLER - PROGRAMM ABGESTUERZT
    echo ===================================================
    echo Bitte mache einen Screenshot von dem Text oben drueber
    echo und zeige ihn dem Entwickler.
    echo ===================================================
    pause
)
