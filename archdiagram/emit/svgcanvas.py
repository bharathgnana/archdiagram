"""Compose a single page SVG from a laid-out diagram.

This is the shared visual model used by the PDF emitter (converted to PDF via
the Node bridge). Icons are passed in as already-rasterised PNG bytes; nodes
without an icon degrade to a labelled, vendor-accented rounded box so output is
always produced.

Pure stdlib: builds an SVG string by hand.
"""

from __future__ import annotations

import base64

from ..layout.engine import ICON_SIZE, Box, LayoutResult
from ..registry.catalog import Catalog
from ..spec.model import Diagram

_FONT = "Segoe UI, Helvetica, Arial, sans-serif"


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _truncate(text: str, limit: int = 22) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "\u2026"


def _lighten(hex_color: str, amount: float = 0.88) -> str:
    """Return a pale tint of ``hex_color`` for group fills."""

    try:
        h = hex_color.lstrip("#")
        r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    except (ValueError, IndexError):
        return "#F4F6F8"
    r = int(r + (255 - r) * amount)
    g = int(g + (255 - g) * amount)
    b = int(b + (255 - b) * amount)
    return f"#{r:02X}{g:02X}{b:02X}"


def _border_point(box: Box, tx: float, ty: float) -> tuple[float, float]:
    """Point on ``box``'s border along the ray toward (tx, ty)."""

    cx, cy = box.cx, box.y + box.h / 2
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return cx, cy
    half_w, half_h = box.w / 2, box.h / 2
    scale_x = half_w / abs(dx) if dx != 0 else float("inf")
    scale_y = half_h / abs(dy) if dy != 0 else float("inf")
    scale = min(scale_x, scale_y)
    return cx + dx * scale, cy + dy * scale


def build_page_svg(
    diagram: Diagram,
    layout: LayoutResult,
    catalog: Catalog,
    icon_pngs: dict[str, bytes] | None = None,
) -> str:
    icon_pngs = icon_pngs or {}
    title_band = 36
    width = layout.width
    height = layout.height + title_band

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}">'
    )
    parts.append(
        '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" '
        'orient="auto" markerUnits="strokeWidth">'
        '<path d="M0,0 L8,3 L0,6 z" fill="#5B6470"/></marker></defs>'
    )
    parts.append(f'<rect x="0" y="0" width="{width:.0f}" height="{height:.0f}" fill="#FFFFFF"/>')

    # Title.
    parts.append(
        f'<text x="{width / 2:.1f}" y="24" text-anchor="middle" '
        f'font-family="{_FONT}" font-size="16" font-weight="600" fill="#1B1F24">'
        f"{_esc(diagram.title)}</text>"
    )

    dy = title_band  # shift all content below the title band

    # Group containers (drawn first, behind nodes/edges).
    for group in diagram.groups:
        gb = layout.group_boxes.get(group.id)
        if gb is None:
            continue
        accent = catalog.accent(group.vendor) if group.vendor else "#9AA5B1"
        fill = _lighten(accent)
        parts.append(
            f'<rect x="{gb.x:.1f}" y="{gb.y + dy:.1f}" width="{gb.w:.1f}" height="{gb.h:.1f}" '
            f'rx="10" ry="10" fill="{fill}" stroke="{accent}" stroke-width="1.5"/>'
        )
        parts.append(
            f'<text x="{gb.x + 12:.1f}" y="{gb.y + dy + 19:.1f}" font-family="{_FONT}" '
            f'font-size="12" font-weight="600" fill="{accent}">{_esc(group.display_label)}</text>'
        )

    # Edges.
    for edge in diagram.edges:
        src = layout.boxes.get(edge.source)
        dst = layout.boxes.get(edge.target)
        if not src or not dst:
            continue
        x1, y1 = _border_point(src, dst.cx, dst.y + dst.h / 2)
        x2, y2 = _border_point(dst, src.cx, src.y + src.h / 2)
        marker = ' marker-end="url(#arrow)"' if edge.directed else ""
        parts.append(
            f'<line x1="{x1:.1f}" y1="{y1 + dy:.1f}" x2="{x2:.1f}" y2="{y2 + dy:.1f}" '
            f'stroke="#5B6470" stroke-width="1.5"{marker}/>'
        )
        if edge.label:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2 + dy
            parts.append(
                f'<rect x="{mx - len(edge.label) * 3.4 - 4:.1f}" y="{my - 9:.1f}" '
                f'width="{len(edge.label) * 6.8 + 8:.1f}" height="14" rx="3" fill="#FFFFFF" '
                f'fill-opacity="0.85"/>'
            )
            parts.append(
                f'<text x="{mx:.1f}" y="{my + 2:.1f}" text-anchor="middle" font-family="{_FONT}" '
                f'font-size="10" fill="#5B6470">{_esc(edge.label)}</text>'
            )

    # Nodes.
    for node in diagram.nodes:
        box = layout.boxes.get(node.id)
        if box is None:
            continue
        entry = catalog.lookup(node.service)
        accent = entry.accent if entry else catalog.accent(node.vendor)
        ix, iy, iw, ih = box.icon_rect(ICON_SIZE, ICON_SIZE)
        iy += dy
        png = icon_pngs.get(node.id)
        if png is not None:
            href = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
            parts.append(
                f'<image x="{ix:.1f}" y="{iy:.1f}" width="{iw:.1f}" height="{ih:.1f}" '
                f'href="{href}" preserveAspectRatio="xMidYMid meet"/>'
            )
        else:
            parts.append(
                f'<rect x="{ix:.1f}" y="{iy:.1f}" width="{iw:.1f}" height="{ih:.1f}" rx="8" '
                f'fill="{accent}"/>'
            )
            initials = _esc((entry.label[:2] if entry else node.display_label[:2]).upper())
            parts.append(
                f'<text x="{ix + iw / 2:.1f}" y="{iy + ih / 2 + 5:.1f}" text-anchor="middle" '
                f'font-family="{_FONT}" font-size="16" font-weight="700" fill="#FFFFFF">'
                f"{initials}</text>"
            )
        lx, ly = box.label_anchor()
        parts.append(
            f'<text x="{lx:.1f}" y="{ly + dy + 6:.1f}" text-anchor="middle" font-family="{_FONT}" '
            f'font-size="11" fill="#1B1F24">{_esc(_truncate(node.display_label))}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)
