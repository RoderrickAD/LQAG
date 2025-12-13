@echo off
title LQAG Launcher
cls

REM Pruefung: Ist der Engine-Ordner da?
if not exist "Engine\python.exe" (
    color 0C
    echo [FEHLER] Der Ordner 'Engine' wurde nicht gefunden!
    echo.
    echo Bitte stelle sicher, dass du:
    REM WICHTIG: Hier keine runden Klammern benutzen, das verwirrt Batch!
    echo 1. Die 'LQAG_Engine_v1.zip' [Engine Base] heruntergeladen und entpackt hast.
    echo 2. Dass der Ordner 'Engine' direkt neben dieser 'START.bat' liegt.
    echo.
    pause
    exit
)

echo Starte LQAG...
REM Wir nutzen das Python aus dem Engine-Ordner
".\Engine\python.exe" ".\src\main.py"

if %errorlevel% neq 0 (
    echo.
    echo [CRASH] Das Programm wurde unerwartet beendet.
    pause
)
