import unittest

from archdiagram.spec.validate import SpecValidationError, validate_spec


class TestValidate(unittest.TestCase):
    def _valid(self):
        return {
            "title": "T",
            "direction": "LR",
            "groups": [{"id": "g", "label": "G", "vendor": "azure"}],
            "nodes": [
                {"id": "a", "service": "azure.aks", "group": "g"},
                {"id": "b", "service": "aws.s3"},
            ],
            "edges": [{"source": "a", "target": "b", "label": "x"}],
        }

    def test_valid_spec(self):
        d = validate_spec(self._valid())
        self.assertEqual(len(d.nodes), 2)
        self.assertEqual(len(d.edges), 1)
        self.assertEqual(d.nodes[0].vendor, "azure")
        self.assertEqual(d.nodes[0].service_key, "aks")

    def test_requires_nodes(self):
        with self.assertRaises(SpecValidationError):
            validate_spec({"nodes": []})

    def test_bad_service_format(self):
        spec = self._valid()
        spec["nodes"][0]["service"] = "azure"  # missing key
        with self.assertRaises(SpecValidationError) as ctx:
            validate_spec(spec)
        self.assertTrue(any("service" in e for e in ctx.exception.errors))

    def test_duplicate_node_id(self):
        spec = self._valid()
        spec["nodes"][1]["id"] = "a"
        with self.assertRaises(SpecValidationError) as ctx:
            validate_spec(spec)
        self.assertTrue(any("duplicate" in e for e in ctx.exception.errors))

    def test_edge_unknown_node(self):
        spec = self._valid()
        spec["edges"][0]["target"] = "missing"
        with self.assertRaises(SpecValidationError) as ctx:
            validate_spec(spec)
        self.assertTrue(any("unknown node" in e for e in ctx.exception.errors))

    def test_unknown_group(self):
        spec = self._valid()
        spec["nodes"][0]["group"] = "nope"
        with self.assertRaises(SpecValidationError):
            validate_spec(spec)

    def test_bad_direction(self):
        spec = self._valid()
        spec["direction"] = "DIAGONAL"
        with self.assertRaises(SpecValidationError):
            validate_spec(spec)

    def test_collects_multiple_errors(self):
        with self.assertRaises(SpecValidationError) as ctx:
            validate_spec({"nodes": [{"id": "", "service": "x"}], "direction": "Z"})
        self.assertGreaterEqual(len(ctx.exception.errors), 2)


if __name__ == "__main__":
    unittest.main()
