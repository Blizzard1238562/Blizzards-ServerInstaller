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

REM Excluded modules are never used by this console-only app (no GUI/tests/
REM async); trimming them keeps the exe ~5 MB smaller. The only third-party
REM runtime dependency is PyYAML, which is small and stays.
python -m PyInstaller --onefile --name Blizzards-Server-Installer ^
    --add-data "plugins.json;." ^
    --console ^
    --exclude-module setuptools --exclude-module pkg_resources ^
    --exclude-module pip --exclude-module numpy ^
    --exclude-module unittest --exclude-module pydoc --exclude-module pydoc_data ^
    --exclude-module doctest --exclude-module lib2to3 ^
    --exclude-module http.server --exclude-module socketserver ^
    --exclude-module asyncio --exclude-module multiprocessing ^
    --exclude-module curses --exclude-module xmlrpc ^
    --exclude-module tkinter --exclude-module ensurepip --exclude-module idlelib ^
    --exclude-module cryptography --exclude-module OpenSSL ^
    --exclude-module cffi --exclude-module zstandard ^
    --exclude-module decimal --exclude-module _decimal ^
    --exclude-module socks --exclude-module zoneinfo --exclude-module _zoneinfo ^
    --exclude-module unicodedata ^
    installer.py

echo.
echo Build finished. Find your exe in the "dist" folder.
pause
