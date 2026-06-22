"""draw.io (.drawio) emitter - dual mode.

- ``native``   : use draw.io's built-in vendor stencil/style strings. Ideal for
                 editing inside draw.io itself; will NOT render in Lucid.
- ``portable`` : embed each icon as a base64 ``image=data:image/svg+xml,...``
                 data URI so the diagram renders outside draw.io's asset host
                 (best chance of icons surviving a Lucid import). Default.

Both modes produce uncompressed mxfile XML with the mandatory ``id=0`` root and
``id=1`` default layer. Pure stdlib string building.
"""

from __future__ import annotations

import html

from ..layout.engine import ICON_SIZE, layout_diagram
from ..registry.catalog import get_catalog
from ..registry.icons import IconResolver
from ..spec.model import Diagram
from .svgcanvas import _lighten

NATIVE = "native"
PORTABLE = "portable"

_FALLBACK_NODE_STYLE = (
    "rounded=1;whiteSpace=wrap;html=1;verticalLabelPosition=bottom;verticalAlign=top;"
    "fillColor={fill};strokeColor=none;fontColor=#FFFFFF;fontSize=11;"
)
_GROUP_STYLE = (
    "rounded=1;whiteSpace=wrap;html=1;verticalAlign=top;align=left;spacingLeft=10;"
    "fontSize=12;fontStyle=1;fillColor={fill};strokeColor={accent};fontColor={accent};"
)
_EDGE_STYLE = "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow={arrow};"


def _attr(value: str) -> str:
    return html.escape(value, quote=True)


def _portable_style(data_uri: str) -> str:
    # draw.io embeds images as `image=data:<mime>,<base64>` (comma, no ';base64').
    drawio_uri = data_uri.replace(";base64,", ",", 1)
    return (
        "shape=image;html=1;imageAspect=0;aspect=fixed;verticalLabelPosition=bottom;"
        "verticalAlign=top;image=" + drawio_uri + ";"
    )


def _cell(
    cell_id: str,
    value: str,
    style: str,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    parent: str = "1",
    vertex: bool = True,
) -> str:
    kind = 'vertex="1"' if vertex else ""
    return (
        f'        <mxCell id="{_attr(cell_id)}" value="{_attr(value)}" style="{_attr(style)}" '
        f'{kind} parent="{_attr(parent)}">\n'
        f'          <mxGeometry x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
        f'as="geometry"/>\n'
        f"        </mxCell>\n"
    )


def emit_drawio(diagram: Diagram, mode: str = PORTABLE, *, icon_cache: str | None = None) -> str:
    if mode not in (NATIVE, PORTABLE):
        raise ValueError(f"drawio mode must be '{NATIVE}' or '{PORTABLE}', got '{mode}'")

    layout = layout_diagram(diagram)
    catalog = get_catalog()
    resolver = IconResolver(icon_cache)

    page_w = int(layout.width)
    page_h = int(layout.height)

    body: list[str] = []

    # Title text cell.
    body.append(
        _cell(
            "title",
            diagram.title,
            "text;html=1;align=center;fontSize=16;fontStyle=1;",
            8,
            8,
            max(200, page_w - 16),
            24,
        )
    )

    # Group containers (behind nodes by document order).
    for group in diagram.groups:
        gb = layout.group_boxes.get(group.id)
        if gb is None:
            continue
        accent = catalog.accent(group.vendor) if group.vendor else "#9AA5B1"
        style = _GROUP_STYLE.format(fill=_lighten(accent), accent=accent)
        body.append(_cell(f"grp_{group.id}", group.display_label, style, gb.x, gb.y, gb.w, gb.h))

    # Nodes.
    for node in diagram.nodes:
        box = layout.boxes.get(node.id)
        if box is None:
            continue
        entry = catalog.lookup(node.service)
        ix, iy, iw, ih = box.icon_rect(ICON_SIZE, ICON_SIZE)

        if entry is not None and mode == NATIVE and entry.native_style:
            style = entry.native_style
        elif entry is not None and mode == PORTABLE:
            data_uri = resolver.data_uri(entry.icon)
            if data_uri:
                style = _portable_style(data_uri)
            else:
                style = _FALLBACK_NODE_STYLE.format(fill=entry.accent)
        else:
            accent = entry.accent if entry else catalog.accent(node.vendor)
            style = _FALLBACK_NODE_STYLE.format(fill=accent)

        body.append(_cell(f"node_{node.id}", node.display_label, style, ix, iy, iw, ih))

    # Edges.
    for i, edge in enumerate(diagram.edges):
        if edge.source not in layout.boxes or edge.target not in layout.boxes:
            continue
        style = _EDGE_STYLE.format(arrow="block" if edge.directed else "none")
        body.append(
            f'        <mxCell id="edge_{i}" value="{_attr(edge.label or "")}" '
            f'style="{_attr(style)}" edge="1" parent="1" '
            f'source="node_{_attr(edge.source)}" target="node_{_attr(edge.target)}">\n'
            f'          <mxGeometry relative="1" as="geometry"/>\n'
            f"        </mxCell>\n"
        )

    model_attrs = (
        f'dx="0" dy="0" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" '
        f'arrows="1" fold="1" page="1" pageScale="1" pageWidth="{page_w}" '
        f'pageHeight="{page_h}" math="0" shadow="0"'
    )
    return (
        '<mxfile host="archdiagram" type="device">\n'
        f'  <diagram id="page-1" name="{_attr(diagram.title)}">\n'
        f"    <mxGraphModel {model_attrs}>\n"
        "      <root>\n"
        '        <mxCell id="0"/>\n'
        '        <mxCell id="1" parent="0"/>\n'
        + "".join(body)
        + "      </root>\n"
        "    </mxGraphModel>\n"
        "  </diagram>\n"
        "</mxfile>\n"
    )
