---
name: architecture-diagram-mcp
description: Design cloud and workflow diagrams with the ArchDiagram MCP, then export editable Draw.io, PowerPoint, Visio, SVG, HTML, or PDF files.
summary: Create editable, vendor-icon architecture and workflow diagrams through a remote MCP server.
version: 0.2.0
tags:
  - architecture
  - diagrams
  - cloud
  - drawio
  - powerpoint
keywords:
  - architecture diagram
  - cloud diagram
  - draw.io
  - visio
  - workflow
use_cases:
  - Create a cloud architecture diagram from a natural-language description
  - Export an editable workflow or swimlane diagram
docs_url: https://github.com/bharathgnana/architecturebuilder
---

# Architecture Diagram MCP

Use the ArchDiagram MCP for system topology, workflow, decision, data-flow, and swimlane diagrams. It renders editable Draw.io, PowerPoint, and Visio files as well as SVG, HTML, and PDF exports.

## Before starting

This skill requires access to the remote **ArchDiagram MCP** server. The buyer receives a personal API key from the vendor after purchase. The buyer must add the server URL and their key as a Bearer token in their MCP-enabled agent's own settings before calling its tools. Do not ask for, store, display, or transmit the key in chat.

The hosted service includes **1,000 MCP HTTP requests per calendar month**. If the quota is exhausted, tell the user to contact the vendor for a higher-limit plan; do not retry repeatedly.

## Workflow

1. Ask for the diagram goal, target cloud/provider, services, relationships, ownership boundaries, and desired export format.
2. Use `list_templates` to select a fitting diagram family, then `list_icons` or `resolve_service` for official Azure, AWS, GCP, Kubernetes, or generic shape choices.
3. Create a JSON spec with unique node IDs, exactly one `service` or `shape` per node, explicit edges, and groups for ownership boundaries.
4. Call `validate_spec` with `strict: true`; resolve reported service names before rendering.
5. Call `generate_diagram` using the requested format. For editable deliverables, prefer `drawio`, `pptx`, or `vsdx`.
6. Inspect labels, flow direction, boundaries, and edge routing. Revise the spec and render again when needed.

## Quality rules

- Use vendor services only when they are accurate; use generic shapes for products or concepts without an official catalog entry.
- Label relationships when the protocol, direction, or data type matters.
- Keep diagrams legible: group platform boundaries and avoid crossing edges where possible.
- For process diagrams, use start/end, process, decision, and data shapes rather than cloud-service icons.
