@echo off
title LQAG v2.1 Launcher
cls

REM Prüfen ob die Engine da ist
if not exist "Engine\python.exe" (
    color 0C
    echo [FEHLER] Engine Ordner nicht gefunden!
    echo.
    echo Bitte lade erst die 'LQAG_Engine_v1.zip' von den Releases herunter
    echo und entpacke den Ordner 'Engine' direkt hierhin.
    echo.
    pause
    exit
)

echo Starte LQAG...
echo.

REM Start mit dem Python aus dem Engine-Ordner
".\Engine\python.exe" ".\src\main.py"

if %errorlevel% neq 0 (
    echo.
    echo [CRASH] Programm abgestuerzt. Siehe oben.
    pause
)
