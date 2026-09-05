@echo off
REM Builds Blizzards-Server-Installer.exe. Run this ON WINDOWS (PyInstaller does
REM not cross-compile - a .exe has to be built on a Windows machine/VM).
REM
REM Usage:
REM   1. Install Python 3.10+ from python.org (check "Add to PATH" during install)
REM   2. Open this folder in a terminal
REM   3. Run: build_exe.bat

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python -m PyInstaller --onefile --name Blizzards-Server-Installer ^
    --add-data "plugins.json;." ^
    --console ^
    installer.py

echo.
echo Build finished. Find your exe in the "dist" folder.
pause
