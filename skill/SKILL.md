---
name: architecture-diagrams
description: Turn a natural-language cloud architecture or workflow description into an editable diagram, using vendor service icons and optional process steps, decisions, data flows, and swim lanes. Export PDF, draw.io, VSDX, SVG, HTML, or editable PowerPoint.
---

# Architecture Diagrams (vendor-icon)

Translate an architecture or workflow description into a small JSON **spec**, then
render it with the `archdiagram` engine. Service nodes use vendor icons; workflow
steps use editable shapes.

## Workflow

```
- [ ] 1. Read the architecture (text, image, or existing diagram)
- [ ] 2. Choose a starter template, then map service components to catalog ids
- [ ] 3. Write the JSON spec (nodes, edges, groups, optional lanes)
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

Choose `cloud` for service topology, `workflow` for general process steps,
`decision` for approval paths, `dataflow` for pipelines and lineage, or
`swimlane` when ownership and handoffs matter. A diagram can mix service and
workflow nodes. Search the catalog for every service node; avoid inventing an id
when a close match exists.

```bash
python -m archdiagram.cli catalog search "kubernetes"
python -m archdiagram.cli catalog list --vendor azure

# Optional: index a local vendor icon pack for more catalog results
python -m tools.build_catalog --icons icons --out catalog/manifest.json
python -m archdiagram.cli templates suggest "approval between teams"
python -m archdiagram.cli templates show swimlane
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
- `nodes[].service`: required for service nodes, `"<vendor>.<service_key>"`.
- For non-service nodes, set `kind` to `process`, `decision`, `data`, `start`, or
  `end` and omit `service`. `kind` defaults to `service`.
- `nodes[].group`: optional; must match a `groups[].id`.
- `lanes`: optional array of `{id, label}`; when present every node needs a
  `lane` referencing a lane id.
- `nodes[].x` / `nodes[].y`: optional explicit coordinates (override auto-layout).
- `edges[].source` / `target`: must reference node ids. `directed` defaults true.
- `edges[].kind`: `flow` (default) or `data` (dashed).
- Layout is automatic and deterministic; only set coordinates to override.

For a complete workflow example with an approval loop and lanes, see
[`../examples/workflow_swimlane.json`](../examples/workflow_swimlane.json).

Before rendering, check that every decision has labelled outgoing paths, every
lane node has an owner, and data transfers use a `data` edge. Validate the spec
and fix all reported paths before generating files. If icons are missing, the
engine returns warnings and draws fallback shapes; tell the user which service
icons were missing.

## Step 4-5: validate and render

```bash
python -m archdiagram.cli validate spec.json

python -m archdiagram.cli render spec.json -f pdf    -o out/arch.pdf
python -m archdiagram.cli render spec.json -f drawio -o out/arch.drawio --drawio-mode portable
python -m archdiagram.cli render spec.json -f vsdx   -o out/arch.vsdx
python -m archdiagram.cli render spec.json -f svg    -o out/arch.svg
python -m archdiagram.cli render spec.json -f html   -o out/arch.html
python -m archdiagram.cli render spec.json -f pptx   -o out/arch.pptx
```

## Choosing a format

| Want | Use |
|------|-----|
| Reliable visual fidelity in Lucidchart (icons always render) | `pdf` |
| Editable in draw.io / diagrams.net | `drawio --drawio-mode native` |
| Editable after Lucid/Visio import (embedded icons) | `drawio --drawio-mode portable` or `vsdx` |
| Browser or vector editor | `html` or `svg` |
| Editable presentation shapes and text | `pptx` |

Lucid does not map draw.io named stencils, so use `portable` (embedded icons)
or `pdf` when the target is Lucidchart.

## Using via MCP instead of the CLI

If the engine is running as an MCP server (`python -m mcp_server.server`), call
the tools directly: `choose_template(description)`, `get_diagram_template(name)`,
`validate_spec(spec_json)`, `render_diagram(spec_json, fmt, out_path, drawio_mode)`,
`search_catalog(query)`, `list_catalog(vendor)`.

## Additional resources

- Spec schema and engine details: [../README.md](../README.md)
- Extend the catalog: add a service entry under
  `archdiagram/registry/catalog_data/<vendor>.json` and an icon source in
  `tools/icon_sources.json`.
