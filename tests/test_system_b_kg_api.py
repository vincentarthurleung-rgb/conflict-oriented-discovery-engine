import tempfile
import unittest
from pathlib import Path

from code_engine.system_b.kg import KGBuilder
from code_engine.system_b.kg.kg_api import KGAPI


class KGAPITests(unittest.TestCase):
    def test_health_and_cytoscape_response(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "kg"; KGBuilder("case_bundles", root).build(); api = KGAPI(root)
            status, health = api.dispatch("/api/health")
            self.assertEqual((status, health["status"]), (200, "OK"))
            status, graph = api.dispatch("/api/triple/search", {"subject": ["metformin"], "object": ["AMPK"]})
            self.assertEqual(status, 200); self.assertTrue(graph["edges"])
            self.assertIn("data", graph["nodes"][0]); self.assertIn("label", graph["edges"][0]["data"])


if __name__ == "__main__": unittest.main()
