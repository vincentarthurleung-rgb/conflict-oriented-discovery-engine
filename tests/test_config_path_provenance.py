import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.runtime_provenance import build_runtime_provenance


class ConfigPathProvenanceTests(unittest.TestCase):
    def test_canonical_config_path_is_recorded(self):
        root=Path(__file__).parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            report=build_runtime_provenance(Path(tmp),repository_root=root,resume_explicit=False,entity_registry_path=root/"configs/normalization/entity_registry.json",automatic_pilot_registry=False,l1_mode="abstract_screening",l1_task_cache_enabled=False,update_global_corpus=False,paper_registry_enabled=False,coverage_precheck=False,allow_coverage_short_circuit=False,merge_knowledge_store=False,update_global_knowledge_store=False,execute=False)
        self.assertFalse(report["legacy_config_used"])
        self.assertEqual(report["config_files_used"], [str(root/"configs/normalization/entity_registry.json")])


if __name__ == "__main__": unittest.main()
