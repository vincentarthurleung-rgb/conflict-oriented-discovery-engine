import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.runtime_provenance import build_runtime_provenance


class GlobalEvidenceIsolationTests(unittest.TestCase):
    def test_post_reasoning_merge_plan_is_not_pre_reasoning_injection(self):
        root=Path(__file__).parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            report=build_runtime_provenance(Path(tmp),repository_root=root,resume_explicit=False,entity_registry_path=None,automatic_pilot_registry=True,l1_mode="abstract_screening",l1_task_cache_enabled=True,update_global_corpus=False,paper_registry_enabled=True,coverage_precheck=False,allow_coverage_short_circuit=False,merge_knowledge_store=True,update_global_knowledge_store=False,execute=False)
        self.assertTrue(report["global_store_read"])
        self.assertFalse(report["global_evidence_injected_before_reasoning"])
        self.assertFalse(report["global_store_write"])


if __name__ == "__main__": unittest.main()
