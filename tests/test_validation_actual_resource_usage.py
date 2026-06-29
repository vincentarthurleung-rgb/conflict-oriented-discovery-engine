import tempfile
import unittest
from pathlib import Path

from code_engine.schemas.validation import ExternalEvidenceRecord, ValidationQueryPlan, ValidationResourcePolicy, ValidationSignal
from code_engine.validation.base import AbstractValidator
from code_engine.validation.execution import execute_validation_query_plans
from code_engine.validation.registry import ValidatorRegistry


class UsageValidator(AbstractValidator):
    name = "UsageValidator"
    source_database = "fixture"
    def __init__(self, **_): pass
    def stream_evidence(self, plan, context):
        for sequence in range(3):
            yield ExternalEvidenceRecord(evidence_id=f"E{sequence}", validator_name=self.name, source_database="fixture", query_plan_id=plan.query_plan_id, anchor_id=plan.anchor_id, evidence_type="fixture", raw_payload_ref=plan.query_context["raw_path"])
    def build_signals(self, evidence_stream, context):
        for evidence in evidence_stream:
            yield ValidationSignal(signal_id=f"S{evidence.evidence_id}", validator_name=self.name, source_database="fixture", query_plan_id=evidence.query_plan_id, anchor_id=evidence.anchor_id, signal_type="fixture", quality=.8, confidence=.8)


class ValidationActualResourceUsageTests(unittest.TestCase):
    def test_actual_usage_and_truncation(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw.json"
            raw.write_bytes(b"1234567890")
            plan = ValidationQueryPlan(query_plan_id="P", anchor_id="A", validator_name="UsageValidator", query_type="fixture", query_context={"raw_path":str(raw)}, execution_mode="local_index", status="allowed", max_records=2, max_signals=5, max_raw_payload_bytes=5)
            registry = ValidatorRegistry(); registry.register(UsageValidator)
            result = execute_validation_query_plans([plan], registry, ValidationResourcePolicy(external_validation_enabled=True), execute=True, run_dir=Path(tmp))
            self.assertEqual(result.actual_records_seen, 3)
            self.assertEqual(result.actual_evidence_written, 2)
            self.assertGreater(result.actual_jsonl_bytes_written, 0)
            self.assertGreater(result.actual_query_seconds, 0)
            self.assertTrue(result.per_query_actual_stats["P"]["truncated"])
            self.assertTrue((Path(tmp) / "validation_resource_usage.json").exists())


if __name__ == "__main__": unittest.main()
