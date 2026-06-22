"""Shared helper: resolve each node's vendor icon to PNG bytes.

SVG icons are rasterised to PNG via the optional Node resvg bridge; PNG icons
are used directly (no Node needed). Returns a ``{node_id: png_bytes}`` map plus
a list of human-readable warnings for missing/unknown icons. Used by both the
PDF and VSDX emitters so their icon behaviour stays identical.
"""

from __future__ import annotations

from ..layout.engine import ICON_SIZE
from ..rasterize.resvg import NodeBridgeError, rasterize_icons, rasterizer_available
from ..registry.catalog import get_catalog
from ..registry.icons import IconResolver
from ..spec.model import Diagram


def node_icon_pngs(
    diagram: Diagram, resolver: IconResolver, scale: float = 2.0
) -> tuple[dict[str, bytes], list[str]]:
    catalog = get_catalog()
    warnings: list[str] = []

    node_relpath: dict[str, str] = {}
    png_direct: dict[str, bytes] = {}
    svg_relpaths: dict[str, str] = {}  # relpath -> svg text (dedup)

    for node in diagram.nodes:
        entry = catalog.lookup(node.service)
        if entry is None:
            warnings.append(f"unknown service '{node.service}' (node '{node.id}') -> fallback box")
            continue
        data = resolver.read_bytes(entry.icon)
        if data is None:
            warnings.append(f"missing icon '{entry.icon}' (node '{node.id}') -> fallback box")
            continue
        node_relpath[node.id] = entry.icon
        if entry.icon.lower().endswith(".svg"):
            svg_relpaths[entry.icon] = data.decode("utf-8", "replace")
        else:
            png_direct[entry.icon] = data

    rendered: dict[str, bytes] = {}
    if svg_relpaths:
        if rasterizer_available():
            width = int(ICON_SIZE * scale)
            items = [{"id": rp, "svg": svg, "width": width} for rp, svg in svg_relpaths.items()]
            try:
                rendered = rasterize_icons(items)
            except NodeBridgeError:
                warnings.append("rasteriser failed -> SVG-icon nodes use fallback boxes")
        else:
            warnings.append("rasteriser unavailable -> SVG-icon nodes use fallback boxes")

    node_pngs: dict[str, bytes] = {}
    for node_id, relpath in node_relpath.items():
        if relpath in png_direct:
            node_pngs[node_id] = png_direct[relpath]
        elif relpath in rendered:
            node_pngs[node_id] = rendered[relpath]
    return node_pngs, warnings
