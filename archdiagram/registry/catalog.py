"""Vendor service catalog.

Loads the bundled ``catalog_data/*.json`` files and exposes a lookup from a
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

    def lookup(self, service: str) -> ServiceEntry | None:
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
            haystacks = (entry.service.lower(), entry.label.lower(), entry.key.lower())
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


@lru_cache(maxsize=1)
def get_catalog() -> Catalog:
    """Build (and cache) the catalog from the bundled data files."""

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
    return Catalog(entries, accents)
