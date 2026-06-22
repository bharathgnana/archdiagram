"""PDF emitter - the primary, Lucid-faithful deliverable.

Every node is rendered as its real vendor icon, baked into a self-contained
page. The flow is:

1. lay the diagram out;
2. rasterise each unique icon SVG to PNG via the Node resvg bridge;
3. compose a page SVG (icons + edges + labels + group containers);
4. convert that SVG to PDF via the Node pdfkit + svg-to-pdfkit bridge.

If the Node PDF bridge is unavailable, :class:`PdfDependencyError` is raised
with an install hint (per the project's dependency policy). If only the
rasteriser is missing, the PDF is still produced with labelled fallback boxes.
"""

from __future__ import annotations

from ..layout.engine import layout_diagram
from ..rasterize.resvg import NodeBridgeError, pdf_bridge_available, svg_to_pdf
from ..registry.catalog import get_catalog
from ..registry.icons import IconResolver
from ..spec.model import Diagram
from .iconglyph import node_icon_pngs
from .svgcanvas import build_page_svg


class PdfDependencyError(RuntimeError):
    """Raised when the Node PDF bridge is required but unavailable."""


def emit_pdf(
    diagram: Diagram,
    out_path: str,
    *,
    icon_cache: str | None = None,
    raster_scale: float = 2.0,
) -> list[str]:
    """Render ``diagram`` to a PDF file. Returns a list of non-fatal warnings."""

    if not pdf_bridge_available():
        raise PdfDependencyError(
            "PDF output requires the Node bridge (pdfkit + svg-to-pdfkit).\n"
            "    cd node && npm install\n"
            "Then retry. (Node 18+ required.)"
        )

    layout = layout_diagram(diagram)
    resolver = IconResolver(icon_cache)
    try:
        node_pngs, warnings = node_icon_pngs(diagram, resolver, raster_scale)
    except NodeBridgeError:
        node_pngs, warnings = {}, ["rasteriser failed -> all nodes use fallback boxes"]

    svg = build_page_svg(diagram, layout, get_catalog(), node_pngs)
    svg_to_pdf(svg, out_path, width=layout.width, height=layout.height + 36, title=diagram.title)
    return warnings
