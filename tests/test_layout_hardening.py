"""Opt-in workflow ranking and group separation stay iterative and stable."""

import unittest

from archdiagram.layout.engine import layout_diagram
from archdiagram.spec.validate import validate_spec


class TestLayoutHardening(unittest.TestCase):
    def test_loopback_keeps_downstream_on_later_rank(self):
        spec = {
            "nodes": [{"id": name, "shape": "process"}
                      for name in ("submit", "review", "revise", "done")],
            "edges": [
                {"source": "submit", "target": "review"},
                {"source": "review", "target": "revise"},
                {"source": "revise", "target": "review"},
                {"source": "review", "target": "done"},
            ],
        }
        boxes = layout_diagram(validate_spec(spec)).boxes
        self.assertLess(boxes["submit"].x, boxes["review"].x)
        self.assertLess(boxes["review"].x, boxes["revise"].x)
        self.assertLess(boxes["review"].x, boxes["done"].x)

    def test_thousand_node_chain_is_iterative(self):
        count = 1000
        spec = {
            "nodes": [{"id": f"n{i}", "shape": "process"} for i in range(count)],
            "edges": [{"source": f"n{i}", "target": f"n{i+1}"}
                      for i in range(count - 1)],
        }
        boxes = layout_diagram(validate_spec(spec)).boxes
        self.assertEqual(len(boxes), count)
        self.assertLess(boxes["n0"].x, boxes["n999"].x)

    def test_tier_and_reverse_directions(self):
        base = {
            "nodes": [{"id": "a", "shape": "process", "tier": 2},
                      {"id": "b", "shape": "process", "tier": 0}],
            "edges": [{"source": "a", "target": "b"}],
        }
        for direction in ("LR", "RL", "TB", "BT"):
            spec = dict(base, direction=direction)
            boxes = layout_diagram(validate_spec(spec)).boxes
            axis = "x" if direction in ("LR", "RL") else "y"
            a = getattr(boxes["a"], axis)
            b = getattr(boxes["b"], axis)
            self.assertGreater(a, b) if direction in ("LR", "TB") else self.assertLess(a, b)

    def test_dense_groups_have_padded_separation(self):
        spec = {
            "groups": [{"id": "one"}, {"id": "two"}, {"id": "three"}],
            "nodes": [
                {"id": "a", "shape": "process", "group": "one"},
                {"id": "b", "shape": "process", "group": "two"},
                {"id": "c", "shape": "process", "group": "three"},
                {"id": "d", "shape": "process", "group": "one"},
                {"id": "e", "shape": "process", "group": "two"},
                {"id": "f", "shape": "process", "group": "three"},
            ],
            "edges": [
                {"source": "a", "target": "d"},
                {"source": "b", "target": "e"},
                {"source": "c", "target": "f"},
            ],
        }
        for direction in ("LR", "TB"):
            boxes = layout_diagram(validate_spec(dict(spec, direction=direction))).group_boxes
            groups = list(boxes.values())
            for index, first in enumerate(groups):
                for second in groups[index + 1:]:
                    disjoint = (first.x + first.w <= second.x or second.x + second.w <= first.x or
                                first.y + first.h <= second.y or second.y + second.h <= first.y)
                    self.assertTrue(disjoint, (direction, first, second))


if __name__ == "__main__":
    unittest.main()
