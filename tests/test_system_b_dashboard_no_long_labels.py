import unittest

from code_engine.system_b.dashboard import DashboardAPI


class DashboardNoLongLabelsTests(unittest.TestCase):
    def setUp(self): self.api = DashboardAPI("tests/fixtures/system_b_dashboard_outputs", "tests/fixtures/system_b_dashboard_outputs/kg")

    def test_overview_has_only_short_canvas_labels(self):
        _, graph = self.api.dispatch("/api/graph/overview")
        self.assertTrue(graph["nodes"])
        self.assertTrue(all(len(item["data"]["label"]) <= 32 for item in graph["nodes"]))
        self.assertTrue(all(item["data"]["label"] == item["data"]["short_label"] for item in graph["nodes"]))
        self.assertTrue(all(item["data"]["label"] == "" for item in graph["edges"]))

    def test_entity_neighborhood_has_no_sentence_labels(self):
        _, graph = self.api.dispatch("/api/entity/entity:ampk/neighborhood", {"depth": ["1"]})
        self.assertLessEqual(len(graph["nodes"]), 10)
        self.assertTrue(all(len(item["data"]["label"]) <= 32 for item in graph["nodes"]))


if __name__ == "__main__": unittest.main()
