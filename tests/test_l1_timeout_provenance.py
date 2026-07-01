import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.runtime_provenance import build_runtime_provenance


class L1TimeoutProvenanceTests(unittest.TestCase):
    def test_timeout_config_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp); (run / "artifacts").mkdir()
            value = build_runtime_provenance(run, repository_root=Path.cwd(), resume_explicit=False,
                entity_registry_path=None, automatic_pilot_registry=False, l1_mode="abstract_screening",
                l1_task_cache_enabled=False, update_global_corpus=False, paper_registry_enabled=True,
                coverage_precheck=False, allow_coverage_short_circuit=False, merge_knowledge_store=False,
                update_global_knowledge_store=False, execute=False,
                l1_timeout_config={"connect_timeout_seconds": 20, "read_timeout_seconds": 180, "max_retries": 2})
        self.assertEqual(value["l1_timeout_config"]["read_timeout_seconds"], 180)
        self.assertEqual(value["abstract_l1_timeout_count"], 0)


if __name__ == "__main__": unittest.main()
