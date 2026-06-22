---
name: architecture-diagrams
description: Turn a natural-language cloud architecture description into an editable diagram whose nodes are official vendor service icons (Azure, AWS, GCP, Kubernetes), exported as PDF, draw.io, or VSDX (Lucid-importable). Use when the user asks to draw, diagram, or visualize a cloud/system architecture, or to produce a .drawio/.vsdx/.pdf architecture diagram with real service icons.
---

# Architecture Diagrams (vendor-icon)

Translate an architecture description into a small JSON **spec**, then render it
with the `archdiagram` engine. Nodes become the real vendor service icons, not
labelled boxes.

## Workflow

```
- [ ] 1. Read the architecture (text, image, or existing diagram)
- [ ] 2. Map each component to a catalog service id (search the catalog)
- [ ] 3. Write the JSON spec (nodes, edges, groups)
- [ ] 4. Validate the spec
- [ ] 5. Render to the requested format(s)
```

## Setup (once)

```bash
git clone https://github.com/bharathgnana/archdiagram.git
cd archdiagram
python -m tools.download_icons          # fetch vendor icons into ./icons (not committed)
cd node && npm install && cd ..         # optional: enables PDF + crisp raster icons
```

The Python core is stdlib-only. Node is only needed for `.pdf` and for
rasterising SVG icons into `.vsdx`/`.pdf`.

## Step 2: find service ids

```bash
python -m archdiagram.cli catalog search "kubernetes"
python -m archdiagram.cli catalog list --vendor azure
```

A service id is `"<vendor>.<service_key>"`, e.g. `azure.aks`, `aws.s3`,
`gcp.cloud_run`. Unknown ids still render as a clean vendor-accented fallback
box, so prefer the closest real id and proceed.

## Step 3: spec format

```json
{
  "title": "Web platform on Azure",
  "direction": "LR",
  "groups": [
    { "id": "app", "label": "Application tier", "vendor": "azure" }
  ],
  "nodes": [
    { "id": "web", "service": "azure.app_service", "label": "Web App", "group": "app" },
    { "id": "aks", "service": "azure.aks",         "label": "AKS",     "group": "app" },
    { "id": "kv",  "service": "azure.key_vault",   "label": "Key Vault" }
  ],
  "edges": [
    { "source": "web", "target": "aks", "label": "api" },
    { "source": "aks", "target": "kv",  "label": "secrets" }
  ]
}
```

Rules:
- `direction`: `LR`, `RL`, `TB`, or `BT` (default `LR`).
- `nodes[].service`: required, `"<vendor>.<service_key>"`.
- `nodes[].group`: optional; must match a `groups[].id`.
- `nodes[].x` / `nodes[].y`: optional explicit coordinates (override auto-layout).
- `edges[].source` / `target`: must reference node ids. `directed` defaults true.
- Layout is automatic and deterministic; only set coordinates to override.

## Step 4-5: validate and render

```bash
python -m archdiagram.cli validate spec.json

python -m archdiagram.cli render spec.json -f pdf    -o out/arch.pdf
python -m archdiagram.cli render spec.json -f drawio -o out/arch.drawio --drawio-mode portable
python -m archdiagram.cli render spec.json -f vsdx   -o out/arch.vsdx
```

## Choosing a format

| Want | Use |
|------|-----|
| Reliable visual fidelity in Lucidchart (icons always render) | `pdf` |
| Editable in draw.io / diagrams.net | `drawio --drawio-mode native` |
| Editable after Lucid/Visio import (embedded icons) | `drawio --drawio-mode portable` or `vsdx` |

Lucid does not map draw.io named stencils, so use `portable` (embedded icons)
or `pdf` when the target is Lucidchart.

## Using via MCP instead of the CLI

If the engine is running as an MCP server (`python -m mcp_server.server`), call
the tools directly: `validate_spec(spec_json)`, `render_diagram(spec_json, fmt,
out_path, drawio_mode)`, `search_catalog(query)`, `list_catalog(vendor)`.

## Additional resources

- Spec schema and engine details: [../README.md](../README.md)
- Extend the catalog: add a service entry under
  `archdiagram/registry/catalog_data/<vendor>.json` and an icon source in
  `tools/icon_sources.json`.
