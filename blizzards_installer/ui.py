"""Small console UI helpers. Prompts and status lines stay ASCII so old
Windows cmd.exe renders them fine without colorama; only the startup
banner uses Unicode block art."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator, Optional

from .meta import VERSION

BANNER_ART = """                ████ █    ██   ████ ████  ██  ███  ███  ████                
                █  █ █    ██     ██   ██ █  █ █  █ █  █ █                   
                ████ █    ██    ██   ██  █  █ █  █ █  █ ████                
                █  █ █    ██   ██   ██   ████ ████ █  █    █                
                █  █ █    ██   █    █    █  █ █ █  █  █    █                
                ████ ████ ██   ████ ████ █  █ █  █ ███  ████                

████ ████ ███  █  █ ████ ███    ██   █  █ ████ ████  ██  █    █    ████ ███ 
█    █    █  █ █  █ █    █  █   ██   ██ █ █     ██  █  █ █    █    █    █  █
████ ████ █  █ █  █ ████ █  █   ██   █ ██ ████  ██  █  █ █    █    ████ █  █
   █ █    ████  ██  █    ████   ██   █  █    █  ██  ████ █    █    █    ████
   █ █    █ █   ██  █    █ █    ██   █  █    █  ██  █  █ █    █    █    █ █ 
████ ████ █  █  █   ████ █  █   ██   █  █ ████  ██  █  █ ████ ████ ████ █  █"""


def banner() -> None:
    try:
        print(BANNER_ART)
        print(f"  v{VERSION} - interactive Minecraft server installer".center(76))
    except UnicodeEncodeError:
        # Block-art glyphs need a Unicode-capable output (real terminals have
        # one). When stdout is redirected to a legacy codepage (e.g. cp1252),
        # degrade to the plain ASCII header instead of crashing.
        print("=" * 64)
        print("  Blizzards Server Installer".center(64))
        print(f"  v{VERSION}".center(64))
        print("=" * 64)
    print()


def section(title: str) -> None:
    print(f"\n--- {title} " + "-" * max(0, 55 - len(title)))


def _line(tag: str, msg: str) -> None:
    print(f"  [{tag}] {msg}")


def info(msg: str) -> None:
    _line("i", msg)


def ok(msg: str) -> None:
    _line("OK", msg)


def warn(msg: str) -> None:
    _line("!", msg)


def error(msg: str) -> None:
    _line("X", msg)


@contextmanager
def activity(label: str) -> Iterator[None]:
    """Animated spinner while a blocking call runs, so the console never
    looks frozen during network waits. Resolves to 'label... done'."""
    stop = threading.Event()
    frames = "|/-\\"

    def _spin() -> None:
        i = 0
        while not stop.wait(0.1):
            try:
                print(f"\r  {label}... {frames[i % 4]}", end="", flush=True)
            except OSError:  # stdout closed (piped away) - stop quietly
                return
            i += 1

    thread = threading.Thread(target=_spin, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join()
        try:
            print(f"\r  {label}... done")
        except OSError:
            pass


def ask_yes_no(question: str, default: bool = True) -> bool:
    """Yes/no prompt. The default (what pressing Enter selects) is always
    shown explicitly and the y/n letters stay lowercase so the suffix never
    changes shape depending on the default."""
    label = "yes" if default else "no"
    while True:
        raw = input(f"  ? {question} [y/n] (default: {label}) ").strip().lower()
        if not raw:
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("    Please answer y or n.")


def ask_text(question: str, default: Optional[str] = None) -> str:
    raw = input(f"  ? {question}{f' [{default}]' if default is not None else ''}: ").strip()
    return raw or default or ""


def ask_int(question: str, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    """Whole-number prompt. Optional minimum/maximum bounds reject nonsense
    values (e.g. negative RAM) by re-asking."""
    while True:
        raw = input(f"  ? {question} [{default}]: ").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            print("    Please enter a whole number.")
            continue
        if (minimum is not None and value < minimum) or (maximum is not None and value > maximum):
            lo = minimum if minimum is not None else "any"
            hi = maximum if maximum is not None else "any"
            print(f"    Please enter a value between {lo} and {hi}.")
            continue
        return value


def ask_choice(question: str, options: list[str], default_index: int = 0) -> int:
    print(f"  ? {question}")
    for idx, opt in enumerate(options, start=1):
        print(f"      {idx}) {opt}{' (default)' * (idx - 1 == default_index)}")
    while True:
        raw = input(f"    Choice [1-{len(options)}]: ").strip()
        if not raw:
            return default_index
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        print("    Invalid choice.")