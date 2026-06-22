"""Resolve vendor icon SVG files from the local (uncommitted) icon cache.

Icons are *not* bundled with the package; they are fetched by
``tools/download_icons.py`` into a cache directory. Resolution order:

1. an explicit ``cache_dir`` argument
2. the ``ARCHDIAGRAM_ICONS`` environment variable
3. ``<repo>/icons``
4. ``~/.cache/archdiagram/icons``

The resolver never raises for a missing icon; callers decide how to degrade
(e.g. draw a labelled fallback box).
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass


def _candidate_dirs(explicit: str | None) -> list[str]:
    dirs: list[str] = []
    if explicit:
        dirs.append(explicit)
    env = os.environ.get("ARCHDIAGRAM_ICONS")
    if env:
        dirs.append(env)
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    dirs.append(os.path.join(repo_root, "icons"))
    dirs.append(os.path.join(os.path.expanduser("~"), ".cache", "archdiagram", "icons"))
    return dirs


@dataclass(frozen=True)
class IconRef:
    """A resolved icon on disk."""

    relpath: str
    abspath: str

    @property
    def exists(self) -> bool:
        return os.path.isfile(self.abspath)


class IconResolver:
    """Locates icon files across the candidate cache directories."""

    def __init__(self, cache_dir: str | None = None) -> None:
        self._dirs = _candidate_dirs(cache_dir)

    @property
    def search_dirs(self) -> list[str]:
        return list(self._dirs)

    def primary_dir(self) -> str:
        return self._dirs[0]

    def resolve(self, relpath: str) -> IconRef:
        relpath = relpath.replace("\\", "/")
        for base in self._dirs:
            candidate = os.path.join(base, *relpath.split("/"))
            if os.path.isfile(candidate):
                return IconRef(relpath=relpath, abspath=candidate)
        # Return a ref pointing at the primary dir even if missing.
        fallback = os.path.join(self._dirs[0], *relpath.split("/"))
        return IconRef(relpath=relpath, abspath=fallback)

    def read_bytes(self, relpath: str) -> bytes | None:
        ref = self.resolve(relpath)
        if not ref.exists:
            return None
        with open(ref.abspath, "rb") as fh:
            return fh.read()

    def read_svg_text(self, relpath: str) -> str | None:
        data = self.read_bytes(relpath)
        if data is None:
            return None
        return data.decode("utf-8")

    def svg_data_uri(self, relpath: str) -> str | None:
        data = self.read_bytes(relpath)
        if data is None:
            return None
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:image/svg+xml;base64,{b64}"

    @staticmethod
    def mime_for(relpath: str) -> str:
        lower = relpath.lower()
        if lower.endswith(".svg"):
            return "image/svg+xml"
        if lower.endswith(".png"):
            return "image/png"
        if lower.endswith((".jpg", ".jpeg")):
            return "image/jpeg"
        return "application/octet-stream"

    def data_uri(self, relpath: str) -> str | None:
        """Return a base64 ``data:`` URI for any supported image type."""

        data = self.read_bytes(relpath)
        if data is None:
            return None
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:{self.mime_for(relpath)};base64,{b64}"
