"""Orthogonal perimeter routing for opt-in workflow diagrams."""

from __future__ import annotations

from .layout.engine import Box, LayoutResult
from .spec.model import Diagram, Edge

Point = tuple[float, float]


def _faces(source: Box, target: Box) -> tuple[str, str]:
    dx = target.cx - source.cx
    dy = (target.y + target.h / 2) - (source.y + source.h / 2)
    if abs(dx) >= abs(dy):
        return ("right", "left") if dx >= 0 else ("left", "right")
    return ("bottom", "top") if dy >= 0 else ("top", "bottom")


def _port(box: Box, face: str, offset: float) -> Point:
    if face in ("left", "right"):
        y = max(box.y + 8, min(box.y + box.h - 8, box.y + box.h / 2 + offset))
        return (box.x if face == "left" else box.x + box.w, y)
    x = max(box.x + 8, min(box.x + box.w - 8, box.cx + offset))
    return (x, box.y if face == "top" else box.y + box.h)


def _face_offset(diagram: Diagram, layout: LayoutResult, edge: Edge,
                 face: str, source_side: bool) -> float:
    peers: list[Edge] = []
    node_id = edge.source if source_side else edge.target
    for other in diagram.edges:
        if (other.source if source_side else other.target) != node_id:
            continue
        other_faces = _faces(layout.boxes[other.source], layout.boxes[other.target])
        if other_faces[0 if source_side else 1] == face:
            peers.append(other)
    index = next((index for index, peer in enumerate(peers) if peer is edge), 0)
    return 12.0 * (index - (len(peers) - 1) / 2)


def _crosses_box(points: list[Point], box: Box) -> bool:
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        if x1 == x2 and box.x < x1 < box.x + box.w:
            if max(min(y1, y2), box.y) < min(max(y1, y2), box.y + box.h):
                return True
        elif y1 == y2 and box.y < y1 < box.y + box.h:
            if max(min(x1, x2), box.x) < min(max(x1, x2), box.x + box.w):
                return True
    return False


def route_edge(diagram: Diagram, layout: LayoutResult, edge: Edge) -> list[Point]:
    """Return a Manhattan polyline that avoids intermediate node boxes."""
    src, dst = layout.boxes[edge.source], layout.boxes[edge.target]
    if edge.source == edge.target:
        return [(src.x + src.w, src.y + src.h / 2 - 10),
                (src.x + src.w + 20, src.y + src.h / 2 - 10),
                (src.x + src.w + 20, src.y - 20),
                (src.cx, src.y - 20), (src.cx, src.y)]
    source_face, target_face = _faces(src, dst)
    start = _port(src, source_face, _face_offset(diagram, layout, edge, source_face, True))
    end = _port(dst, target_face, _face_offset(diagram, layout, edge, target_face, False))
    horizontal = source_face in ("left", "right")
    if horizontal:
        middle = (start[0] + end[0]) / 2
        points = [start, (middle, start[1]), (middle, end[1]), end]
    else:
        middle = (start[1] + end[1]) / 2
        points = [start, (start[0], middle), (end[0], middle), end]
    obstacles = [box for node_id, box in layout.boxes.items()
                 if node_id not in (edge.source, edge.target)]
    if not any(_crosses_box(points, box) for box in obstacles):
        return points

    # Detour through an empty corridor 10px outside the intermediate boxes.
    if horizontal:
        top = min(box.y for box in obstacles) - 10
        bottom = max(box.y + box.h for box in obstacles) + 10
        corridor = min((top, bottom), key=lambda y: abs(y - start[1]) + abs(y - end[1]))
        first_x = start[0] + (12 if source_face == "right" else -12)
        last_x = end[0] + (-12 if target_face == "left" else 12)
        return [start, (first_x, start[1]), (first_x, corridor),
                (last_x, corridor), (last_x, end[1]), end]
    left = min(box.x for box in obstacles) - 10
    right = max(box.x + box.w for box in obstacles) + 10
    corridor = min((left, right), key=lambda x: abs(x - start[0]) + abs(x - end[0]))
    first_y = start[1] + (12 if source_face == "bottom" else -12)
    last_y = end[1] + (-12 if target_face == "top" else 12)
    return [start, (start[0], first_y), (corridor, first_y),
            (corridor, last_y), (end[0], last_y), end]


def label_position(points: list[Point]) -> Point:
    """Center a label on the longest routed segment."""
    first, second = max(zip(points, points[1:]),
                        key=lambda pair: abs(pair[1][0] - pair[0][0]) +
                                         abs(pair[1][1] - pair[0][1]))
    return (first[0] + second[0]) / 2, (first[1] + second[1]) / 2
