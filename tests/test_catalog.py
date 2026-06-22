import unittest

from archdiagram.registry.catalog import get_catalog


class TestCatalog(unittest.TestCase):
    def setUp(self):
        self.catalog = get_catalog()

    def test_vendors_present(self):
        for v in ("aws", "azure", "gcp", "kubernetes"):
            self.assertIn(v, self.catalog.vendors)

    def test_lookup_known(self):
        entry = self.catalog.lookup("azure.aks")
        self.assertIsNotNone(entry)
        self.assertEqual(entry.vendor, "azure")
        self.assertTrue(entry.icon)
        self.assertTrue(entry.accent.startswith("#"))

    def test_lookup_unknown(self):
        self.assertIsNone(self.catalog.lookup("nope.nothing"))

    def test_search_matches(self):
        results = self.catalog.search("aks")
        services = {e.service for e in results}
        self.assertIn("azure.aks", services)

    def test_search_empty(self):
        self.assertEqual(self.catalog.search("   "), [])


if __name__ == "__main__":
    unittest.main()
