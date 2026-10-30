---
name: data-flow
description: Use for stores, feeds, transforms, documents, and lineage between data sources and consumers.
---

# Data flow

Use this skill for where data comes from, how it changes, and where it lands. Use a cylinder for persistent stores, a process shape for transforms, an IO shape for a feed, and a document shape for a produced artifact.

## Spec rules

- Use `shape: "data_store"`, `process`, `io`, `document`, or `decision` according to each node's role.
- Each lineage edge uses `source`, `target`, and `kind: "data"`; label it with the dataset or contract if useful.
- `direction: "LR"` is the normal default. Use `tier` to keep stages in order. IDs must be unique strings.
- Service icons may coexist with shapes when a concrete cloud service matters.

```json
{"title":"Investment lineage","direction":"LR","nodes":[{"id":"feed","shape":"io","label":"Trade feed"},{"id":"clean","shape":"process","label":"Normalize"},{"id":"store","shape":"data_store","label":"Warehouse"},{"id":"report","shape":"document","label":"Risk report"}],"edges":[{"source":"feed","target":"clean","kind":"data","label":"trades"},{"source":"clean","target":"store","kind":"data","label":"curated"},{"source":"store","target":"report","kind":"data","label":"positions"}]}
```

## Render and inspect

On first use run `python -m tools.bootstrap`. Run `python -m archdiagram.cli validate spec.json`, then `python -m archdiagram.cli render spec.json -f svg -o out/lineage.svg`. Other formats are `drawio`, `html`, `pdf`, `pptx`, and `vsdx`; PDF needs `python -m tools.bootstrap --pdf`. Check direction, dataset labels, and store boundaries, then revise and render again. Via MCP, use `get_diagram_template("data_flow")`, `validate_spec`, and `generate_diagram`.
