import unittest
from code_engine.hypothesis.hyperedge_builder import build_hypothesis_hyperedge


class HypothesisHyperedgeIntegrationTests(unittest.TestCase):
    def test_provenance_and_requirements_preserved(self):
        source = {"hypothesis_id": "H1", "candidate_type": "mechanism_conflict_hypothesis", "hypothesis_text": "grounded", "source_scope": "full_text", "subject_canonical_id": "S", "object_canonical_id": "O", "linked_conflict_candidate_ids": ["C"], "linked_fulltext_confirmation_ids": ["F"], "linked_mechanism_edge_ids": ["M"], "linked_evidence_ids": ["E"], "validation_requirements": [{"requirement_type": "expression_direction_check"}]}
        edge = build_hypothesis_hyperedge(source)
        self.assertEqual(edge.linked_conflict_ids, ["C"])
        self.assertEqual(edge.linked_mechanism_edge_ids, ["M"])
        self.assertIn("E", edge.evidence_ids)
        self.assertEqual(edge.validation_requirements[0]["requirement_type"], "expression_direction_check")


if __name__ == "__main__": unittest.main()
