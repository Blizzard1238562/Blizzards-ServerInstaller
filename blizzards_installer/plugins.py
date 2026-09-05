"""Plugin registry loading + Modrinth downloads.

The plugin list itself lives in plugins.json (next to installer.py), not in
code - see its _comment field for how entries map to Modrinth projects.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

from . import net
from .ui import error, info, ok, section, warn

MODRINTH_API = "https://api.modrinth.com/v2"


def _data_base() -> Path:
    """Directory to look for bundled data files in. When PyInstaller freezes
    this into a onefile .exe, bundled data (plugins.json) is extracted to a
    temp dir exposed as sys._MEIPASS at runtime - a plain __file__ lookup
    would fail there. In development this module sits in the
    blizzards_installer/ package folder, so the registry is one level up."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent


PLUGIN_REGISTRY_PATH = _data_base() / "plugins.json"


def load_plugin_registry() -> tuple[list[dict], dict]:
    with open(PLUGIN_REGISTRY_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["plugins"], data.get("categories", {})


def plugins_for_server(plugins: list[dict], server_type: str) -> tuple[list[dict], list[dict]]:
    """Split the registry into plugins that can run on a server type and
    plugins that must be skipped.

    Only Folia currently differs: the wizard offers exactly the plugins whose
    authors ship Folia-compatible builds (flagged `"folia": true` in
    plugins.json) and skips the rest. Every other type is Paper-compatible
    and gets the full list."""
    if server_type == "folia":
        offered = [p for p in plugins if p.get("folia")]
        skipped = [p for p in plugins if not p.get("folia")]
        return offered, skipped
    return plugins, []


def resolve_dependencies(selected_ids: set[str], plugins_by_id: dict[str, dict]) -> set[str]:
    """Pull in any 'requires' dependencies for the chosen plugins (recursively),
    printing a note so the user knows why something extra got installed."""
    resolved = set(selected_ids)
    changed = True
    while changed:
        changed = False
        for pid in list(resolved):
            for dep in plugins_by_id[pid].get("requires", []):
                if dep not in resolved:
                    resolved.add(dep)
                    info(f"'{plugins_by_id[pid]['name']}' requires '{plugins_by_id[dep]['name']}' - adding it too.")
                    changed = True
    return resolved


def _primary_file(files: list[dict]) -> Optional[dict]:
    """Pick the download entry Modrinth marks as primary, else the first."""
    if not files:
        return None
    return next((f for f in files if f.get("primary")), files[0])


def get_modrinth_plugin_download(slug: str, mc_version: str, loader: str) -> tuple[str, str]:
    """Return (download_url, filename) for the newest compatible version of a
    Modrinth project, preferring an exact game-version + loader match and
    falling back to a loader-only match (newest) with a warning if needed."""

    def _pick(versions: list[dict]) -> Optional[dict]:
        if not versions:
            return None
        rank = {"release": 0, "beta": 1, "alpha": 2}
        # Two stable sorts: newest-first within each stability tier, then
        # group by tier (release preferred over beta/alpha).
        by_date = sorted(versions, key=lambda v: v.get("date_published", ""), reverse=True)
        by_tier = sorted(by_date, key=lambda v: rank.get(v.get("version_type", "release"), 3))
        return by_tier[0]

    params_exact = {
        "loaders": json.dumps([loader]),
        "game_versions": json.dumps([mc_version]),
    }
    versions = net.http_get_json_optional(f"{MODRINTH_API}/project/{slug}/version", params=params_exact)
    chosen = _pick(versions) if isinstance(versions, list) else None

    if not chosen:
        warn(f"No build of '{slug}' targets Minecraft {mc_version} exactly - grabbing the newest {loader} build instead.")
        params_loose = {"loaders": json.dumps([loader])}
        versions = net.http_get_json_optional(f"{MODRINTH_API}/project/{slug}/version", params=params_loose)
        chosen = _pick(versions) if isinstance(versions, list) else None

    if not chosen:
        raise RuntimeError(f"No downloadable versions found for Modrinth project '{slug}'.")

    primary = _primary_file(chosen.get("files", []))
    if not primary:
        raise RuntimeError(f"'{slug}' has a matching version but no files attached.")
    return primary["url"], primary["filename"]


def install_plugins(chosen: list[dict], mc_version: str, loader: str, plugins_dir: Path) -> list[dict]:
    section("Installing plugins")
    installed = []
    for plugin in chosen:
        try:
            info(f"Fetching latest '{plugin['name']}' for {mc_version}...")
            url, filename = get_modrinth_plugin_download(plugin["modrinth_slug"], mc_version, loader)
            net.download_file(url, plugins_dir / filename, filename)
            installed.append(plugin)
        except Exception as exc:
            error(f"Failed to install {plugin['name']}: {exc}")
    return installed


def write_tab_config(server_dir: Path, server_name: str, color_code: str = "") -> None:
    """Write a real, minimal TAB config.yml.

    Replaces TAB's fancy default header/footer with a plain tablist: the
    server name rendered in Minecraft "small font" (Unicode small caps, e.g.
    ᴍɪɴᴇᴄʀᴀꜰᴛ) on top and an online-player count below. Everything else is
    left to TAB's own defaults (it re-adds missing options on load).
    color_code is an optional legacy color code (e.g. "&6") applied to the
    name line only.
    """
    tab_dir = server_dir / "plugins" / "TAB"
    tab_dir.mkdir(parents=True, exist_ok=True)
    header_line = _yaml_double_quote(f"{color_code}{small_caps(server_name)}")
    config = (
        "# TAB config generated by Blizzards Server Installer.\n"
        "# The default header/footer was replaced with a minimal tablist: your server\n"
        "# name in Minecraft small font (small caps) on top plus the player count.\n"
        "# TAB fills any options missing here with its own defaults on load, so you\n"
        "# can override anything else later. Restart or run /tab reload to apply.\n"
        "\n"
        "header-footer:\n"
        "  enabled: true\n"
        "  designs:\n"
        "    default:\n"
        "      header:\n"
        f"        - {header_line}\n"
        "        - \"&7Online: %online%\"\n"
        "      footer: []\n"
    )
    (tab_dir / "config.yml").write_text(config, encoding="utf-8")
    ok(f"Wrote plugins/TAB/config.yml (minimal tablist with '{server_name}')")


def _yaml_double_quote(text: str) -> str:
    """Double-quote a string for embedding in the generated YAML."""
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def small_caps(text: str) -> str:
    """Render ASCII letters as Minecraft "small font" small caps (ᴛʜɪꜱ).

    Letters without a small-cap form (x) are left as-is; digits, spaces and
    punctuation are passed through unchanged."""
    return text.translate(SMALL_CAPS)


# Unicode small caps for a-z/A-Z (Minecraft small font). x has no small-cap
# form, so it maps to itself.
SMALL_CAPS = {}
for _lower, _upper, _glyph in [
    ("a", "A", "ᴀ"),
    ("b", "B", "ʙ"),
    ("c", "C", "ᴄ"),
    ("d", "D", "ᴅ"),
    ("e", "E", "ᴇ"),
    ("f", "F", "ꜰ"),
    ("g", "G", "ɢ"),
    ("h", "H", "ʜ"),
    ("i", "I", "ɪ"),
    ("j", "J", "ᴊ"),
    ("k", "K", "ᴋ"),
    ("l", "L", "ʟ"),
    ("m", "M", "ᴍ"),
    ("n", "N", "ɴ"),
    ("o", "O", "ᴏ"),
    ("p", "P", "ᴘ"),
    ("q", "Q", "ǫ"),
    ("r", "R", "ʀ"),
    ("s", "S", "ꜱ"),
    ("t", "T", "ᴛ"),
    ("u", "U", "ᴜ"),
    ("v", "V", "ᴠ"),
    ("w", "W", "ᴡ"),
    ("x", "X", "x"),
    ("y", "Y", "ʏ"),
    ("z", "Z", "ᴢ"),
]:
    SMALL_CAPS[ord(_lower)] = _glyph
    SMALL_CAPS[ord(_upper)] = _glyph
