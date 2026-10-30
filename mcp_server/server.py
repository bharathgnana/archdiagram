"""FastMCP registration for the SDK-free diagram tool functions."""

from __future__ import annotations

from .tools import (
    choose_template,
    get_diagram_template,
    list_catalog,
    render_diagram,
    search_catalog,
    validate_spec,
)

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "A compatible MCP SDK (1.x) is required. Install it with:\n"
        "    pip install \"archdiagram[mcp]\""
    ) from exc

mcp = FastMCP("archdiagram")

for tool in (
    validate_spec,
    render_diagram,
    search_catalog,
    list_catalog,
    choose_template,
    get_diagram_template,
):
    mcp.tool()(tool)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
