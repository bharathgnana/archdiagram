# MCP server

Install with `python -m pip install -e ".[mcp]"` and run `python -m
mcp_server.server` over stdio. MCP SDK 1.x is optional; `mcp_server/tools.py`
can be imported and tested without it. A client configuration is in
[`../examples/mcp.json`](../examples/mcp.json).

## Tools

| Tool | Purpose |
|---|---|
| `list_templates` | Four family starters plus compatibility templates |
| `list_icons(query, provider, limit)` | Filter catalog icons |
| `resolve_service(service)` | Match ID, alias, providerless name, or fuzzy name |
| `get_catalog_info` | Provider and icon counts |
| `validate_spec(spec_json, strict)` | Parse a spec and return all errors |
| `generate_diagram(spec, format, out_path, inline, template, strict)` | Render and report path, format, MIME type, bytes, counts, size, and warnings |

`render_diagram`, `search_catalog`, `list_catalog`, `choose_template`, and
`get_diagram_template` remain available as compatibility tools. `inline` returns
content only for text formats (`drawio`, `svg`, `html`). A template sets direction
only when the input spec omits it. Strict mode rejects unknown services; default
mode emits fallback boxes and suggestions.

The resources `archdiag://schema` and `archdiag://catalog` give clients a compact
schema and catalog summary. Prompts `describe_diagram` and
`describe_architecture` guide spec creation. Set `ARCHDIAG_MANIFEST` to a
generated icon manifest and `ARCHDIAG_OUTPUT_DIR` for default output paths.

## Cloud Run

Hosted rendering returns text content or base64-encoded binary content in the
tool response; local paths and local icon caches are not accepted remotely.

The container uses stdio locally and automatically switches to Streamable HTTP
at `/mcp` when Cloud Run sets `PORT`. The GitHub OIDC deployment setup and
one-time Google Cloud bootstrap are documented in
[`mcp_deployment.md`](mcp_deployment.md).
