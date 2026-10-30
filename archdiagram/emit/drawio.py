"""draw.io (.drawio) emitter with native, portable, and compressed modes.

- ``native``   : use draw.io's built-in vendor stencil/style strings. Ideal for
                 editing inside draw.io itself; will NOT render in Lucid.
- ``portable`` : embed each icon as a base64 ``image=data:image/svg+xml,...``
                 data URI so the diagram renders outside draw.io's asset host
                 (best chance of icons surviving a Lucid import). Default.

All modes include the mandatory ``id=0`` root and ``id=1`` default layer.
Compressed mode wraps the portable model in raw-deflate/base64 form.
"""

from __future__ import annotations

import html
import base64
import urllib.parse
import zlib

from ..layout.engine import ICON_SIZE, lane_bands, layout_diagram
from ..registry.catalog import catalog_for
from ..registry.icons import IconResolver
from ..spec.model import Diagram
from ..shapes import SHAPES
from .svgcanvas import _lighten

NATIVE = "native"
PORTABLE = "portable"
COMPRESSED = "compressed"

_FALLBACK_NODE_STYLE = (
    "rounded=1;whiteSpace=wrap;html=1;verticalLabelPosition=bottom;verticalAlign=top;"
    "fillColor={fill};strokeColor=none;fontColor=#FFFFFF;fontSize=11;"
)
_GROUP_STYLE = (
    "rounded=1;whiteSpace=wrap;html=1;verticalAlign=top;align=left;spacingLeft=10;"
    "fontSize=12;fontStyle=1;fillColor={fill};strokeColor={accent};fontColor={accent};"
)
_EDGE_STYLE = "edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;endArrow={arrow};"
_KIND_SHAPES = {
    "process": "rounded=1;arcSize=12;",
    "decision": "rhombus;",
    "data": "shape=parallelogram;",
    "start": "ellipse;",
    "end": "ellipse;",
}


def _attr(value: str) -> str:
    return html.escape(value, quote=True)


def _portable_style(data_uri: str) -> str:
    # draw.io embeds images as `image=data:<mime>,<base64>` (comma, no ';base64').
    drawio_uri = data_uri.replace(";base64,", ",", 1)
    return (
        "shape=image;html=1;imageAspect=0;aspect=fixed;verticalLabelPosition=bottom;"
        "verticalAlign=top;image=" + drawio_uri + ";"
    )


def _compressed_xml(xml: str) -> str:
    """Wrap the model XML using diagrams.net's URI-encoded raw-deflate form."""
    start = xml.index("<mxGraphModel ")
    end = xml.index("</mxGraphModel>", start) + len("</mxGraphModel>")
    model = xml[start:end]
    encoded = urllib.parse.quote(model, safe="-_.!~*'()")
    compressor = zlib.compressobj(wbits=-15)
    payload = base64.b64encode(compressor.compress(encoded.encode("utf-8")) +
                               compressor.flush()).decode("ascii")
    prefix = xml[:start]
    suffix = xml[end:]
    return prefix + payload + suffix


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
    if mode not in (NATIVE, PORTABLE, COMPRESSED):
        raise ValueError(f"drawio mode must be '{NATIVE}', '{PORTABLE}', or '{COMPRESSED}', got '{mode}'")

    layout = layout_diagram(diagram)
    catalog = catalog_for(diagram)
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

    for lane_id, lane_label, lb in lane_bands(diagram, layout):
        style = (
            "rounded=1;whiteSpace=wrap;html=1;verticalAlign=top;align=left;spacingLeft=10;"
            "fontSize=12;fontStyle=1;fillColor=#F5F5F5;strokeColor=#999999;opacity=30;"
            if diagram.lane_orientation else
            "rounded=1;whiteSpace=wrap;html=1;verticalAlign=top;align=left;spacingLeft=10;"
            "fontSize=12;fontStyle=1;fillColor=#F7F9FC;strokeColor=#BCC7D4;"
        )
        body.append(_cell(f"lane_{lane_id}", lane_label, style, lb.x, lb.y, lb.w, lb.h))

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
        if node.kind != "service":
            if node.shape:
                shape_style = SHAPES[node.shape]
                style = (shape_style.drawio + "whiteSpace=wrap;html=1;align=center;verticalAlign=middle;"
                         f"fillColor={shape_style.fill};strokeColor={shape_style.stroke};"
                         "fontColor=#1B1F24;fontSize=12;")
            else:
                style = (
                    _KIND_SHAPES[node.kind] + "whiteSpace=wrap;html=1;align=center;verticalAlign=middle;"
                    "fillColor=#F1F5F9;strokeColor=#486581;fontColor=#1B1F24;fontSize=12;"
                )
            body.append(_cell(f"node_{node.id}", node.display_label, style, box.x, box.y, box.w, box.h))
            continue
        entry = catalog.lookup(node.service)
        ix, iy, iw, ih = box.icon_rect(ICON_SIZE, ICON_SIZE)

        if entry is not None and mode == NATIVE and entry.native_style:
            style = entry.native_style
        elif entry is not None and (mode in (PORTABLE, COMPRESSED) or not entry.native_style):
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
        if edge.kind == "data" or edge.dashed:
            style += "dashed=1;dashPattern=6 4;"
        if edge.color:
            style += f"strokeColor={edge.color};"
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
    xml = (
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
    return _compressed_xml(xml) if mode == COMPRESSED else xml
