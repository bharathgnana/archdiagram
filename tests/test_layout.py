import unittest

from archdiagram.layout.engine import MARGIN, layout_diagram
from archdiagram.spec.validate import validate_spec


class TestLayout(unittest.TestCase):
    def _diagram(self):
        return validate_spec(
            {
                "direction": "LR",
                "groups": [{"id": "g"}],
                "nodes": [
                    {"id": "a", "service": "aws.ec2", "group": "g"},
                    {"id": "b", "service": "aws.eks", "group": "g"},
                    {"id": "c", "service": "aws.s3"},
                ],
                "edges": [
                    {"source": "a", "target": "b"},
                    {"source": "b", "target": "c"},
                ],
            }
        )

    def test_layers_ordered_left_to_right(self):
        layout = layout_diagram(self._diagram())
        a, b, c = layout.boxes["a"], layout.boxes["b"], layout.boxes["c"]
        self.assertLess(a.x, b.x)
        self.assertLess(b.x, c.x)

    def test_deterministic(self):
        d = self._diagram()
        l1 = layout_diagram(d)
        l2 = layout_diagram(d)
        self.assertEqual(
            {k: (v.x, v.y) for k, v in l1.boxes.items()},
            {k: (v.x, v.y) for k, v in l2.boxes.items()},
        )

    def test_explicit_coords_override(self):
        # Node 'a' is naturally leftmost (layer 0). An explicit large x must
        # override that, making it the rightmost node after layout.
        d = self._diagram()
        d.nodes[0].x = 3000.0
        layout = layout_diagram(d)
        max_x = max(b.x for b in layout.boxes.values())
        self.assertEqual(layout.boxes["a"].x, max_x)

    def test_group_box_covers_members(self):
        layout = layout_diagram(self._diagram())
        gb = layout.group_boxes["g"]
        for nid in ("a", "b"):
            box = layout.boxes[nid]
            self.assertGreaterEqual(box.x, gb.x)
            self.assertLessEqual(box.x + box.w, gb.x + gb.w)

    def test_origin_normalized(self):
        layout = layout_diagram(self._diagram())
        all_x = [b.x for b in layout.boxes.values()] + [
            g.x for g in layout.group_boxes.values()
        ]
        all_y = [b.y for b in layout.boxes.values()] + [
            g.y for g in layout.group_boxes.values()
        ]
        # Nothing is negative and the top-left content edge sits at MARGIN.
        self.assertGreaterEqual(min(all_x), 0)
        self.assertGreaterEqual(min(all_y), 0)
        self.assertEqual(min(all_x), MARGIN)
        self.assertEqual(min(all_y), MARGIN)


if __name__ == "__main__":
    unittest.main()
