@echo off
title LQAG Installer - Richte Umgebung ein...
color 0A

echo ========================================================
echo   LQAG INSTALLER - (Das dauert ca. 5-10 Minuten)
echo ========================================================
echo.

if exist "Engine" (
    echo [INFO] Engine-Ordner existiert bereits.
    echo Falls du neu installieren willst, loesche den Ordner 'Engine'.
    pause
    exit
)

REM 1. Python Embeddable herunterladen (ca. 10 MB)
mkdir Engine
cd Engine
echo [1/5] Lade Python 3.10 herunter...
curl -L -o python.zip https://www.python.org/ftp/python/3.10.11/python-3.10.11-embed-amd64.zip
echo [INFO] Entpacke Python...
tar -xf python.zip
del python.zip

REM 2. Pip aktivieren
echo [2/5] Aktiviere PIP Paketmanager...
curl -L -o get-pip.py https://bootstrap.pypa.io/get-pip.py
python.exe get-pip.py --no-warn-script-location

REM 3. pth Datei patchen (wichtig damit pip geht)
echo [INFO] Konfiguriere Python Pfade...
echo import site>> python310._pth

REM 4. PyTorch installieren (Das Grosse Paket - 2.5 GB)
echo.
echo [3/5] Installiere PyTorch (GPU Support)... 
echo       DAS DAUERT LANGE! BITTE WARTEN...
python.exe -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

REM 5. Restliche Bibliotheken
echo.
echo [4/5] Installiere TTS und Tools...
python.exe -m pip install numpy==1.26.4
python.exe -m pip install TTS easyocr pyaudio keyboard pyautogui opencv-python pillow soundfile

echo.
echo [5/5] Raeume auf...
del get-pip.py

cd ..
echo.
echo ========================================================
echo   INSTALLATION FERTIG!
echo   Du kannst jetzt START.bat klicken.
echo ========================================================
pause
