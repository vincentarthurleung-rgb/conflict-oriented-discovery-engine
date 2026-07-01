import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.runtime_provenance import build_runtime_provenance, contamination_check


class StaticWeightProvenanceTests(unittest.TestCase):
    def test_static_weight_provenance_false_and_true_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp); (run / "artifacts").mkdir()
            provenance = build_runtime_provenance(run, repository_root=Path.cwd(), resume_explicit=False,
                entity_registry_path=None, automatic_pilot_registry=False, l1_mode="abstract_screening",
                l1_task_cache_enabled=False, update_global_corpus=False, paper_registry_enabled=True,
                coverage_precheck=False, allow_coverage_short_circuit=False, merge_knowledge_store=False,
                update_global_knowledge_store=False, execute=False)
        self.assertFalse(provenance["static_journal_weight_used"])
        self.assertFalse(provenance["belief_weight_used_for_reasoning"])
        self.assertFalse(provenance["impact_factor_used_for_reasoning"])
        contaminated = {**provenance, "belief_weight_used_for_reasoning": True, "warnings": []}
        self.assertIn("static_belief_weight_used_in_core_reasoning", contamination_check(contaminated)["blocking_reasons"])


if __name__ == "__main__": unittest.main()
