import unittest

from code_engine.system_b.dashboard import DashboardAPI


class DashboardSummaryProjectionTests(unittest.TestCase):
    def setUp(self): self.api = DashboardAPI("system_b_outputs", "system_b_outputs/kg")

    def test_default_overview_collapses_provenance_and_unavailable_validators(self):
        _, graph = self.api.dispatch("/api/graph/overview")
        types = {item["data"]["type"] for item in graph["nodes"]}
        self.assertNotIn("evidence", types); self.assertNotIn("paper", types)
        validators = [item["data"] for item in graph["nodes"] if item["data"]["type"] == "validator"]
        self.assertFalse(any(item.get("metadata", {}).get("status") == "recommended_unavailable" for item in validators))
        claim = next(item["data"] for item in graph["edges"] if item["data"]["edge_type"] == "claim_relation")
        self.assertEqual(claim["evidence_count"], 1); self.assertIn("evidence_sentence", claim["evidence"][0])

    def test_triple_search_is_minimal_focused_subgraph(self):
        _, graph = self.api.dispatch("/api/triple/search", {"subject": ["metformin"], "object": ["AMPK"]})
        self.assertLessEqual(len(graph["nodes"]), 6)
        self.assertEqual({item["data"]["id"] for item in graph["nodes"]}, {"entity:metformin", "entity:ampk"})
        self.assertTrue(all(item["data"]["edge_type"] == "claim_relation" for item in graph["edges"]))

    def test_debug_explicitly_returns_raw_labels(self):
        _, graph = self.api.dispatch("/api/graph/overview", {"detail": ["debug"]})
        self.assertEqual(graph["detail"], "debug")
        self.assertEqual(graph["warning"], "Debug graph may be visually cluttered.")
        self.assertTrue(any(len(item["data"]["label"]) > 32 for item in graph["nodes"]))


if __name__ == "__main__": unittest.main()
