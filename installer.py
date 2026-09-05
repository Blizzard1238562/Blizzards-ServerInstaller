#!/usr/bin/env python3
"""Blizzards Server Installer - entry point.

The actual code lives in the blizzards_installer/ package (see its docstring
for a module map); this file only checks dependencies, runs the wizard and
handles top-level errors. Requires: Python 3.9+, `PyYAML` (see
requirements.txt); HTTP uses the standard library. A JDK/JRE on PATH is
required to auto-generate Paper's default config files during install - if
Java isn't found, the installer still works, it just leaves a short note on
what to change by hand.

CLI flags (scripting / headless use): any of the flags below runs the Quick
start install without asking anything - missing values fall back to the same
defaults the wizard would offer, and failures exit with a non-zero code.

  --quick            unattended Quick start install
  --dir PATH         install folder (default: ./server)
  --name NAME        server name (default: Minecraft Server)
  --ram MB           RAM for the start script (default: auto-detected)

If --dir points at a folder that already contains a Blizzards install, the
installer refreshes that server instead (newest jar + plugins, configs kept).
"""

import argparse
import sys
import traceback
from pathlib import Path

try:
    import yaml  # noqa: F401
except ImportError:
    print("Missing dependency 'PyYAML'. Install it with: pip install pyyaml")
    sys.exit(1)

from blizzards_installer.ui import banner, error, info, warn
from blizzards_installer.update import available_update
from blizzards_installer.wizard import run_quick_unattended, run_wizard


def _parse_args(argv):
    parser = argparse.ArgumentParser(
        prog="Blizzards-Server-Installer",
        description="Interactive Minecraft server installer (Paper/Purpur/Pufferfish/Folia).",
    )
    parser.add_argument("--quick", action="store_true", help="run the Quick start without prompts")
    parser.add_argument("--dir", metavar="PATH", help="install directory (default: ./server)")
    parser.add_argument("--name", metavar="NAME", help="server name (default: Minecraft Server)")
    parser.add_argument("--ram", metavar="MB", type=int, help="RAM for the start script in MB")
    return parser.parse_args(argv)


def main(argv=None) -> None:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    unattended = args.quick or args.dir is not None or args.name is not None or args.ram is not None

    banner()
    try:
        newest = available_update()
    except Exception:
        newest = None
    if newest:
        info(f"Update available: {newest} - download it from the GitHub releases page.")
    try:
        if unattended:
            run_quick_unattended(
                server_name=args.name,
                server_dir=Path(args.dir) if args.dir else None,
                ram_mb=args.ram,
            )
        else:
            run_wizard()
    except KeyboardInterrupt:
        print()
        warn("Cancelled by user.")
        if unattended:
            sys.exit(130)
    except Exception:
        error("Something went wrong:")
        traceback.print_exc()
        if unattended:
            sys.exit(1)
    finally:
        if not unattended:
            try:
                input("\nPress Enter to exit...")
            except (EOFError, KeyboardInterrupt):
                pass


if __name__ == "__main__":
    main()
