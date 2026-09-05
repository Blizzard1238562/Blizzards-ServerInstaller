"""HTTP helpers: JSON GETs and streamed file downloads with a progress readout.

Built on the standard library (urllib.request + ssl) so the packaged binary
does not have to ship the requests/urllib3/certifi stack. HTTPS uses the
system certificate store via ssl.create_default_context().
"""

from __future__ import annotations

import gzip
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .meta import USER_AGENT

HTTP_TIMEOUT = 30
DOWNLOAD_CHUNK = 1 << 16

_SSL_CONTEXT = ssl.create_default_context()

# urllib.request hands non-2xx responses to us as HTTPError exceptions and
# network-level failures as URLError. We translate them into small classes of
# our own so callers get stable, testable error types no matter which HTTP
# library backs this module.


class HTTPError(Exception):
    """An HTTP response with a non-2xx status code."""

    def __init__(self, url: str, code: int, reason: str = ""):
        self.url = url
        self.status_code = code
        self.code = code  # urllib's urllib.error.HTTPError names it .code
        self.reason = reason
        detail = f" ({reason})" if reason else ""
        super().__init__(f"HTTP {code} for {url}{detail}")


class ConnectionError(OSError):
    """The server could not be reached at all (DNS, refused, timeout, TLS)."""


def _open(url: str):
    """Open url with our User-Agent/SSL context; convert errors to ours.

    Returns the response object with a read()/readinto() file-like API and a
    .headers mapping. Non-2xx responses and network failures are raised as
    HTTPError / ConnectionError.
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        return urllib.request.urlopen(request, timeout=HTTP_TIMEOUT, context=_SSL_CONTEXT)
    except urllib.error.HTTPError as exc:
        raise HTTPError(url, exc.code, exc.reason) from exc
    except urllib.error.URLError as exc:
        raise ConnectionError(str(exc.reason)) from exc
    except (TimeoutError, OSError) as exc:
        raise ConnectionError(str(exc)) from exc


def _decode_body(resp) -> bytes:
    """Read the whole body, transparently undoing gzip if the server sent it."""
    raw = resp.read()
    if resp.headers.get("Content-Encoding", "").lower() == "gzip":
        return gzip.decompress(raw)
    return raw


def http_get_json(url: str, params: dict | None = None) -> dict | list:
    query = urllib.parse.urlencode(params) if params else ""
    if query:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{query}"
    with _open(url) as resp:
        body = _decode_body(resp)
    return json.loads(body.decode("utf-8"))


def http_get_json_optional(url: str, params: dict | None = None):
    """Like http_get_json, but treats HTTP 404 as "nothing matched these
    filters" and returns None instead of raising (Modrinth answers a request
    for versions of a loader/game-version a project doesn't support with 404
    rather than an empty list). Other errors still propagate."""
    try:
        return http_get_json(url, params=params)
    except HTTPError as exc:
        if exc.status_code == 404:
            return None
        raise


def download_file(url: str, dest: Path, label: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with _open(url) as resp:
        content_length = resp.headers.get("Content-Length")
        total = int(content_length) if content_length else 0
        gzip_body = resp.headers.get("Content-Encoding", "").lower() == "gzip"
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f:
            written = 0
            if gzip_body:
                # We don't ask for gzip, but if a server sends it anyway, buffer
                # the compressed body and undo it once (rare path).
                f.write(gzip.decompress(resp.read()))
            else:
                while True:
                    chunk = resp.read(DOWNLOAD_CHUNK)
                    if not chunk:
                        break
                    f.write(chunk)
                    written += len(chunk)
                    if total:
                        pct = written * 100 // total
                        print(f"\r      downloading {label}... {pct:3d}%", end="", flush=True)
                    else:
                        print(f"\r      downloading {label}... {written // 1024} KB", end="", flush=True)
        print()
        tmp.replace(dest)
