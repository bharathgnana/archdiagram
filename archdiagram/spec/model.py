"""Typed, immutable-ish model for an architecture diagram spec.

These dataclasses are produced by :func:`archdiagram.spec.validate.validate_spec`
after a raw ``dict`` (parsed from JSON) has been validated. Keeping the model
separate from validation means the rest of the engine can rely on well-formed
objects and never has to defensively re-check the input.
"""

from __future__ import annotations

from dataclasses import dataclass, field

VALID_DIRECTIONS = ("LR", "TB", "RL", "BT")
VALID_NODE_KINDS = ("service", "process", "decision", "data", "start", "end")
VALID_EDGE_KINDS = ("flow", "data")


@dataclass
class Node:
    """A service icon or workflow shape.

    For service nodes, ``service`` is ``"<vendor>.<service_key>"``
    (e.g. ``"azure.app_service"``). Other kinds omit it.
    ``x``/``y`` are optional explicit coordinates (top-left, in points) that
    override the computed layout position.
    """

    id: str
    service: str | None = None
    label: str | None = None
    group: str | None = None
    kind: str = "service"
    lane: str | None = None
    x: float | None = None
    y: float | None = None

    @property
    def vendor(self) -> str:
        return self.service.split(".", 1)[0] if self.service else ""

    @property
    def service_key(self) -> str:
        parts = self.service.split(".", 1) if self.service else []
        return parts[1] if len(parts) == 2 else ""

    @property
    def display_label(self) -> str:
        return self.label if self.label else self.id


@dataclass
class Edge:
    """A connection between two node ids."""

    source: str
    target: str
    label: str | None = None
    directed: bool = True
    kind: str = "flow"


@dataclass
class Lane:
    """A named swim lane. Nodes refer to it through ``Node.lane``."""

    id: str
    label: str | None = None

    @property
    def display_label(self) -> str:
        return self.label or self.id


@dataclass
class Group:
    """A visual container that encloses member nodes.

    Membership is expressed on the node side (``Node.group``); the group only
    carries presentation metadata. ``vendor`` optionally styles the container
    with a vendor accent colour.
    """

    id: str
    label: str | None = None
    vendor: str | None = None

    @property
    def display_label(self) -> str:
        return self.label if self.label else self.id


@dataclass
class Diagram:
    """A complete, validated diagram."""

    title: str = "Architecture"
    direction: str = "LR"
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    groups: list[Group] = field(default_factory=list)
    lanes: list[Lane] = field(default_factory=list)

    def node_by_id(self, node_id: str) -> Node | None:
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def group_by_id(self, group_id: str) -> Group | None:
        for group in self.groups:
            if group.id == group_id:
                return group
        return None

    def nodes_in_group(self, group_id: str) -> list[Node]:
        return [n for n in self.nodes if n.group == group_id]
