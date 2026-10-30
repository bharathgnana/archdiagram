"""Pure-Python MCP tool functions; this module never imports the MCP SDK."""

from __future__ import annotations

import os
import json
from pathlib import Path

from archdiagram.emit.pdf import PdfDependencyError
from archdiagram.engine import render_to_file, resolve_services
from archdiagram.formats import FORMATS
from archdiagram.registry.catalog import get_catalog
from archdiagram.spec.validate import SpecError, SpecValidationError, load_spec
from archdiagram.templates import get_template, list_templates as _list_templates, suggest_template


def validate_spec(spec_json: str, strict: bool = False) -> dict:
    """Validate a diagram spec and return all errors or a compact summary."""
    try:
        diagram = load_spec(spec_json)
        if strict:
            resolve_services(diagram, strict=True)
    except SpecValidationError as exc:
        return {"ok": False, "errors": exc.errors}
    except SpecError as exc:
        return {"ok": False, "errors": [str(exc)]}
    return {
        "ok": True,
        "summary": {
            "title": diagram.title,
            "nodes": len(diagram.nodes),
            "edges": len(diagram.edges),
            "groups": len(diagram.groups),
            "lanes": len(diagram.lanes),
        },
    }


def render_diagram(
    spec_json: str,
    fmt: str,
    out_path: str,
    drawio_mode: str = "portable",
    icon_cache: str | None = None,
    strict: bool = False,
) -> dict:
    """Render a JSON spec to pdf, drawio, vsdx, svg, html, or pptx."""
    try:
        diagram = load_spec(spec_json)
    except SpecError as exc:
        return {"ok": False, "errors": getattr(exc, "errors", [str(exc)])}
    fmt = fmt.lower()
    if fmt not in FORMATS:
        return {"ok": False, "errors": [f"unknown format '{fmt}'; use {'|'.join(FORMATS)}"]}
    try:
        result = render_to_file(diagram, fmt, out_path,
                                icon_cache=icon_cache, drawio_mode=drawio_mode,
                                strict=strict)
    except (PdfDependencyError, SpecError, ValueError) as exc:
        return {"ok": False, "errors": getattr(exc, "errors", [str(exc)])}
    return {"ok": True, "path": os.path.abspath(out_path), "warnings": list(result.warnings)}


def search_catalog(query: str) -> dict:
    """Search the vendor service catalog by service id or label."""
    results = get_catalog().search(query)
    return {"results": [{"service": e.service, "label": e.label} for e in results]}


def list_catalog(vendor: str | None = None) -> dict:
    """List all catalog services, optionally filtered by vendor."""
    entries = get_catalog().all_entries()
    if vendor:
        entries = [e for e in entries if e.vendor == vendor]
    return {
        "vendors": get_catalog().vendors,
        "services": [
            {"service": e.service, "label": e.label}
            for e in sorted(entries, key=lambda x: x.service)
        ],
    }


def choose_template(description: str) -> dict:
    """Recommend a cloud, workflow, decision, dataflow, or swimlane starter spec."""
    name = suggest_template(description)
    return {"name": name, "spec": get_template(name), "templates": _list_templates()}


def get_diagram_template(name: str) -> dict:
    """Get an editable starter spec by name. Use choose_template to select one."""
    try:
        return {"ok": True, "spec": get_template(name)}
    except ValueError as exc:
        return {"ok": False, "errors": [str(exc)]}


def list_templates() -> dict:
    """List the four diagram families and compatibility starter templates."""
    return {"templates": _list_templates()}


def list_icons(query: str = "", provider: str | None = None, limit: int = 25) -> dict:
    """List catalog icons using an optional query and provider filter."""
    if limit < 1:
        return {"ok": False, "errors": ["limit must be positive"]}
    catalog = get_catalog()
    entries = catalog.search(query, limit=100000) if query else catalog.all_entries()
    if provider:
        entries = [entry for entry in entries if entry.vendor == provider.lower()]
    return {"icons": [dict(service=entry.service, label=entry.label, provider=entry.vendor,
                           icon=entry.icon) for entry in entries[:limit]],
            "total": len(entries)}


def resolve_service(service: str) -> dict:
    """Resolve a service name and explain the match or suggest alternatives."""
    entry, method, suggestions = get_catalog().resolve(service)
    return {"ok": entry is not None, "service": entry.service if entry else None,
            "method": method, "suggestions": suggestions,
            "icon": entry.icon if entry else None}


def get_catalog_info() -> dict:
    """Summarize catalog providers and entry counts."""
    catalog = get_catalog()
    entries = catalog.all_entries()
    return {"providers": catalog.vendors, "icon_count": len(entries),
            "counts": {vendor: sum(entry.vendor == vendor for entry in entries)
                       for vendor in catalog.vendors}}


def _raw_spec(source: str | dict) -> dict:
    if isinstance(source, dict):
        return dict(source)
    text = source.strip()
    if not text.startswith("{"):
        text = Path(source).read_text(encoding="utf-8")
    raw = json.loads(text)
    if not isinstance(raw, dict):
        raise ValueError("spec must be a JSON object")
    return raw


def generate_diagram(spec: str | dict, format: str = "svg", out_path: str | None = None,
                     inline: bool = False, template: str | None = None,
                     strict: bool = False) -> dict:
    """Render a spec and return path, dimensions, counts, format, and warnings."""
    try:
        raw = _raw_spec(spec)
        if template:
            starter = get_template(template)
            raw.setdefault("direction", starter["direction"])
        output_dir = Path(os.environ.get("ARCHDIAG_OUTPUT_DIR", "out"))
        path = Path(out_path) if out_path else output_dir / f"diagram.{format}"
        result = render_to_file(raw, format, str(path), strict=strict)
    except (OSError, json.JSONDecodeError, ValueError, SpecError, PdfDependencyError) as exc:
        return {"ok": False, "errors": getattr(exc, "errors", [str(exc)])}
    response = {"ok": True, "path": str(path.resolve()), "format": result.format.name,
                "mime_type": result.format.mime_type, "bytes": len(result.content),
                "nodes": len(result.diagram.nodes), "edges": len(result.diagram.edges),
                "groups": len(result.diagram.groups), "width": result.width,
                "height": result.height, "warnings": list(result.warnings),
                "template": template}
    if inline and not result.format.binary:
        response["content"] = result.content.decode("utf-8")
    return response


def schema_resource() -> str:
    """A compact schema reference for MCP clients."""
    from archdiagram.shapes import SHAPES
    return json.dumps({"directions": ["LR", "RL", "TB", "BT"],
                       "shapes": list(SHAPES),
                       "node": {"required": ["id", "service or shape"],
                                "optional": ["label", "tier", "lane", "group", "x", "y"]},
                       "edge": {"required": ["source", "target"],
                                "optional": ["label", "kind", "dashed", "color"]}},
                      sort_keys=True)


def catalog_resource() -> str:
    return json.dumps(get_catalog_info(), sort_keys=True)


def describe_diagram(description: str, diagram_type: str) -> str:
    return (f"Create a {diagram_type} JSON spec for: {description}. "
            "Choose a matching template, validate the spec, then generate and inspect the diagram.")


def describe_architecture(description: str) -> str:
    return describe_diagram(description, "architecture_diagram")
