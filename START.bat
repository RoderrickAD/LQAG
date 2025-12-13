@echo off
title LQAG v2.1
cls

if not exist "Engine\python.exe" (
    color 0C
    echo [FEHLER] Engine nicht gefunden!
    echo Bitte fuehre erst die INSTALL.bat aus!
    pause
    exit
)

echo Starte LQAG...
echo (Konsole offen lassen fuer Debug-Infos)
echo.

".\Engine\python.exe" ".\src\main.py"

if %errorlevel% neq 0 (
    color 0C
    echo.
    echo [CRASH] Das Programm wurde unerwartet beendet.
    pause
)
