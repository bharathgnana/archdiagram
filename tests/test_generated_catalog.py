"""Generated vendor icon packs feed catalog search and rendering."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from archdiagram.emit.drawio import NATIVE, emit_drawio
from archdiagram.emit.svg import render_svg
from archdiagram.registry.catalog import get_catalog
from archdiagram.spec.validate import validate_spec
from tools.build_catalog import build_catalog, svg_dimensions


class TestGeneratedCatalog(unittest.TestCase):
    def test_build_search_and_render_local_icon(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            icons = root / "icons"
            category = icons / "Azure" / "AI + Machine Learning"
            category.mkdir(parents=True)
            icon = category / "03513-icon-service-Contoso_AI_Studio.svg"
            icon.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 36">'
                            '<rect width="24" height="36"/></svg>', encoding="utf-8")
            manifest = build_catalog(icons)
            self.assertEqual(manifest["icon_count"], 1)
            entry = manifest["icons"]["azure.contoso_ai_studio"]
            self.assertEqual((entry["width"], entry["height"]), (24, 36))
            self.assertEqual(entry["category"], "AI + Machine Learning")
            out = root / "manifest.json"
            out.write_text(json.dumps(manifest), encoding="utf-8")
            with patch.dict(os.environ, {"ARCHDIAGRAM_CATALOG": str(out)}):
                get_catalog.cache_clear()
                try:
                    catalog = get_catalog()
                    self.assertEqual(catalog.lookup("azure.contoso_ai_studio").icon, entry["file"])
                    self.assertIn("azure.contoso_ai_studio", [e.service for e in catalog.search("studio")])
                    self.assertIn("azure.contoso_ai_studio", [e.service for e in catalog.search("machine learning")])
                    self.assertIsNotNone(catalog.lookup("azure.aks"))
                    diagram = validate_spec({"nodes": [{"id": "studio", "service": "azure.contoso_ai_studio"}]})
                    svg, warnings = render_svg(diagram, icon_cache=str(icons))
                    self.assertEqual(warnings, [])
                    self.assertIn("data:image/svg+xml;base64,", svg)
                    self.assertIn("data:image/svg+xml,", emit_drawio(diagram, mode=NATIVE, icon_cache=str(icons)))
                finally:
                    get_catalog.cache_clear()

    def test_duplicate_names_and_invalid_svg(self):
        with tempfile.TemporaryDirectory() as temp:
            icons = Path(temp) / "icons"
            for category in ("one", "two"):
                folder = icons / "aws" / category
                folder.mkdir(parents=True)
                (folder / "S3.svg").write_text("invalid svg", encoding="utf-8")
            manifest = build_catalog(icons)
            self.assertEqual(set(manifest["icons"]), {"aws.s3", "aws.s3_2"})
            self.assertEqual(svg_dimensions(icons / "aws" / "one" / "S3.svg"), (48, 48))


if __name__ == "__main__":
    unittest.main()
