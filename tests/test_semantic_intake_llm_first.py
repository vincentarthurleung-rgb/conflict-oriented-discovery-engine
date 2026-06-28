import unittest

from code_engine.domain.models import default_domain_profiles
from code_engine.encoder.semantic_intake import run_semantic_intake


def payload(domain="neuropharmacology", confidence=0.9, alternatives=None):
    routing = {"domain_id": domain, "domain_profile_id": domain, "confidence": confidence, "alternative_domains": alternatives or [], "reasoning_summary": "semantic match", "ambiguities": [], "warnings": [], "requires_manual_review": False}
    return {"research_intent": {"raw_user_input": "query", "language": "en", "task_type": "mechanism_overview", "research_goal": "understand mechanism", "primary_entities": ["entity"], "secondary_entities": [], "disease_or_condition": [], "mechanism_entities": [], "comparison_entities": [], "outcome_entities": [], "intervention_entities": [], "context_terms": [], "domain_routing": routing, "confidence": confidence, "ambiguities": [], "warnings": []}, "domain_routing": routing, "seed_triples": [], "search_concepts": [], "recommended_search_queries": ["entity mechanism"], "negative_filters": [], "ambiguities": [], "warnings": [], "verified": False}


class FakeLLM:
    def __init__(self, value): self.value = value
    def extract_json(self, prompt, **kwargs): return self.value


class SemanticIntakeLLMFirstTests(unittest.TestCase):
    def test_llm_domains_and_alternatives(self):
        for domain in ("neuropharmacology", "clinical_outcome"):
            result = run_semantic_intake("query", default_domain_profiles(), execute=True, api=True, llm_client=FakeLLM(payload(domain)))
            self.assertEqual(result.domain_routing.domain_id, domain)
            self.assertEqual(result.semantic_mode, "llm_semantic")
        ambiguous = run_semantic_intake("query", default_domain_profiles(), execute=True, api=True, llm_client=FakeLLM(payload(alternatives=[{"domain_id": "clinical_outcome", "confidence": 0.7}])))
        self.assertTrue(ambiguous.domain_routing.alternative_domains)

    def test_low_confidence_requires_review(self):
        result = run_semantic_intake("query", default_domain_profiles(), execute=True, api=True, llm_client=FakeLLM(payload(confidence=0.4)))
        self.assertTrue(result.domain_routing.requires_manual_review)


if __name__ == "__main__": unittest.main()
