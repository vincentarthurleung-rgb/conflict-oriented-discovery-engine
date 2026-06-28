import unittest

from code_engine.domain.models import default_domain_profiles
from code_engine.encoder.semantic_intake import run_semantic_intake


class SemanticFallbackTests(unittest.TestCase):
    def test_no_api_is_degraded_and_domain_agnostic(self):
        result = run_semantic_intake("氯胺酮与抑郁症", default_domain_profiles())
        self.assertEqual(result.semantic_mode, "deterministic_degraded")
        self.assertEqual(result.domain_routing.domain_id, "general_biomedical")
        self.assertTrue(result.domain_routing.requires_manual_review)

    def test_explicit_relation_is_parsed_generically(self):
        result = run_semantic_intake("A -> B", default_domain_profiles())
        self.assertEqual((result.seed_triples[0].subject, result.seed_triples[0].object), ("A", "B"))
        self.assertFalse(result.seed_triples[0].is_evidence)


if __name__ == "__main__": unittest.main()
