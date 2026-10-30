"""Explicit shape specs validate and render without a vendor icon catalog."""

import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from unittest.mock import patch

from archdiagram.engine import render
from archdiagram.layout.engine import layout_diagram
from archdiagram.normalize import normalize_edges
from archdiagram.rasterize.resvg import pdf_bridge_available
from archdiagram.shapes import SHAPES
from archdiagram.spec.validate import validate_spec, validation_errors
from archdiagram.templates import get_template


def shape_spec():
    names = tuple(SHAPES)
    return {
        "title": "All shapes",
        "nodes": [{"id": name, "shape": name, "label": name.replace("_", " ").title()}
                  for name in names],
        "edges": [{"source": names[i], "target": names[i + 1],
                   "dashed": i == 2, "color": "AA33CC" if i == 2 else "#224466"}
                  for i in range(len(names) - 1)],
    }


class TestExplicitShapes(unittest.TestCase):
    def test_opt_in_edge_normalization_and_shortcut_reporting(self):
        spec = {
            "nodes": [{"id": name, "shape": "process"} for name in ("a", "b", "c")],
            "edges": [
                {"source": "a", "target": "b", "label": "first"},
                {"source": "a", "target": "b", "label": "second"},
                {"source": "b", "target": "c"},
                {"source": "a", "target": "c"},
                {"source": "c", "target": "a"},
            ],
        }
        result = render(spec, "svg")
        self.assertEqual(len(result.diagram.edges), 4)
        self.assertEqual(result.diagram.edges[0].label, "first")
        self.assertTrue(any("dropped duplicate edge a->b" in w for w in result.warnings))
        self.assertTrue(any("redundant edge a->c" in w for w in result.warnings))

        legacy = validate_spec(get_template("workflow"))
        legacy.edges.append(legacy.edges[0])
        same, warnings = normalize_edges(legacy)
        self.assertIs(same, legacy)
        self.assertEqual(warnings, [])

    def test_model_sizes_and_validation(self):
        diagram = validate_spec(shape_spec())
        layout = layout_diagram(diagram)
        for node in diagram.nodes:
            style = SHAPES[node.shape]
            box = layout.boxes[node.id]
            self.assertEqual((box.w, box.h), (style.width, style.height))
        self.assertEqual(diagram.edges[2].color, "#AA33CC")
        self.assertTrue(diagram.edges[2].dashed)

        bad = shape_spec()
        bad["nodes"][0]["service"] = "azure.aks"
        bad["nodes"][1]["id"] = ["not", "hashable"]
        bad["nodes"][2]["tier"] = True
        bad["edges"][0]["color"] = "red"
        bad["edges"][1]["dashed"] = "yes"
        bad["nodes"][3]["extra"] = 1
        errors = validation_errors(bad)
        for path in ("nodes[0].service", "nodes[1].id", "nodes[2].tier",
                     "nodes[3].extra", "edges[0].color", "edges[1].dashed"):
            self.assertTrue(any(path in error for error in errors), (path, errors))

    def test_all_shapes_in_drawio_svg_vsdx_and_pptx(self):
        spec = shape_spec()
        with patch("archdiagram.registry.catalog.get_catalog", side_effect=AssertionError("loaded")):
            drawio = render(spec, "drawio").content
            svg = render(spec, "svg").content
            vsdx = render(spec, "vsdx").content
            pptx = render(spec, "pptx").content
            pdf = render(spec, "pdf").content if pdf_bridge_available() else None
        drawio_xml = ET.fromstring(drawio)
        styles = {cell.get("id"): cell.get("style", "")
                  for cell in drawio_xml.iter("mxCell")}
        self.assertIn("rhombus", styles["node_decision"])
        self.assertIn("shape=document", styles["node_document"])
        self.assertIn("mxgraph.flowchart.database", styles["node_data_store"])
        self.assertIn("strokeColor=#AA33CC", styles["edge_2"])
        ET.fromstring(svg)
        self.assertIn(b"<ellipse", svg)
        self.assertIn(b"#AA33CC", svg)
        if pdf is not None:
            self.assertTrue(pdf.startswith(b"%PDF-"))
        with tempfile.TemporaryDirectory() as directory:
            for name, data in (("vsdx", vsdx), ("pptx", pptx)):
                path = Path(directory) / f"diagram.{name}"
                path.write_bytes(data)
                with zipfile.ZipFile(path) as archive:
                    self.assertIsNone(archive.testzip())
                    xml_name = "visio/pages/page1.xml" if name == "vsdx" else "ppt/slides/slide1.xml"
                    xml = archive.read(xml_name)
                    ET.fromstring(xml)
                    self.assertIn(b"Data Store", xml)
                    if name == "pptx":
                        self.assertIn(b'prst="can"', xml)


if __name__ == "__main__":
    unittest.main()
