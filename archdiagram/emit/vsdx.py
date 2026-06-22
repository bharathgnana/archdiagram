"""VSDX (Visio) emitter using only stdlib ``zipfile`` + ``xml``.

Produces an Open Packaging Conventions package that Visio / draw.io / Lucid can
open. Vendor icons are embedded as PNG media (rasterised via the optional Node
resvg bridge) referenced by Foreign (bitmap) shapes. When the rasteriser is
unavailable, nodes degrade to labelled, vendor-accented rectangles - the
package is still valid.

Visio uses inches with a bottom-left origin (Y up); the layout uses points with
a top-left origin, so coordinates are scaled and Y-flipped here.
"""

from __future__ import annotations

import os
import zipfile

from ..layout.engine import ICON_SIZE, layout_diagram
from ..registry.catalog import get_catalog
from ..registry.icons import IconResolver
from ..spec.model import Diagram
from .iconglyph import node_icon_pngs
from .svgcanvas import _border_point, _esc, _lighten

PX_PER_INCH = 96.0

_NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
_NS_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_NS_DOCREL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _in(px: float) -> str:
    return f"{px / PX_PER_INCH:.4f}"


def _content_types(has_media: bool) -> str:
    png = '  <Default Extension="png" ContentType="image/png"/>\n' if has_media else ""
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<Types xmlns="{_NS_CT}">\n'
        '  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
        '  <Default Extension="xml" ContentType="application/xml"/>\n'
        f"{png}"
        '  <Override PartName="/visio/document.xml" ContentType="application/vnd.ms-visio.drawing.main+xml"/>\n'
        '  <Override PartName="/visio/pages/pages.xml" ContentType="application/vnd.ms-visio.pages+xml"/>\n'
        '  <Override PartName="/visio/pages/page1.xml" ContentType="application/vnd.ms-visio.page+xml"/>\n'
        "</Types>\n"
    )


def _root_rels() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<Relationships xmlns="{_NS_REL}">\n'
        '  <Relationship Id="rId1" '
        'Type="http://schemas.microsoft.com/visio/2010/relationships/document" '
        'Target="visio/document.xml"/>\n'
        "</Relationships>\n"
    )


def _document_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<VisioDocument xmlns="http://schemas.microsoft.com/office/visio/2012/main" '
        f'xmlns:r="{_NS_DOCREL}">\n'
        "  <DocumentSettings DefaultTextStyle=\"0\" DefaultLineStyle=\"0\" DefaultFillStyle=\"0\">\n"
        '    <GlyphSettingsEnabled>0</GlyphSettingsEnabled>\n'
        "  </DocumentSettings>\n"
        "</VisioDocument>\n"
    )


def _document_rels() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<Relationships xmlns="{_NS_REL}">\n'
        '  <Relationship Id="rId1" '
        'Type="http://schemas.microsoft.com/visio/2010/relationships/pages" '
        'Target="pages/pages.xml"/>\n'
        "</Relationships>\n"
    )


def _pages_xml(width_px: float, height_px: float) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Pages xmlns="http://schemas.microsoft.com/office/visio/2012/main" '
        f'xmlns:r="{_NS_DOCREL}">\n'
        '  <Page ID="0" Name="Page-1" ViewScale="1" ViewCenterX="0" ViewCenterY="0">\n'
        "    <PageSheet>\n"
        f'      <Cell N="PageWidth" V="{_in(width_px)}"/>\n'
        f'      <Cell N="PageHeight" V="{_in(height_px)}"/>\n'
        '      <Cell N="DrawingScale" V="1"/>\n'
        '      <Cell N="DrawingSizeType" V="3"/>\n'
        "    </PageSheet>\n"
        '    <Rel r:id="rId1"/>\n'
        "  </Page>\n"
        "</Pages>\n"
    )


def _pages_rels() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<Relationships xmlns="{_NS_REL}">\n'
        '  <Relationship Id="rId1" '
        'Type="http://schemas.microsoft.com/visio/2010/relationships/page" '
        'Target="page1.xml"/>\n'
        "</Relationships>\n"
    )


def _rect_geometry(noshow_fill: bool = False) -> str:
    fill = '      <Cell N="NoFill" V="1"/>\n' if noshow_fill else ""
    return (
        '    <Section N="Geometry" IX="0">\n'
        f"{fill}"
        '      <Row T="RelMoveTo" IX="1"><Cell N="X" V="0"/><Cell N="Y" V="0"/></Row>\n'
        '      <Row T="RelLineTo" IX="2"><Cell N="X" V="1"/><Cell N="Y" V="0"/></Row>\n'
        '      <Row T="RelLineTo" IX="3"><Cell N="X" V="1"/><Cell N="Y" V="1"/></Row>\n'
        '      <Row T="RelLineTo" IX="4"><Cell N="X" V="0"/><Cell N="Y" V="1"/></Row>\n'
        '      <Row T="RelLineTo" IX="5"><Cell N="X" V="0"/><Cell N="Y" V="0"/></Row>\n'
        "    </Section>\n"
    )


def _line_geometry() -> str:
    return (
        '    <Section N="Geometry" IX="0">\n'
        '      <Row T="MoveTo" IX="1"><Cell N="X" V="0"/><Cell N="Y" V="0"/></Row>\n'
        '      <Row T="LineTo" IX="2"><Cell N="X" F="Width"/><Cell N="Y" F="Height"/></Row>\n'
        "    </Section>\n"
    )


def _rect_shape(
    shape_id: int,
    x: float,
    y: float,
    w: float,
    h: float,
    page_h: float,
    *,
    fill: str | None,
    stroke: str | None,
    text: str = "",
    valign_top: bool = False,
    font_color: str = "#1B1F24",
) -> str:
    pin_x = _in(x + w / 2)
    pin_y = _in(page_h - (y + h / 2))
    cells = [
        f'      <Cell N="PinX" V="{pin_x}"/>',
        f'      <Cell N="PinY" V="{pin_y}"/>',
        f'      <Cell N="Width" V="{_in(w)}"/>',
        f'      <Cell N="Height" V="{_in(h)}"/>',
        '      <Cell N="LocPinX" F="Width*0.5" V="0"/>',
        '      <Cell N="LocPinY" F="Height*0.5" V="0"/>',
    ]
    if fill is not None:
        cells.append(f'      <Cell N="FillForegnd" V="{fill}"/>')
        cells.append('      <Cell N="FillPattern" V="1"/>')
    else:
        cells.append('      <Cell N="FillPattern" V="0"/>')
    if stroke is not None:
        cells.append(f'      <Cell N="LineColor" V="{stroke}"/>')
        cells.append('      <Cell N="LinePattern" V="1"/>')
    else:
        cells.append('      <Cell N="LinePattern" V="0"/>')
    cells.append(f'      <Cell N="LineColor2" V="{font_color}"/>')
    if valign_top:
        cells.append('      <Cell N="VerticalAlign" V="0"/>')
    text_xml = f"    <Text>{_esc(text)}</Text>\n" if text else ""
    return (
        f'    <Shape ID="{shape_id}" Type="Shape">\n'
        + "\n".join(cells)
        + "\n"
        + _rect_geometry(noshow_fill=fill is None)
        + text_xml
        + "    </Shape>\n"
    )


def _image_shape(
    shape_id: int, x: float, y: float, w: float, h: float, page_h: float, rel_id: str
) -> str:
    pin_x = _in(x + w / 2)
    pin_y = _in(page_h - (y + h / 2))
    return (
        f'    <Shape ID="{shape_id}" Type="Foreign">\n'
        f'      <Cell N="PinX" V="{pin_x}"/>\n'
        f'      <Cell N="PinY" V="{pin_y}"/>\n'
        f'      <Cell N="Width" V="{_in(w)}"/>\n'
        f'      <Cell N="Height" V="{_in(h)}"/>\n'
        '      <Cell N="LocPinX" F="Width*0.5" V="0"/>\n'
        '      <Cell N="LocPinY" F="Height*0.5" V="0"/>\n'
        '      <Cell N="ImgOffsetX" V="0"/>\n'
        '      <Cell N="ImgOffsetY" V="0"/>\n'
        '      <Cell N="ImgWidth" F="Width" V="0"/>\n'
        '      <Cell N="ImgHeight" F="Height" V="0"/>\n'
        f'      <ForeignData ForeignType="Bitmap"><Rel r:id="{rel_id}"/></ForeignData>\n'
        "    </Shape>\n"
    )


def _line_shape(
    shape_id: int, x1: float, y1: float, x2: float, y2: float, page_h: float, stroke: str
) -> str:
    bx, by = _in(x1), _in(page_h - y1)
    ex, ey = _in(x2), _in(page_h - y2)
    w = (x2 - x1) / PX_PER_INCH
    h = (y1 - y2) / PX_PER_INCH
    return (
        f'    <Shape ID="{shape_id}" Type="Shape">\n'
        f'      <Cell N="BeginX" V="{bx}"/>\n'
        f'      <Cell N="BeginY" V="{by}"/>\n'
        f'      <Cell N="EndX" V="{ex}"/>\n'
        f'      <Cell N="EndY" V="{ey}"/>\n'
        f'      <Cell N="PinX" V="{bx}"/>\n'
        f'      <Cell N="PinY" V="{by}"/>\n'
        f'      <Cell N="Width" V="{w:.4f}"/>\n'
        f'      <Cell N="Height" V="{h:.4f}"/>\n'
        '      <Cell N="LocPinX" V="0"/>\n'
        '      <Cell N="LocPinY" V="0"/>\n'
        f'      <Cell N="LineColor" V="{stroke}"/>\n'
        '      <Cell N="LinePattern" V="1"/>\n'
        '      <Cell N="EndArrow" V="4"/>\n'
        + _line_geometry()
        + "    </Shape>\n"
    )


def emit_vsdx(
    diagram: Diagram,
    out_path: str,
    *,
    icon_cache: str | None = None,
    raster_scale: float = 2.0,
) -> list[str]:
    """Write ``diagram`` to a .vsdx file. Returns non-fatal warnings."""

    layout = layout_diagram(diagram)
    catalog = get_catalog()
    resolver = IconResolver(icon_cache)
    node_pngs, warnings = node_icon_pngs(diagram, resolver, raster_scale)

    page_h = layout.height
    page_w = layout.width

    shapes: list[str] = []
    media: dict[str, bytes] = {}  # media filename -> bytes
    page_rels: list[str] = []
    sid = 1
    rel_counter = 1

    # Group containers first.
    for group in diagram.groups:
        gb = layout.group_boxes.get(group.id)
        if gb is None:
            continue
        accent = catalog.accent(group.vendor) if group.vendor else "#9AA5B1"
        shapes.append(
            _rect_shape(
                sid, gb.x, gb.y, gb.w, gb.h, page_h,
                fill=_lighten(accent), stroke=accent, text=group.display_label,
                valign_top=True, font_color=accent,
            )
        )
        sid += 1

    # Nodes: icon (image or fallback rect) + label.
    for node in diagram.nodes:
        box = layout.boxes.get(node.id)
        if box is None:
            continue
        entry = catalog.lookup(node.service)
        accent = entry.accent if entry else catalog.accent(node.vendor)
        ix, iy, iw, ih = box.icon_rect(ICON_SIZE, ICON_SIZE)
        png = node_pngs.get(node.id)
        if png is not None:
            rel_id = f"rId{rel_counter}"
            fname = f"image{rel_counter}.png"
            media[fname] = png
            page_rels.append(
                f'  <Relationship Id="{rel_id}" '
                f'Type="{_NS_DOCREL}/image" Target="../media/{fname}"/>'
            )
            rel_counter += 1
            shapes.append(_image_shape(sid, ix, iy, iw, ih, page_h, rel_id))
            sid += 1
            shapes.append(
                _rect_shape(
                    sid, box.x, box.y + box.h - 24, box.w, 20, page_h,
                    fill=None, stroke=None, text=node.display_label,
                )
            )
            sid += 1
        else:
            shapes.append(
                _rect_shape(
                    sid, ix, iy, iw, ih, page_h, fill=accent, stroke=None,
                    text=node.display_label, font_color="#FFFFFF",
                )
            )
            sid += 1

    # Edges as straight connectors.
    for edge in diagram.edges:
        src = layout.boxes.get(edge.source)
        dst = layout.boxes.get(edge.target)
        if not src or not dst:
            continue
        x1, y1 = _border_point(src, dst.cx, dst.y + dst.h / 2)
        x2, y2 = _border_point(dst, src.cx, src.y + src.h / 2)
        shapes.append(_line_shape(sid, x1, y1, x2, y2, page_h, "#5B6470"))
        sid += 1

    page1 = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<PageContents xmlns="http://schemas.microsoft.com/office/visio/2012/main" '
        f'xmlns:r="{_NS_DOCREL}">\n'
        "  <Shapes>\n" + "".join(shapes) + "  </Shapes>\n"
        "</PageContents>\n"
    )

    page1_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<Relationships xmlns="{_NS_REL}">\n' + "\n".join(page_rels) + "\n</Relationships>\n"
        if page_rels
        else None
    )

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _content_types(bool(media)))
        zf.writestr("_rels/.rels", _root_rels())
        zf.writestr("visio/document.xml", _document_xml())
        zf.writestr("visio/_rels/document.xml.rels", _document_rels())
        zf.writestr("visio/pages/pages.xml", _pages_xml(page_w, page_h))
        zf.writestr("visio/pages/_rels/pages.xml.rels", _pages_rels())
        zf.writestr("visio/pages/page1.xml", page1)
        if page1_rels:
            zf.writestr("visio/pages/_rels/page1.xml.rels", page1_rels)
        for fname, data in media.items():
            zf.writestr(f"visio/media/{fname}", data)

    return warnings
