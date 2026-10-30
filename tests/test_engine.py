"""CLI and MCP use the same renderer bytes and format metadata."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from archdiagram.cli import main as cli_main
from archdiagram.engine import render
from archdiagram.formats import FORMATS
from archdiagram.rasterize.resvg import pdf_bridge_available
from archdiagram.templates import get_template
from mcp_server.tools import render_diagram


class TestSharedEngine(unittest.TestCase):
    def test_cli_and_mcp_write_identical_bytes(self):
        spec = get_template("workflow")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "spec.json"
            source.write_text(json.dumps(spec), encoding="utf-8")
            with patch("archdiagram.registry.icons._candidate_dirs", return_value=[directory]):
                for fmt in FORMATS:
                    if fmt == "pdf" and not pdf_bridge_available():
                        continue
                    with self.subTest(format=fmt):
                        cli_out = root / f"cli.{fmt}"
                        mcp_out = root / f"mcp.{fmt}"
                        with contextlib.redirect_stdout(io.StringIO()):
                            self.assertEqual(cli_main(["render", str(source), "-f", fmt,
                                                       "-o", str(cli_out)]), 0)
                        response = render_diagram(json.dumps(spec), fmt, str(mcp_out))
                        self.assertTrue(response["ok"], response)
                        self.assertEqual(cli_out.read_bytes(), mcp_out.read_bytes())
                        self.assertEqual(cli_out.read_bytes(), render(spec, fmt).content)

    def test_shape_only_render_does_not_load_vendor_catalog(self):
        with patch("archdiagram.registry.catalog.get_catalog", side_effect=AssertionError("loaded")):
            result = render(get_template("workflow"), "svg")
        self.assertIn(b"<svg", result.content)
        self.assertEqual(result.format.extension, ".svg")
        self.assertFalse(result.format.binary)
        self.assertTrue(FORMATS["pptx"].binary)


if __name__ == "__main__":
    unittest.main()
