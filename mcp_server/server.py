"""archdiagram MCP server.

Exposes the engine to any MCP-capable agent (Cursor, Claude Code/Desktop,
Codex, etc.). The third-party ``mcp`` SDK is imported only here.

Run:
    pip install "archdiagram[mcp]"
    python -m mcp_server.server         # stdio transport

Tools:
    validate_spec(spec_json)                       -> validation result
    render_diagram(spec_json, fmt, out_path, ...)  -> writes a diagram file
    search_catalog(query)                          -> matching services
    list_catalog(vendor?)                          -> all services
"""

from __future__ import annotations

import json
import os

from archdiagram.emit.drawio import NATIVE, PORTABLE, emit_drawio
from archdiagram.emit.pdf import PdfDependencyError, emit_pdf
from archdiagram.emit.vsdx import emit_vsdx
from archdiagram.registry.catalog import get_catalog
from archdiagram.spec.validate import SpecError, SpecValidationError, load_spec

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "The MCP SDK is not installed. Install it with:\n    pip install \"archdiagram[mcp]\""
    ) from exc

mcp = FastMCP("archdiagram")


@mcp.tool()
def validate_spec(spec_json: str) -> dict:
    """Validate an architecture spec (JSON string). Returns ok + errors/summary."""

    try:
        diagram = load_spec(spec_json)
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
        },
    }


@mcp.tool()
def render_diagram(
    spec_json: str,
    fmt: str,
    out_path: str,
    drawio_mode: str = "portable",
    icon_cache: str | None = None,
) -> dict:
    """Render a spec to a diagram file.

    Args:
        spec_json: the architecture spec as a JSON string.
        fmt: one of "pdf", "drawio", "vsdx".
        out_path: absolute or relative path to write.
        drawio_mode: "portable" (embedded icons, best for Lucid) or "native".
        icon_cache: optional icon cache directory override.
    """

    try:
        diagram = load_spec(spec_json)
    except SpecError as exc:
        return {"ok": False, "errors": getattr(exc, "errors", [str(exc)])}

    fmt = fmt.lower()
    warnings: list[str] = []
    try:
        if fmt == "pdf":
            warnings = emit_pdf(diagram, out_path, icon_cache=icon_cache)
        elif fmt == "drawio":
            mode = PORTABLE if drawio_mode == "portable" else NATIVE
            xml = emit_drawio(diagram, mode=mode, icon_cache=icon_cache)
            os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as fh:
                fh.write(xml)
        elif fmt == "vsdx":
            warnings = emit_vsdx(diagram, out_path, icon_cache=icon_cache)
        else:
            return {"ok": False, "errors": [f"unknown format '{fmt}'; use pdf|drawio|vsdx"]}
    except PdfDependencyError as exc:
        return {"ok": False, "errors": [str(exc)]}

    return {"ok": True, "path": os.path.abspath(out_path), "warnings": warnings}


@mcp.tool()
def search_catalog(query: str) -> dict:
    """Search the vendor service catalog by service id or label."""

    results = get_catalog().search(query)
    return {"results": [{"service": e.service, "label": e.label} for e in results]}


@mcp.tool()
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


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
