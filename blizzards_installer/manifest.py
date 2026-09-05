"""Install manifest for re-run-to-update.

During an install the wizard records what it put into the server folder
(software, Minecraft version, RAM, plugin ids) in a small JSON file. Running
the installer again into that folder can then offer to refresh the server jar
and plugin jars to their newest builds without touching the world or the
configs the user has since changed.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

MANIFEST_NAME = "blizzards-installer.json"
TOOL_TAG = "blizzards-server-installer"


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def manifest_path(server_dir: Path) -> Path:
    return server_dir / MANIFEST_NAME


def write_manifest(
    server_dir: Path,
    *,
    server_type: str,
    mc_version: str,
    ram_mb: int,
    plugin_ids: list[str],
) -> dict:
    """Record an install into server_dir; returns the manifest dict."""
    data = {
        "tool": TOOL_TAG,
        "created": _utc_now(),
        "updated": _utc_now(),
        "server_type": server_type,
        "mc_version": mc_version,
        "ram_mb": ram_mb,
        "plugins": list(plugin_ids),
    }
    manifest_path(server_dir).write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def read_manifest(server_dir: Path) -> dict | None:
    """Return the manifest dict if server_dir holds one of our installs.

    None for a missing file, unreadable JSON, or a file that wasn't written
    by this tool (tool tag mismatch) - i.e. the folder is not one we manage.
    """
    path = manifest_path(server_dir)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("tool") != TOOL_TAG:
        return None
    return data


def touch_manifest(server_dir: Path, manifest: dict) -> None:
    """Bump the 'updated' timestamp after an update run."""
    manifest["updated"] = _utc_now()
    manifest_path(server_dir).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
