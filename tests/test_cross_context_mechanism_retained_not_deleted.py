import unittest

from tests.test_context_mismatch_downgrades_core_to_cross_context import HINTS, RESOLVED
from code_engine.normalization.layered_grounding import decide_l2_evidence_layer


class CrossContextRetentionTests(unittest.TestCase):
    def test_heterotopic_ossification_is_retained_outside_cancer_core(self):
        result = decide_l2_evidence_layer(
            {"evidence_sentence": "Metformin prevents heterotopic ossification via activation of AMPK.", "subject_raw": "metformin", "object_raw": "AMPK", "confidence": .9},
            RESOLVED, RESOLVED, None, None, HINTS,
            seed_triple={"relation": {"family": "activates"}, "context": {"terms": ["cancer"]}},
            query_record={"query": "metformin AMPK cancer", "context_strict": True},
            paper_metadata={"title": "Metformin attenuates trauma-induced heterotopic ossification"})
        self.assertTrue(result["retained"])
        self.assertEqual(result["graph_layer"], "cross_context_mechanism_layer")
        self.assertFalse(result["canonical_graph_eligible"])


if __name__ == "__main__": unittest.main()
