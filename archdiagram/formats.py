"""One registry for diagram formats and their renderer adapters."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .emit.drawio import NATIVE, PORTABLE, emit_drawio
from .emit.pdf import emit_pdf
from .emit.pptx import emit_pptx
from .emit.svg import render_html, render_svg
from .emit.vsdx import emit_vsdx
from .spec.model import Diagram

Renderer = Callable[[Diagram, str | None, str], tuple[bytes, list[str]]]


@dataclass(frozen=True)
class OutputFormat:
    name: str
    extension: str
    mime_type: str
    binary: bool
    renderer: Renderer


def _file_renderer(emitter: Callable, extension: str) -> Renderer:
    def render(diagram: Diagram, icon_cache: str | None, _drawio_mode: str) -> tuple[bytes, list[str]]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / f"diagram.{extension}"
            warnings = emitter(diagram, str(path), icon_cache=icon_cache)
            return path.read_bytes(), warnings
    return render


def _drawio(diagram: Diagram, icon_cache: str | None, drawio_mode: str) -> tuple[bytes, list[str]]:
    mode = PORTABLE if drawio_mode == "portable" else NATIVE
    return emit_drawio(diagram, mode=mode, icon_cache=icon_cache).encode("utf-8"), []


def _svg(diagram: Diagram, icon_cache: str | None, _drawio_mode: str) -> tuple[bytes, list[str]]:
    content, warnings = render_svg(diagram, icon_cache=icon_cache)
    return content.encode("utf-8"), warnings


def _html(diagram: Diagram, icon_cache: str | None, _drawio_mode: str) -> tuple[bytes, list[str]]:
    content, warnings = render_html(diagram, icon_cache=icon_cache)
    return content.encode("utf-8"), warnings


FORMATS: dict[str, OutputFormat] = {
    "pdf": OutputFormat("pdf", ".pdf", "application/pdf", True, _file_renderer(emit_pdf, "pdf")),
    "drawio": OutputFormat("drawio", ".drawio", "application/vnd.jgraph.mxfile", False, _drawio),
    "vsdx": OutputFormat("vsdx", ".vsdx", "application/vnd.ms-visio.drawing", True,
                         _file_renderer(emit_vsdx, "vsdx")),
    "svg": OutputFormat("svg", ".svg", "image/svg+xml", False, _svg),
    "html": OutputFormat("html", ".html", "text/html", False, _html),
    "pptx": OutputFormat("pptx", ".pptx",
                         "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                         True, _file_renderer(emit_pptx, "pptx")),
}


def get_format(name: str) -> OutputFormat:
    try:
        return FORMATS[name.lower()]
    except KeyError as exc:
        raise ValueError(f"unknown format '{name}'; use {'|'.join(FORMATS)}") from exc
