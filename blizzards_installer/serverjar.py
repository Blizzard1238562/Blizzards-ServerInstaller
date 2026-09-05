"""Server jar download.

Primary source is mcjars.app; since its exact JSON shape for build objects
isn't publicly pinned down anywhere we could verify ahead of time, we scan
responses defensively for a server jar download URL instead of hardcoding
fragile key paths. If mcjars is unreachable or nothing usable comes back, we
fall back to PaperMC's own official Fill API (only applicable when
server_type == "paper").

The SERVER_TYPES registry below is where server software gets added. It maps
our internal server type key -> mcjars.app "type" path segment, plus the
Modrinth loader tag used to filter plugin downloads. Purpur, Folia and
Pufferfish are all Paper forks that keep Paper's plugin API and config
system, so plugins tagged for the "paper" loader on Modrinth work across all
of them - that's why modrinth_loader is "paper" for every entry below, even
though mcjars needs the fork's own type name to find the right jar. The
wizard's server-type picker just lists whatever is in here, and the plugin
download / config patching logic is generic across all entries.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from . import net
from .ui import info, ok, warn

SERVER_TYPES = {
    "paper": {"mcjars": "PAPER", "modrinth_loader": "paper", "label": "Paper"},
    "purpur": {"mcjars": "PURPUR", "modrinth_loader": "paper", "label": "Purpur"},
    "pufferfish": {"mcjars": "PUFFERFISH", "modrinth_loader": "paper", "label": "Pufferfish"},
    "folia": {"mcjars": "FOLIA", "modrinth_loader": "paper", "label": "Folia"},
}

MCJARS_API_BASES = [
    "https://mcjars.app/api/v1",
    "https://mcjars.app/api/v2",
]
PAPERMC_FILL_API = "https://fill.papermc.io/v3/projects"


def _find_jar_url(obj, _depth: int = 0):
    """Recursively hunt a parsed JSON structure for a .jar download URL.
    Prefers a 'downloads' sub-object shaped like {"SERVER": {"url": ...}} /
    {"server": {"url": ...}} if present (this matches mcjars' documented
    build/download concept), otherwise falls back to any http(s) URL string
    ending in .jar found anywhere in the structure."""
    if _depth > 12:
        return None
    if isinstance(obj, dict):
        downloads = obj.get("downloads")
        if isinstance(downloads, dict):
            for key in ("SERVER", "server", "APPLICATION", "application", "primary"):
                entry = downloads.get(key)
                if isinstance(entry, dict) and isinstance(entry.get("url"), str):
                    return entry["url"]
                if isinstance(entry, str) and entry.startswith("http"):
                    return entry
        for key in ("url", "downloadUrl", "download_url", "jarUrl", "jar_url"):
            val = obj.get(key)
            if isinstance(val, str) and val.startswith("http") and val.endswith(".jar"):
                return val
        for v in obj.values():
            found = _find_jar_url(v, _depth + 1)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_jar_url(item, _depth + 1)
            if found:
                return found
    elif isinstance(obj, str):
        if obj.startswith("http") and obj.endswith(".jar"):
            return obj
    return None


def _try_mcjars(mcjars_type: str, mc_version: str) -> Optional[str]:
    for base in MCJARS_API_BASES:
        for path in (f"{base}/builds/{mcjars_type}/{mc_version}", f"{base}/version/{mc_version}/builds"):
            try:
                data = net.http_get_json(path)
            except Exception:
                continue
            builds = data.get("builds") if isinstance(data, dict) else data
            if not builds:
                continue
            # Best-effort: newest build first. mcjars typically returns newest
            # first already; if entries carry an explicit build number we sort
            # on that to be safe.
            if isinstance(builds, list) and builds and isinstance(builds[0], dict):
                if all("buildNumber" in b or "build" in b for b in builds if isinstance(b, dict)):
                    builds = sorted(
                        builds,
                        key=lambda b: b.get("buildNumber", b.get("build", 0)),
                        reverse=True,
                    )
            url = _find_jar_url(builds)
            if url:
                return url
    return None


def _try_papermc_fill(mc_version: str) -> Optional[str]:
    try:
        data = net.http_get_json(f"{PAPERMC_FILL_API}/paper/versions/{mc_version}/builds")
    except Exception:
        return None
    if not isinstance(data, list) or not data:
        return None
    # Prefer STABLE channel builds, newest last per PaperMC docs -> take the
    # last stable one, otherwise just the last build overall.
    stable = [b for b in data if b.get("channel") == "STABLE"]
    pool = stable if stable else data
    build = pool[-1]
    try:
        return build["downloads"]["server:default"]["url"]
    except (KeyError, TypeError):
        return _find_jar_url(build)


def download_server_jar(server_type: str, mc_version: str, dest: Path) -> None:
    server = SERVER_TYPES[server_type]
    info(f"Looking up {server['label']} {mc_version} on mcjars.app...")
    url = _try_mcjars(server["mcjars"], mc_version)

    if not url and server_type == "paper":
        warn("mcjars.app did not return a usable build, falling back to the official PaperMC API...")
        url = _try_papermc_fill(mc_version)

    if not url:
        raise RuntimeError(
            f"Could not find a {server['label']} build for Minecraft {mc_version}. "
            "Double check the version number is correct and has a released server build."
        )

    net.download_file(url, dest, dest.name)
    ok(f"Downloaded {dest.name}")
