"""Hand-rolled layered layout (no graphviz, no third-party deps).

Nodes are assigned to layers by a longest path over the directed
component graph (cycles share a layer). Within a layer
nodes are ordered so that members of the same group stay adjacent. Layer axis
follows the diagram ``direction`` (``LR``/``RL`` horizontal, ``TB``/``BT``
vertical). Explicit ``x``/``y`` on a node override the computed cell origin.

All coordinates are in points with the origin at the top-left.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import deque

from ..spec.model import Diagram
from ..shapes import SHAPES

ICON_SIZE = 48
NODE_W = 132
NODE_H = 92
H_GAP = 64
V_GAP = 40
MARGIN = 48
GROUP_PAD = 22
GROUP_HEADER = 30
LANE_PAD = 20
LANE_HEADER = 28


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
class LaneBox:
    lane_id: str
    x: float
    y: float
    w: float
    h: float


@dataclass
class LayoutResult:
    boxes: dict[str, Box]
    group_boxes: dict[str, GroupBox] = field(default_factory=dict)
    lane_boxes: dict[str, LaneBox] = field(default_factory=dict)
    width: float = 0.0
    height: float = 0.0


def _compute_layers(diagram: Diagram) -> dict[str, int]:
    """Collapse cycles, then assign longest-path layers to the acyclic graph."""

    ids = [node.id for node in diagram.nodes]
    adjacent = {node_id: [] for node_id in ids}
    reverse = {node_id: [] for node_id in ids}
    for edge in diagram.edges:
        if edge.directed:
            adjacent[edge.source].append(edge.target)
            reverse[edge.target].append(edge.source)

    # Iterative Kosaraju avoids recursion limits on large workflow specs.
    seen: set[str] = set()
    order: list[str] = []
    for start in ids:
        if start in seen:
            continue
        seen.add(start)
        stack = [(start, iter(adjacent[start]))]
        while stack:
            node_id, children = stack[-1]
            try:
                target = next(children)
            except StopIteration:
                order.append(node_id)
                stack.pop()
                continue
            if target not in seen:
                seen.add(target)
                stack.append((target, iter(adjacent[target])))

    component: dict[str, int] = {}
    component_count = 0
    for start in reversed(order):
        if start in component:
            continue
        index = component_count
        component_count += 1
        component[start] = index
        stack = [start]
        while stack:
            node_id = stack.pop()
            for source in reverse[node_id]:
                if source not in component:
                    component[source] = index
                    stack.append(source)

    count = max(component.values(), default=-1) + 1
    graph = [set() for _ in range(count)]
    indegree = [0] * count
    for source, targets in adjacent.items():
        for target in targets:
            a, b = component[source], component[target]
            if a != b and b not in graph[a]:
                graph[a].add(b)
                indegree[b] += 1
    depths = [0] * count
    queue = deque(i for i, degree in enumerate(indegree) if degree == 0)
    while queue:
        source = queue.popleft()
        for target in sorted(graph[source]):
            depths[target] = max(depths[target], depths[source] + 1)
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    return {node_id: depths[component[node_id]] for node_id in ids}


def _compute_forward_layers(diagram: Diagram) -> dict[str, int]:
    """Drop DFS back edges, then rank the remaining DAG by longest path."""
    ids = [node.id for node in diagram.nodes]
    adjacency = {node_id: [] for node_id in ids}
    for edge in diagram.edges:
        if edge.directed:
            adjacency[edge.source].append(edge.target)
    forward = {node_id: [] for node_id in ids}
    state = {node_id: 0 for node_id in ids}
    for start in ids:
        if state[start]:
            continue
        state[start] = 1
        stack = [(start, iter(adjacency[start]))]
        while stack:
            source, children = stack[-1]
            try:
                target = next(children)
            except StopIteration:
                state[source] = 2
                stack.pop()
                continue
            if state[target] == 1:
                continue
            forward[source].append(target)
            if state[target] == 0:
                state[target] = 1
                stack.append((target, iter(adjacency[target])))
    indegree = {node_id: 0 for node_id in ids}
    for targets in forward.values():
        for target in targets:
            indegree[target] += 1
    queue = deque(node_id for node_id in ids if indegree[node_id] == 0)
    depths = {node_id: 0 for node_id in ids}
    while queue:
        source = queue.popleft()
        for target in forward[source]:
            depths[target] = max(depths[target], depths[source] + 1)
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    return depths


def _separate_groups(diagram: Diagram, boxes: dict[str, Box],
                     group_boxes: dict[str, GroupBox], horizontal: bool) -> None:
    """Move later unpinned groups across the flow until padded boxes clear."""
    if len(group_boxes) < 2:
        return
    members = {group.id: [node for node in diagram.nodes if node.group == group.id]
               for group in diagram.groups}
    for _ in range(len(group_boxes) * len(group_boxes)):
        ordered = sorted(group_boxes.values(), key=lambda box: box.y if horizontal else box.x)
        moved = False
        for index, first in enumerate(ordered):
            for second in ordered[index + 1:]:
                if horizontal:
                    flow_overlap = first.x < second.x + second.w and second.x < first.x + first.w
                    delta = first.y + first.h + GROUP_PAD - second.y
                    pinned = any(node.y is not None for node in members[second.group_id])
                else:
                    flow_overlap = first.y < second.y + second.h and second.y < first.y + first.h
                    delta = first.x + first.w + GROUP_PAD - second.x
                    pinned = any(node.x is not None for node in members[second.group_id])
                if not flow_overlap or delta <= 0 or pinned:
                    continue
                for node in members[second.group_id]:
                    if horizontal:
                        boxes[node.id].y += delta
                    else:
                        boxes[node.id].x += delta
                if horizontal:
                    second.y += delta
                else:
                    second.x += delta
                moved = True
        if not moved:
            return


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


def _layout_shaped(diagram: Diagram) -> LayoutResult:
    """Size explicit shapes individually, leaving the legacy grid untouched."""
    horizontal = diagram.direction in ("LR", "RL")
    reverse = diagram.direction in ("RL", "BT")
    layers = _compute_forward_layers(diagram)
    for node in diagram.nodes:
        if node.tier is not None:
            layers[node.id] = node.tier
    by_layer: dict[int, list[str]] = {}
    dimensions: dict[str, tuple[int, int]] = {}
    for node in diagram.nodes:
        by_layer.setdefault(layers[node.id], []).append(node.id)
        style = SHAPES.get(node.shape or "")
        dimensions[node.id] = (style.width, style.height) if style else (NODE_W, NODE_H)

    boxes: dict[str, Box] = {}
    flow = MARGIN
    for layer in sorted(by_layer, reverse=reverse):
        members = _order_within_layer(by_layer[layer], diagram)
        cross = MARGIN
        flow_size = max((dimensions[nid][0] if horizontal else dimensions[nid][1])
                        for nid in members)
        for node_id in members:
            width, height = dimensions[node_id]
            if horizontal:
                boxes[node_id] = Box(node_id, float(flow), float(cross), width, height)
                cross += height + V_GAP
            else:
                boxes[node_id] = Box(node_id, float(cross), float(flow), width, height)
                cross += width + H_GAP
        flow += flow_size + (H_GAP if horizontal else V_GAP)

    for node in diagram.nodes:
        box = boxes[node.id]
        if node.x is not None:
            box.x = node.x
        if node.y is not None:
            box.y = node.y
    group_boxes = _compute_group_boxes(diagram, boxes)
    _separate_groups(diagram, boxes, group_boxes, horizontal)
    _normalize_origin(boxes, group_boxes, {})
    width = max([MARGIN] + [box.x + box.w for box in boxes.values()] +
                [box.x + box.w for box in group_boxes.values()]) + MARGIN
    height = max([MARGIN] + [box.y + box.h for box in boxes.values()] +
                 [box.y + box.h for box in group_boxes.values()]) + MARGIN
    return LayoutResult(boxes=boxes, group_boxes=group_boxes, width=width, height=height)


def layout_diagram(diagram: Diagram) -> LayoutResult:
    if any(node.shape is not None or node.tier is not None for node in diagram.nodes):
        return _layout_shaped(diagram)
    horizontal = diagram.direction in ("LR", "RL")
    reverse = diagram.direction in ("RL", "BT")

    layers = _compute_layers(diagram)
    max_layer = max(layers.values(), default=0)

    by_layer: dict[int, list[str]] = {}
    for node in diagram.nodes:
        by_layer.setdefault(layers[node.id], []).append(node.id)

    boxes: dict[str, Box] = {}
    lane_boxes: dict[str, LaneBox] = {}
    if diagram.lanes:
        counts = {
            lane.id: max(
                (sum(n.lane == lane.id for n in diagram.nodes if layers[n.id] == layer)
                 for layer in range(max_layer + 1)), default=0
            )
            for lane in diagram.lanes
        }
        cursor = MARGIN
        for lane in diagram.lanes:
            slots = max(1, counts[lane.id])
            if horizontal:
                band = LANE_HEADER + 2 * LANE_PAD + slots * NODE_H + (slots - 1) * V_GAP
                span = 2 * LANE_PAD + (max_layer + 1) * NODE_W + max_layer * H_GAP
                lane_boxes[lane.id] = LaneBox(lane.id, MARGIN, cursor, span, band)
            else:
                band = 2 * LANE_PAD + slots * NODE_W + (slots - 1) * H_GAP
                span = LANE_HEADER + 2 * LANE_PAD + (max_layer + 1) * NODE_H + max_layer * V_GAP
                lane_boxes[lane.id] = LaneBox(lane.id, cursor, MARGIN, band, span)
            cursor += band + LANE_PAD
        occupied: dict[tuple[int, str], int] = {}
        for layer_idx in range(max_layer + 1):
            members = _order_within_layer(by_layer.get(layer_idx, []), diagram)
            place_idx = (max_layer - layer_idx) if reverse else layer_idx
            for node_id in members:
                lane_id = diagram.node_by_id(node_id).lane
                lb = lane_boxes[lane_id]
                slot = occupied.get((layer_idx, lane_id), 0)
                occupied[(layer_idx, lane_id)] = slot + 1
                if horizontal:
                    x = lb.x + LANE_PAD + place_idx * (NODE_W + H_GAP)
                    y = lb.y + LANE_HEADER + LANE_PAD + slot * (NODE_H + V_GAP)
                else:
                    x = lb.x + LANE_PAD + slot * (NODE_W + H_GAP)
                    y = lb.y + LANE_HEADER + LANE_PAD + place_idx * (NODE_H + V_GAP)
                boxes[node_id] = Box(node_id, float(x), float(y))
    else:
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

    _normalize_origin(boxes, group_boxes, lane_boxes)

    width = MARGIN
    height = MARGIN
    for box in boxes.values():
        width = max(width, box.x + box.w)
        height = max(height, box.y + box.h)
    for gb in group_boxes.values():
        width = max(width, gb.x + gb.w)
        height = max(height, gb.y + gb.h)
    for lb in lane_boxes.values():
        width = max(width, lb.x + lb.w)
        height = max(height, lb.y + lb.h)
    width += MARGIN
    height += MARGIN

    return LayoutResult(boxes=boxes, group_boxes=group_boxes, lane_boxes=lane_boxes, width=width, height=height)


def _normalize_origin(boxes: dict[str, Box], group_boxes: dict[str, GroupBox], lane_boxes: dict[str, LaneBox]) -> None:
    """Shift everything so the top-left content edge sits at MARGIN, MARGIN."""

    xs = [b.x for b in boxes.values()] + [g.x for g in group_boxes.values()] + [l.x for l in lane_boxes.values()]
    ys = [b.y for b in boxes.values()] + [g.y for g in group_boxes.values()] + [l.y for l in lane_boxes.values()]
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
    for lane in lane_boxes.values():
        lane.x += dx
        lane.y += dy


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
