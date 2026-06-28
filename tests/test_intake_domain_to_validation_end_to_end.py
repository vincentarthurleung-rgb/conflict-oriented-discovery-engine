import unittest

from code_engine.domain.router import default_domain_router
from code_engine.extraction.l1_extractor import build_l1_dry_run_plan
from code_engine.query.intake import parse_research_intake
from code_engine.query.search_planner import build_literature_search_plan
from code_engine.validation.registry import ValidatorRegistry
from code_engine.validation.router import DomainAdaptiveValidationRouter


class IntakeDomainToValidationEndToEndTests(unittest.TestCase):
    def test_offline_domain_adaptive_planning(self):
        intake = parse_research_intake("我想了解当前氯胺酮在抑郁症中的作用", use_api=False)
        intent = intake.research_intent
        profile = default_domain_router().resolve(intent.domain_id)
        search = build_literature_search_plan(intent, seed_triples=intake.seed_triples, domain_profile=profile)
        l1 = build_l1_dry_run_plan(
            "Ketamine increased BDNF in mouse prefrontal cortex.",
            domain_profile=profile,
            cache_path="missing-cache.json",
        )
        plan = DomainAdaptiveValidationRouter().create_plan(
            {"hypothesis_id": "H1", "seed_pair": "ketamine -> BDNF"},
            profile,
            relation_type="drug_gene_expression",
        )
        previews = [
            ValidatorRegistry().register_defaults().validate(name, plan.questions[0])
            for name in plan.selected_validators
        ]

        self.assertEqual(search.domain_id, "neuropharmacology")
        self.assertEqual(l1["prompt_profile_id"], "neuropharmacology_l1_v2")
        self.assertEqual(l1["api_calls_made"], 0)
        self.assertEqual(plan.validator_profile_id, "neuropharmacology_validation")
        self.assertTrue(all(item.validation_status != "supported" for item in previews))


if __name__ == "__main__":
    unittest.main()
