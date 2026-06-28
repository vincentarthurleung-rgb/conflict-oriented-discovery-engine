import json
import unittest
from pathlib import Path

from code_engine.hypothesis.policy_search import score_mechanism_path


FIXTURE = json.loads((Path(__file__).parent / "fixtures/v42_minimal.json").read_text())


class PolicySearchTests(unittest.TestCase):
    def test_fixed_heuristic_formula(self):
        path = {"nodes": FIXTURE["hypothesis"]["core_path"], "edges": ["e1", "e2", "e3"], "evidence_strength": 0.8, "conflict_information_gain": 0.5, "context_separability": 0.6, "validation_coverage": 0.4, "novelty": 0.7, "feasibility": 0.9}
        score = score_mechanism_path(path)
        self.assertAlmostEqual(score.total_score, 0.64)
        self.assertIn("not_reinforcement_learning", score.warnings[0])


if __name__ == "__main__": unittest.main()
