import tempfile
import unittest
from pathlib import Path

from code_engine.hypothesis.search import run_hypothesis_search_for_run


class HypothesisRunAdapterTests(unittest.TestCase):
    def test_adapter_never_invokes_global_stage6(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_hypothesis_search_for_run({"conflict_edge_count": 1}, {"edges": [{"has_conflict": True}], "paths": [{"path_id": "p"}]}, {"domain_id": "general_biomedical"}, Path(tmp), dry_run=False)
            self.assertEqual(result["status"], "blocked")
            self.assertTrue(result["mechanism_graph_used"])
            self.assertEqual(result["conflicted_mechanism_edge_count"], 1)
            self.assertIn("legacy_stage6_run_scoped_callable_missing", result["reason"])


if __name__ == "__main__": unittest.main()
