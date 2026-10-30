"""Starter specs and a deterministic template recommendation for agents."""

from __future__ import annotations

from copy import deepcopy

_TEMPLATES = {
    "cloud": {
        "description": "Vendor service architecture with groups and data connections",
        "spec": {
            "title": "Cloud architecture", "direction": "LR",
            "groups": [{"id": "platform", "label": "Platform", "vendor": "azure"}],
            "nodes": [
                {"id": "app", "service": "azure.app_service", "label": "App", "group": "platform"},
                {"id": "store", "service": "azure.storage_account", "label": "Storage", "group": "platform"},
            ],
            "edges": [{"source": "app", "target": "store", "kind": "data", "label": "data"}],
        },
    },
    "workflow": {
        "description": "Process flow with start, decision, data, and end steps",
        "spec": {
            "title": "Workflow", "direction": "LR",
            "nodes": [
                {"id": "start", "kind": "start", "label": "Start"},
                {"id": "work", "kind": "process", "label": "Perform task"},
                {"id": "check", "kind": "decision", "label": "Approved?"},
                {"id": "record", "kind": "data", "label": "Save result"},
                {"id": "end", "kind": "end", "label": "End"},
            ],
            "edges": [
                {"source": "start", "target": "work"},
                {"source": "work", "target": "check"},
                {"source": "check", "target": "record", "label": "Yes"},
                {"source": "record", "target": "end"},
            ],
        },
    },
    "decision": {
        "description": "Approval or decision tree with labelled outcomes",
        "spec": {
            "title": "Decision flow", "direction": "LR",
            "nodes": [
                {"id": "start", "kind": "start", "label": "Request received"},
                {"id": "review", "kind": "process", "label": "Review request"},
                {"id": "decide", "kind": "decision", "label": "Approved?"},
                {"id": "approve", "kind": "end", "label": "Approved"},
                {"id": "reject", "kind": "end", "label": "Rejected"},
            ],
            "edges": [
                {"source": "start", "target": "review"},
                {"source": "review", "target": "decide"},
                {"source": "decide", "target": "approve", "label": "Yes"},
                {"source": "decide", "target": "reject", "label": "No"},
            ],
        },
    },
    "dataflow": {
        "description": "Data pipeline or lineage with dashed data transfers",
        "spec": {
            "title": "Data flow", "direction": "LR",
            "nodes": [
                {"id": "source", "kind": "data", "label": "Source data"},
                {"id": "transform", "kind": "process", "label": "Transform"},
                {"id": "store", "kind": "data", "label": "Data store"},
                {"id": "consumer", "kind": "process", "label": "Consumer"},
            ],
            "edges": [
                {"source": "source", "target": "transform", "kind": "data"},
                {"source": "transform", "target": "store", "kind": "data"},
                {"source": "store", "target": "consumer", "kind": "data"},
            ],
        },
    },
    "swimlane": {
        "description": "Workflow split across owners or teams in swim lanes",
        "spec": {
            "title": "Team workflow", "direction": "LR",
            "lanes": [{"id": "requester", "label": "Requester"}, {"id": "reviewer", "label": "Reviewer"}],
            "nodes": [
                {"id": "submit", "kind": "process", "label": "Submit", "lane": "requester"},
                {"id": "review", "kind": "decision", "label": "Approve?", "lane": "reviewer"},
                {"id": "done", "kind": "end", "label": "Done", "lane": "requester"},
            ],
            "edges": [
                {"source": "submit", "target": "review"},
                {"source": "review", "target": "done", "label": "Yes"},
            ],
        },
    },
}


def list_templates() -> list[dict[str, str]]:
    return [{"name": name, "description": item["description"]} for name, item in _TEMPLATES.items()]


def get_template(name: str) -> dict:
    if name not in _TEMPLATES:
        raise ValueError(f"unknown template '{name}'; use {', '.join(_TEMPLATES)}")
    return deepcopy(_TEMPLATES[name]["spec"])


def suggest_template(description: str) -> str:
    words = description.lower()
    if any(term in words for term in ("swimlane", "swim lane", "owner", "handoff", "team")):
        return "swimlane"
    if any(term in words for term in ("data flow", "dataflow", "pipeline", "lineage", "etl")):
        return "dataflow"
    if any(term in words for term in ("decision", "approval", "approve", "reject")):
        return "decision"
    if any(term in words for term in ("workflow", "process", "flowchart")):
        return "workflow"
    return "cloud"
