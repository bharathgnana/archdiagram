"""Fetch official vendor icon SVGs into the local (uncommitted) icon cache.

Icons are intentionally *not* committed to the repo. This tool downloads them
on demand using only the standard library (``urllib``).

Source resolution per catalog entry (icon relpath, e.g. ``azure/app_services.svg``):

1. an explicit URL in ``tools/icon_sources.json`` under ``"sources"``;
2. otherwise, if the entry's draw.io ``native`` style references an
   ``image=img/lib/...svg`` asset, that path is fetched from the public
   draw.io asset host.

Entries whose ``native`` style uses an mxgraph stencil (many AWS/GCP/Kubernetes
services) have no derivable SVG URL; add those to ``icon_sources.json``.

Usage:
    python -m tools.download_icons [--vendors azure,aws] [--dest DIR] [--force] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

# Import the catalog from the core package.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from archdiagram.registry.catalog import ServiceEntry, get_catalog  # noqa: E402

DRAWIO_ASSET_HOST = "https://app.diagrams.net/"
_IMG_LIB_RE = re.compile(r"image=(img/lib/[^;]+\.svg)")

_SOURCES_FILE = os.path.join(os.path.dirname(__file__), "icon_sources.json")


def _default_dest() -> str:
    env = os.environ.get("ARCHDIAGRAM_ICONS")
    if env:
        return env
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "icons"))


def _load_overrides() -> dict[str, str]:
    if not os.path.isfile(_SOURCES_FILE):
        return {}
    with open(_SOURCES_FILE, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data.get("sources", {})


def _derive_url(entry: ServiceEntry, overrides: dict[str, str]) -> str | None:
    if entry.icon in overrides:
        return overrides[entry.icon]
    match = _IMG_LIB_RE.search(entry.native_style)
    if match:
        return DRAWIO_ASSET_HOST + match.group(1)
    return None


def _download(url: str, dest_path: str, timeout: float = 30.0) -> None:
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "archdiagram-icon-downloader/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (trusted manifest URLs)
        data = resp.read()
    with open(dest_path, "wb") as fh:
        fh.write(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download vendor icons into the local cache.")
    parser.add_argument("--vendors", help="comma-separated vendor filter (e.g. azure,aws)")
    parser.add_argument("--dest", help="destination icon cache dir (default: <repo>/icons)")
    parser.add_argument("--force", action="store_true", help="re-download existing icons")
    parser.add_argument("--dry-run", action="store_true", help="list actions without downloading")
    args = parser.parse_args(argv)

    dest = args.dest or _default_dest()
    vendor_filter = (
        {v.strip() for v in args.vendors.split(",") if v.strip()} if args.vendors else None
    )
    overrides = _load_overrides()
    catalog = get_catalog()

    downloaded = skipped = missing_src = failed = 0
    for entry in sorted(catalog.all_entries(), key=lambda e: e.service):
        if vendor_filter and entry.vendor not in vendor_filter:
            continue
        dest_path = os.path.join(dest, *entry.icon.split("/"))
        if os.path.isfile(dest_path) and not args.force:
            skipped += 1
            continue
        url = _derive_url(entry, overrides)
        if not url:
            missing_src += 1
            print(f"  no source  {entry.service:<32} ({entry.icon})  -- add to icon_sources.json")
            continue
        if args.dry_run:
            print(f"  would GET  {entry.service:<32} <- {url}")
            downloaded += 1
            continue
        try:
            _download(url, dest_path)
            downloaded += 1
            print(f"  ok         {entry.service:<32} -> {entry.icon}")
        except (urllib.error.URLError, OSError) as exc:
            failed += 1
            print(f"  FAILED     {entry.service:<32} <- {url}\n             {exc}")

    print(
        f"\nIcons -> {dest}\n"
        f"  downloaded={downloaded} skipped(existing)={skipped} "
        f"no-source={missing_src} failed={failed}"
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
