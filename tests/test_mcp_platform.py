"""MCP business logic works with no MCP SDK installed."""

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp_server import tools


class TestMcpPlatform(unittest.TestCase):
    def test_catalog_templates_and_resources(self):
        names = {item["name"] for item in tools.list_templates()["templates"]}
        self.assertTrue({"architecture_diagram", "process_flow", "decision_flow", "data_flow"}
                        <= names)
        self.assertTrue(tools.list_icons("aks", provider="azure", limit=2)["icons"])
        self.assertEqual(tools.resolve_service("azure.aks")["method"], "canonical")
        self.assertGreater(tools.get_catalog_info()["icon_count"], 0)
        self.assertIn("shapes", json.loads(tools.schema_resource()))
        self.assertIn("providers", json.loads(tools.catalog_resource()))
        self.assertIn("approval", tools.describe_diagram("approval", "decision_flow"))

    def test_generate_metadata_inline_and_template_default(self):
        raw = {"title": "A&B", "nodes": [{"id": "a", "shape": "start"},
                                         {"id": "b", "shape": "end"}],
               "edges": [{"source": "a", "target": "b"}]}
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"ARCHDIAG_OUTPUT_DIR": directory}):
                result = tools.generate_diagram(raw, "svg", inline=True,
                                                template="decision_flow")
                self.assertTrue(result["ok"], result)
                self.assertEqual(result["template"], "decision_flow")
                self.assertEqual(result["nodes"], 2)
                self.assertEqual(result["bytes"], len(Path(result["path"]).read_bytes()))
                self.assertIn("A&amp;B", result["content"])
                binary = tools.generate_diagram(raw, "pptx", inline=True)
                self.assertTrue(binary["ok"], binary)
                self.assertNotIn("content", binary)
                self.assertEqual(binary["mime_type"],
                                 "application/vnd.openxmlformats-officedocument.presentationml.presentation")

    def test_server_import_when_sdk_available(self):
        if importlib.util.find_spec("mcp") is None:
            self.skipTest("optional MCP SDK is not installed")
        from mcp_server import server
        self.assertIsNotNone(server.mcp)


if __name__ == "__main__":
    unittest.main()
