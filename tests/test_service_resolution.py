"""Service resolution prefers exact names and makes misses actionable."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from archdiagram.cli import main
from archdiagram.engine import render
from archdiagram.registry.catalog import Catalog, ServiceEntry
from archdiagram.spec.validate import SpecValidationError
from mcp_server.tools import render_diagram, validate_spec
from tools.build_catalog import build_catalog


def catalog():
    entries = [
        ServiceEntry("azure", "key_vault", "Key Vault", "", "azure/key_vault.svg",
                     "#0078D4", aliases=("secrets vault",)),
        ServiceEntry("aws", "s3", "Simple Storage Service", "", "aws/s3.svg", "#ED7100"),
    ]
    return Catalog({entry.service: entry for entry in entries},
                   {"azure": "#0078D4", "aws": "#ED7100"})


class TestServiceResolution(unittest.TestCase):
    def test_ranked_resolution_and_both_miss_modes(self):
        with patch("archdiagram.registry.catalog.get_catalog", return_value=catalog()):
            for service, method in (("azure.key_vault", "canonical"),
                                    ("secrets vault", "alias"),
                                    ("key_vault", "providerless"),
                                    ("azure.key_vaut", "fuzzy")):
                with self.subTest(service=service):
                    entry, actual, _ = catalog().resolve(service)
                    self.assertEqual((entry.service, actual), ("azure.key_vault", method))
                    result = render({"nodes": [{"id": "a", "service": service}]}, "svg")
                    self.assertEqual(result.diagram.nodes[0].service, "azure.key_vault")
            raw = {"nodes": [{"id": "a", "service": "mystery.data"}]}
            result = render(raw, "svg")
            self.assertTrue(any("suggestions:" in warning for warning in result.warnings))
            with self.assertRaises(SpecValidationError):
                render(raw, "svg", strict=True)
            with tempfile.TemporaryDirectory() as directory:
                output = str(Path(directory) / "diagram.svg")
                self.assertFalse(render_diagram(json.dumps(raw), "svg", output, strict=True)["ok"])
                self.assertFalse(validate_spec(json.dumps(raw), strict=True)["ok"])
                source = Path(directory) / "spec.json"
                source.write_text(json.dumps(raw), encoding="utf-8")
                self.assertEqual(main(["validate", str(source), "--strict"]), 1)
                self.assertEqual(main(["render", str(source), "-f", "svg", "-o", output,
                                       "--strict"]), 1)
                self.assertFalse(Path(output).exists())

    def test_catalog_builder_keeps_standalone_service_word(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "icons" / "azure"
            folder.mkdir(parents=True)
            (folder / "Service-App.svg").write_text('<svg width="24" height="36"/>',
                                                     encoding="utf-8")
            manifest = build_catalog(folder.parent)
            self.assertIn("azure.service_app", manifest["icons"])


if __name__ == "__main__":
    unittest.main()
