"""Editable one-slide PowerPoint export, written with the Python standard library."""

from __future__ import annotations

import html
import os
import zipfile

from ..layout.engine import ICON_SIZE, layout_diagram
from ..registry.catalog import get_catalog
from ..registry.icons import IconResolver
from ..spec.model import Diagram
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


def _text(text: str, size: int = 1200, color: str = "1B1F24") -> str:
    return (
        '<p:txBody><a:bodyPr wrap="square" anchor="ctr"/><a:lstStyle/>'
        '<a:p><a:pPr algn="ctr"/><a:r>'
        f'<a:rPr lang="en-US" sz="{size}"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill></a:rPr>'
        f'<a:t>{_e(text)}</a:t></a:r><a:endParaRPr lang="en-US"/></a:p></p:txBody>'
    )


def _shape(sid: int, name: str, x: float, y: float, w: float, h: float, *,
           geom: str = "rect", fill: str = "FFFFFF", line: str = "486581",
           text: str = "", size: int = 1200) -> str:
    return (
        '<p:sp><p:nvSpPr>'
        f'<p:cNvPr id="{sid}" name="{_e(name)}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
        '<p:spPr><a:xfrm>'
        f'<a:off x="{_n(x)}" y="{_n(y)}"/><a:ext cx="{_n(w)}" cy="{_n(h)}"/>'
        f'</a:xfrm><a:prstGeom prst="{geom}"><a:avLst/></a:prstGeom>'
        f'<a:solidFill><a:srgbClr val="{_color(fill)}"/></a:solidFill>'
        f'<a:ln w="12700"><a:solidFill><a:srgbClr val="{_color(line)}"/></a:solidFill></a:ln>'
        '</p:spPr>' + (_text(text, size) if text else '') + '</p:sp>'
    )


def _line(sid: int, x1: float, y1: float, x2: float, y2: float, *,
          directed: bool, dashed: bool) -> str:
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
        '<a:ln w="19050"><a:solidFill><a:srgbClr val="5B6470"/></a:solidFill>'
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


def emit_pptx(diagram: Diagram, out_path: str, *, icon_cache: str | None = None) -> list[str]:
    """Write a PPTX. Shapes and text remain editable; vendor icons are embedded PNGs."""
    layout = layout_diagram(diagram)
    catalog = get_catalog()
    images, warnings = node_icon_pngs(diagram, IconResolver(icon_cache))
    shapes: list[str] = []
    slide_rels = [("rId1", f"{R}/slideLayout", "../slideLayouts/slideLayout1.xml")]
    media: dict[str, bytes] = {}
    sid = 2

    shapes.append(_shape(sid, "Title", 8, 4, layout.width-16, 32,
                         fill="FFFFFF", line="FFFFFF", text=diagram.title, size=1600))
    sid += 1
    for lane in diagram.lanes:
        lb = layout.lane_boxes.get(lane.id)
        if lb:
            shapes.append(_shape(sid, f"Lane {lane.id}", lb.x, lb.y+36, lb.w, lb.h,
                                 fill="F7F9FC", line="BCC7D4"))
            sid += 1
            shapes.append(_shape(sid, f"Lane label {lane.id}", lb.x+8, lb.y+38, min(150, lb.w-16), 24,
                                 fill="F7F9FC", line="F7F9FC", text=lane.display_label))
            sid += 1
    for group in diagram.groups:
        gb = layout.group_boxes.get(group.id)
        if gb:
            shapes.append(_shape(sid, f"Group {group.id}", gb.x, gb.y+36, gb.w, gb.h,
                                 fill="F1F5F9", line="9AA5B1"))
            sid += 1
            shapes.append(_shape(sid, f"Group label {group.id}", gb.x+8, gb.y+38, min(150, gb.w-16), 24,
                                 fill="F1F5F9", line="F1F5F9", text=group.display_label))
            sid += 1
    for edge in diagram.edges:
        x1, y1, x2, y2 = edge_endpoints(diagram, layout, edge)
        shapes.append(_line(sid, x1, y1+36, x2, y2+36,
                            directed=edge.directed, dashed=edge.kind == "data"))
        sid += 1
        if edge.label:
            shapes.append(_shape(sid, f"Edge label {sid}", (x1+x2)/2-38, (y1+y2)/2+27,
                                 76, 18, fill="FFFFFF", line="FFFFFF", text=edge.label, size=1000))
            sid += 1
    geom = {"process":"roundRect", "decision":"diamond", "data":"parallelogram",
            "start":"ellipse", "end":"ellipse"}
    for node in diagram.nodes:
        box = layout.boxes[node.id]
        if node.kind != "service":
            shapes.append(_shape(sid, f"Node {node.id}", box.x, box.y+36, box.w, box.h,
                                 geom=geom[node.kind], fill="F1F5F9", line="486581",
                                 text=node.display_label))
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
    blank = _tree_start() + '</p:spTree>'
    layout_xml = (f'<p:sldLayout xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}" type="blank" preserve="1">'
                  f'<p:cSld name="Blank">{blank}</p:cSld>'
                  '<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>')
    master = (f'<p:sldMaster xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}">'
              f'<p:cSld>{blank}</p:cSld><p:clrMap accent1="accent1" accent2="accent2" '
              'accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" '
              'bg1="lt1" bg2="lt2" folHlink="folHlink" hlink="hlink" tx1="dk1" tx2="dk2"/>'
              '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>'
              '</p:sldMaster>')
    presentation = (f'<p:presentation xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}">'
                    '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
                    '<p:sldIdLst><p:sldId id="256" r:id="rId2"/></p:sldIdLst>'
                    f'<p:sldSz cx="{_n(layout.width)}" cy="{_n(layout.height+36)}" type="cust"/>'
                    '<p:notesSz cx="6858000" cy="9144000"/></p:presentation>')
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
        ]))
        write_stable(zf, 'ppt/slides/slide1.xml', slide)
        write_stable(zf, 'ppt/slides/_rels/slide1.xml.rels', _rels(slide_rels))
        write_stable(zf, 'ppt/slideLayouts/slideLayout1.xml', layout_xml)
        write_stable(zf, 'ppt/slideLayouts/_rels/slideLayout1.xml.rels', _rels([
            ('rId1', f'{R}/slideMaster', '../slideMasters/slideMaster1.xml'),
        ]))
        write_stable(zf, 'ppt/slideMasters/slideMaster1.xml', master)
        write_stable(zf, 'ppt/slideMasters/_rels/slideMaster1.xml.rels', _rels([
            ('rId1', f'{R}/slideLayout', '../slideLayouts/slideLayout1.xml'),
            ('rId2', f'{R}/theme', '../theme/theme1.xml'),
        ]))
        write_stable(zf, 'ppt/theme/theme1.xml', _theme())
        for fname, data in media.items():
            write_stable(zf, f'ppt/media/{fname}', data)
    return warnings
