import json
import unittest

from tools import freeze_search_plan_v23_beta_2_primary_heldout_v2_neutral_review_offline as freeze


class PrimaryHeldoutV2NeutralReviewFreezeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protected = freeze.protected_state()
        cls.outputs = freeze.build_outputs(cls.protected)

    def test_generation_is_byte_deterministic(self):
        self.assertEqual(self.outputs, freeze.build_outputs(self.protected))

    def test_required_counts_and_hashes(self):
        summary = json.loads(self.outputs["summary.json"])
        self.assertEqual(summary["selected_paper_count"], 60)
        self.assertEqual(summary["pass_a_view_count"], 60)
        self.assertEqual(summary["pass_a_content_changes"], 0)
        self.assertEqual(summary["pass_b_view_count"], 60)
        self.assertEqual(summary["pass_a_batch_count"], 6)
        self.assertEqual(summary["pass_b_batch_count"], 6)
        self.assertEqual(
            summary["pass_a_source_sha256"],
            freeze.EXPECTED["primary_v2_pass_a_blinded_views_sha256"],
        )

    def test_no_labels_metrics_or_forbidden_exposure(self):
        leakage = json.loads(self.outputs["review_surface_leakage_audit.json"])
        validation = json.loads(self.outputs["validation.json"])
        self.assertEqual(leakage["forbidden_exposure_findings"], 0)
        self.assertTrue(validation["checks"]["pass_b_views_frozen_before_pass_a_labels"])
        self.assertTrue(validation["checks"]["pass_a_labels_created_zero"])
        self.assertTrue(validation["checks"]["pass_b_labels_created_zero"])

    def test_zero_yield_reporting_is_frozen(self):
        audit = json.loads(self.outputs["zero_yield_case_reporting_audit.json"])
        self.assertEqual(
            [(row["case_id"], row["metadata_record_count"], row["selected_paper_count"])
             for row in audit["cases"]],
            [("heldout_v2_104", 180, 0), ("heldout_v2_107", 0, 0)],
        )
        self.assertTrue(audit["zero_denominator_behavior_explicitly_defined"])

    def test_output_batch_files_are_physical_and_exact(self):
        for key in ("primary_v2_pass_a_batch_manifest.json", "primary_v2_pass_b_batch_manifest.json"):
            manifest = json.loads(self.outputs[key])
            self.assertEqual([row["record_count"] for row in manifest["batches"]], [10] * 6)
            for row in manifest["batches"]:
                self.assertIn(row["path"], self.outputs)
                self.assertEqual(freeze.sha_bytes(self.outputs[row["path"]]), row["sha256"])


if __name__ == "__main__":
    unittest.main()
