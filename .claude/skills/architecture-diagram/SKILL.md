---
name: architecture-diagram
description: Use for cloud system topology and service relationships where Azure, AWS, GCP, or Kubernetes vendor icons matter.
---

# Architecture diagram

Use this skill for systems and service topology. Choose a service from the catalog for each icon node. Use groups for platform boundaries and edges for dependencies or data transfer. Use `process-flow` for operational sequences.

## Spec rules

- Each node has a unique string `id` and exactly one `service` or `shape`.
- A service may be a canonical ID such as `azure.app_service`, an alias, or an unambiguous name. Run `catalog search` and use `--strict` to reject unresolved services.
- `direction` is `LR`, `RL`, `TB`, or `BT`. `x` and `y` pin a node. `group` must name a defined group.
- Use `kind: "data"` on an edge for a data transfer. Give edges labels when the relationship needs explanation.

```json
{"title":"Azure web app","direction":"LR","nodes":[{"id":"web","service":"azure.app_service","label":"Web app"},{"id":"storage","service":"azure.storage_account","label":"Storage"}],"edges":[{"source":"web","target":"storage","kind":"data","label":"uploads"}]}
```

## Render and inspect

On first use run `python -m tools.bootstrap --icons`. Run `python -m archdiagram.cli catalog search "app service"`, then `python -m archdiagram.cli validate spec.json --strict`. Render with `python -m archdiagram.cli render spec.json -f drawio -o out/architecture.drawio`; change `-f` to `svg`, `html`, `pdf`, `pptx`, or `vsdx` as needed. PDF needs `python -m tools.bootstrap --pdf`. Open the output, check labels, edges, and icons, revise the spec, and render again. Via MCP, use `list_icons`, `validate_spec`, then `generate_diagram`.
