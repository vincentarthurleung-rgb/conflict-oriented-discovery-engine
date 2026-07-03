import json,tempfile,unittest
from pathlib import Path
from code_engine.cli.export_case_bundle import export_case_bundle

class ManifestSyncTests(unittest.TestCase):
    def test_canonical_counts_win_and_missing_optional_fields_warn(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); run=root/"runs/source_rebuilt"; artifacts=run/"artifacts"; artifacts.mkdir(parents=True)
            profile=json.loads(Path("configs/case_profiles/metformin_ampk_cancer.case_profile.json").read_text())
            files={
                "case_domain_profile.json":profile,
                "validator_selection_report.json":{"validator_selection":{"executed_validators":["lincs_l1000"],"recommended_but_unavailable":[]}},
                "pipeline_stage_summary.json":{"status":"completed"},
                "l7_external_validation_summary.json":{"status":"partially_completed","matched_signature_count":42,"validation_target_count":6,"overall_validation_score":0.507738,"interpretation_distribution":{"supportive":0,"mixed":6,"insufficient":0}},
                "l7_lincs_validation_summary.json":{"matched_signature_count":42,"validation_target_count":6,"overall_validation_score":0.507738,"interpretation_distribution":{"supportive":0,"mixed":6,"insufficient":0}},
                "hypothesis_summary.json":{"formal_hypothesis_count":0,"manual_review_followup_count":2,"abstract_only_followup_count":2,"display_hypothesis_count":0,"display_followup_count":2},
                "graph_conflict_summary.json":{"true_graph_conflict_count":0},
                "core_observation_summary.json":{"core_observation_count":3},
                "l35_fulltext_retrieval_summary.json":{"status":"not_enabled","candidate_paper_count":0},
                "l35_fulltext_l1_summary.json":{"fulltext_l1_claim_count":0},
                "l35_fulltext_conflict_confirmation_summary.json":{"status":"not_enabled","fulltext_confirmed_conflict_count":0},
            }
            for name,value in files.items(): (artifacts/name).write_text(json.dumps(value))
            for name in ("validator_selection_report.md","whitebox_case_report.md"): (artifacts/name).write_text("ok")
            _,manifest=export_case_bundle(run,"configs/case_profiles/metformin_ampk_cancer.case_profile.json",root/"bundles")
            self.assertTrue(manifest["ready_for_system_b"]); self.assertEqual(manifest["manual_review_followup_count"],2); self.assertEqual(manifest["formal_hypothesis_count"],0); self.assertEqual(manifest["true_graph_conflict_count"],0); self.assertEqual(manifest["fulltext_confirmation_status"],"not_enabled")
            self.assertEqual(manifest["matched_signature_count"],42); self.assertEqual(manifest["external_validation_interpretation"],"mixed")
            self.assertIn("hypothesis_summary_missing_field: high_confidence_hypothesis_count",manifest["bundle_export_warnings"])

    def test_missing_optional_artifacts_do_not_crash(self):
        with tempfile.TemporaryDirectory() as td:
            run=Path(td)/"run"; (run/"artifacts").mkdir(parents=True)
            _,manifest=export_case_bundle(run,"configs/case_profiles/metformin_ampk_cancer.case_profile.json",Path(td)/"bundles")
            self.assertIn("missing_artifact: hypothesis_summary.json",manifest["bundle_export_warnings"])
