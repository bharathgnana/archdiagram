"""Interchange formats keep editable structures and survive a round trip."""

import base64
import io
import urllib.parse
import unittest
import xml.etree.ElementTree as ET
import zipfile
import zlib

from archdiagram.emit.drawio import COMPRESSED, PORTABLE
from archdiagram.engine import render
from archdiagram.shapes import SHAPES


def shape_spec():
    names = tuple(SHAPES)
    return {"title": "Editable shapes",
            "nodes": [{"id": name, "shape": name, "label": name} for name in names],
            "edges": [{"source": names[index], "target": names[index + 1]}
                      for index in range(len(names) - 1)]}


class TestInterchange(unittest.TestCase):
    def test_compressed_drawio_round_trip(self):
        spec = shape_spec()
        compressed = ET.fromstring(render(spec, "drawio", drawio_mode=COMPRESSED).content)
        token = compressed.find("diagram").text
        self.assertNotIn(";", token)
        model = urllib.parse.unquote(zlib.decompress(base64.b64decode(token), -15).decode())
        plain = ET.fromstring(render(spec, "drawio", drawio_mode=PORTABLE).content)
        expected = plain.find("diagram/mxGraphModel")
        self.assertEqual(ET.tostring(ET.fromstring(model)).strip(), ET.tostring(expected).strip())

    def test_modern_pptx_has_editable_polyline_and_fit_text(self):
        payload = render(shape_spec(), "pptx").content
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            slide = ET.fromstring(archive.read("ppt/slides/slide1.xml"))
            presentation = ET.fromstring(archive.read("ppt/presentation.xml"))
        ns = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
              "a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
        routed = slide.findall(".//p:sp/p:spPr/a:custGeom", ns)
        self.assertEqual(len(routed), len(shape_spec()["edges"]))
        self.assertEqual(slide.findall(".//p:cxnSp/a:custGeom", ns), [])
        size = presentation.find("p:sldSz", ns)
        self.assertAlmostEqual(int(size.get("cx")) / int(size.get("cy")), 16 / 9, places=3)
        self.assertTrue(slide.findall(".//p:sp/p:txBody", ns))

    def test_modern_vsdx_has_routed_geometry_and_character_size(self):
        payload = render(shape_spec(), "vsdx").content
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            page = ET.fromstring(archive.read("visio/pages/page1.xml"))
        ns = {"v": "http://schemas.microsoft.com/office/visio/2012/main"}
        paths = page.findall(".//v:Shape/v:Section[@N='Geometry']", ns)
        self.assertTrue(any(len(path.findall("v:Row", ns)) >= 4 for path in paths))
        self.assertTrue(page.findall(".//v:Section[@N='Character']/v:Row/v:Cell[@N='Size']", ns))


if __name__ == "__main__":
    unittest.main()
