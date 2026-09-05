#!/usr/bin/env python3
"""Blizzards Server Installer - entry point.

The actual code lives in the blizzards_installer/ package (see its docstring
for a module map); this file only checks dependencies, runs the wizard and
handles top-level errors. Requires: Python 3.9+, `PyYAML` (see
requirements.txt); HTTP uses the standard library. A JDK/JRE on PATH is
required to auto-generate Paper's default config files during install - if
Java isn't found, the installer still works, it just leaves a short note on
what to change by hand.
"""

import sys
import traceback

try:
    import yaml  # noqa: F401
except ImportError:
    print("Missing dependency 'PyYAML'. Install it with: pip install pyyaml")
    sys.exit(1)

from blizzards_installer.ui import banner, error, warn
from blizzards_installer.wizard import run_wizard


def main() -> None:
    banner()
    try:
        run_wizard()
    except KeyboardInterrupt:
        print()
        warn("Cancelled by user.")
    except Exception:
        error("Something went wrong:")
        traceback.print_exc()
    finally:
        try:
            input("\nPress Enter to exit...")
        except (EOFError, KeyboardInterrupt):
            pass


if __name__ == "__main__":
    main()
