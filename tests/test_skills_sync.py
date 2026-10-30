"""Repository skills and locally mounted shared copies stay byte identical."""

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
NAMES = ("architecture-diagram", "process-flow", "decision-flow", "data-flow")


class TestSkillsSync(unittest.TestCase):
    def test_skill_copies_match_when_shared_library_mounted(self):
        shared = ROOT / ".claude" / "skills"
        if not shared.exists():
            self.skipTest("shared globalskills project junction is not mounted")
        for name in NAMES:
            with self.subTest(skill=name):
                source = ROOT / "skill" / name / "SKILL.md"
                copy = shared / name / "SKILL.md"
                self.assertTrue(copy.exists(), f"missing shared copy: {copy}")
                self.assertEqual(source.read_bytes(), copy.read_bytes())
                text = source.read_text(encoding="utf-8")
                self.assertIn("python -m tools.bootstrap", text)
                self.assertIn("## Spec rules", text)
                self.assertIn("## Render and inspect", text)

    def test_plugin_manifest_points_to_root(self):
        manifest = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
        marketplace = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
        self.assertEqual(manifest["mcpServers"]["archdiagram"]["cwd"], "${CLAUDE_PLUGIN_ROOT}")
        self.assertEqual(marketplace["plugins"][0]["source"], "./")


if __name__ == "__main__":
    unittest.main()
