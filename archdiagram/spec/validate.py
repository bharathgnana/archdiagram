"""Hand-rolled spec validation (no ``jsonschema``).

The validator walks a raw ``dict`` (typically ``json.load`` output), collects
*all* problems with precise paths (e.g. ``nodes[2].service``) and either raises
:class:`SpecValidationError` or returns a fully-built :class:`Diagram`.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from .model import VALID_DIRECTIONS, VALID_EDGE_KINDS, VALID_NODE_KINDS, Diagram, Edge, Group, Lane, Node
from ..shapes import SHAPES

_RGB_COLOR = re.compile(r"#?[0-9a-fA-F]{6}\Z")


class SpecError(Exception):
    """Base class for spec problems."""


class SpecValidationError(SpecError):
    """Raised when a spec fails validation. Carries every collected message."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        joined = "\n".join(f"  - {e}" for e in errors)
        super().__init__(f"Spec validation failed with {len(errors)} error(s):\n{joined}")


class _Collector:
    """Accumulates error messages keyed by a dotted path."""

    def __init__(self) -> None:
        self.errors: list[str] = []

    def add(self, path: str, message: str) -> None:
        self.errors.append(f"{path}: {message}")

    def require_type(self, path: str, value: Any, types: tuple[type, ...], label: str) -> bool:
        if not isinstance(value, types):
            self.add(path, f"expected {label}, got {type(value).__name__}")
            return False
        # bool is a subclass of int; reject it where a number/string is wanted.
        if bool not in types and isinstance(value, bool):
            self.add(path, f"expected {label}, got bool")
            return False
        return True


def _validate_node(raw: Any, path: str, col: _Collector) -> Node | None:
    if not isinstance(raw, dict):
        col.add(path, f"expected object, got {type(raw).__name__}")
        return None

    ok = True
    node_id = raw.get("id")
    if not col.require_type(f"{path}.id", node_id, (str,), "string"):
        ok = False
    elif not node_id.strip():
        col.add(f"{path}.id", "must not be empty")
        ok = False

    service = raw.get("service")
    has_shape = "shape" in raw
    shape = raw.get("shape")
    if has_shape and (not isinstance(shape, str) or shape not in SHAPES):
        col.add(f"{path}.shape", f"must be one of {', '.join(SHAPES)}")
        ok = False
    kind = raw.get("kind", "service")
    if has_shape and isinstance(shape, str) and shape in SHAPES:
        if "kind" in raw and kind != shape:
            col.add(f"{path}.kind", "must match shape when both are provided")
            ok = False
        kind = shape
    if not isinstance(kind, str) or kind not in VALID_NODE_KINDS:
        col.add(f"{path}.kind", f"must be one of {', '.join(VALID_NODE_KINDS)}")
        ok = False
    if has_shape and service is not None:
        col.add(f"{path}.service", "a node may have a service or a shape, not both")
        ok = False
    if kind == "service":
        if not col.require_type(f"{path}.service", service, (str,), "string"):
            ok = False
        elif "." not in service or not all(service.split(".", 1)):
            col.add(f"{path}.service", "must be '<vendor>.<service_key>' (e.g. 'azure.app_service')")
            ok = False
    elif service is not None:
        col.add(f"{path}.service", "only service nodes may specify a service")
        ok = False

    label = raw.get("label")
    if label is not None and not col.require_type(f"{path}.label", label, (str,), "string"):
        ok = False

    group = raw.get("group")
    if group is not None and not col.require_type(f"{path}.group", group, (str,), "string"):
        ok = False

    lane = raw.get("lane")
    if lane is not None and not col.require_type(f"{path}.lane", lane, (str,), "string"):
        ok = False

    x = raw.get("x")
    if x is not None and not col.require_type(f"{path}.x", x, (int, float), "number"):
        ok = False
    y = raw.get("y")
    if y is not None and not col.require_type(f"{path}.y", y, (int, float), "number"):
        ok = False

    tier = raw.get("tier")
    if tier is not None and (not isinstance(tier, int) or isinstance(tier, bool) or tier < 0):
        col.add(f"{path}.tier", "expected a non-negative integer")
        ok = False

    _warn_unknown_keys(raw, {"id", "service", "shape", "label", "group", "kind", "lane", "tier", "x", "y"}, path, col)

    if not ok:
        return None
    return Node(
        id=node_id,
        service=service,
        label=label,
        group=group,
        kind=kind,
        lane=lane,
        x=float(x) if x is not None else None,
        y=float(y) if y is not None else None,
        shape=shape if has_shape else (kind if kind in ("io", "document", "data_store") else None),
        tier=tier,
    )


def _validate_edge(raw: Any, path: str, col: _Collector) -> Edge | None:
    if not isinstance(raw, dict):
        col.add(path, f"expected object, got {type(raw).__name__}")
        return None

    ok = True
    source = raw.get("source")
    if not col.require_type(f"{path}.source", source, (str,), "string"):
        ok = False
    target = raw.get("target")
    if not col.require_type(f"{path}.target", target, (str,), "string"):
        ok = False

    label = raw.get("label")
    if label is not None and not col.require_type(f"{path}.label", label, (str,), "string"):
        ok = False

    directed = raw.get("directed", True)
    if not col.require_type(f"{path}.directed", directed, (bool,), "boolean"):
        ok = False

    kind = raw.get("kind", "flow")
    if not isinstance(kind, str) or kind not in VALID_EDGE_KINDS:
        col.add(f"{path}.kind", f"must be one of {', '.join(VALID_EDGE_KINDS)}")
        ok = False

    dashed = raw.get("dashed", False)
    if not isinstance(dashed, bool):
        col.add(f"{path}.dashed", "expected boolean")
        ok = False
    color = raw.get("color")
    if color is not None and (not isinstance(color, str) or not _RGB_COLOR.fullmatch(color)):
        col.add(f"{path}.color", "expected six-digit RGB hex color")
        ok = False

    _warn_unknown_keys(raw, {"source", "target", "label", "directed", "kind", "dashed", "color"}, path, col)

    if not ok:
        return None
    return Edge(source=source, target=target, label=label, directed=bool(directed), kind=kind,
                dashed=dashed, color=("#" + color.lstrip("#").upper()) if color else None)


def _validate_lane(raw: Any, path: str, col: _Collector) -> Lane | None:
    if not isinstance(raw, dict):
        col.add(path, f"expected object, got {type(raw).__name__}")
        return None
    lane_id = raw.get("id")
    if not isinstance(lane_id, str) or not lane_id.strip():
        col.add(f"{path}.id", "must be a nonempty string")
    label = raw.get("label")
    if label is not None and not isinstance(label, str):
        col.add(f"{path}.label", "expected string")
    _warn_unknown_keys(raw, {"id", "label"}, path, col)
    if not isinstance(lane_id, str) or not lane_id.strip() or (label is not None and not isinstance(label, str)):
        return None
    return Lane(id=lane_id, label=label)


def _validate_group(raw: Any, path: str, col: _Collector) -> Group | None:
    if not isinstance(raw, dict):
        col.add(path, f"expected object, got {type(raw).__name__}")
        return None

    ok = True
    group_id = raw.get("id")
    if not col.require_type(f"{path}.id", group_id, (str,), "string"):
        ok = False
    elif not group_id.strip():
        col.add(f"{path}.id", "must not be empty")
        ok = False

    label = raw.get("label")
    if label is not None and not col.require_type(f"{path}.label", label, (str,), "string"):
        ok = False
    vendor = raw.get("vendor")
    if vendor is not None and not col.require_type(f"{path}.vendor", vendor, (str,), "string"):
        ok = False

    _warn_unknown_keys(raw, {"id", "label", "vendor"}, path, col)

    if not ok:
        return None
    return Group(id=group_id, label=label, vendor=vendor)


def _warn_unknown_keys(raw: dict, known: set[str], path: str, col: _Collector) -> None:
    for key in raw:
        if key not in known:
            col.add(f"{path}.{key}", "unknown field")


def validate_spec(raw: Any) -> Diagram:
    """Validate a raw spec ``dict`` and return a :class:`Diagram`.

    Raises :class:`SpecValidationError` listing every problem found.
    """

    col = _Collector()

    if not isinstance(raw, dict):
        raise SpecValidationError([f"<root>: expected object, got {type(raw).__name__}"])

    title = raw.get("title", "Architecture")
    if not isinstance(title, str):
        col.add("title", f"expected string, got {type(title).__name__}")
        title = "Architecture"

    direction = raw.get("direction", "LR")
    if not isinstance(direction, str):
        col.add("direction", f"expected string, got {type(direction).__name__}")
        direction = "LR"
    elif direction not in VALID_DIRECTIONS:
        col.add("direction", f"must be one of {', '.join(VALID_DIRECTIONS)}")

    raw_nodes = raw.get("nodes", [])
    nodes: list[Node] = []
    if not isinstance(raw_nodes, list):
        col.add("nodes", f"expected array, got {type(raw_nodes).__name__}")
    else:
        if not raw_nodes:
            col.add("nodes", "at least one node is required")
        for i, raw_node in enumerate(raw_nodes):
            node = _validate_node(raw_node, f"nodes[{i}]", col)
            if node is not None:
                nodes.append(node)

    raw_groups = raw.get("groups", [])
    groups: list[Group] = []
    if not isinstance(raw_groups, list):
        col.add("groups", f"expected array, got {type(raw_groups).__name__}")
    else:
        for i, raw_group in enumerate(raw_groups):
            group = _validate_group(raw_group, f"groups[{i}]", col)
            if group is not None:
                groups.append(group)

    raw_edges = raw.get("edges", [])
    edges: list[Edge] = []
    if not isinstance(raw_edges, list):
        col.add("edges", f"expected array, got {type(raw_edges).__name__}")
    else:
        for i, raw_edge in enumerate(raw_edges):
            edge = _validate_edge(raw_edge, f"edges[{i}]", col)
            if edge is not None:
                edges.append(edge)

    raw_lanes = raw.get("lanes", [])
    lanes: list[Lane] = []
    if not isinstance(raw_lanes, list):
        col.add("lanes", f"expected array, got {type(raw_lanes).__name__}")
    else:
        for i, raw_lane in enumerate(raw_lanes):
            lane = _validate_lane(raw_lane, f"lanes[{i}]", col)
            if lane is not None:
                lanes.append(lane)

    lane_orientation = raw.get("lane_orientation")
    if lane_orientation is not None and lane_orientation not in ("horizontal", "vertical"):
        col.add("lane_orientation", "must be horizontal or vertical")
    _warn_unknown_keys(raw, {"title", "direction", "nodes", "edges", "groups", "lanes", "lane_orientation"}, "<root>", col)

    # Cross-reference checks (only meaningful once individual items parsed).
    _check_cross_references(nodes, edges, groups, lanes, col)

    if col.errors:
        raise SpecValidationError(col.errors)

    return Diagram(title=title, direction=direction, nodes=nodes, edges=edges, groups=groups,
                   lanes=lanes, lane_orientation=lane_orientation)


def validation_errors(raw: Any) -> list[str]:
    """Collect all validation errors without changing the raising legacy API."""
    try:
        validate_spec(raw)
    except SpecValidationError as exc:
        return exc.errors
    return []


def _check_cross_references(
    nodes: list[Node], edges: list[Edge], groups: list[Group], lanes: list[Lane], col: _Collector
) -> None:
    node_ids: set[str] = set()
    for i, node in enumerate(nodes):
        if node.id in node_ids:
            col.add(f"nodes[{i}].id", f"duplicate node id '{node.id}'")
        node_ids.add(node.id)

    group_ids: set[str] = set()
    for i, group in enumerate(groups):
        if group.id in group_ids:
            col.add(f"groups[{i}].id", f"duplicate group id '{group.id}'")
        group_ids.add(group.id)

    for i, node in enumerate(nodes):
        if node.group is not None and node.group not in group_ids:
            col.add(f"nodes[{i}].group", f"references unknown group '{node.group}'")

    lane_ids: set[str] = set()
    for i, lane in enumerate(lanes):
        if lane.id in lane_ids:
            col.add(f"lanes[{i}].id", f"duplicate lane id '{lane.id}'")
        lane_ids.add(lane.id)
    for i, node in enumerate(nodes):
        if node.lane is not None and node.lane not in lane_ids:
            col.add(f"nodes[{i}].lane", f"references unknown lane '{node.lane}'")
        elif lanes and node.lane is None:
            col.add(f"nodes[{i}].lane", "required when lanes are defined")

    for i, edge in enumerate(edges):
        if edge.source not in node_ids:
            col.add(f"edges[{i}].source", f"references unknown node '{edge.source}'")
        if edge.target not in node_ids:
            col.add(f"edges[{i}].target", f"references unknown node '{edge.target}'")


def load_spec(source: Any) -> Diagram:
    """Load and validate a spec from a path, JSON string, bytes, or ``dict``."""

    if isinstance(source, dict):
        return validate_spec(source)

    if isinstance(source, (bytes, bytearray)):
        source = source.decode("utf-8")

    if isinstance(source, str):
        # Treat as a file path if it points to an existing file, else as JSON text.
        if os.path.exists(source):
            with open(source, "r", encoding="utf-8") as fh:
                text = fh.read()
        else:
            text = source
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            raise SpecError(f"invalid JSON: {exc}") from exc
        return validate_spec(raw)

    raise SpecError(f"unsupported spec source type: {type(source).__name__}")
