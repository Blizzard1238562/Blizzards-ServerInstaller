"""Optional playit.gg integration: make a freshly installed server joinable
by others without port forwarding.

Design notes (see docs/public-servers.md):

- The agent is downloaded from the playit GitHub release matching the
  current platform (their own /download pages are HTML, so we resolve the
  latest release via the GitHub API instead of pinning a version).
- First run needs a one-time interactive claim. The v1.0.x agent is a daemon
  that persists its secret to the OS user config dir
  (%LOCALAPPDATA%\\playit_gg\\playit.toml on Windows) and expects a frontend
  (the console UI) to provision that secret, so claiming cannot be fully
  automated without playit credentials. We therefore open the agent's claim
  console for the user and document the dashboard "Add Agent" secret as an
  alternative.
- After the agent is claimed, `start-public.bat` / `start-public.sh` run the
  agent and the server together.

Everything in this module is best-effort: callers wrap it so a failure only
warns and the install still completes.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path

from . import net
from .scripts import _aikars_flags
from .ui import info, ok, warn

PLAYIT_RELEASES_API = "https://api.github.com/repos/playit-cloud/playit-agent/releases/latest"

_LINUX_ARCH_ASSETS = {
    "amd64": "amd64",
    "x86_64": "amd64",
    "aarch64": "aarch64",
    "arm64": "aarch64",
    "armv7l": "armv7",
    "armv6l": "armv7",
    "i686": "i686",
    "x86": "i686",
}


def agent_asset() -> tuple[str, str]:
    """Return (asset_name, download_url) for the current platform from the
    latest playit release. Raises RuntimeError when nothing matches."""
    data = net.http_get_json(PLAYIT_RELEASES_API)
    if not isinstance(data, dict):
        raise RuntimeError("The playit.gg release API returned an unexpected response.")
    assets = [
        a for a in data.get("assets", [])
        if isinstance(a, dict) and a.get("name") and a.get("browser_download_url")
    ]
    machine = platform.machine().lower()

    if sys.platform == "win32":
        arch = "x86_64" if machine in ("amd64", "x86_64") else ("x86" if machine in ("x86", "i386", "i686") else None)
        if not arch:
            raise RuntimeError(f"No playit.gg agent for this Windows architecture ({machine}).")
        wanted = [f"playit-windows-{arch}-signed.exe", f"playit-windows-{arch}.exe"]
    elif sys.platform.startswith("linux"):
        arch = _LINUX_ARCH_ASSETS.get(machine, "amd64")
        wanted = [f"playit-linux-{arch}"]
    elif sys.platform == "darwin":
        raise RuntimeError(
            "playit.gg publishes macOS agents only from playit.gg/download, "
            "not as GitHub release assets - install that one by hand."
        )
    else:
        raise RuntimeError(f"playit.gg does not support this platform ({sys.platform}).")

    for want in wanted:
        for asset in assets:
            if asset["name"] == want:
                return asset["name"], asset["browser_download_url"]
    raise RuntimeError(
        "Could not find a playit.gg agent download for this machine in the latest release."
    )


def install_agent(server_dir: Path) -> Path:
    """Download the playit.gg agent into server_dir/playit and return its path."""
    name, url = agent_asset()
    dest = server_dir / "playit" / name
    net.download_file(url, dest, "playit.gg agent")
    if os.name != "nt":
        os.chmod(dest, 0o755)
    ok(f"Downloaded the playit.gg agent ({name})")
    return dest


def open_claim_console(agent: Path) -> bool:
    """Open the agent's one-time claim screen.

    On Windows this launches the agent in its own console window (the v1.0.x
    agent needs that console frontend to provision the account secret). On
    other platforms we cannot open a terminal for the user, so we print
    instructions and return False."""
    if sys.platform == "win32":
        # 0x10 == CREATE_NEW_CONSOLE (not defined on POSIX Python builds).
        subprocess.Popen(
            [str(agent)],
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0x10),
        )
        info(
            "A new window opened to claim the playit.gg agent: log in or create "
            "a free account there, then you can close that window."
        )
        return True
    warn("Open a terminal in the server folder and run the playit agent once to claim it:")
    return False


def _agent_name_and_path(server_dir: Path) -> tuple[str, Path]:
    """Find the downloaded agent. Falls back to any file in server_dir/playit."""
    playit_dir = server_dir / "playit"
    if not playit_dir.exists():
        raise FileNotFoundError("The playit.gg agent is not downloaded yet.")
    files = sorted(p for p in playit_dir.iterdir() if p.is_file())
    if not files:
        raise FileNotFoundError("The playit.gg agent is not downloaded yet.")
    return files[0].name, files[0]


def write_public_files(server_dir: Path, jar_name: str, ram_mb: int) -> None:
    """Write start-public.bat/sh (agent + server) and PUBLIC_SERVER.txt."""
    agent_name, _agent_path = _agent_name_and_path(server_dir)
    flags = _aikars_flags(ram_mb)

    (server_dir / "start-public.bat").write_text(
        "@echo off\r\n"
        f'start "Blizzards Server - playit tunnel" "{server_dir / "playit" / agent_name}"\r\n'
        f"java {flags} -jar \"{jar_name}\" --nogui\r\n"
        "pause\r\n",
        encoding="utf-8",
    )

    sh = server_dir / "start-public.sh"
    sh.write_text(
        "#!/usr/bin/env bash\n"
        "cd \"$(dirname \"$0\")\"\n"
        f'("./playit/{agent_name}" &)\n'
        f'java {flags} -jar "{jar_name}" --nogui\n',
        encoding="utf-8",
    )
    try:
        os.chmod(sh, 0o755)
    except Exception:
        pass

    notes = server_dir / "PUBLIC_SERVER.txt"
    notes.write_text(
        "Making your server public with playit.gg\n"
        "========================================\n"
        "\n"
        "The playit.gg agent was downloaded into the playit/ folder. It tunnels\n"
        "traffic to playit's network so players can join without you opening any\n"
        "ports on your router.\n"
        "\n"
        "First time only - claim the agent:\n"
        "  Option A: run start-public.bat (Windows) / ./start-public.sh (Linux).\n"
        "    The agent window will ask you to log in or create a free playit.gg\n"
        "    account once. After that it stays linked on this machine.\n"
        "  Option B: open https://playit.gg, go to Agents -> Add Agent, copy the\n"
        "    secret key, and follow the on-screen steps to link this machine.\n"
        "\n"
        "Then expose the server:\n"
        "  1. In the playit.gg dashboard, find your agent and create a tunnel:\n"
        "     type Minecraft Java, protocol TCP, local address 127.0.0.1:25565.\n"
        "  2. playit shows you a public address (hostname:port). Share that\n"
        "     address; players add it in Minecraft's multiplayer screen.\n"
        "\n"
        "Notes:\n"
        "  - The agent and the server must both keep running while you play.\n"
        "  - Anyone with the address can try to join: consider enabling the\n"
        "    whitelist in server.properties if the server is not just for friends.\n"
        "  - Free playit accounts get one TCP tunnel (Java Edition). Bedrock/UDP\n"
        "    needs their paid tier.\n",
        encoding="utf-8",
    )
    ok("Wrote start-public.bat, start-public.sh and PUBLIC_SERVER.txt")
