"""Integrity, phase separation, and replay tests for v2.3-alpha2.1."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import audit_search_plan_v23_alpha2_1_functional_relation_refinement_offline as audit
from tools import run_search_plan_v23_alpha2_1_functional_relation_refinement_offline as run


class FunctionalRelationRefinementIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.phase1, cls.decisions, cls.digest = run.build_phase1()

    def test_frozen_audits_are_exact_and_predate_phase1(self):
        expected = audit.build_outputs()
        self.assertEqual(set(expected), audit.AUDIT_FILES)
        self.assertTrue(all((run.RUN / name).read_bytes() == body for name, body in expected.items()))
        self.assertEqual(json.loads(expected["alpha2_direct_blocker_audit.json"])["packet_count"], 14)
        unresolved = json.loads(expected["alpha2_direct_unresolved_audit.json"])
        self.assertEqual(unresolved["packet_count"], 15)
        self.assertEqual(unresolved["generic_fixable_count"], 5)

    def test_phase1_is_preacquisition_only_and_has_70_unique_records(self):
        self.assertEqual(len(self.decisions), 70)
        self.assertEqual(len({row["packet_id"] for row in self.decisions}), 70)
        forbidden = {"tier", "relevance_state", "contaminant_class", "development_failure_families"}
        for row in self.decisions:
            self.assertFalse(set(row) & forbidden)
            self.assertTrue(row["decision"]["preacquisition_only"])
            self.assertTrue(row["shadow_only"])

    def test_phase1_does_not_call_retrospective_join(self):
        with patch.object(run, "join_after_freeze", side_effect=AssertionError("label leak")):
            run.build_phase1()

    def test_phase1_replay_and_frozen_bytes_are_identical(self):
        again, decisions, digest = run.build_phase1()
        self.assertEqual((self.phase1, self.decisions, self.digest), (again, decisions, digest))
        frozen, frozen_digest = run.load_frozen_phase1()
        body = b"".join(run.alpha1.frozen.canonical_json(row) + b"\n" for row in frozen)
        self.assertEqual(body, self.phase1["v23_alpha2_1_relation_shadow_decisions.jsonl"])
        self.assertEqual(frozen_digest, self.digest)

    def test_exact_six_state_taxonomy_is_preserved(self):
        self.assertEqual(set(run.EVIDENCE_STATES), {
            "DIRECT_FUNCTIONAL", "FUNCTIONAL_CHAIN", "ASSOCIATION_ONLY", "BACKGROUND_ONLY",
            "MULTI_TARGET_AMBIGUOUS", "UNRESOLVED",
        })

    def test_comparison_has_all_required_populations(self):
        frozen, digest = run.load_frozen_phase1()
        phase2, summary = run.build_phase2(frozen, digest)
        comparison = json.loads(phase2["alpha2_vs_alpha2_1_comparison.json"])
        expected = {"all_70": 70, "direct_32": 32, "tier_a_direct_24": 24,
                    "tier_a_nondirect_11": 11, "tier_b_direct_8": 8,
                    "functional_relation_unresolved_24": 24}
        self.assertEqual({name: value["N"] for name, value in comparison["subsets"].items()}, expected)
        self.assertEqual(comparison["alpha2_direct_blocker_state"], 14)
        self.assertEqual(comparison["alpha2_tier_a_direct_blocker_state"], 11)
        self.assertEqual(summary["alpha2_1_direct_blocker_state"], comparison["alpha2_1_direct_blocker_state"])

    def test_counterfactuals_and_cross_module_do_not_activate_precedence(self):
        frozen, digest = run.load_frozen_phase1()
        phase2, _ = run.build_phase2(frozen, digest)
        counterfactual = json.loads(phase2["counterfactual_policy_comparison.json"])
        self.assertFalse(counterfactual["production_activation"])
        self.assertIsNone(counterfactual["selected_for_production"])
        for candidate in ("candidate_a", "candidate_b", "candidate_c"):
            effect = counterfactual[candidate]["effects"]
            self.assertEqual(effect["total_affected"] + effect["unaffected"], 70)
        cross = json.loads(phase2["cross_module_shadow_analysis.json"])
        self.assertFalse(cross["cross_module_precedence_created"])
        self.assertFalse(cross["composite_score_created"])

    def test_production_specific_rule_audit_is_zero_and_detects_injection(self):
        frozen, _ = run.load_frozen_phase1()
        joined = run.join_after_freeze(frozen)
        self.assertEqual(run.heldout_specific_rule_audit(joined)["production_case_specific_rules"], 0)
        with tempfile.TemporaryDirectory(dir=run.ROOT) as directory:
            path = Path(directory) / "production.py"
            path.write_text("if packet_id == 'heldout_rrpv1_0001':\n    pass\n")
            with patch.object(run, "PRODUCTION_FILES", [path]):
                self.assertGreater(run.heldout_specific_rule_audit(joined)["production_case_specific_rules"], 0)

    def test_upstream_hashes_and_historical_manifest_are_exact(self):
        self.assertEqual(audit.verify_upstreams()["v23_alpha2_functional_relation_shadow_sha256"],
                         audit.ALPHA2_ROOT)
        historical = run.historical_manifest_audit()
        self.assertEqual(historical["status"], "PASS")
        self.assertFalse(historical["historical_manifest_modified"])

    def test_output_membership_manifest_and_replay_are_exact(self):
        self.assertEqual(len(run.REQUIRED), 19)
        self.assertEqual({path.name for path in run.RUN.iterdir()}, run.REQUIRED)
        self.assertTrue(all(path.is_file() and not path.is_symlink() for path in run.RUN.iterdir()))
        outputs = {name: (run.RUN / name).read_bytes() for name in run.REQUIRED}
        manifest = json.loads(outputs["implementation_manifest.json"])
        expected = run.REQUIRED - {"implementation_manifest.json", "summary.json"}
        self.assertEqual({row["path"] for row in manifest["aggregate_components"]}, expected)
        pairs = []
        for row in manifest["aggregate_components"]:
            self.assertEqual(row["sha256"], run.alpha1.frozen.digest(outputs[row["path"]]))
            pairs.append([row["path"], row["sha256"]])
        self.assertEqual(manifest["v23_alpha2_1_functional_relation_refinement_sha256"],
                         run.alpha1.frozen.digest(run.alpha1.frozen.canonical_json(pairs)))
        self.assertEqual(run.generate_and_freeze(), outputs)


if __name__ == "__main__":
    unittest.main()
