"""Pure-Python MCP tool functions; this module never imports the MCP SDK."""

from __future__ import annotations

import os

from archdiagram.emit.pdf import PdfDependencyError
from archdiagram.engine import render_to_file, resolve_services
from archdiagram.formats import FORMATS
from archdiagram.registry.catalog import get_catalog
from archdiagram.spec.validate import SpecError, SpecValidationError, load_spec
from archdiagram.templates import get_template, list_templates, suggest_template


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
    return {"name": name, "spec": get_template(name), "templates": list_templates()}


def get_diagram_template(name: str) -> dict:
    """Get an editable starter spec by name. Use choose_template to select one."""
    try:
        return {"ok": True, "spec": get_template(name)}
    except ValueError as exc:
        return {"ok": False, "errors": [str(exc)]}
