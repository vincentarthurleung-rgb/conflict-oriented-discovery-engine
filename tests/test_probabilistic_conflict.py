import json
import unittest
from pathlib import Path

from code_engine.graph.probabilistic_conflict import compute_probabilistic_conflict_state


FIXTURE = json.loads((Path(__file__).parent / "fixtures/v42_minimal.json").read_text())


class ProbabilisticConflictTests(unittest.TestCase):
    def test_state_is_normalized_and_preserves_legacy_label(self):
        state = compute_probabilistic_conflict_state(FIXTURE["conflict_edge"])
        total = state.p_conflict + state.p_context_dependent + state.p_noise_or_low_support + state.p_time_or_condition_dependent + state.p_uncontested
        self.assertAlmostEqual(total, 1.0, places=5)
        self.assertEqual(state.legacy_conflict_type, "Type I")
        self.assertIn("heuristic", state.posterior_source)


if __name__ == "__main__": unittest.main()
