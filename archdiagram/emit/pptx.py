"""Editable one-slide PowerPoint export, written with the Python standard library."""

from __future__ import annotations

import html
import math
import os
import re
import zipfile
from pathlib import Path

from ..layout.engine import ICON_SIZE, LayoutResult, lane_bands, layout_diagram
from ..registry.catalog import Catalog, catalog_for
from ..registry.icons import IconResolver
from ..spec.model import Diagram
from ..shapes import SHAPES
from ..normalize import is_modern_diagram
from ..routing import label_position, route_edge
from .iconglyph import node_icon_pngs
from .svgcanvas import edge_endpoints
from .ziputil import write_stable

EMU = 9525  # One layout unit (CSS pixel) in Office units.
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"


def _e(value: str) -> str:
    return html.escape(value, quote=True)


def _n(value: float) -> int:
    return round(value * EMU)


def _color(value: str) -> str:
    return value.lstrip("#").upper()


def _text(text: str, size: int = 1200, color: str = "1B1F24", *,
          font_scale: int | None = None, tight: bool = False) -> str:
    autofit = f'<a:normAutofit fontScale="{font_scale}"/>' if font_scale else ''
    margins = ' lIns="0" rIns="0" tIns="0" bIns="0"' if tight else ''
    body_pr = (f'<a:bodyPr wrap="square" anchor="ctr"{margins}>{autofit}</a:bodyPr>'
               if font_scale else f'<a:bodyPr wrap="square" anchor="ctr"{margins}/>')
    return (
        f'<p:txBody>{body_pr}<a:lstStyle/>'
        '<a:p><a:pPr algn="ctr"/><a:r>'
        f'<a:rPr lang="en-US" sz="{size}"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill></a:rPr>'
        f'<a:t>{_e(text)}</a:t></a:r><a:endParaRPr lang="en-US"/></a:p></p:txBody>'
    )


def _fit_text(label: str, w: float, h: float, geom: str) -> tuple[int, int | None]:
    """Choose readable type and a final Office shrink factor for narrow shapes."""
    factor = {"diamond": 0.35, "parallelogram": 0.72, "can": 0.72,
              "flowChartDocument": 0.72}.get(geom, 0.84)
    usable_w, usable_h = max(12, w * factor - 8), max(12, h * 0.72 - 6)
    for size in range(1200, 599, -50):
        px = size / 75
        capacity = max(1, int(usable_w / (px * 0.56)))
        lines = sum(max(1, math.ceil(len(word) / capacity)) for word in label.splitlines())
        if not lines:
            lines = max(1, math.ceil(len(label) / capacity))
        if lines * px * 1.17 <= usable_h and len(label) <= capacity * max(1, int(usable_h / (px * 1.17))):
            return size, None
    # Let Office shrink the text further when even the readable minimum overflows.
    capacity = max(1, int(usable_w / (8 * 0.56)))
    estimated = max(1, math.ceil(len(label) / capacity)) * 8 * 1.17
    return 600, max(10000, min(100000, int(100000 * usable_h / estimated)))


def _shape(sid: int, name: str, x: float, y: float, w: float, h: float, *,
           geom: str = "rect", fill: str = "FFFFFF", line: str = "486581",
           text: str = "", size: int = 1200, opacity: int | None = None,
           fit: bool = False) -> str:
    fill_xml = (f'<a:solidFill><a:srgbClr val="{_color(fill)}"/></a:solidFill>'
                if opacity is None else
                f'<a:solidFill><a:srgbClr val="{_color(fill)}"><a:alpha val="{opacity}"/>'
                '</a:srgbClr></a:solidFill>')
    return (
        '<p:sp><p:nvSpPr>'
        f'<p:cNvPr id="{sid}" name="{_e(name)}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
        '<p:spPr><a:xfrm>'
        f'<a:off x="{_n(x)}" y="{_n(y)}"/><a:ext cx="{_n(w)}" cy="{_n(h)}"/>'
        f'</a:xfrm><a:prstGeom prst="{geom}"><a:avLst/></a:prstGeom>'
        f'{fill_xml}'
        f'<a:ln w="12700"><a:solidFill><a:srgbClr val="{_color(line)}"/></a:solidFill></a:ln>'
        '</p:spPr>' + (_text(text, _fit_text(text, w, h, geom)[0],
                              font_scale=_fit_text(text, w, h, geom)[1], tight=True) if fit and text
                       else _text(text, size) if text else '') + '</p:sp>'
    )


def _polyline(sid: int, points: list[tuple[float, float]], *, directed: bool,
              dashed: bool, color: str) -> str:
    """Editable polyline shape; PowerPoint repairs custom connector geometry."""
    left = min(x for x, _ in points)
    top = min(y for _, y in points)
    width = max(1, _n(max(x for x, _ in points) - left))
    height = max(1, _n(max(y for _, y in points) - top))
    commands = []
    for index, (x, y) in enumerate(points):
        tag = 'moveTo' if index == 0 else 'lnTo'
        commands.append(f'<a:{tag}><a:pt x="{_n(x-left)}" y="{_n(y-top)}"/></a:{tag}>')
    dash = '<a:prstDash val="dash"/>' if dashed else ''
    arrow = '<a:tailEnd type="triangle"/>' if directed else ''
    path_commands = ''.join(commands)
    return (
        '<p:sp><p:nvSpPr>'
        f'<p:cNvPr id="{sid}" name="Routed edge {sid}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr><a:xfrm><a:off x="{_n(left)}" y="{_n(top)}"/>'
        f'<a:ext cx="{width}" cy="{height}"/></a:xfrm>'
        '<a:custGeom><a:avLst/><a:gdLst/><a:ahLst/><a:cxnLst/>'
        '<a:rect l="l" t="t" r="r" b="b"/><a:pathLst>'
        f'<a:path w="{width}" h="{height}" fill="none">{path_commands}</a:path>'
        '</a:pathLst></a:custGeom><a:noFill/>'
        f'<a:ln w="19050"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
        f'{dash}{arrow}</a:ln></p:spPr></p:sp>'
    )


def _line(sid: int, x1: float, y1: float, x2: float, y2: float, *,
          directed: bool, dashed: bool, color: str = "5B6470") -> str:
    flip_h = ' flipH="1"' if x2 < x1 else ''
    flip_v = ' flipV="1"' if y2 < y1 else ''
    dash = '<a:prstDash val="dash"/>' if dashed else ''
    arrow = '<a:tailEnd type="triangle"/>' if directed else ''
    return (
        '<p:cxnSp><p:nvCxnSpPr>'
        f'<p:cNvPr id="{sid}" name="Connector {sid}"/><p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>'
        f'<p:spPr><a:xfrm{flip_h}{flip_v}><a:off x="{_n(min(x1,x2))}" y="{_n(min(y1,y2))}"/>'
        f'<a:ext cx="{max(1,_n(abs(x2-x1)))}" cy="{max(1,_n(abs(y2-y1)))}"/></a:xfrm>'
        '<a:prstGeom prst="line"><a:avLst/></a:prstGeom>'
        f'<a:ln w="19050"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
        f'{dash}{arrow}</a:ln></p:spPr></p:cxnSp>'
    )


def _picture(sid: int, name: str, x: float, y: float, w: float, h: float, rid: str) -> str:
    return (
        '<p:pic><p:nvPicPr>'
        f'<p:cNvPr id="{sid}" name="{_e(name)}"/><p:cNvPicPr><a:picLocks noChangeAspect="1"/>'
        '</p:cNvPicPr><p:nvPr/></p:nvPicPr>'
        f'<p:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
        '<p:spPr><a:xfrm>'
        f'<a:off x="{_n(x)}" y="{_n(y)}"/><a:ext cx="{_n(w)}" cy="{_n(h)}"/>'
        '</a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>'
    )


def _tree_start() -> str:
    return (
        '<p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/>'
        '<p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
        '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
    )


def _rels(items: list[tuple[str, str, str]]) -> str:
    body = ''.join(
        f'<Relationship Id="{rid}" Type="{typ}" Target="{target}"/>'
        for rid, typ, target in items
    )
    return f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="{PKG}">{body}</Relationships>'


def _theme() -> str:
    colors = ''.join(
        f'<a:{name}><a:srgbClr val="{value}"/></a:{name}>'
        for name, value in [
            ('dk1','1B1F24'),('lt1','FFFFFF'),('dk2','35465A'),('lt2','F7F9FC'),
            ('accent1','486581'),('accent2','4F85B5'),('accent3','76A5AF'),
            ('accent4','9AA5B1'),('accent5','5B6470'),('accent6','CCD6E0'),
            ('hlink','0563C1'),('folHlink','954F72'),
        ]
    )
    return (
        f'<a:theme xmlns:a="{A}" name="Archdiagram"><a:themeElements>'
        f'<a:clrScheme name="Archdiagram">{colors}</a:clrScheme>'
        '<a:fontScheme name="Archdiagram"><a:majorFont><a:latin typeface="Aptos Display"/>'
        '</a:majorFont><a:minorFont><a:latin typeface="Aptos"/></a:minorFont></a:fontScheme>'
        '<a:fmtScheme name="Archdiagram"><a:fillStyleLst><a:solidFill><a:schemeClr val="accent1"/>'
        '</a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w="9525"/></a:lnStyleLst>'
        '<a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>'
        '<a:bgFillStyleLst><a:solidFill><a:schemeClr val="lt1"/></a:solidFill></a:bgFillStyleLst>'
        '</a:fmtScheme></a:themeElements></a:theme>'
    )


def emit_pptx(diagram: Diagram, out_path: str, *, icon_cache: str | None = None,
              layout: LayoutResult | None = None,
              catalog: Catalog | None = None) -> list[str]:
    """Write a PPTX. Shapes and text remain editable; vendor icons are embedded PNGs."""
    layout = layout if layout is not None else layout_diagram(diagram)
    modern = is_modern_diagram(diagram)
    catalog = catalog if catalog is not None else catalog_for(diagram)
    images, warnings = node_icon_pngs(diagram, IconResolver(icon_cache), catalog=catalog)
    shapes: list[str] = []
    slide_rels = [("rId1", f"{R}/slideLayout", "../slideLayouts/slideLayout1.xml")]
    media: dict[str, bytes] = {}
    sid = 2

    shapes.append(_shape(sid, "Title", 8, 4, layout.width-16, 32,
                         fill="FFFFFF", line="FFFFFF", text=diagram.title, size=1600))
    sid += 1
    for lane_id, lane_label, lb in lane_bands(diagram, layout):
        modern = diagram.lane_orientation is not None
        fill = "F5F5F5" if modern else "F7F9FC"
        line = "999999" if modern else "BCC7D4"
        shapes.append(_shape(sid, f"Lane {lane_id}", lb.x, lb.y+36, lb.w, lb.h,
                             fill=fill, line=line, opacity=30000 if modern else None))
        sid += 1
        shapes.append(_shape(sid, f"Lane label {lane_id}", lb.x+8, lb.y+38, min(150, lb.w-16), 24,
                             fill=fill, line=fill, text=lane_label, size=900 if modern else 1200))
        sid += 1
    for group in diagram.groups:
        gb = layout.group_boxes.get(group.id)
        if gb:
            shapes.append(_shape(sid, f"Group {group.id}", gb.x, gb.y+36, gb.w, gb.h,
                                 fill="F1F5F9", line="9AA5B1"))
            sid += 1
            shapes.append(_shape(sid, f"Group label {group.id}", gb.x+8, gb.y+38, min(150, gb.w-16), 24,
                                 fill="F1F5F9", line="F1F5F9", text=group.display_label,
                                 size=900 if modern else 1200))
            sid += 1
    for edge in diagram.edges:
        if modern:
            points = route_edge(diagram, layout, edge)
            shapes.append(_polyline(sid, [(x, y+36) for x, y in points],
                                    directed=edge.directed,
                                    dashed=edge.kind == "data" or edge.dashed,
                                    color=_color(edge.color or "#5B6470")))
            lx, ly = label_position(points)
        else:
            x1, y1, x2, y2 = edge_endpoints(diagram, layout, edge)
            shapes.append(_line(sid, x1, y1+36, x2, y2+36,
                                directed=edge.directed, dashed=edge.kind == "data" or edge.dashed,
                                color=_color(edge.color or "#5B6470")))
            lx, ly = (x1+x2)/2, (y1+y2)/2
        sid += 1
        if edge.label:
            shapes.append(_shape(sid, f"Edge label {sid}", lx-38, ly+27,
                                 76, 18, fill="FFFFFF", line="FFFFFF", text=edge.label, size=1000))
            sid += 1
    geom = {"process":"roundRect", "decision":"diamond", "data":"parallelogram",
            "start":"ellipse", "end":"ellipse"}
    for node in diagram.nodes:
        box = layout.boxes[node.id]
        if node.kind != "service":
            style = SHAPES[node.shape] if node.shape else None
            shapes.append(_shape(sid, f"Node {node.id}", box.x, box.y+36, box.w, box.h,
                                 geom=style.pptx if style else geom[node.kind],
                                 fill=style.fill if style else "F1F5F9",
                                 line=style.stroke if style else "486581",
                                 text=node.display_label, fit=modern))
            sid += 1
            continue
        ix, iy, iw, ih = box.icon_rect(ICON_SIZE, ICON_SIZE)
        if node.id in images:
            rid = f"rId{len(slide_rels)+1}"
            fname = f"image{len(media)+1}.png"
            media[fname] = images[node.id]
            slide_rels.append((rid, f"{R}/image", f"../media/{fname}"))
            shapes.append(_picture(sid, f"Icon {node.id}", ix, iy+36, iw, ih, rid))
        else:
            entry = catalog.lookup(node.service)
            accent = entry.accent if entry else catalog.accent(node.vendor)
            shapes.append(_shape(sid, f"Service {node.id}", ix, iy+36, iw, ih,
                                 geom="roundRect", fill=_color(accent), line=_color(accent),
                                 text=node.display_label[:2].upper()))
        sid += 1
        shapes.append(_shape(sid, f"Label {node.id}", box.x, box.y+36+box.h-25,
                             box.w, 22, fill="FFFFFF", line="FFFFFF", text=node.display_label, size=1100))
        sid += 1

    slide = (f'<p:sld xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}"><p:cSld>'
             + _tree_start() + ''.join(shapes) + '</p:spTree></p:cSld>'
             '<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>')
    static = Path(__file__).with_name("pptx_parts")
    def static_part(name: str) -> bytes:
        # Preserve the established golden bytes across Git checkout platforms.
        return (static / name).read_text(encoding="utf-8").replace("\n", "\r\n").encode("utf-8")
    presentation = (static / "presentation.xml").read_text(encoding="utf-8")
    slide_width = max(layout.width, (layout.height+36)*16/9) if modern else layout.width
    slide_height = max(layout.height+36, layout.width*9/16) if modern else layout.height+36
    presentation = re.sub(r'<p:sldSz\b[^>]*/>',
                          f'<p:sldSz cx="{_n(slide_width)}" cy="{_n(slide_height)}"/>',
                          presentation, count=1)
    content_types = (
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="png" ContentType="image/png"/>'
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
        '<Override PartName="/ppt/slides/slide1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>'
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>'
        '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
        '<Override PartName="/ppt/presProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presProps+xml"/>'
        '<Override PartName="/ppt/viewProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.viewProps+xml"/>'
        '<Override PartName="/ppt/tableStyles.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.tableStyles+xml"/>'
        '</Types>'
    )
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        write_stable(zf, '[Content_Types].xml', content_types)
        write_stable(zf, '_rels/.rels', _rels([('rId1', f'{R}/officeDocument', 'ppt/presentation.xml')]))
        write_stable(zf, 'ppt/presentation.xml', presentation)
        write_stable(zf, 'ppt/_rels/presentation.xml.rels', _rels([
            ('rId1', f'{R}/slideMaster', 'slideMasters/slideMaster1.xml'),
            ('rId2', f'{R}/slide', 'slides/slide1.xml'),
            ('rId3', f'{R}/presProps', 'presProps.xml'),
            ('rId4', f'{R}/viewProps', 'viewProps.xml'),
            ('rId5', f'{R}/theme', 'theme/theme1.xml'),
            ('rId6', f'{R}/tableStyles', 'tableStyles.xml'),
        ]))
        write_stable(zf, 'ppt/slides/slide1.xml', slide)
        write_stable(zf, 'ppt/slides/_rels/slide1.xml.rels', _rels(slide_rels))
        write_stable(zf, 'ppt/slideLayouts/slideLayout1.xml',
                     static_part('slideLayout1.xml'))
        write_stable(zf, 'ppt/slideLayouts/_rels/slideLayout1.xml.rels', _rels([
            ('rId1', f'{R}/slideMaster', '../slideMasters/slideMaster1.xml'),
        ]))
        write_stable(zf, 'ppt/slideMasters/slideMaster1.xml',
                     static_part('slideMaster1.xml'))
        write_stable(zf, 'ppt/slideMasters/_rels/slideMaster1.xml.rels', _rels([
            ('rId1', f'{R}/slideLayout', '../slideLayouts/slideLayout1.xml'),
            ('rId12', f'{R}/theme', '../theme/theme1.xml'),
        ]))
        for name in ('theme1.xml', 'presProps.xml', 'viewProps.xml', 'tableStyles.xml'):
            part = ('ppt/theme/theme1.xml' if name == 'theme1.xml' else f'ppt/{name}')
            write_stable(zf, part, static_part(name))
        for fname, data in media.items():
            write_stable(zf, f'ppt/media/{fname}', data)
    return warnings
