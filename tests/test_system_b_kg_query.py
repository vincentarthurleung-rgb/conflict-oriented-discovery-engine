import tempfile
import unittest
from pathlib import Path

from code_engine.system_b.kg import KGBuilder, KGQueryEngine


class KGQueryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name) / "kg"
        KGBuilder("tests/fixtures/system_b_case_bundles", self.root).build(); self.query = KGQueryEngine(self.root)

    def tearDown(self): self.temp.cleanup()

    def test_entity_and_triple_search(self):
        self.assertEqual(self.query.search_entity("AMPK")[0]["id"], "entity:ampk")
        exact = self.query.search_triples("metformin", "activates", "AMPK")
        partial = self.query.search_triples(subject="metform")
        self.assertEqual(len(exact), 3); self.assertEqual(len(partial), 3)

    def test_path_is_bounded_and_case_subgraph_is_scoped(self):
        paths = self.query.find_paths("metformin", "AMPK", max_depth=1)
        self.assertTrue(paths); self.assertTrue(all(item["length"] <= 1 for item in paths))
        contextual_paths = self.query.find_paths("metformin", "cancer", max_depth=3)
        self.assertTrue(contextual_paths); self.assertTrue(all(item["length"] <= 3 for item in contextual_paths))
        subgraph = self.query.get_case_subgraph("metformin_ampk_cancer")
        self.assertTrue(subgraph["nodes"]); self.assertTrue(subgraph["edges"])
        self.assertTrue(all(item.get("case_id") == "metformin_ampk_cancer" for item in subgraph["edges"]))
        self.assertEqual(self.query.get_case_subgraph("missing"), {"nodes": [], "edges": []})


if __name__ == "__main__": unittest.main()
