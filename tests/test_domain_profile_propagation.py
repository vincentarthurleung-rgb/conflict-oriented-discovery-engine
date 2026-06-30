import unittest

from code_engine.domain.router import default_domain_router
from code_engine.normalization.resolver import ResolverCascade
from code_engine.query.intent import parse_research_intent
from code_engine.query.search_planner import build_literature_search_plan
from code_engine.schemas.l1_extraction import L1ExtractedClaim
from code_engine.validation.planner import build_validation_plan


class DomainProfilePropagationTests(unittest.TestCase):
    def test_profile_reaches_each_adaptive_boundary(self):
        intent = parse_research_intent("domain: neuropharmacology ketamine depression mechanism")
        profile = default_domain_router().resolve(intent.domain_id)
        search = build_literature_search_plan(intent, domain_profile=profile)
        claim = L1ExtractedClaim(
            claim_id="C1", paper_id="P1", chunk_id="CH1", chunk_hash="hash",
            domain_id=profile.domain_id, subdomain_id=profile.subdomain_id or "",
            domain_profile_id=profile.profile_id, prompt_profile_id=profile.prompt_profile_id,
            prompt_version=profile.prompt_version,
            output_schema_version=profile.output_schema_version,
            extraction_policy_version=profile.extraction_policy_version,
            model_name="fake-model", compiled_prompt_hash="compiled",
            validator_profile_id=profile.validator_profile_id,
            required_context_slots=list(profile.required_context_slots),
            subject_raw="ketamine", object_raw="BDNF",
            evidence_sentence="Ketamine increased BDNF in mouse cortex.",
            species="mouse", treatment="ketamine", assay_or_readout="protein assay",
        )
        decision = ResolverCascade(
            domain_id=profile.domain_id,
            entity_registry_profile=profile.entity_registry_profile,
            resolver_policy_id=profile.resolver_policy_id,
        ).resolve_entity("BDNF")
        validation = build_validation_plan(
            {"hypothesis_id": "H1", "seed_pair": "ketamine -> BDNF"},
            profile,
            relation_type="drug_gene_expression",
        )

        self.assertEqual(intent.domain_profile_id, profile.profile_id)
        self.assertEqual(search.source_domain_profile["validator_profile_id"], profile.validator_profile_id)
        self.assertEqual(claim.validator_profile_id, profile.validator_profile_id)
        self.assertTrue(claim.missing_required_context_slots)
        self.assertEqual(decision.entity_registry_profile, profile.entity_registry_profile)
        self.assertEqual(decision.entity_resolution_status, "unresolved")
        self.assertFalse(decision.allow_high_confidence_graph_use)
        self.assertEqual(validation.validator_profile_id, profile.validator_profile_id)


if __name__ == "__main__":
    unittest.main()
