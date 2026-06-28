import unittest

from code_engine.query.intent import parse_research_intent
from code_engine.query.search_planner import build_literature_search_plan
from code_engine.query.seed_triples import SeedResearchTriple


class DomainSpecificSearchPlannerTests(unittest.TestCase):
    def query_text(self, text):
        intent = parse_research_intent(text)
        plan = build_literature_search_plan(intent)
        return plan, " ".join(item.query_string for item in plan.pubmed_queries).casefold()

    def test_domain_templates(self):
        neuro, neuro_text = self.query_text("ketamine depression mechanism")
        self.assertEqual(neuro.domain_id, "neuropharmacology")
        self.assertIn("bdnf", neuro_text)
        clinical, clinical_text = self.query_text("esketamine treatment-resistant depression clinical efficacy")
        self.assertIn("randomized controlled trial", clinical_text)
        binding, binding_text = self.query_text("ketamine NMDA receptor binding affinity")
        self.assertIn("ic50", binding_text)

    def test_seed_triples_are_query_metadata_not_evidence(self):
        intent = parse_research_intent("ketamine depression mechanism")
        seed = SeedResearchTriple(
            triple_id="seed-1", subject="ketamine", relation="affects", object="BDNF",
            source="user_intent", planning_only=True,
        )
        plan = build_literature_search_plan(intent, seed_triples=[seed])
        payload = plan.model_dump()
        self.assertIn("seed-1", {item for query in payload["mechanism_queries"] for item in query["from_seed_triples"]})
        self.assertNotIn("evidence_ids", payload)


if __name__ == "__main__":
    unittest.main()
