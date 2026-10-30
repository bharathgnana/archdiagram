---
name: process-flow
description: Use for operational step sequences, rework loops, handoffs, and optional swim lanes that show who owns each action.
---

# Process flow

Use this skill for ordered work steps. Give each action a process shape, each condition a decision shape, and each entry and exit a start or end shape. Add `io` for input or output and `document` for an artifact. Use `decision-flow` when the main purpose is separate approval outcomes.

## Spec rules

- Each node has a unique string `id` and a `shape`: `start`, `end`, `process`, `decision`, `io`, or `document`.
- An edge uses `source` and `target`; loop backs may point to an earlier node. Label decision exits.
- Optional `lanes` is an ordered array of `{id,label}`. Set a node's `lane` to one of those IDs. `lane_orientation` is `horizontal` or `vertical`; nodes without a lane go to a trailing band.
- In lane mode, omit explicit `x` and `y`. Use `tier` when a step needs a particular flow rank.

```json
{"title":"Approval work","direction":"TB","nodes":[{"id":"start","shape":"start"},{"id":"draft","shape":"process"},{"id":"check","shape":"decision","label":"Complete?"},{"id":"end","shape":"end"}],"edges":[{"source":"start","target":"draft"},{"source":"draft","target":"check"},{"source":"check","target":"draft","label":"Revise"},{"source":"check","target":"end","label":"Submit"}]}
```

## Render and inspect

On first use run `python -m tools.bootstrap`. Run `python -m archdiagram.cli validate spec.json`, then `python -m archdiagram.cli render spec.json -f svg -o out/process.svg`. Use `drawio`, `html`, `pdf`, `pptx`, or `vsdx` for other outputs; PDF needs `python -m tools.bootstrap --pdf`. Open the result and inspect the loop, rank order, and lane headers. Revise and render again. Via MCP, use `get_diagram_template("process_flow")`, `validate_spec`, and `generate_diagram`.
