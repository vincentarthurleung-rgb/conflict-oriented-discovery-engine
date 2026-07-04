import json
import tempfile
import unittest
from pathlib import Path

from code_engine.query.search_planner import LiteratureSearchQuery
from code_engine.search.discovery_planning import DIRECTIONAL_PATTERN, NEUTRAL_RELATIONS, assess_discovery_queries
from code_engine.search.search_plan_replay import load_frozen_search_plan
from tests.case_factory_test_support import generate


CONTRAST_QUERY="Mediator-X suppresses cell proliferation in an early context but promotes migration in an advanced disease context."


class DiscoveryNeutralPlanningTests(unittest.TestCase):
    def test_conflict_case_is_neutral_balanced_and_context_preserving(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); manifest=generate(root,query=CONTRAST_QUERY)
            payload=json.loads((root/"generated/generic_case/search_plan.frozen.json").read_text())
            seed=payload["seed_triple"]
            self.assertIn(seed["relation"]["family"],NEUTRAL_RELATIONS)
            self.assertNotIn(seed["object"]["name"].casefold(),{"suppresses","promotes"})
            self.assertIn("context-dependent role",payload["intended_context_terms"])
            self.assertGreaterEqual(payload["query_count"],3)
            self.assertTrue(payload["discovery_query_balance_valid"]); self.assertTrue(manifest["discovery_query_balance_valid"])
            self.assertTrue({"entity_pair_core","mechanism_context","context_coverage"}.issubset(payload["discovery_query_groups"]))
            self.assertTrue(all(not DIRECTIONAL_PATTERN.search(q["query_string"]) for q in payload["pubmed_queries"]))
            load_frozen_search_plan(root/"generated/generic_case/search_plan.frozen.json",fail_if_drift=True)

    def test_one_query_is_high_risk(self):
        query=LiteratureSearchQuery(query_id="q",query_string="Entity disease biology",purpose="entity_pair_core",query_group="entity_pair_core")
        quality=assess_discovery_queries([query])
        self.assertFalse(quality["discovery_query_balance_valid"]); self.assertEqual(quality["one_sided_retrieval_risk"],"high")
