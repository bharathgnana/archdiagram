import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

from archdiagram.emit.drawio import NATIVE, PORTABLE, emit_drawio
from archdiagram.emit.vsdx import emit_vsdx
from archdiagram.spec.validate import validate_spec


def _diagram():
    return validate_spec(
        {
            "title": "Test Arch",
            "direction": "LR",
            "groups": [{"id": "g", "label": "Group", "vendor": "azure"}],
            "nodes": [
                {"id": "a", "service": "azure.aks", "label": "AKS", "group": "g"},
                {"id": "b", "service": "aws.s3", "label": "S3"},
                {"id": "c", "service": "made.up", "label": "Unknown"},
            ],
            "edges": [
                {"source": "a", "target": "b", "label": "e1"},
                {"source": "b", "target": "c"},
            ],
        }
    )


class TestDrawio(unittest.TestCase):
    def _assert_structure(self, xml: str):
        root = ET.fromstring(xml)
        ids = [c.get("id") for c in root.iter("mxCell")]
        self.assertIn("0", ids)
        self.assertIn("1", ids)
        # node + edge cells exist
        self.assertIn("node_a", ids)
        self.assertIn("edge_0", ids)

    def test_portable_mode_wellformed(self):
        self._assert_structure(emit_drawio(_diagram(), mode=PORTABLE))

    def test_native_mode_wellformed(self):
        self._assert_structure(emit_drawio(_diagram(), mode=NATIVE))

    def test_native_uses_stencil_style(self):
        xml = emit_drawio(_diagram(), mode=NATIVE)
        self.assertIn("mxgraph.aws4", xml)  # aws.s3 native stencil

    def test_invalid_mode(self):
        with self.assertRaises(ValueError):
            emit_drawio(_diagram(), mode="bogus")


class TestVsdx(unittest.TestCase):
    def test_package_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "x.vsdx")
            emit_vsdx(_diagram(), out)
            self.assertTrue(os.path.isfile(out))
            with zipfile.ZipFile(out) as zf:
                names = set(zf.namelist())
                for required in (
                    "[Content_Types].xml",
                    "_rels/.rels",
                    "visio/document.xml",
                    "visio/pages/pages.xml",
                    "visio/pages/page1.xml",
                ):
                    self.assertIn(required, names)
                # every xml part is well-formed
                for n in names:
                    if n.endswith(".xml"):
                        ET.fromstring(zf.read(n))


if __name__ == "__main__":
    unittest.main()
