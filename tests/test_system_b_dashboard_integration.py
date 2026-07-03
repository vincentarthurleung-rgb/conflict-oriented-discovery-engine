import unittest
from unittest.mock import patch

from code_engine.system_b.dashboard import DashboardAPI


class DashboardIntegrationTests(unittest.TestCase):
    def test_dashboard_and_kg_routes_without_external_calls(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("external call")):
            api = DashboardAPI("system_b_outputs", "system_b_outputs/kg")
            status, graph = api.dispatch("/api/graph/overview")
            self.assertEqual(status, 200); self.assertTrue(graph["nodes"])
            status, entities = api.dispatch("/api/entity/search", {"q": ["AMPK"]})
            self.assertEqual(status, 200); self.assertTrue(entities["results"])
            status, evidence = api.dispatch("/api/evidence/evidence:a821374bfaaead34")
            self.assertEqual(status, 200); self.assertEqual(evidence["case_id"], "metformin_ampk_cancer")


if __name__ == "__main__": unittest.main()
