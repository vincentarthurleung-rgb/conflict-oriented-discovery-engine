import json
import unittest
from pathlib import Path

from code_engine.hypothesis.hyperedge_builder import build_hypothesis_hyperedge


FIXTURE = json.loads((Path(__file__).parent / "fixtures/v42_minimal.json").read_text())


class HypothesisHyperedgeTests(unittest.TestCase):
    def test_legacy_hypothesis_becomes_hyperedge(self):
        edge = build_hypothesis_hyperedge(FIXTURE["hypothesis"], conflict_edges=[FIXTURE["conflict_edge"]], validation_results=[FIXTURE["validation"]], coverage_verdict="Partial_Coverage_Delta_Update_Recommended")
        self.assertGreater(len(edge.entities), 2)
        self.assertIn("MTOR", edge.mechanism_path)
        self.assertEqual(edge.coverage_status, "partial_coverage")


if __name__ == "__main__": unittest.main()
