"""Orthogonal routes avoid intermediate boxes and separate shared ports."""

import unittest
import xml.etree.ElementTree as ET

from archdiagram.engine import render
from archdiagram.layout.engine import layout_diagram
from archdiagram.routing import _crosses_box, route_edge
from archdiagram.spec.validate import validate_spec


class TestRouting(unittest.TestCase):
    def test_skips_intermediate_node_and_offsets_fan_out(self):
        spec = {
            "nodes": [{"id": "a", "shape": "process", "tier": 0},
                      {"id": "b", "shape": "process", "tier": 1},
                      {"id": "c", "shape": "process", "tier": 2}],
            "edges": [{"source": "a", "target": "b"},
                      {"source": "a", "target": "c", "label": "skip"},
                      {"source": "b", "target": "c"}],
        }
        diagram = validate_spec(spec)
        layout = layout_diagram(diagram)
        direct = route_edge(diagram, layout, diagram.edges[0])
        shortcut = route_edge(diagram, layout, diagram.edges[1])
        self.assertNotEqual(direct[0], shortcut[0])
        self.assertFalse(_crosses_box(shortcut, layout.boxes["b"]))
        self.assertTrue(all((a[0] == b[0] or a[1] == b[1])
                            for a, b in zip(shortcut, shortcut[1:])))
        svg = render(spec, "svg").content
        self.assertIn(b'<path d="M', svg)
        self.assertIn(b">skip</text>", svg)

    def test_svg_and_html_escape_text_once(self):
        spec = {
            "title": "A & B <C>",
            "nodes": [{"id": "first", "shape": "process", "label": "R&D <test>"},
                      {"id": "last", "shape": "end"}],
            "edges": [{"source": "first", "target": "last", "label": "Yes & No"}],
        }
        svg = render(spec, "svg").content.decode()
        html = render(spec, "html").content.decode()
        ET.fromstring(svg)
        self.assertIn("A &amp; B &lt;C&gt;", svg)
        self.assertIn("R&amp;D &lt;test&gt;", svg)
        self.assertIn("Yes &amp; No", html)
        self.assertNotIn("&amp;amp;", svg)


if __name__ == "__main__":
    unittest.main()
