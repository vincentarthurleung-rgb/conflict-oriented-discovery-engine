import json
import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.orchestrator import run_workflow


class WorkflowDomainPropagationTests(unittest.TestCase):
    def test_neuropharmacology_reaches_plans(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            state = run_workflow("氯胺酮在抑郁症中的作用", run_dir=directory, until="validation")
            search = json.loads((directory / "artifacts/search_plan.json").read_text(encoding="utf-8"))
            l1 = json.loads((directory / "artifacts/l1_plan.json").read_text(encoding="utf-8"))
            validation = json.loads((directory / "artifacts/validation_plan.json").read_text(encoding="utf-8"))
            self.assertEqual(state.domain_id, "neuropharmacology")
            self.assertEqual(search["domain_id"], "neuropharmacology")
            self.assertEqual(l1["prompt_profile_id"], state.prompt_profile_id)
            self.assertEqual(validation["validator_profile_id"], state.validator_profile_id)


if __name__ == "__main__":
    unittest.main()
