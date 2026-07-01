import unittest
from pathlib import Path

from code_engine.evidence_graph.builders import normalize_observation_to_evidence_edge


class NoStaticJournalWeightCoreTests(unittest.TestCase):
    def test_evidence_graph_ignores_belief_weight_and_static_csv(self):
        base = {"paper_id": "P", "subject_canonical_id": "A", "object_canonical_id": "B",
                "direction": "increase", "evidence_sentence": "A increased B."}
        context = {"run_id": "R", "topic_id": None, "query_id": "Q"}
        low = normalize_observation_to_evidence_edge({**base, "belief_weight": 0.1}, {}, context)
        high = normalize_observation_to_evidence_edge({**base, "belief_weight": 0.99}, {}, context)
        self.assertIsNone(low.confidence)
        self.assertEqual(low.confidence, high.confidence)
        source = Path("src/code_engine/evidence_graph/builders.py").read_text()
        self.assertNotIn("literature_quality_audit.csv", source)


if __name__ == "__main__": unittest.main()
