# AGENTS.md

Guidance for AI coding agents (Cursor, Claude Code/Desktop, Codex, etc.) using
this repository.

## What this repo does

`archdiagram` converts a JSON architecture **spec** into an editable diagram
whose nodes are official vendor service icons (Azure, AWS, GCP, Kubernetes),
exported as `.pdf`, `.drawio`, or `.vsdx` (all Lucidchart-importable).

Your job as an agent: translate the user's natural-language architecture into
the JSON spec, then render it.

## Two ways to use it

1. **Skill** - read [skill/SKILL.md](skill/SKILL.md) and follow it. It contains
   the spec schema, catalog lookup, and render commands.
2. **MCP server** - run `python -m mcp_server.server` and call the tools
   `validate_spec`, `render_diagram`, `search_catalog`, `list_catalog`. A sample
   client config is in [examples/mcp.json](examples/mcp.json).

## Quick start

```bash
python -m tools.download_icons            # fetch vendor icons into ./icons
cd node && npm install && cd ..           # optional: PDF + crisp raster icons
python -m archdiagram.cli catalog search "kubernetes"
python -m archdiagram.cli render spec.json -f pdf -o out/arch.pdf
```

## Conventions

- Core engine is **stdlib-only** (no third-party Python deps). Keep it that way.
- The `mcp` SDK is allowed **only** under `mcp_server/`.
- Node (`@resvg/resvg-js`, `pdfkit`, `svg-to-pdfkit`) is optional and confined to
  `node/` + `archdiagram/rasterize/`.
- Vendor icons are **not committed**; they are fetched by `tools/download_icons.py`.
- Tests use stdlib `unittest`: `python -m unittest discover -s tests`.
