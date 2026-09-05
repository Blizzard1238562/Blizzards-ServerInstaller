"""Small console UI helpers (kept ASCII-only so old Windows cmd.exe renders
them fine without extra dependencies like colorama)."""

from __future__ import annotations

from typing import Optional

from .meta import VERSION


def banner() -> None:
    print("=" * 64)
    print("  Blizzards Server Installer".center(64))
    print(f"  v{VERSION}".center(64))
    print("=" * 64)
    print()


def section(title: str) -> None:
    print()
    print(f"--- {title} " + "-" * max(0, 55 - len(title)))


def info(msg: str) -> None:
    print(f"  [i] {msg}")


def ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def warn(msg: str) -> None:
    print(f"  [!] {msg}")


def error(msg: str) -> None:
    print(f"  [X] {msg}")


def ask_yes_no(question: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        raw = input(f"  ? {question} {suffix} ").strip().lower()
        if not raw:
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("    Please answer y or n.")


def ask_text(question: str, default: Optional[str] = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    raw = input(f"  ? {question}{suffix}: ").strip()
    return raw if raw else (default or "")


def ask_int(question: str, default: int) -> int:
    while True:
        raw = input(f"  ? {question} [{default}]: ").strip()
        if not raw:
            return default
        try:
            return int(raw)
        except ValueError:
            print("    Please enter a whole number.")


def ask_choice(question: str, options: list[str], default_index: int = 0) -> int:
    print(f"  ? {question}")
    for idx, opt in enumerate(options, start=1):
        marker = " (default)" if idx - 1 == default_index else ""
        print(f"      {idx}) {opt}{marker}")
    while True:
        raw = input(f"    Choice [1-{len(options)}]: ").strip()
        if not raw:
            return default_index
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        print("    Invalid choice.")
