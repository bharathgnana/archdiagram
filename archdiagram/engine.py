"""Shared validate, resolve, layout, render, and write pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .formats import OutputFormat, get_format
from .layout.engine import LayoutResult, layout_diagram
from .normalize import normalize_edges
from .registry.catalog import catalog_for
from .spec.model import Diagram
from .spec.validate import load_spec


@dataclass(frozen=True)
class RenderResult:
    diagram: Diagram
    format: OutputFormat
    layout: LayoutResult
    content: bytes
    warnings: tuple[str, ...]

    @property
    def width(self) -> float:
        return self.layout.width

    @property
    def height(self) -> float:
        return self.layout.height


def render(source: Any, fmt: str, *, icon_cache: str | None = None,
           drawio_mode: str = "portable") -> RenderResult:
    """Render a raw spec or validated diagram without writing a file."""
    diagram = source if isinstance(source, Diagram) else load_spec(source)
    diagram, normalization_warnings = normalize_edges(diagram)
    catalog_for(diagram)
    layout = layout_diagram(diagram)
    output_format = get_format(fmt)
    content, warnings = output_format.renderer(diagram, icon_cache, drawio_mode)
    return RenderResult(diagram, output_format, layout, content,
                        tuple(normalization_warnings + warnings))


def render_to_file(source: Any, fmt: str, out_path: str, *,
                   icon_cache: str | None = None,
                   drawio_mode: str = "portable") -> RenderResult:
    result = render(source, fmt, icon_cache=icon_cache, drawio_mode=drawio_mode)
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(result.content)
    return result
