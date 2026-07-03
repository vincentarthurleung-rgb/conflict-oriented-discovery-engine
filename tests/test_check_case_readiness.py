import os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from code_engine.validation.readiness import check_case_readiness

class ReadinessTests(unittest.TestCase):
    def test_missing_llm_env_blocks_before_execution(self):
        with patch.dict(os.environ, {}, clear=True):
            report=check_case_readiness("configs/case_profiles/metformin_ampk_cancer.case_profile.json","configs/search_plans/metformin_ampk_cancer_2000_2020.llm_v1.frozen.json")
        self.assertFalse(report["ready"]); self.assertIn("missing L1_PROVIDER",report["blocking_reasons"])
    def test_fixture_lincs_summary_is_detected(self):
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ,{"L1_PROVIDER":"deepseek","MODEL_NAME":"m","DEEPSEEK_API_KEY":"x"},clear=True):
            root=Path(td); index=root/"lincs_l1000/index/GSE70138"; index.mkdir(parents=True)
            (index/"metformin_index_summary.json").write_text('{"selected_signature_count":42,"selected_gene_count":978,"compact_matrix_orientation":"signatures_x_genes"}')
            (index/"metformin_top_genes.jsonl").write_text("{}\n")
            report=check_case_readiness("configs/case_profiles/metformin_ampk_cancer.case_profile.json","configs/search_plans/metformin_ampk_cancer_2000_2020.llm_v1.frozen.json",root)
        self.assertEqual(report["resources"][0]["index_summary"]["selected_signature_count"],42)
