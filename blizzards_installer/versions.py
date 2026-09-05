"""Minecraft version discovery via Mojang's own manifest - the authoritative
list of real released versions, independent of whichever jar-hosting API we
use."""

from __future__ import annotations

from . import net
from .ui import ask_choice, ask_text, warn

MOJANG_VERSION_MANIFEST = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"

MANUAL_VERSION_PROMPT = "Enter the Minecraft version (e.g. 1.21.4)"


def get_recent_release_versions(limit: int = 15) -> list[str]:
    data = net.http_get_json(MOJANG_VERSION_MANIFEST)
    if not isinstance(data, dict):
        return []
    versions = [v["id"] for v in data.get("versions", []) if v.get("type") == "release"]
    return versions[:limit]


def choose_minecraft_version() -> str:
    try:
        recent = get_recent_release_versions()
    except Exception as exc:
        warn(f"Could not reach Mojang's version list ({exc}).")
        recent = []

    if recent:
        manual = "Type a version manually"
        idx = ask_choice("Which Minecraft version do you want?", recent + [manual], default_index=0)
        if idx != len(recent):
            return recent[idx]
    return ask_text(MANUAL_VERSION_PROMPT)
