import unittest

import code_engine.normalization.entity_type as types
from code_engine.normalization.candidates import EntityCandidate


class GenericEntityTypeTests(unittest.TestCase):
    def test_no_pilot_type_rules_and_priority(self):
        self.assertFalse(hasattr(types, "TYPE_RULES"))
        self.assertEqual(types.infer_entity_type_candidates("anything", l1_entity_type_hint="compound")[0]["entity_type"], "compound")
        external = EntityCandidate(surface="x", normalized_surface="x", canonical_id="G:1", canonical_name="X", entity_type="gene", source="external", provider_name="fake", is_grounded=True, overall_score=.9)
        self.assertEqual(types.infer_entity_type_candidates("x", provider_candidates=[external])[0]["entity_type"], "gene")
        self.assertEqual(types.classify_entity_type("MTOR", "mtor"), "unknown")
        self.assertEqual(types.infer_entity_type_candidates("ordinary phrase"), [])


if __name__ == "__main__": unittest.main()
