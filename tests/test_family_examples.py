"""Every shipped family example renders through both public entry points."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from archdiagram.cli import main
from archdiagram.formats import FORMATS
from archdiagram.rasterize.resvg import pdf_bridge_available
from mcp_server.tools import generate_diagram


ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ("azure_architecture", "approval_process", "trade_settlement_swimlane",
            "kyc_decision_tree", "investment_data_lineage")


class TestFamilyExamples(unittest.TestCase):
    def test_cli_and_mcp_match_every_available_format(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            for name in EXAMPLES:
                source = ROOT / "examples" / f"{name}.json"
                spec = json.loads(source.read_text(encoding="utf-8"))
                for fmt in FORMATS:
                    if fmt == "pdf" and not pdf_bridge_available():
                        continue
                    with self.subTest(example=name, format=fmt):
                        cli_path = output / f"cli_{name}.{fmt}"
                        mcp_path = output / f"mcp_{name}.{fmt}"
                        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                            exit_code = main(["render", str(source), "-f", fmt,
                                              "-o", str(cli_path)])
                        self.assertEqual(exit_code, 0)
                        result = generate_diagram(spec, fmt, out_path=str(mcp_path))
                        self.assertTrue(result["ok"], result)
                        self.assertEqual(cli_path.read_bytes(), mcp_path.read_bytes())
                        self.assertGreater(result["width"], 0)
                        self.assertGreater(result["height"], 0)


if __name__ == "__main__":
    unittest.main()
