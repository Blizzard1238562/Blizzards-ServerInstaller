#!/usr/bin/env bash
set -e

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 was not found. Install it with your package manager first,"
    echo "e.g. 'sudo apt install python3 python3-pip' on Debian/Ubuntu."
    exit 1
fi

cd "$(dirname "$0")"

if ! python3 -c "import requests" >/dev/null 2>&1 || ! python3 -c "import ruamel.yaml" >/dev/null 2>&1; then
    echo "Installing dependencies..."
    python3 -m pip install -r requirements.txt --break-system-packages 2>/dev/null \
        || python3 -m pip install -r requirements.txt
fi

python3 installer.py
