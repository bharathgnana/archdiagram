"""Byte snapshots of the shipped examples without an optional icon cache."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from archdiagram.emit.drawio import NATIVE, PORTABLE, emit_drawio
from archdiagram.emit.pdf import emit_pdf
from archdiagram.emit.pptx import emit_pptx
from archdiagram.emit.svg import render_html, render_svg
from archdiagram.emit.vsdx import emit_vsdx
from archdiagram.rasterize.resvg import pdf_bridge_available
from archdiagram.spec.validate import load_spec

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "tests" / "golden"
EXAMPLES = (
    "sample_spec", "azure_foundry", "aws_kelvin", "gcp_agentic",
    "workflow_swimlane",
)
FORMATS = ("portable.drawio", "native.drawio", "svg", "html", "vsdx", "pptx")


def render_example(name: str, fmt: str) -> bytes:
    diagram = load_spec(str(ROOT / "examples" / f"{name}.json"))
    with tempfile.TemporaryDirectory() as empty_icons:
        # Keep snapshots independent of downloaded icons on a developer's PC.
        with patch("archdiagram.registry.icons._candidate_dirs", return_value=[empty_icons]):
            if fmt == "portable.drawio":
                return emit_drawio(diagram, mode=PORTABLE).encode("utf-8")
            if fmt == "native.drawio":
                return emit_drawio(diagram, mode=NATIVE).encode("utf-8")
            if fmt == "svg":
                return render_svg(diagram)[0].encode("utf-8")
            if fmt == "html":
                return render_html(diagram)[0].encode("utf-8")
            with tempfile.TemporaryDirectory() as output_dir:
                output = Path(output_dir) / f"out.{fmt}"
                if fmt == "vsdx":
                    emit_vsdx(diagram, str(output))
                elif fmt == "pptx":
                    emit_pptx(diagram, str(output))
                else:
                    emit_pdf(diagram, str(output))
                return output.read_bytes()


class TestShippedExamplesGolden(unittest.TestCase):
    def test_all_examples_match_bytes(self):
        for name in EXAMPLES:
            for fmt in FORMATS:
                with self.subTest(example=name, format=fmt):
                    expected = (GOLDEN / f"{name}.{fmt}").read_bytes()
                    self.assertEqual(render_example(name, fmt), expected)

    def test_pdf_examples_match_bytes_when_bridge_available(self):
        if not pdf_bridge_available():
            self.skipTest("optional Node PDF bridge is not installed")
        for name in EXAMPLES:
            with self.subTest(example=name):
                expected = (GOLDEN / f"{name}.pdf").read_bytes()
                self.assertEqual(render_example(name, "pdf"), expected)


if __name__ == "__main__":
    if "--update" in sys.argv:
        GOLDEN.mkdir(parents=True, exist_ok=True)
        for example in EXAMPLES:
            formats = FORMATS + (("pdf",) if pdf_bridge_available() else ())
            for fmt in formats:
                path = GOLDEN / f"{example}.{fmt}"
                path.write_bytes(render_example(example, fmt))
                print(path.relative_to(ROOT))
    else:
        unittest.main()
