"""Opt-in edge normalization and forward-graph diagnostics."""

from __future__ import annotations

from collections import deque
from dataclasses import replace

from .spec.model import Diagram, Edge


def _is_modern(diagram: Diagram) -> bool:
    return (any(node.shape is not None or node.tier is not None for node in diagram.nodes)
            or any(edge.dashed or edge.color is not None for edge in diagram.edges)
            or diagram.lane_orientation is not None)


def normalize_edges(diagram: Diagram) -> tuple[Diagram, list[str]]:
    """Keep the first edge per pair; report every drop and redundant shortcut."""
    if not _is_modern(diagram):
        return diagram, []

    first: set[tuple[str, str]] = set()
    kept: list[Edge] = []
    warnings: list[str] = []
    for index, edge in enumerate(diagram.edges):
        pair = (edge.source, edge.target)
        if pair in first:
            warnings.append(f"dropped duplicate edge {edge.source}->{edge.target} at edges[{index}]")
        else:
            first.add(pair)
            kept.append(edge)

    ids = [node.id for node in diagram.nodes]
    outgoing: dict[str, list[str]] = {node_id: [] for node_id in ids}
    for edge in kept:
        if edge.directed:
            outgoing[edge.source].append(edge.target)

    # Iterative DFS identifies back edges without a Python recursion limit.
    state = {node_id: 0 for node_id in ids}
    back: set[tuple[str, str]] = set()
    for start in ids:
        if state[start]:
            continue
        state[start] = 1
        stack = [(start, iter(outgoing[start]))]
        while stack:
            source, children = stack[-1]
            try:
                target = next(children)
            except StopIteration:
                state[source] = 2
                stack.pop()
                continue
            if state[target] == 1:
                back.add((source, target))
            elif state[target] == 0:
                state[target] = 1
                stack.append((target, iter(outgoing[target])))

    forward = {node_id: [target for target in outgoing[node_id]
                         if (node_id, target) not in back] for node_id in ids}
    indegree = {node_id: 0 for node_id in ids}
    for targets in forward.values():
        for target in targets:
            indegree[target] += 1
    ready = deque(node_id for node_id in ids if indegree[node_id] == 0)
    topological: list[str] = []
    while ready:
        source = ready.popleft()
        topological.append(source)
        for target in forward[source]:
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)

    bits = {node_id: 1 << index for index, node_id in enumerate(ids)}
    reach = {node_id: 0 for node_id in ids}
    for source in reversed(topological):
        mask = 0
        for target in forward[source]:
            mask |= bits[target] | reach[target]
        reach[source] = mask
    for source in ids:
        targets = forward[source]
        masks = [bits[target] | reach[target] for target in targets]
        suffix = [0] * (len(masks) + 1)
        for index in range(len(masks) - 1, -1, -1):
            suffix[index] = suffix[index + 1] | masks[index]
        prefix = 0
        for index, target in enumerate(targets):
            if (prefix | suffix[index + 1]) & bits[target]:
                warnings.append(f"transitively redundant edge {source}->{target} (retained)")
            prefix |= masks[index]

    return replace(diagram, edges=kept), warnings
