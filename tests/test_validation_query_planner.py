import json
import tempfile
import unittest
from pathlib import Path

from code_engine.schemas.validation import ValidationAnchor, ValidationQuestion, ValidationResourcePolicy, ValidatorRoute
from code_engine.validation.cache import ValidationQueryCache, build_validation_cache_key
from code_engine.validation.query_planner import plan_validation_queries, write_validation_query_plans
from code_engine.validation.registry import ValidatorRegistry


class ValidationQueryPlannerTests(unittest.TestCase):
    def setUp(self):
        self.anchor=ValidationAnchor(anchor_id="A1",anchor_type="triple_anchor",entities=[{"canonical_id":"CHEM:SIROLIMUS","name":"sirolimus"},{"canonical_id":"GENE:MTOR","name":"MTOR"}],validation_intent="binding_activity_check")
        self.question=ValidationQuestion(question_id="Q1",anchor_id="A1",validator_intent="binding_activity_check",entities=self.anchor.entities,relation_family="drug_target_binding")
        self.route=ValidatorRoute(route_id="R1",question_id="Q1",anchor_id="A1",validator_name="ChEMBLValidator",reason="test")
        self.registry=ValidatorRegistry().register_defaults()

    def plan(self,mode,policy):
        return plan_validation_queries([self.route],[self.question],[self.anchor],self.registry,policy,mode)[0]

    def test_local_remote_cache_and_missing(self):
        fixture=Path(__file__).parent/"fixtures/validation_indexes/chembl.jsonl"
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp,"chembl.jsonl").write_text(fixture.read_text())
            local=self.plan("local_index",ValidationResourcePolicy(index_dir=tmp,max_records_per_validator=10,max_signals_per_validator=5))
            self.assertEqual((local.execution_mode,local.status),("local_index","allowed"))
            self.assertEqual((local.max_records,local.max_signals),(10,5))
            artifacts=write_validation_query_plans([local],tmp)
            self.assertTrue(Path(artifacts["plans"]).exists())
        missing=self.plan("local_index",ValidationResourcePolicy(index_dir="missing"))
        self.assertEqual(missing.status,"no_index")
        blocked=self.plan("remote_api",ValidationResourcePolicy(external_validation_enabled=True,network_enabled=False))
        self.assertEqual(blocked.status,"blocked")
        allowed=self.plan("remote_api",ValidationResourcePolicy(external_validation_enabled=True,network_enabled=True))
        self.assertEqual(allowed.status,"allowed")
        with tempfile.TemporaryDirectory() as tmp:
            cache_path=Path(tmp)/"validation_query_cache.sqlite"
            key=build_validation_cache_key("ChEMBLValidator","binding_activity_check",self.question.entities,"drug_target_binding",None,None,{},"validator_capability_v1")
            ValidationQueryCache(cache_path).store(key,[{"evidence_id":"E"}])
            cached=self.plan("cache_only",ValidationResourcePolicy(cache_dir=tmp))
            self.assertEqual(cached.status,"allowed")
        miss=self.plan("cache_only",ValidationResourcePolicy(cache_dir="missing"))
        self.assertEqual(miss.status,"no_cache")

    def test_too_broad_is_blocked(self):
        question=self.question.model_copy(update={"entities":[]})
        plan=plan_validation_queries([self.route],[question],[self.anchor],self.registry,ValidationResourcePolicy(),"auto")[0]
        self.assertEqual(plan.status,"too_broad")


if __name__ == "__main__": unittest.main()
