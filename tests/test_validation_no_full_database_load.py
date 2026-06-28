import inspect
import unittest

import code_engine.validation.storage as storage
from code_engine.schemas.validation import ValidationQueryPlan, ValidationResourcePolicy
from code_engine.validation.resource_guard import check_validation_query_plan_against_policy


class ValidationNoFullDatabaseLoadTests(unittest.TestCase):
    def test_no_pandas_csv_and_broad_scan_blocked(self):
        source=inspect.getsource(storage)
        self.assertNotIn("pandas.read_csv",source)
        self.assertNotIn("pd.read_csv",source)
        plan=ValidationQueryPlan(query_plan_id="P",anchor_id="A",validator_name="V",query_type="x",query_entities=[{"canonical_id":"X"}],execution_mode="local_index",status="allowed",query_context={"requires_full_scan":True})
        checked=check_validation_query_plan_against_policy(plan,ValidationResourcePolicy())
        self.assertEqual(checked.status,"blocked")
        self.assertEqual(ValidationResourcePolicy().max_concurrent_validator_queries,1)


if __name__ == "__main__": unittest.main()
