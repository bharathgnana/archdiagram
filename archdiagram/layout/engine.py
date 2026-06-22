"""Hand-rolled layered layout (no graphviz, no third-party deps).

Nodes are assigned to layers by a longest-path relaxation over the directed
edges (cycles are tolerated via a bounded number of passes). Within a layer
nodes are ordered so that members of the same group stay adjacent. Layer axis
follows the diagram ``direction`` (``LR``/``RL`` horizontal, ``TB``/``BT``
vertical). Explicit ``x``/``y`` on a node override the computed cell origin.

All coordinates are in points with the origin at the top-left.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..spec.model import Diagram

ICON_SIZE = 48
NODE_W = 132
NODE_H = 92
H_GAP = 64
V_GAP = 40
MARGIN = 48
GROUP_PAD = 22
GROUP_HEADER = 30


@dataclass
class Box:
    """The cell rectangle reserved for a node (icon + label area)."""

    node_id: str
    x: float
    y: float
    w: float = NODE_W
    h: float = NODE_H

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    def icon_rect(self, icon_w: float = ICON_SIZE, icon_h: float = ICON_SIZE) -> tuple[float, float, float, float]:
        """Centered icon rectangle near the top of the cell (x, y, w, h)."""

        ix = self.x + (self.w - icon_w) / 2
        iy = self.y + 8
        return ix, iy, icon_w, icon_h

    def label_anchor(self) -> tuple[float, float]:
        """Center-x / top-y for the label text, below the icon."""

        return self.cx, self.y + 8 + ICON_SIZE + 6


@dataclass
class GroupBox:
    group_id: str
    x: float
    y: float
    w: float
    h: float


@dataclass
class LayoutResult:
    boxes: dict[str, Box]
    group_boxes: dict[str, GroupBox] = field(default_factory=dict)
    width: float = 0.0
    height: float = 0.0


def _compute_layers(diagram: Diagram) -> dict[str, int]:
    """Longest-path layering with bounded relaxation (cycle-safe)."""

    layer = {node.id: 0 for node in diagram.nodes}
    edges = [(e.source, e.target) for e in diagram.edges if e.directed]
    n = len(diagram.nodes)
    for _ in range(max(1, n)):
        changed = False
        for src, dst in edges:
            if src in layer and dst in layer and layer[dst] < layer[src] + 1:
                layer[dst] = layer[src] + 1
                changed = True
        if not changed:
            break
    return layer


def _order_within_layer(node_ids: list[str], diagram: Diagram) -> list[str]:
    """Keep group members adjacent while preserving stable insertion order."""

    index = {node.id: i for i, node in enumerate(diagram.nodes)}
    group_of = {node.id: (node.group or "") for node in diagram.nodes}
    # First appearance order of each group within this layer determines group order.
    group_rank: dict[str, int] = {}
    for nid in node_ids:
        g = group_of[nid]
        if g not in group_rank:
            group_rank[g] = len(group_rank)
    return sorted(node_ids, key=lambda nid: (group_rank[group_of[nid]], index[nid]))


def layout_diagram(diagram: Diagram) -> LayoutResult:
    horizontal = diagram.direction in ("LR", "RL")
    reverse = diagram.direction in ("RL", "BT")

    layers = _compute_layers(diagram)
    max_layer = max(layers.values(), default=0)

    by_layer: dict[int, list[str]] = {}
    for node in diagram.nodes:
        by_layer.setdefault(layers[node.id], []).append(node.id)

    boxes: dict[str, Box] = {}
    for layer_idx in range(max_layer + 1):
        members = _order_within_layer(by_layer.get(layer_idx, []), diagram)
        place_idx = (max_layer - layer_idx) if reverse else layer_idx
        for slot, node_id in enumerate(members):
            if horizontal:
                x = MARGIN + place_idx * (NODE_W + H_GAP)
                y = MARGIN + slot * (NODE_H + V_GAP)
            else:
                x = MARGIN + slot * (NODE_W + H_GAP)
                y = MARGIN + place_idx * (NODE_H + V_GAP)
            boxes[node_id] = Box(node_id=node_id, x=float(x), y=float(y))

    # Explicit coordinate overrides.
    for node in diagram.nodes:
        if node.x is not None or node.y is not None:
            box = boxes[node.id]
            if node.x is not None:
                box.x = node.x
            if node.y is not None:
                box.y = node.y

    group_boxes = _compute_group_boxes(diagram, boxes)

    _normalize_origin(boxes, group_boxes)

    width = MARGIN
    height = MARGIN
    for box in boxes.values():
        width = max(width, box.x + box.w)
        height = max(height, box.y + box.h)
    for gb in group_boxes.values():
        width = max(width, gb.x + gb.w)
        height = max(height, gb.y + gb.h)
    width += MARGIN
    height += MARGIN

    return LayoutResult(boxes=boxes, group_boxes=group_boxes, width=width, height=height)


def _normalize_origin(boxes: dict[str, Box], group_boxes: dict[str, GroupBox]) -> None:
    """Shift everything so the top-left content edge sits at MARGIN, MARGIN."""

    xs = [b.x for b in boxes.values()] + [g.x for g in group_boxes.values()]
    ys = [b.y for b in boxes.values()] + [g.y for g in group_boxes.values()]
    if not xs or not ys:
        return
    dx = MARGIN - min(xs)
    dy = MARGIN - min(ys)
    if dx == 0 and dy == 0:
        return
    for b in boxes.values():
        b.x += dx
        b.y += dy
    for g in group_boxes.values():
        g.x += dx
        g.y += dy


def _compute_group_boxes(diagram: Diagram, boxes: dict[str, Box]) -> dict[str, GroupBox]:
    group_boxes: dict[str, GroupBox] = {}
    for group in diagram.groups:
        members = [boxes[n.id] for n in diagram.nodes_in_group(group.id) if n.id in boxes]
        if not members:
            continue
        min_x = min(b.x for b in members) - GROUP_PAD
        min_y = min(b.y for b in members) - GROUP_PAD - GROUP_HEADER
        max_x = max(b.x + b.w for b in members) + GROUP_PAD
        max_y = max(b.y + b.h for b in members) + GROUP_PAD
        group_boxes[group.id] = GroupBox(
            group_id=group.id,
            x=min_x,
            y=min_y,
            w=max_x - min_x,
            h=max_y - min_y,
        )
    return group_boxes
