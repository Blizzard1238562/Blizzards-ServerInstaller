"""HTTP helpers: JSON GETs and streamed file downloads with a progress readout."""

from __future__ import annotations

from pathlib import Path

import requests

from .meta import USER_AGENT

HTTP_TIMEOUT = 30
DOWNLOAD_CHUNK = 1 << 16


def http_get_json(url: str, params: dict | None = None) -> dict | list:
    resp = requests.get(
        url, params=params, headers={"User-Agent": USER_AGENT}, timeout=HTTP_TIMEOUT
    )
    resp.raise_for_status()
    return resp.json()


def http_get_json_optional(url: str, params: dict | None = None):
    """Like http_get_json, but treats HTTP 404 as "nothing matched these
    filters" and returns None instead of raising (Modrinth answers a request
    for versions of a loader/game-version a project doesn't support with 404
    rather than an empty list). Other errors still propagate."""
    try:
        return http_get_json(url, params=params)
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            return None
        raise


def download_file(url: str, dest: Path, label: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, headers={"User-Agent": USER_AGENT}, stream=True, timeout=HTTP_TIMEOUT) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("Content-Length", 0))
        written = 0
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f:
            for chunk in resp.iter_content(chunk_size=DOWNLOAD_CHUNK):
                if not chunk:
                    continue
                f.write(chunk)
                written += len(chunk)
                if total:
                    pct = written * 100 // total
                    print(f"\r      downloading {label}... {pct:3d}%", end="", flush=True)
                else:
                    print(f"\r      downloading {label}... {written // 1024} KB", end="", flush=True)
        print()
        tmp.replace(dest)
