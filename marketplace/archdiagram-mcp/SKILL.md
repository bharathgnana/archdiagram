---
name: architecture-diagram-mcp
description: Design cloud and workflow diagrams through the hosted ArchDiagram MCP, then export editable Draw.io, PowerPoint, Visio, SVG, or HTML files.
summary: Create editable, vendor-icon architecture and workflow diagrams through a remote MCP server.
version: 0.4.0
pricing_type: free
price: 0
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
docs_url: https://archdiagram-mcp-moryq375tq-el.a.run.app/
---

# Architecture Diagram MCP

Use the ArchDiagram MCP for system topology, workflow, decision, data-flow, and swimlane diagrams. It renders editable Draw.io, PowerPoint, and Visio files as well as SVG and HTML exports. Hosted PDF output is not currently available.

## Before starting

**This Agensi connector is free. The separately operated hosted service requires a paid subscription through Razorpay; downloading or loading this skill does not include hosted access. Agensi does not host the server or collect its subscription payments.**

Open https://archdiagram-mcp-moryq375tq-el.a.run.app/ to check service availability and the current monthly price. Sign in with your verified email, complete Razorpay checkout if payments are available, return to the studio and refresh payment status, then create a personal API key after payment is confirmed. If payments are not yet available, stop and tell the user; do not imply that a subscription can already be purchased.

This skill requires access to the remote **ArchDiagram MCP** server at `https://archdiagram-mcp-moryq375tq-el.a.run.app/mcp`. The user must add the server URL and their key as a Bearer token in their MCP-enabled agent's own settings before calling its tools. Do not ask for, store, display, or transmit the key in chat.

The standard hosted plan includes **1,000 MCP HTTP requests or browser renders per UTC calendar month**. Each HTTP request counts, including protocol setup and tool discovery; this is not a promise of 1,000 rendered diagrams. Access requires a captured subscription payment and ends at the paid-through date. Cancel renewal in the studio; paid access continues through the paid period. Refunds or payment disputes can suspend access. If the quota is exhausted, tell the user to contact the vendor for a higher-limit plan; do not retry repeatedly.

## Workflow

1. Ask for the diagram goal, target cloud/provider, services, relationships, ownership boundaries, and desired export format.
2. Use `list_templates` to select a fitting diagram family, then `list_icons` or `resolve_service` for Azure, AWS, GCP, Kubernetes, or generic shape choices. Catalog entries are available, but the current hosted container lacks downloaded vendor icons, so exports may use fallback shapes.
3. Create a JSON spec with unique node IDs, exactly one `service` or `shape` per node, explicit edges, and groups for ownership boundaries.
4. Call `validate_spec` with `strict: true`; resolve reported service names before rendering.
5. Call `generate_diagram` using the requested format. For editable deliverables, prefer `drawio`, `pptx`, or `vsdx`.
6. Inspect labels, flow direction, boundaries, and edge routing. Revise the spec and render again when needed.

## Quality rules

- Use vendor services only when they are accurate; use generic shapes for products or concepts without an official catalog entry.
- Label relationships when the protocol, direction, or data type matters.
- Keep diagrams legible: group platform boundaries and avoid crossing edges where possible.
- For process diagrams, use start/end, process, decision, and data shapes rather than cloud-service icons.

## Client setup

Use `mcp-config.example.json` as a Streamable HTTP configuration template. Replace `${ARCHDIAGRAM_API_KEY}` through your agent's supported environment or secret mechanism; do not paste a real key into shared files. Field names and environment-variable expansion vary by client. The required values are the HTTPS `/mcp` URL and `Authorization: Bearer <personal key>` header. If the agent cannot attach authorization headers, use a compatible MCP client.

See `SETUP.md` for onboarding and troubleshooting. This ZIP contains the connector instructions and configuration template, not the server implementation.
