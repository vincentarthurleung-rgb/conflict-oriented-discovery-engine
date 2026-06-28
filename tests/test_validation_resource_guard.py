import unittest

from code_engine.schemas.validation import ValidationQueryPlan, ValidationResourcePolicy
from code_engine.validation.resource_guard import check_validation_query_plan_against_policy


def plan(**updates):
    base=ValidationQueryPlan(query_plan_id="P",anchor_id="A",validator_name="V",query_type="x",query_entities=[{"canonical_id":"X"}],execution_mode="local_index",status="allowed",max_records=1000,max_signals=100,max_raw_payload_bytes=10000000,timeout_seconds=100)
    return base.model_copy(update=updates)


class ValidationResourceGuardTests(unittest.TestCase):
    def test_limits_and_scan_policy(self):
        policy=ValidationResourcePolicy(max_memory_mb=10,max_records_per_validator=10,max_records_per_anchor=20,max_signals_per_validator=3,max_raw_payload_bytes_per_validator=100,max_query_seconds=5)
        checked=check_validation_query_plan_against_policy(plan(estimated_memory_mb=20),policy)
        self.assertEqual(checked.status,"blocked")
        bounded=check_validation_query_plan_against_policy(plan(estimated_memory_mb=1,estimated_records=1000),policy)
        self.assertEqual((bounded.max_records,bounded.max_signals,bounded.max_raw_payload_bytes,bounded.timeout_seconds),(10,3,100,5))
        self.assertIn("raw_payload_truncated",bounded.warnings)
        broad=check_validation_query_plan_against_policy(plan(query_context={"requires_full_scan":True}),ValidationResourcePolicy())
        self.assertEqual(broad.status,"blocked")
        allowed=check_validation_query_plan_against_policy(plan(query_context={"requires_full_scan":True},max_records=10,max_signals=3),ValidationResourcePolicy(allow_large_local_scan=True))
        self.assertEqual(allowed.status,"allowed")
        self.assertEqual(ValidationResourcePolicy().max_concurrent_validator_queries,1)


if __name__ == "__main__": unittest.main()
