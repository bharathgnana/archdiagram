"""Output emitters: PDF (primary), draw.io (dual-mode), VSDX."""

from .drawio import emit_drawio
from .pdf import PdfDependencyError, emit_pdf
from .vsdx import emit_vsdx

__all__ = ["emit_drawio", "emit_pdf", "emit_vsdx", "PdfDependencyError"]
