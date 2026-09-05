"""Installer self-update check.

Looks up the newest GitHub Release once at startup and reports it if it is
newer than the running version. Purely informational: network failures, rate
limits and missing releases are swallowed so an update hint is never a
blocker. HTTP is done with the standard library and a short timeout so the
check stays invisible on slow or offline machines.
"""

from __future__ import annotations

import json
import re
import urllib.request

from .meta import USER_AGENT, VERSION

RELEASE_URL = "https://api.github.com/repos/Blizzard1238562/Blizzards-ServerInstaller/releases/latest"
CHECK_TIMEOUT = 6


def _parse_version(text: str) -> tuple[int, ...]:
    """Turn 'v1.2.0' or '1.2.0-beta.1' into a comparable integer tuple.
    Suffixes like '-beta.1' are ignored: a prerelease tag then compares equal
    to the release it precedes, which is the safe direction for a hint."""
    match = re.match(r"\s*v?(\d+(?:\.\d+)*)", text or "")
    if not match:
        return ()
    return tuple(int(part) for part in match.group(1).split("."))


def _latest_release_tag(timeout: int = CHECK_TIMEOUT) -> str | None:
    request = urllib.request.Request(RELEASE_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    tag = (data.get("tag_name") or "").strip()
    if not tag:
        return None
    return tag if tag.startswith("v") else f"v{tag}"


def available_update(timeout: int = CHECK_TIMEOUT) -> str | None:
    """Return the newest release tag when it is newer than VERSION, else None."""
    try:
        tag = _latest_release_tag(timeout=timeout)
    except Exception:
        return None
    if not tag or _parse_version(tag) <= _parse_version(VERSION):
        return None
    return tag
