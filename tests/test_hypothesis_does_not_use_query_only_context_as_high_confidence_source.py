import tempfile
import unittest
from pathlib import Path

from code_engine.hypothesis.search import run_hypothesis_search_for_run


class HypothesisQueryOnlyGateTests(unittest.TestCase):
    def test_query_only_observation_cannot_be_high_confidence_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = Path(tmp) / "artifacts"; artifacts.mkdir()
            (artifacts / "l2_abstract_observations.jsonl").write_text(
                '{"observation_id":"O1","context_compatibility_status":"context_query_only","core_context_eligible":false,"canonical_graph_eligible":false}\n')
            result = run_hypothesis_search_for_run({}, {}, {}, Path(tmp), dry_run=False)
            self.assertEqual(result["hypothesis_high_confidence_count"], 0)
            self.assertEqual(result["graph_conflict_candidates_used"], 0)


if __name__ == "__main__": unittest.main()
