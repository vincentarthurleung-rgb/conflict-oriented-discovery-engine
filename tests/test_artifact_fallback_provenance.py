import json
import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.runtime_provenance import build_runtime_provenance


class ArtifactFallbackProvenanceTests(unittest.TestCase):
    def test_nonempty_old_l2_fallback_is_reported(self):
        root=Path(__file__).parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp); (run/"artifacts").mkdir()
            (run/"artifacts/l2_observations.json").write_text(json.dumps([{"observation_id":"O"}]))
            report=build_runtime_provenance(run,repository_root=root,resume_explicit=False,entity_registry_path=None,automatic_pilot_registry=True,l1_mode="abstract_screening",l1_task_cache_enabled=False,update_global_corpus=False,paper_registry_enabled=False,coverage_precheck=False,allow_coverage_short_circuit=False,merge_knowledge_store=False,update_global_knowledge_store=False,execute=False)
        self.assertIn("l2_observations.json",report["legacy_artifacts_read"])
        self.assertIn("legacy_artifact_fallback_read_explicitly_reported",report["warnings"])


if __name__ == "__main__": unittest.main()
