import tempfile, unittest
from pathlib import Path
from code_engine.workflow.runtime_provenance import build_runtime_provenance

class TemporalFilterProvenanceTests(unittest.TestCase):
    def test_runtime_filter_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp); (run / "artifacts").mkdir()
            filt = {"enabled": True, "paper_year_from": None, "paper_year_to": 2015, "temporal_role": "discovery", "source": "cli_argument", "hardcoded_cutoff_used": False}
            value = build_runtime_provenance(run, repository_root=Path.cwd(), resume_explicit=False, entity_registry_path=None,
                automatic_pilot_registry=False, l1_mode="abstract_screening", l1_task_cache_enabled=False,
                update_global_corpus=False, paper_registry_enabled=True, coverage_precheck=False,
                allow_coverage_short_circuit=False, merge_knowledge_store=False, update_global_knowledge_store=False,
                execute=False, paper_year_filter=filt)
        self.assertEqual(value["paper_year_filter"], filt)
        self.assertFalse(value["temporal_filter_violation_detected"])

if __name__ == "__main__": unittest.main()
