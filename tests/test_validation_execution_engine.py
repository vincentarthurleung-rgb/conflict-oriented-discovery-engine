import json
import tempfile
import unittest
from pathlib import Path

from code_engine.schemas.validation import ValidationQueryPlan, ValidationResourcePolicy
from code_engine.validation.execution import execute_validation_query_plans
from code_engine.validation.registry import ValidatorRegistry
from code_engine.validation.cache import ValidationQueryCache
from code_engine.schemas.validation import ExternalEvidenceRecord


class ValidationExecutionEngineTests(unittest.TestCase):
    def local_plan(self):
        fixture=Path(__file__).parent/"fixtures/validation_indexes/chembl.jsonl"
        return ValidationQueryPlan(query_plan_id="P",anchor_id="A",validator_name="ChEMBLValidator",query_type="binding_activity_check",query_entities=[{"canonical_id":"CHEM:SIROLIMUS"},{"canonical_id":"GENE:MTOR"}],query_context={"index_path":str(fixture),"index_type":"jsonl"},execution_mode="local_index",index_name="chembl",status="allowed",max_records=5,max_signals=5)

    def test_dry_run_and_local_streaming(self):
        registry=ValidatorRegistry().register_defaults(); policy=ValidationResourcePolicy(external_validation_enabled=True)
        with tempfile.TemporaryDirectory() as tmp:
            dry=execute_validation_query_plans([self.local_plan()],registry,policy,run_dir=Path(tmp))
            self.assertEqual((dry.status,dry.evidence_count),("planned",0))
            result=execute_validation_query_plans([self.local_plan()],registry,policy,execute=True,run_dir=Path(tmp))
            self.assertEqual((result.evidence_count,result.signal_count),(1,1))
            self.assertEqual(len((Path(tmp)/"external_validation_evidence.jsonl").read_text().splitlines()),1)

    def test_no_network_remote_is_blocked(self):
        plan=self.local_plan().model_copy(update={"execution_mode":"remote_api"})
        result=execute_validation_query_plans([plan],ValidatorRegistry().register_defaults(),ValidationResourcePolicy(external_validation_enabled=True),execute=True,network_enabled=False)
        self.assertEqual(result.executed_query_count,0)
        self.assertEqual(result.blocked_query_count,1)

    def test_cache_only_uses_cached_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=ValidationQueryCache(Path(tmp)/"validation_query_cache.sqlite")
            plan=self.local_plan().model_copy(update={"execution_mode":"cache_only","cache_key":"K"})
            record=ExternalEvidenceRecord(evidence_id="E",validator_name="ChEMBLValidator",source_database="ChEMBL",query_plan_id="P",anchor_id="A",evidence_type="binding_activity_record",score=.8)
            cache.store("K",[record])
            result=execute_validation_query_plans([plan],ValidatorRegistry().register_defaults(),ValidationResourcePolicy(cache_dir=tmp),execute=True,cache_enabled=True,run_dir=Path(tmp))
            self.assertEqual(result.cache_hit_count,1)
            self.assertEqual(result.evidence_count,1)


if __name__ == "__main__": unittest.main()
