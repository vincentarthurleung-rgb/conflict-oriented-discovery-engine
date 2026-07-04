import tempfile
import unittest
from pathlib import Path

from code_engine.encoder.models import SemanticIntakeResult
from code_engine.encoder.seed_quality import validate_seed_triple
from tests.case_factory_test_support import generate


class SemanticRobustnessTests(unittest.TestCase):
    def test_nullable_lists_are_normalized(self):
        value=SemanticIntakeResult.model_validate({"research_intent":{"raw_user_input":"x","verification_warnings":None,
            "comparison_entities":None,"outcome_entities":None,"intervention_entities":None,"mechanism_entities":None,
            "disease_or_condition":None,"context_terms":None},"domain_routing":{"alternative_domains":None},
            "seed_triples":None,"search_concepts":None,"recommended_search_queries":None,"negative_filters":None,
            "ambiguities":None,"warnings":None,"verification_warnings":None})
        self.assertEqual(value.verification_warnings,[]); self.assertEqual(value.seed_triples,[])
        self.assertEqual(value.research_intent.comparison_entities,[]); self.assertEqual(value.domain_routing.alternative_domains,[])

    def test_stopword_object_is_invalid(self):
        result=validate_seed_triple({"subject":{"name":"Entity-X"},"relation":{"name":"associated"},
            "object":{"name":"has"},"confidence":.9})
        self.assertFalse(result["valid"]); self.assertEqual(result["quality"],"invalid")

    def test_degraded_blocks_by_default_and_override_marks_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); blocked=generate(root,allow_degraded_intake=False)
            self.assertEqual(blocked["status"],"CASE_FACTORY_BLOCKED_SEMANTIC_INTAKE")
            allowed=generate(root,overwrite_generated=True,allow_degraded_intake=True)
            self.assertTrue(allowed["semantic_intake_degraded"]); self.assertFalse(allowed["full_run_recommended"])

    def test_frozen_metadata_complete(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); generate(root)
            plan=json.loads((root/"generated/generic_case/search_plan.frozen.json").read_text())
            for key in ("case_id","case_type","planner_mode","model","query_count","paper_year_from","paper_year_to","generated_at","human_reviewed"):
                self.assertIn(key,plan)
