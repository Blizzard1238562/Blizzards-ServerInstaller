"""Run + management script generation for installed servers.

start.bat/sh launch the server with Aikar's flags - the widely-used, well-
tested JVM flag set for Paper servers: https://docs.papermc.io/paper/aikars-flags

stop/restart/backup cover day-to-day operation: stop terminates only the java
process started with this server's jar (other Java programs are left alone),
restart stops and starts again, and backup archives the worlds + plugins into
backups/ with a timestamp. Windows scripts use PowerShell (ships with every
supported Windows); Linux/macOS scripts use plain bash + tar/pkill.
"""

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


def _bat(*lines: str) -> str:
    return "\r\n".join(lines) + "\r\n"


def _pcre_escape(name: str) -> str:
    """Escape a jar name for use inside a pgrep/pkill regular expression."""
    return name.replace(".", r"\.")


def _win_kill(jar_name: str) -> str:
    """One PowerShell one-liner that stops the java process started with
    jar_name. Deliberately avoids double quotes and other cmd metacharacters
    so it can live unescaped inside a .bat file; matches on the process
    command line, so unrelated Java processes are untouched."""
    return (
        "$p = Get-CimInstance Win32_Process | Where-Object { "
        "$_.Name -eq 'java.exe' -and $_.CommandLine -like '*"
        + jar_name
        + "*' }; "
        "if ($p) { $p | ForEach-Object { Stop-Process -Id $_.ProcessId -Force "
        "-ErrorAction SilentlyContinue }; Write-Host 'Server stopped.' } "
        "else { Write-Host 'Server is not running.' }"
    )


def _win_backup() -> str:
    """One PowerShell one-liner zipping the worlds + plugins into backups/."""
    return (
        "$stamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'; "
        "$targets = @(); "
        "foreach ($n in @('world','world_nether','world_the_end','plugins')) "
        "{ if (Test-Path $n) { $targets += $n } }; "
        "if ($targets.Count -eq 0) { Write-Host 'Nothing to back up yet - "
        "start the server once first.' } "
        "else { Compress-Archive -Path $targets -DestinationPath "
        "(Join-Path 'backups' ('backup-' + $stamp + '.zip')) -Force; "
        "Write-Host ('Backup written: backups\\backup-' + $stamp + '.zip') }"
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

    write_management_scripts(server_dir, jar_name)
    ok("Wrote start.bat/start.sh plus stop, restart and backup helper scripts")


def write_management_scripts(server_dir: Path, jar_name: str) -> None:
    """Write stop/restart/backup scripts next to start.bat/start.sh.

    The scripts are regenerated per server because they need the exact jar
    name to target only this server's java process.
    """
    sh = server_dir / "stop.sh"
    sh.write_text(
        "#!/usr/bin/env bash\n"
        "# Stops this server if it is running. Only the java process started\n"
        "# with this server's jar is stopped - other Java programs are left\n"
        "# alone. Sends a normal stop signal (the JVM shuts down and saves),\n"
        "# escalating to a hard kill after 30 seconds.\n"
        'cd "$(dirname "$0")"\n'
        f'pat="{_pcre_escape(jar_name)}"\n'
        'if ! pgrep -f "$pat" >/dev/null 2>&1; then\n'
        '  echo "Server is not running."\n'
        "  exit 0\n"
        "fi\n"
        'echo "Stopping the server..."\n'
        'pkill -f "$pat"\n'
        "i=0\n"
        "while [ $i -lt 30 ]; do\n"
        '  if ! pgrep -f "$pat" >/dev/null 2>&1; then\n'
        '    echo "Server stopped."\n'
        "    exit 0\n"
        "  fi\n"
        "  sleep 1\n"
        "  i=$((i + 1))\n"
        "done\n"
        'echo "Server did not stop in 30s - forcing."\n'
        'pkill -9 -f "$pat"\n',
        encoding="utf-8",
    )

    restart_sh = server_dir / "restart.sh"
    restart_sh.write_text(
        "#!/usr/bin/env bash\n"
        "# Restarts this server: stops the running instance (if any), waits\n"
        "# two seconds, then starts the server again in this terminal.\n"
        'cd "$(dirname "$0")"\n'
        './stop.sh\n'
        "sleep 2\n"
        "exec ./start.sh\n",
        encoding="utf-8",
    )

    backup_sh = server_dir / "backup.sh"
    backup_sh.write_text(
        "#!/usr/bin/env bash\n"
        "# Backs up the worlds and plugins folders into backups/ as a\n"
        "# timestamped tar.gz. Stop the server first for a fully consistent\n"
        "# backup.\n"
        'cd "$(dirname "$0")"\n'
        "mkdir -p backups\n"
        'stamp=$(date +%Y-%m-%d_%H-%M-%S)\n'
        "targets=()\n"
        "for d in world world_nether world_the_end plugins; do\n"
        '  [ -d "$d" ] && targets+=("$d")\n'
        "done\n"
        "if [ ${#targets[@]} -eq 0 ]; then\n"
        '  echo "Nothing to back up yet - start the server once first."\n'
        "  exit 0\n"
        "fi\n"
        'tar -czf "backups/backup-${stamp}.tar.gz" "${targets[@]}"\n'
        'echo "Backup written: backups/backup-${stamp}.tar.gz"\n',
        encoding="utf-8",
    )
    for script in (sh, restart_sh, backup_sh):
        try:
            os.chmod(script, 0o755)
        except Exception:
            pass

    (server_dir / "stop.bat").write_text(
        _bat(
            "@echo off",
            "REM Stops this server if it is running. Only the java process started",
            "REM with this server's jar is stopped - other Java programs are left",
            'REM alone. For a clean shutdown, type "stop" in the server console',
            "REM instead; this script is for when that console window is gone.",
            f'powershell -NoProfile -Command "{_win_kill(jar_name)}"',
            "pause",
        ),
        encoding="utf-8",
    )

    (server_dir / "restart.bat").write_text(
        _bat(
            "@echo off",
            "REM Restarts this server: stops the running instance (if any), waits",
            "REM two seconds, then starts the server again in this window.",
            f'powershell -NoProfile -Command "{_win_kill(jar_name)}"',
            "timeout /t 2 /nobreak >nul",
            'call "%~dp0start.bat"',
        ),
        encoding="utf-8",
    )

    (server_dir / "backup.bat").write_text(
        _bat(
            "@echo off",
            "REM Backs up this server's worlds and plugins into the backups folder",
            "REM as a timestamped zip. Stop the server first for a fully",
            "REM consistent backup.",
            'cd /d "%~dp0"',
            "if not exist backups mkdir backups",
            f'powershell -NoProfile -Command "{_win_backup()}"',
            "pause",
        ),
        encoding="utf-8",
    )
