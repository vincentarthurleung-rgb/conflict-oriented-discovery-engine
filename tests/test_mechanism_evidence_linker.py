import unittest

from code_engine.mechanism.evidence_linker import link_evidence_to_mechanism_edges
from code_engine.mechanism.models import MechanismEdge


class MechanismEvidenceLinkerTests(unittest.TestCase):
    def test_exact_and_paper_fallback(self):
        exact = MechanismEdge(edge_id="e1", source_node_id="a", target_node_id="b", claim_ids=["C1"], paper_ids=["P1"])
        fallback = MechanismEdge(edge_id="e2", source_node_id="a", target_node_id="c", paper_ids=["P2"])
        evidence = [{"evidence_id": "EV1", "paper_id": "P1"}, {"evidence_id": "EV2", "paper_id": "P2"}, {"evidence_id": "SEED", "paper_id": "P2", "is_evidence": False, "source": "llm_semantic_intake"}]
        linked = link_evidence_to_mechanism_edges([exact, fallback], evidence, [{"claim_id": "C1", "evidence_id": "EV1"}])
        self.assertEqual(linked[0].evidence_ids, ["EV1"])
        self.assertEqual(linked[1].evidence_ids, ["EV2"])
        self.assertIn("evidence_linked_by_paper_level_fallback", linked[1].warnings)
        self.assertNotIn("SEED", linked[1].evidence_ids)


if __name__ == "__main__": unittest.main()
