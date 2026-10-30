"""FastMCP registration for the SDK-free diagram tool functions."""

from __future__ import annotations

from .tools import (
    catalog_resource,
    choose_template,
    describe_architecture,
    describe_diagram,
    generate_diagram,
    get_catalog_info,
    get_diagram_template,
    list_catalog,
    list_icons,
    list_templates,
    render_diagram,
    resolve_service,
    schema_resource,
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
    list_templates,
    list_icons,
    resolve_service,
    get_catalog_info,
    generate_diagram,
):
    mcp.tool()(tool)

mcp.resource("archdiag://schema")(schema_resource)
mcp.resource("archdiag://catalog")(catalog_resource)
mcp.prompt()(describe_diagram)
mcp.prompt()(describe_architecture)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
