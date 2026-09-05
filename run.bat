@echo off
setlocal

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found on PATH.
    echo Install it from https://python.org - make sure "Add python.exe to PATH" is checked during setup.
    pause
    exit /b 1
)

python -c "import yaml" >nul 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    python -m pip install -r requirements.txt
)

python installer.py
