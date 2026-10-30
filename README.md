# archdiagram

[![CI](https://github.com/bharathgnana/archdiagram/actions/workflows/ci.yml/badge.svg)](https://github.com/bharathgnana/archdiagram/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

Turn a JSON spec into an **editable diagram** for four families: architecture,
process flow, decision flow, and data flow. Architecture nodes can use Azure,
AWS, GCP, and Kubernetes vendor icons. The other families use editable shapes,
loops, labelled branches, lineage edges, and optional swim lanes.

A coding agent (Cursor, Claude Code, Codex) translates a natural-language architecture into a small
JSON **spec**; the deterministic Python core renders that spec to:

| Format    | Best for | Vendor icons | Editable after import |
|-----------|----------|--------------|------------------------|
| `.pdf`    | **Lucidchart visual fidelity**, handoff, printing | baked in, always render | no (Lucid embeds as image) |
| `.drawio` | editing in draw.io / diagrams.net | native stencils or embedded | yes |
| `.vsdx`   | Visio / Lucid editable import | embedded PNG glyphs | yes |
| `.svg`    | portable vector image | embedded icons | SVG shapes are editable in vector tools |
| `.html`   | standalone browser view | embedded icons | via embedded SVG |
| `.pptx`   | PowerPoint handoff | embedded PNG glyphs | shapes and text are editable |

`drawio` has `native`, `portable`, and `compressed` modes. Compressed mode uses
draw.io's raw-deflate model encoding and portable embedded icons. For Lucidchart,
prefer PDF when icon fidelity matters; compressed draw.io imports can lose image
shapes. PDF needs the optional Node helpers. Shape-only PPTX and VSDX need no Node.

> Lucid note: Lucid does not map draw.io's named vendor stencils or its `img/lib/...` icon
> references, so those render blank on import. `.drawio`/`.vsdx` therefore **embed** icons
> (`--drawio-mode portable`) to maximise render success, and the **PDF** is the reliable
> icons-always-render deliverable for Lucid.

## Gallery

Rendered from the specs in [`examples/`](examples/) - same engine, real vendor icons.

| Azure | AWS | GCP |
|-------|-----|-----|
| ![Azure AI Foundry](docs/azure_foundry.png) | ![AWS](docs/aws_kelvin.png) | ![GCP](docs/gcp_agentic.png) |

## Design constraints

- **Core engine = pure Python stdlib.** No graphviz, no browser, no third-party Python deps.
  Spec validation is hand-rolled (no `jsonschema`). `.vsdx` is written with `zipfile` + `xml`.
- **Python 3.11+.** Tests use stdlib `unittest`.
- **Optional, isolated, non-stdlib deps:**
  - `mcp` SDK - only inside `mcp_server/`.
  - Node + `@resvg/resvg-js` - rasterise SVG icons to PNG for `.vsdx`, `.pptx`, and `.pdf`.
    If absent, `.vsdx` and `.pptx` use labelled fallback shapes; `.pdf` errors with an install hint.
  - Node + `pdfkit` + `svg-to-pdfkit` - SVG -> PDF for `.pdf`.
- **Vendor icons are not committed.** Fetch them with `tools/download_icons.py`.

## Quick start

```bash
# 1. check the core; add --icons to fetch vendor icons
python -m tools.bootstrap
python -m tools.bootstrap --icons

# 2. (optional) install the Node rasterise/pdf bridge
python -m tools.bootstrap --pdf

# 3. render a spec
python -m archdiagram.cli render examples/sample_spec.json --format pdf    -o out/arch.pdf
python -m archdiagram.cli render examples/sample_spec.json --format drawio -o out/arch.drawio --drawio-mode portable
python -m archdiagram.cli render examples/sample_spec.json --format vsdx   -o out/arch.vsdx
python -m archdiagram.cli render examples/workflow_swimlane.json --format svg  -o out/workflow.svg
python -m archdiagram.cli render examples/workflow_swimlane.json --format html -o out/workflow.html
python -m archdiagram.cli render examples/workflow_swimlane.json --format pptx -o out/workflow.pptx
```

## Spec format

```json
{
  "title": "Web platform",
  "direction": "LR",
  "groups": [{ "id": "app", "label": "Application tier", "vendor": "azure" }],
  "nodes": [
    { "id": "web", "service": "azure.app_service", "label": "Web App", "group": "app" },
    { "id": "aks", "service": "azure.aks",         "label": "AKS",     "group": "app" },
    { "id": "kv",  "service": "azure.key_vault",   "label": "Key Vault" }
  ],
  "edges": [
    { "source": "web", "target": "aks", "label": "http" },
    { "source": "aks", "target": "kv" }
  ]
}
```

`service` accepts a canonical ID, alias, providerless name, or a confident fuzzy
match. Unknown names render a fallback box with suggestions. Add `--strict` to
`validate` or `render` to reject unresolved names.

### Four families

| Family | Primary nodes | Typical direction | Example |
|---|---|---|---|
| Architecture | `service` vendor icons | `LR` | [`azure_architecture.json`](examples/azure_architecture.json) |
| Process flow | `start`, `end`, `process`, `decision`, `io`, `document` | `TB` | [`approval_process.json`](examples/approval_process.json), [`trade_settlement_swimlane.json`](examples/trade_settlement_swimlane.json) |
| Decision flow | decision diamonds and separate end nodes | `TB` | [`kyc_decision_tree.json`](examples/kyc_decision_tree.json) |
| Data flow | `data_store`, `io`, `process`, `document` | `LR` | [`investment_data_lineage.json`](examples/investment_data_lineage.json) |

### Spec reference

- Top level: `title`, `direction` (`LR`, `RL`, `TB`, `BT`), `nodes`, `edges`,
  optional `groups`, `lanes`, and `lane_orientation` (`horizontal` or `vertical`).
- Node: unique string `id`, exactly one of `service` or `shape`, optional `label`,
  `group`, `lane`, nonnegative integer `tier`, and explicit `x`/`y`. The shape enum
  is `start`, `end`, `process`, `decision`, `io`, `document`, `data_store`.
- Edge: `source` and `target` node IDs, optional `label`, `kind` (`flow` or
  `data`), `directed`, `dashed`, and six digit RGB `color` with optional `#`.
- Group: `id`, `label`, and optional `vendor`; a node's `group` names it.
- Lane: ordered `{id,label}` objects; a node's `lane` names one. Nodes without
  a lane appear in a trailing unassigned band. Explicit `x`/`y` are rejected in
  modern lane mode so a node cannot leave its band. Groups nested in lanes are
  outside the supported layout.

For older specs, `kind` remains accepted as a shape alias. Specs without new
shape or lane fields use the legacy layout and keep the checked in golden bytes.

### Index a larger local icon pack

The bundled catalog covers common services. To search and render additional SVGs from a
vendor icon pack you already have, place them under `icons/<vendor>/`, with optional
category folders, then build a manifest:

```bash
python -m tools.build_catalog --icons icons --out catalog/manifest.json
python -m archdiagram.cli catalog search "AI Studio"
```

The manifest records service IDs, categories, aliases, dimensions, and paths relative to
`icons/`. The SVG files remain local. Bundled IDs take precedence when both catalogs
contain the same service. Generated IDs use lowercase words joined by underscores,
such as `azure.ai_studio`; duplicate names gain `_2`, `_3`, and so on. The icon
directory used for rendering must be the same one used to build the manifest. For
nondefault locations, set `ARCHDIAGRAM_CATALOG` to the manifest path and pass
`--icons <directory>` when rendering (or set `ARCHDIAGRAM_ICONS`). Generated SVGs
are embedded in draw.io when no native stencil is available.

For older workflow specs, `nodes[].kind` still selects `process`, `decision`,
`data`, `start`, or `end`. New specs should use `shape`. `edges[].kind: "data"`
draws a dashed data transfer.

```bash
python -m archdiagram.cli templates list
python -m archdiagram.cli templates suggest "approval between two teams"
python -m archdiagram.cli templates show swimlane
python -m archdiagram.cli templates show dataflow
```

## Layout

Node positions use a deterministic layered layout. New shape specs use an
iterative cycle tolerant ranker: loop backs stay visible while downstream steps
remain on later ranks. Swim lanes reserve ordered bands. Explicit `tier`
overrides rank; `x`/`y` override placement outside modern lane mode.

## Use from an AI agent

This repo is built to be driven by agentic AI tools (Cursor, Claude Code/Desktop,
Codex, ...) straight from Git. Pick either path:

### 1. As a skill

Choose the relevant family skill under [`skill/`](skill/). The old
[`skill/SKILL.md`](skill/SKILL.md) is a compatibility pointer. Each skill has
spec rules, a worked example, and a render and inspect loop. See also
[`AGENTS.md`](AGENTS.md).

```bash
git clone https://github.com/bharathgnana/archdiagram.git
cd archdiagram && python -m tools.bootstrap
```

### 2. As an MCP server

```bash
pip install "archdiagram[mcp]"
python -m mcp_server.server          # stdio transport
```

Exposes `list_templates`, `list_icons`, `resolve_service`, `get_catalog_info`,
`validate_spec`, and `generate_diagram`, plus the earlier tool names as aliases.
The MCP tools use the same engine as the CLI. Details are in
[`docs/mcp_server.md`](docs/mcp_server.md). A sample client config is in [`examples/mcp.json`](examples/mcp.json)
(drop it into `.cursor/mcp.json` or `claude_desktop_config.json`).

## Repository layout

```
archdiagram/        pure-Python core (spec, layout, catalog, emitters)
mcp_server/         optional MCP server (only place the `mcp` SDK is used)
node/               optional Node bridge (resvg rasterise + svg->pdf)
tools/              icon downloader + icon source map
skill/              SKILL.md for agentic AI tools
examples/           sample specs + mcp.json
tests/              stdlib unittest suite
```

## Tests

```bash
python -m unittest discover -s tests
```

## Contributing

Anyone can clone, install (`pip install -e .`), and use it. To propose changes,
fork and open a pull request - see [`CONTRIBUTING.md`](CONTRIBUTING.md) for the
dev setup and workflow.
