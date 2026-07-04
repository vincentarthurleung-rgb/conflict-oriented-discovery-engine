import json
import tempfile
import unittest
from pathlib import Path
from code_engine.search.search_plan_replay import load_frozen_search_plan
from tests.case_factory_test_support import generate

class CaseFactoryFrozenPlanTests(unittest.TestCase):
    def test_frozen_plan_loads_with_existing_loader(self):
        with tempfile.TemporaryDirectory() as tmp:
            generate(Path(tmp)); path=Path(tmp)/"generated/generic_case/search_plan.frozen.json"
            payload=json.loads(path.read_text()); self.assertEqual(payload["artifact_schema_version"],"frozen_search_plan.v1")
            self.assertTrue(payload["frozen"]); plan,replay=load_frozen_search_plan(path,fail_if_drift=True)
            self.assertTrue(plan.pubmed_queries); self.assertFalse(replay["search_plan_drift_detected"])
