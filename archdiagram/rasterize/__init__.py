"""Optional Node bridge for rasterising SVG icons and writing PDF.

The core engine never imports this at module load in a way that requires Node;
callers check :func:`rasterizer_available` / :func:`pdf_bridge_available` and
degrade gracefully.
"""

from .resvg import (
    NodeBridgeError,
    pdf_bridge_available,
    rasterize_icons,
    rasterizer_available,
    svg_to_pdf,
)

__all__ = [
    "NodeBridgeError",
    "pdf_bridge_available",
    "rasterize_icons",
    "rasterizer_available",
    "svg_to_pdf",
]
