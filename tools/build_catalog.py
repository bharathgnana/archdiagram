"""Index locally supplied vendor SVGs for archdiagram's service catalog.

Usage: python -m tools.build_catalog --icons icons --out catalog/manifest.json
The manifest contains icon paths relative to --icons; SVGs are never copied.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

_DEFAULT_SIZE = 48.0
_LENGTH = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(?:px|pt)?\s*$", re.I)
_LEADING_NUMBER = re.compile(r"^\d+[\s_-]*")
_ICON_PREFIX = re.compile(r"^(?:icon[\s_-]+service[\s_-]+|icon[\s_-]+)", re.I)
_WORDS = re.compile(r"[A-Za-z0-9]+")
_NOISE = {"icon", "logo", "color", "colour"}


def _length(value: str | None) -> float | None:
    match = _LENGTH.fullmatch(value or "")
    if not match:
        return None
    number = float(match.group(1))
    return number if math.isfinite(number) and number > 0 else None


def svg_dimensions(path: Path) -> tuple[float, float]:
    """Prefer explicit SVG dimensions, then viewBox, then a 48px fallback."""
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return _DEFAULT_SIZE, _DEFAULT_SIZE
    if root.tag.rsplit("}", 1)[-1].lower() != "svg":
        return _DEFAULT_SIZE, _DEFAULT_SIZE
    width, height = _length(root.get("width")), _length(root.get("height"))
    if width and height:
        return width, height
    viewbox = re.split(r"[\s,]+", (root.get("viewBox") or "").strip())
    if len(viewbox) == 4:
        width = width or _length(viewbox[2])
        height = height or _length(viewbox[3])
    return width or _DEFAULT_SIZE, height or _DEFAULT_SIZE


def _tokens(stem: str, provider: str) -> list[str]:
    stem = _ICON_PREFIX.sub("", _LEADING_NUMBER.sub("", stem))
    words = [word.lower() for word in _WORDS.findall(stem)]
    prefixes = {
        "azure": {"azure", "microsoft"},
        "aws": {"aws", "amazon"},
        "gcp": {"gcp", "google", "cloud"},
        "kubernetes": {"kubernetes", "k8s"},
    }.get(provider, {provider})
    while words and words[0] in prefixes:
        words.pop(0)
    return [word for word in words if word not in _NOISE and not word.isdigit()]


def build_catalog(icons_dir: Path) -> dict:
    """Build a deterministic manifest from icons/<provider>/**/*.svg."""
    if not icons_dir.is_dir():
        raise ValueError(f"icon directory not found: {icons_dir}")
    entries: dict[str, dict] = {}
    collisions: dict[str, int] = {}
    for provider_dir in sorted(path for path in icons_dir.iterdir() if path.is_dir()):
        provider = provider_dir.name.lower()
        for svg in sorted(path for path in provider_dir.rglob("*")
                          if path.is_file() and path.suffix.lower() == ".svg"):
            rel = svg.relative_to(icons_dir)
            tokens = _tokens(svg.stem, provider)
            slug = "_".join(tokens) or "icon"
            base_id = f"{provider}.{slug}"
            suffix = collisions.get(base_id, 0) + 1
            collisions[base_id] = suffix
            service_id = base_id if suffix == 1 else f"{base_id}_{suffix}"
            width, height = svg_dimensions(svg)
            label = " ".join(tokens).title() if tokens else svg.stem
            entries[service_id] = {
                "provider": provider,
                "category": rel.parts[1] if len(rel.parts) > 2 else "general",
                "file": rel.as_posix(),
                "label": label,
                "width": round(width, 2),
                "height": round(height, 2),
                "aliases": sorted(set((label.lower(), " ".join(tokens), *tokens)) - {""}),
            }
    return {
        "version": 1,
        "icon_count": len(entries),
        "providers": sorted({item["provider"] for item in entries.values()}),
        "icons": entries,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--icons", type=Path, default=Path("icons"), help="local icon cache root")
    parser.add_argument("--out", type=Path, default=Path("catalog/manifest.json"), help="manifest output")
    args = parser.parse_args(argv)
    manifest = build_catalog(args.icons)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {manifest['icon_count']} icons to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
