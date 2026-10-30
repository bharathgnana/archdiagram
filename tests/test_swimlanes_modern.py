"""Opt-in swim lanes honor band order, orientation, and unassigned nodes."""

import unittest
import xml.etree.ElementTree as ET
import io
import zipfile

from archdiagram.engine import render
from archdiagram.layout.engine import UNASSIGNED_LANE, layout_diagram
from archdiagram.spec.validate import validate_spec, validation_errors


def lane_spec(orientation="horizontal"):
    return {
        "title": "Review",
        "direction": "RL",  # ignored when lane_orientation is explicit
        "lane_orientation": orientation,
        "lanes": [{"id": "reviewer", "label": "Reviewer"},
                  {"id": "requester", "label": "Requester"}],
        "nodes": [
            {"id": "submit", "shape": "process", "lane": "requester"},
            {"id": "review", "shape": "decision", "lane": "reviewer"},
            {"id": "archive", "shape": "document"},
        ],
        "edges": [{"source": "submit", "target": "review"},
                  {"source": "review", "target": "archive"}],
    }


class TestModernSwimlanes(unittest.TestCase):
    def test_order_and_both_orientations(self):
        for orientation in ("horizontal", "vertical"):
            diagram = validate_spec(lane_spec(orientation))
            layout = layout_diagram(diagram)
            self.assertEqual(list(layout.lane_boxes), ["reviewer", "requester", UNASSIGNED_LANE])
            axis = "y" if orientation == "horizontal" else "x"
            bands = list(layout.lane_boxes.values())
            self.assertLess(getattr(bands[0], axis), getattr(bands[1], axis))
            self.assertLess(getattr(bands[1], axis), getattr(bands[2], axis))
            flow_axis = "x" if orientation == "horizontal" else "y"
            self.assertLess(getattr(layout.boxes["submit"], flow_axis),
                            getattr(layout.boxes["review"], flow_axis))
            for node in diagram.nodes:
                box = layout.boxes[node.id]
                band = layout.lane_boxes[node.lane or UNASSIGNED_LANE]
                self.assertGreaterEqual(box.x, band.x)
                self.assertGreaterEqual(box.y, band.y)
                self.assertLessEqual(box.x + box.w, band.x + band.w)
                self.assertLessEqual(box.y + box.h, band.y + band.h)

    def test_validation_for_unknown_lanes_and_coordinates(self):
        spec = lane_spec()
        spec["lanes"] = [{"id": 42}]
        spec["nodes"][0]["lane"] = "missing"
        spec["nodes"][1]["x"] = 500
        errors = validation_errors(spec)
        self.assertTrue(any("unknown lane" in error for error in errors))
        self.assertTrue(any("explicit x/y" in error for error in errors))
        self.assertTrue(any("lanes[0].id" in error for error in errors))

    def test_renderers_draw_unassigned_band_behind_nodes(self):
        spec = lane_spec()
        drawio = render(spec, "drawio").content
        svg = render(spec, "svg").content
        vsdx = render(spec, "vsdx").content
        pptx = render(spec, "pptx").content
        root = ET.fromstring(drawio)
        ids = [element.get("id") for element in root.iter("mxCell")]
        self.assertLess(ids.index("lane_" + UNASSIGNED_LANE), ids.index("node_archive"))
        self.assertIn(b"fillColor=#F5F5F5", drawio)
        self.assertIn(b"Unassigned", svg)
        self.assertIn(b'fill-opacity="0.3"', svg)
        with zipfile.ZipFile(io.BytesIO(vsdx)) as package:
            self.assertIn(b"Unassigned", package.read("visio/pages/page1.xml"))
        with zipfile.ZipFile(io.BytesIO(pptx)) as package:
            self.assertIn(b"Unassigned", package.read("ppt/slides/slide1.xml"))


if __name__ == "__main__":
    unittest.main()
