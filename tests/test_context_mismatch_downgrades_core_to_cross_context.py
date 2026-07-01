import unittest
from types import SimpleNamespace

from code_engine.normalization.layered_grounding import RuntimeEntityHint, decide_l2_evidence_layer


HINTS = [RuntimeEntityHint("metformin", ("metformin",), "compound", "seed_subject", "test", .95),
         RuntimeEntityHint("AMPK", ("AMPK",), "protein", "seed_object", "test", .95),
         RuntimeEntityHint("cancer", ("cancer",), "context", "context", "test", .8)]
RESOLVED = SimpleNamespace(allow_high_confidence_graph_use=True, confidence=.95)


class ContextMismatchLayerTests(unittest.TestCase):
    def test_cardiac_evidence_is_retained_outside_core(self):
        sentence = "Metformin suppressed CHMP2B accumulation and ameliorated H/R dysfunction by activating AMPK."
        result = decide_l2_evidence_layer({"evidence_sentence": sentence, "subject_raw": "metformin", "object_raw": "AMPK", "confidence": .9},
                                          RESOLVED, RESOLVED, None, None, HINTS,
                                          seed_triple={"relation": {"family": "activates"}, "context": {"terms": ["cancer"]}},
                                          paper_metadata={"title": "Metformin-Enhanced Cardiac AMPK Pathways"})
        self.assertTrue(result["retained"])
        self.assertEqual(result["graph_layer"], "cross_context_mechanism_layer")
        self.assertFalse(result["canonical_graph_eligible"])
        self.assertEqual(result["excluded_from_core_reason"], "context_mismatch")
        self.assertEqual(result["direct_relation_sign"], 1)


if __name__ == "__main__": unittest.main()
