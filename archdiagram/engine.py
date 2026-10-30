"""Shared validate, resolve, layout, render, and write pipeline."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .formats import OutputFormat, get_format
from .layout.engine import LayoutResult, layout_diagram
from .normalize import normalize_edges
from .registry.catalog import catalog_for
from .spec.model import Diagram
from .spec.validate import SpecValidationError, load_spec


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


def resolve_services(diagram: Diagram, *, strict: bool = False) -> tuple[Diagram, list[str]]:
    """Resolve service names in the engine, retaining fallback nodes by default."""
    catalog = catalog_for(diagram)
    resolution_warnings: list[str] = []
    missing: list[str] = []
    resolved_nodes = []
    for node in diagram.nodes:
        if node.service is None:
            resolved_nodes.append(node)
            continue
        entry, method, suggestions = catalog.resolve(node.service)
        if entry is None:
            message = f"nodes[{node.id}].service: unknown service '{node.service}'"
            if suggestions:
                message += f"; suggestions: {', '.join(suggestions)}"
            (missing if strict else resolution_warnings).append(message)
            resolved_nodes.append(node)
        else:
            if method != "canonical":
                resolution_warnings.append(f"resolved '{node.service}' to '{entry.service}' via {method}")
            resolved_nodes.append(replace(node, service=entry.service) if node.service != entry.service else node)
    if missing:
        raise SpecValidationError(missing)
    if any(before is not after for before, after in zip(diagram.nodes, resolved_nodes)):
        diagram = replace(diagram, nodes=resolved_nodes)
    return diagram, resolution_warnings


def render(source: Any, fmt: str, *, icon_cache: str | None = None,
           drawio_mode: str = "portable", strict: bool = False) -> RenderResult:
    """Render a raw spec or validated diagram without writing a file."""
    diagram = source if isinstance(source, Diagram) else load_spec(source)
    diagram, normalization_warnings = normalize_edges(diagram)
    diagram, resolution_warnings = resolve_services(diagram, strict=strict)
    layout = layout_diagram(diagram)
    output_format = get_format(fmt)
    content, warnings = output_format.renderer(diagram, icon_cache, drawio_mode)
    return RenderResult(diagram, output_format, layout, content,
                        tuple(normalization_warnings + resolution_warnings + warnings))


def render_to_file(source: Any, fmt: str, out_path: str, *,
                   icon_cache: str | None = None,
                   drawio_mode: str = "portable", strict: bool = False) -> RenderResult:
    result = render(source, fmt, icon_cache=icon_cache, drawio_mode=drawio_mode, strict=strict)
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(result.content)
    return result
