---
name: decision-flow
description: Use for approval or eligibility logic with labelled approve, reject, and escalate branches ending in distinct outcomes.
---

# Decision flow

Use this skill when the diagram explains a choice and its outcomes. Give each decision a diamond. Label every outgoing branch and end each outcome at its own terminator. Mark exception paths dashed.

## Spec rules

- Use `shape: "decision"` for each question and `shape: "end"` for each outcome.
- Every branch has `source`, `target`, and a useful `label`, such as `Yes`, `No`, `Approve`, `Reject`, or `Escalate`.
- Set `dashed: true` for exception and escalation paths. Set `color` to a six digit RGB hex string when a branch needs emphasis.
- `direction: "TB"` suits most decision trees. Give all node IDs unique strings.

```json
{"title":"KYC decision","direction":"TB","nodes":[{"id":"start","shape":"start"},{"id":"review","shape":"decision","label":"Identity verified?"},{"id":"approve","shape":"end","label":"Approve"},{"id":"reject","shape":"end","label":"Reject"},{"id":"escalate","shape":"end","label":"Escalate"}],"edges":[{"source":"start","target":"review"},{"source":"review","target":"approve","label":"Yes"},{"source":"review","target":"reject","label":"No"},{"source":"review","target":"escalate","label":"Exception","dashed":true}]}
```

## Render and inspect

On first use run `python -m tools.bootstrap`. Run `python -m archdiagram.cli validate spec.json`, then `python -m archdiagram.cli render spec.json -f drawio -o out/decision.drawio`. Other formats are `svg`, `html`, `pdf`, `pptx`, and `vsdx`; PDF needs `python -m tools.bootstrap --pdf`. Inspect branch labels and confirm every result has its own end node. Revise and render again. Via MCP, use `get_diagram_template("decision_flow")`, `validate_spec`, and `generate_diagram`.
