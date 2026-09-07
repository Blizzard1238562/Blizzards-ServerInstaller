"""Minecraft version discovery via Mojang's own manifest - the authoritative
list of real released versions, independent of whichever jar-hosting API we
use."""

from __future__ import annotations

import re

from . import net
from .ui import activity, ask_choice, ask_text, warn

MOJANG_VERSION_MANIFEST = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"

MANUAL_VERSION_PROMPT = "Enter the Minecraft version (e.g. 1.21.4)"

# Manual version entries end up in jar filenames and generated start scripts,
# so only a safe charset is accepted (letters, digits, dots, dashes,
# underscores - covers 1.21.4, 1.20.1-pre2, 23w14a, b1.7.3, ...). A leading
# "v" is rejected: that's a git-tag habit, never a real Minecraft version.
MC_VERSION_RE = re.compile(r"^(?![vV])[0-9A-Za-z][0-9A-Za-z._-]{0,39}$")


def is_valid_mc_version(text: str) -> bool:
    return bool(MC_VERSION_RE.fullmatch(text or ""))


def ask_manual_version() -> str:
    """Ask for a version by hand, re-prompting until it looks like one."""
    while True:
        version = ask_text(MANUAL_VERSION_PROMPT)
        if is_valid_mc_version(version):
            return version
        warn("That doesn't look like a Minecraft version - use letters, digits, dots, dashes or underscores (e.g. 1.21.4).")


def get_recent_release_versions(limit: int = 15) -> list[str]:
    with activity("Fetching Minecraft version list"):
        data = net.http_get_json(MOJANG_VERSION_MANIFEST)
    if not isinstance(data, dict):
        return []
    return [v["id"] for v in data.get("versions", []) if v.get("type") == "release"][:limit]


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
    return ask_manual_version()