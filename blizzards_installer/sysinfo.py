"""Zero-dependency system info helpers.

Only what the wizard needs: total physical RAM, used to prefill the RAM
question with a sensible value (no new runtime dependency - just ctypes on
Windows, /proc/meminfo on Linux and sysctl on macOS). Any failure falls back
to a flat default so the installer never breaks on an exotic platform.
"""

from __future__ import annotations

import os
import subprocess

DEFAULT_RAM_MB = 4096
MAX_RECOMMENDED_MB = 8192


def _meminfo_kb(text: str) -> int | None:
    """Parse MemTotal from /proc/meminfo content (returns kB)."""
    for line in text.splitlines():
        if line.startswith("MemTotal:"):
            try:
                return int(line.split()[1])
            except (IndexError, ValueError):
                return None
    return None


def total_ram_mb() -> int | None:
    """Total physical RAM in MB, or None when it can't be determined."""
    try:
        if os.name == "nt":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.ullTotalPhys // (1024 * 1024))
            return None
        if os.path.exists("/proc/meminfo"):
            with open("/proc/meminfo", "r", encoding="utf-8") as fh:
                kb = _meminfo_kb(fh.read())
            return int(kb // 1024) if kb else None
        result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip().isdigit():
            return int(result.stdout.strip()) // (1024 * 1024)
    except Exception:
        pass
    return None


def suggest_ram_mb(total_mb: int) -> int:
    """Turn total RAM into a start-script suggestion.

    Half of the machine's memory, capped at 8 GB (allocating beyond that to a
    single Minecraft server rarely helps), floored to a 256 MB step and never
    below 1 GB so tiny machines still leave room for the OS.
    """
    if not total_mb or total_mb <= 0:
        return DEFAULT_RAM_MB
    half = total_mb // 2
    suggested = min(half, MAX_RECOMMENDED_MB)
    suggested = suggested // 256 * 256
    return max(1024, suggested)


def recommended_ram_mb() -> int:
    """Suggested default RAM for the wizard; never raises."""
    total = total_ram_mb()
    if total is None:
        return DEFAULT_RAM_MB
    return suggest_ram_mb(total)
