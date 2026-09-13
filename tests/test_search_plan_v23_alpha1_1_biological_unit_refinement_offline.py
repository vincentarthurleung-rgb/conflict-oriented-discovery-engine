"""Integrity, separation, and replay tests for V1_1 outcome-informed development."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import audit_search_plan_v23_alpha1_1_biological_unit_refinement_offline as audit
from tools import run_search_plan_v23_alpha1_1_biological_unit_refinement_offline as run


class FrozenAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.outputs = audit.build_audit_outputs()

    def test_alpha1_roots_are_exact(self):
        result = audit.verify_alpha1()
        self.assertEqual(result["alpha1_root"], audit.ALPHA1_ROOT)
        self.assertEqual(result["alpha1_shadow_decisions_sha256"], audit.ALPHA1_SHADOW)

    def test_all_11_incompatible_records_have_required_trace(self):
        data = json.loads(self.outputs["alpha1_incompatible_decision_audit.json"])
        self.assertEqual(data["packet_count"], 11)
        self.assertEqual(data["classification_counts"], {
            "DIRECT_PAPER_FALSE_INCOMPATIBILITY": 1,
            "NONDIRECT_BUT_NOT_UNIT_FAILURE": 1,
            "TRUE_UNIT_INCOMPATIBILITY_CAPTURE": 9,
        })
        required = {"packet_id", "case_id", "tier", "target_context_qualifiers",
                    "target_biological_unit_interpretation", "preacquisition_observed_unit_surfaces",
                    "resolved_observed_units", "cell_identity_state", "anatomical_region_state",
                    "overall_state", "reason_codes", "registry_relations_used", "policy_rules_used",
                    "frozen_retrospective", "retrospective_incompatibility_classification"}
        self.assertTrue(all(required <= set(row) for row in data["records"]))

    def test_direct_false_incompatibility_has_generic_root_cause(self):
        data = json.loads(self.outputs["alpha1_incompatible_decision_audit.json"])
        deep = data["direct_false_incompatibility_deep_audit"]
        self.assertEqual(deep["cause_scope"], "generic_context_dimension_and_applicability_failure")
        self.assertFalse(deep["packet_specific_repair_justified"])
        self.assertTrue(deep["generic_applicability_fix_justified"])
        self.assertEqual(deep["alpha1_reason_codes"], ["DISTINCT_CELL_TYPE"])

    def test_all_12_unresolved_wrong_unit_records_are_not_forced(self):
        data = json.loads(self.outputs["alpha1_unresolved_wrong_unit_audit.json"])
        self.assertEqual(data["packet_count"], 12)
        self.assertEqual(sum(data["reason_distribution"].values()), 12)
        self.assertTrue(data["no_forced_incompatible_decisions"])
        self.assertTrue(all(not row["force_to_incompatible"] for row in data["records"]))

    def test_only_two_generic_changes_are_implemented(self):
        data = json.loads(self.outputs["alpha1_refinement_decision.json"])
        implemented = [row["change_id"] for row in data["changes"] if row["implemented"]]
        self.assertEqual(implemented, ["V1_1_CONTEXT_DIMENSION_APPLICABILITY",
                                       "V1_1_POSITIVE_INCOMPATIBILITY_PRECONDITIONS"])
        self.assertEqual(data["registry_relations_added_or_changed"], [])


class ReplayAndSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.phase1, cls.decisions, cls.digest = run.build_phase1()
        cls.frozen_records, cls.frozen_digest = run.load_frozen_phase1()
        cls.phase2, cls.summary = run.build_phase2(cls.frozen_records, cls.frozen_digest)

    def test_phase1_is_70_unique_preacquisition_records(self):
        self.assertEqual(len(self.decisions), 70)
        self.assertEqual(len({row["packet_id"] for row in self.decisions}), 70)
        for row in self.decisions:
            self.assertTrue(row["decision"]["preacquisition_only"])
            self.assertTrue(row["shadow_only"])
            self.assertNotIn("relevance_state", row)
            self.assertNotIn("contaminant_class", row)
            self.assertNotIn("tier", row)

    def test_phase1_does_not_call_post_freeze_join(self):
        with patch.object(run, "join_after_freeze", side_effect=AssertionError("label leak")):
            run.build_phase1()

    def test_phase1_and_frozen_bytes_are_identical(self):
        again, decisions, digest = run.build_phase1()
        self.assertEqual(self.phase1, again)
        self.assertEqual(self.decisions, decisions)
        self.assertEqual(self.digest, digest)
        body = b"".join(run.alpha1.frozen.canonical_json(row) + b"\n" for row in self.frozen_records)
        self.assertEqual(body, self.phase1["v23_alpha1_1_shadow_decisions.jsonl"])
        self.assertEqual(self.frozen_digest, self.digest)

    def test_comparison_preserves_requested_totals_and_safety(self):
        comparison = json.loads(self.phase2["alpha1_vs_alpha1_1_comparison.json"])
        self.assertEqual(comparison["all_70"]["N"], 70)
        self.assertEqual(comparison["wrong_biological_unit_21"]["N"], 21)
        self.assertEqual(comparison["directly_relevant_32"]["N"], 32)
        self.assertEqual(comparison["alpha1_direct_incompatible"], 1)
        self.assertEqual(comparison["alpha1_1_direct_incompatible"], 0)
        self.assertEqual(comparison["alpha1_wrong_unit_incompatible"], 9)
        self.assertEqual(comparison["alpha1_1_wrong_unit_incompatible"], 9)

    def test_counterfactuals_do_not_activate_policy(self):
        data = json.loads(self.phase2["counterfactual_policy_comparison.json"])
        self.assertFalse(data["production_activation"])
        self.assertIsNone(data["selected_for_production"])
        self.assertEqual(data["candidate_a"]["retained_papers"] + data["candidate_a"]["rejected_papers"], 70)
        self.assertEqual(data["candidate_b"]["retained_papers"], 70)
        self.assertEqual(data["candidate_c"]["retained_papers"], 70)

    def test_production_specific_rule_audit_zero_and_detects_injection(self):
        joined = run.join_after_freeze(self.frozen_records)
        self.assertEqual(run.heldout_specific_rule_audit(joined)["production_case_specific_rules"], 0)
        with tempfile.TemporaryDirectory(dir=run.ROOT) as directory:
            path = Path(directory) / "production.py"
            path.write_text("if case_id == 'heldout_v1_001':\n    pass\n")
            with patch.object(run, "PRODUCTION_FILES", [path]):
                self.assertGreater(run.heldout_specific_rule_audit(joined)["production_case_specific_rules"], 0)

    def test_v1_sources_and_alpha1_frozen_outputs_are_unchanged(self):
        self.assertEqual(run.verify_v1_immutability(), run.verify_v1_immutability())
        before = run.alpha1_run_hashes()
        audit.verify_alpha1()
        self.assertEqual(before, run.alpha1_run_hashes())

    def test_final_manifest_aggregate_is_nonrecursive_and_exact(self):
        outputs = {name: (run.RUN / name).read_bytes() for name in run.REQUIRED}
        manifest = json.loads(outputs["implementation_manifest.json"])
        self.assertEqual({row["path"] for row in manifest["aggregate_components"]},
                         run.REQUIRED - {"implementation_manifest.json", "summary.json"})
        pairs = []
        for row in manifest["aggregate_components"]:
            self.assertEqual(row["sha256"], run.alpha1.frozen.digest(outputs[row["path"]]))
            pairs.append([row["path"], row["sha256"]])
        self.assertEqual(manifest["v23_alpha1_1_biological_unit_refinement_sha256"],
                         run.alpha1.frozen.digest(run.alpha1.frozen.canonical_json(pairs)))

    def test_complete_existing_output_replay_is_byte_identical(self):
        before = {name: (run.RUN / name).read_bytes() for name in run.REQUIRED}
        self.assertEqual(run.generate_and_freeze(), before)
        self.assertEqual(before, {name: (run.RUN / name).read_bytes() for name in run.REQUIRED})


if __name__ == "__main__":
    unittest.main()
