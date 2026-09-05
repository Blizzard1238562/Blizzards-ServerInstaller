"""Start script generation (Aikar's flags - the widely-used, well-tested JVM
flag set for Paper servers: https://docs.papermc.io/paper/aikars-flags)."""

from __future__ import annotations

import os
from pathlib import Path

from .ui import ok


def _aikars_flags(ram_mb: int) -> str:
    return (
        f"-Xms{ram_mb}M -Xmx{ram_mb}M "
        "-XX:+UseG1GC -XX:+ParallelRefProcEnabled -XX:MaxGCPauseMillis=200 "
        "-XX:+UnlockExperimentalVMOptions -XX:+DisableExplicitGC -XX:+AlwaysPreTouch "
        "-XX:G1NewSizePercent=30 -XX:G1MaxNewSizePercent=40 -XX:G1HeapRegionSize=8M "
        "-XX:G1ReservePercent=20 -XX:G1HeapWastePercent=5 -XX:G1MixedGCCountTarget=4 "
        "-XX:InitiatingHeapOccupancyPercent=15 -XX:G1MixedGCLiveThresholdPercent=90 "
        "-XX:G1RSetUpdatingPauseTimePercent=5 -XX:SurvivorRatio=32 "
        "-XX:+PerfDisableSharedMem -XX:MaxTenuringThreshold=1 "
        "-Dusing.aikars.flags=https://mcflags.emc.gs -Daikars.new.flags=true"
    )


def write_start_scripts(server_dir: Path, jar_name: str, ram_mb: int) -> None:
    flags = _aikars_flags(ram_mb)

    bat = server_dir / "start.bat"
    bat.write_text(
        "@echo off\r\n"
        f"java {flags} -jar \"{jar_name}\" --nogui\r\n"
        "pause\r\n",
        encoding="utf-8",
    )

    sh = server_dir / "start.sh"
    sh.write_text(
        "#!/usr/bin/env bash\n"
        f'java {flags} -jar "{jar_name}" --nogui\n',
        encoding="utf-8",
    )
    try:
        os.chmod(sh, 0o755)
    except Exception:
        pass

    ok("Wrote start.bat and start.sh")
