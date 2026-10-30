"""Vendor service catalog.

Loads the bundled ``catalog_data/*.json`` files and an optional generated icon
manifest, and exposes a lookup from a
``"<vendor>.<service_key>"`` string to a :class:`ServiceEntry` containing the
draw.io native style, the icon filename (for embedding / PDF / vsdx), default
size and the vendor accent colour (used for graceful fallback boxes).

This module is pure stdlib and has no knowledge of any output format.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache

_CATALOG_DIR = os.path.join(os.path.dirname(__file__), "catalog_data")

# Neutral fallback accent for unknown vendors.
_DEFAULT_ACCENT = "#6B7280"


@dataclass(frozen=True)
class ServiceEntry:
    """A single catalog entry for one vendor service."""

    vendor: str
    key: str
    label: str
    native_style: str
    icon: str
    accent: str
    w: int = 48
    h: int = 48
    category: str = ""
    aliases: tuple[str, ...] = ()

    @property
    def service(self) -> str:
        return f"{self.vendor}.{self.key}"


class Catalog:
    """In-memory index of all known vendor services."""

    def __init__(self, entries: dict[str, ServiceEntry], accents: dict[str, str]) -> None:
        self._entries = entries
        self._accents = accents

    @property
    def vendors(self) -> list[str]:
        return sorted(self._accents)

    def lookup(self, service: str | None) -> ServiceEntry | None:
        return self._entries.get(service)

    def accent(self, vendor: str) -> str:
        return self._accents.get(vendor, _DEFAULT_ACCENT)

    def all_entries(self) -> list[ServiceEntry]:
        return list(self._entries.values())

    def search(self, query: str, limit: int = 25) -> list[ServiceEntry]:
        """Case-insensitive substring search over service id and label."""

        q = query.strip().lower()
        if not q:
            return []
        scored: list[tuple[int, ServiceEntry]] = []
        for entry in self._entries.values():
            haystacks = (entry.service.lower(), entry.label.lower(), entry.key.lower(),
                         entry.category.lower(), *(alias.lower() for alias in entry.aliases))
            best = None
            for hay in haystacks:
                if hay == q:
                    best = 0
                    break
                if hay.startswith(q):
                    best = min(1, best) if best is not None else 1
                elif q in hay:
                    best = min(2, best) if best is not None else 2
            if best is not None:
                scored.append((best, entry))
        scored.sort(key=lambda item: (item[0], item[1].service))
        return [entry for _, entry in scored[:limit]]


def _load_vendor_file(path: str) -> tuple[str, str, dict[str, ServiceEntry]]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    vendor = data["vendor"]
    accent = data.get("accent", _DEFAULT_ACCENT)
    entries: dict[str, ServiceEntry] = {}
    for key, svc in data.get("services", {}).items():
        entry = ServiceEntry(
            vendor=vendor,
            key=key,
            label=svc.get("label", key.replace("_", " ").title()),
            native_style=svc.get("native", ""),
            icon=svc.get("icon", f"{vendor}/{key}.svg"),
            accent=accent,
            w=int(svc.get("w", 48)),
            h=int(svc.get("h", 48)),
        )
        entries[entry.service] = entry
    return vendor, accent, entries


def _manifest_path() -> str:
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.environ.get("ARCHDIAGRAM_CATALOG", os.path.join(repo_root, "catalog", "manifest.json"))


def _load_manifest(path: str, accents: dict[str, str]) -> dict[str, ServiceEntry]:
    """Load entries generated from local vendor SVG packs.

    Existing bundled IDs retain their definitions when the two catalogs merge.
    Icon paths are relative to the icon cache, never to the manifest file.
    """
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if data.get("version") != 1 or not isinstance(data.get("icons"), dict):
        raise ValueError(f"unsupported icon catalog manifest: {path}")
    entries: dict[str, ServiceEntry] = {}
    for service, item in data["icons"].items():
        vendor = item["provider"]
        if not service.startswith(vendor + "."):
            raise ValueError(f"invalid icon catalog id: {service}")
        icon = item["file"].replace("\\", "/")
        if (icon.split("/", 1)[0].lower() != vendor or ":" in icon or
                any(part in ("", ".", "..") for part in icon.split("/"))):
            raise ValueError(f"invalid icon catalog path: {icon}")
        accents.setdefault(vendor, _DEFAULT_ACCENT)
        entries[service] = ServiceEntry(
            vendor=vendor,
            key=service[len(vendor) + 1:],
            label=item.get("label", service[len(vendor) + 1:].replace("_", " ").title()),
            native_style="",
            icon=icon,
            accent=accents[vendor],
            w=round(item.get("width", 48)),
            h=round(item.get("height", 48)),
            category=item.get("category", ""),
            aliases=tuple(item.get("aliases", ())),
        )
    return entries


@lru_cache(maxsize=1)
def get_catalog() -> Catalog:
    """Build (and cache) the bundled catalog plus an optional local manifest."""

    entries: dict[str, ServiceEntry] = {}
    accents: dict[str, str] = {}
    if os.path.isdir(_CATALOG_DIR):
        for name in sorted(os.listdir(_CATALOG_DIR)):
            if not name.endswith(".json"):
                continue
            vendor, accent, vendor_entries = _load_vendor_file(
                os.path.join(_CATALOG_DIR, name)
            )
            accents[vendor] = accent
            entries.update(vendor_entries)
    manifest = _manifest_path()
    if os.path.isfile(manifest):
        for service, entry in _load_manifest(manifest, accents).items():
            entries.setdefault(service, entry)
    return Catalog(entries, accents)
