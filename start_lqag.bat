@echo off
setlocal
title LQAG Vorleser
cls

REM =======================================================
REM Arbeitsverzeichnis erzwingen (auch bei Leerzeichen)
REM =======================================================
cd /d "%~dp0"
echo Arbeitsverzeichnis: "%CD%"
echo.

REM =======================================================
REM 1. PYTHON PRUEFEN
REM =======================================================
echo Pruefe Python Installation...
python --version >nul 2>&1
if %errorlevel% neq 0 goto ERROR_PYTHON

REM =======================================================
REM 2. VENV PRUEFEN
REM =======================================================
if not exist "venv" goto INSTALL_VENV

REM =======================================================
REM 3. START
REM =======================================================
:START_APP
echo.
echo Starte Umgebung...
if not exist "venv\Scripts\activate.bat" goto ERROR_VENV_BROKEN

call venv\Scripts\activate.bat

echo Pruefe Main-Datei...
if not exist "src\main.py" goto ERROR_MAIN

echo Starte LQAG Vorleser...
echo -----------------------------------------------------
python src/main.py
if %errorlevel% neq 0 goto CRASHED

goto END

REM =======================================================
REM ROUTINEN & FEHLERBEHANDLUNG
REM =======================================================

:INSTALL_VENV
echo.
echo =====================================================
echo ERST-INSTALLATION (Nur beim ersten Mal)
echo =====================================================
echo Erstelle virtuelle Umgebung (venv)...
python -m venv venv
if %errorlevel% neq 0 goto ERROR_VENV_CREATE

echo Aktiviere Umgebung...
call venv\Scripts\activate.bat

echo Installiere Bibliotheken (TTS, OCR, etc.)...
echo Das kann 2-5 Minuten dauern. Bitte warten.
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo Installation fertig!
goto START_APP

:ERROR_PYTHON
echo.
echo [FEHLER] Python wurde nicht gefunden!
echo.
echo Bitte installiere Python von python.org.
echo WICHTIG: Setze beim Installieren den Haken bei "Add Python to PATH".
echo.
pause
exit /b

:ERROR_VENV_CREATE
echo.
echo [FEHLER] Konnte venv nicht erstellen.
echo Hast du Schreibrechte in diesem Ordner?
pause
exit /b

:ERROR_VENV_BROKEN
echo.
echo [FEHLER] Die virtuelle Umgebung ist beschraedigt.
echo Bitte loesche den Ordner "venv" und starte neu.
pause
exit /b

:ERROR_MAIN
echo.
echo [FEHLER] Datei "src\main.py" fehlt!
echo Bist du im richtigen Ordner?
pause
exit /b

:CRASHED
echo.
echo -----------------------------------------------------
echo Das Programm wurde unerwartet beendet.
echo Siehe Fehlermeldung oben.
echo -----------------------------------------------------
pause
exit /b

:END
echo.
echo Programm beendet.
pause
