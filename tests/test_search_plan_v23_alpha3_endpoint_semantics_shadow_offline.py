"""Integrity, isolation, and replay tests for v2.3-alpha3 EndpointSemanticsV1."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import run_search_plan_v23_alpha3_endpoint_semantics_shadow_offline as run


class EndpointSemanticsShadowIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.phase1, cls.decisions, cls.digest = run.build_phase1()
        cls.frozen, cls.frozen_digest = run.load_frozen_phase1()
        cls.phase2, cls.summary = run.build_phase2(cls.frozen, cls.frozen_digest)

    def test_upstream_roots_are_exact(self):
        roots = run.verify_upstreams()
        self.assertEqual(roots["v22_to_v23_error_analysis_sha256"], run.ERROR_ROOT)
        self.assertEqual(roots["v23_alpha1_1_biological_unit_refinement_sha256"], run.ALPHA1_1_ROOT)
        self.assertEqual(roots["v23_alpha2_1_functional_relation_refinement_sha256"], run.ALPHA2_1_ROOT)
        self.assertEqual(roots["v23_alpha2_1_relation_shadow_decisions_sha256"], run.ALPHA2_1_SHADOW)

    def test_phase1_has_70_unique_allowlisted_records(self):
        self.assertEqual(len(self.decisions), 70)
        self.assertEqual(len({row["packet_id"] for row in self.decisions}), 70)
        forbidden = {"tier", "relevance_state", "contaminant_class", "development_failure_families"}
        for row in self.decisions:
            self.assertFalse(set(row) & forbidden)
            self.assertTrue(row["decision"]["preacquisition_only"])
            self.assertTrue(row["shadow_only"])

    def test_phase1_does_not_call_retrospective_join(self):
        with patch.object(run, "join_after_freeze", side_effect=AssertionError("retrospective leak")):
            run.build_phase1()

    def test_phase1_replay_and_frozen_bytes_are_identical(self):
        again, decisions, digest = run.build_phase1()
        self.assertEqual((self.phase1, self.decisions, self.digest), (again, decisions, digest))
        body = b"".join(run.alpha1.frozen.canonical_json(row) + b"\n" for row in self.frozen)
        self.assertEqual(body, self.phase1["v23_alpha3_endpoint_shadow_decisions.jsonl"])
        self.assertEqual(self.frozen_digest, self.digest)

    def test_decision_schema_and_exact_state_taxonomy(self):
        required = {
            "packet_id", "applicable", "target_endpoint_spec", "observed_endpoint_candidates",
            "entity_state", "property_state", "process_state", "molecular_state_state",
            "compartment_state", "condition_state", "response_context_state", "overall_state",
            "endpoint_evidence_role", "matched_surfaces", "reason_codes", "resolver_status",
            "registry_version", "policy_version", "decision_mode", "preacquisition_only",
        }
        self.assertEqual(set(run.ENDPOINT_STATES), {
            "EXACT", "AUTHORIZED_EQUIVALENT", "PARTIAL", "UNRESOLVED", "INCOMPATIBLE"
        })
        self.assertTrue(all(required <= set(row["decision"]) for row in self.decisions))

    def test_requested_retrospective_population_totals(self):
        capture = json.loads(self.phase2["endpoint_mismatch_capture.json"])
        direct = json.loads(self.phase2["direct_paper_safety_analysis.json"])
        tier_a_direct = json.loads(self.phase2["tier_a_direct_safety_analysis.json"])
        tier_a_nondirect = json.loads(self.phase2["tier_a_nondirect_endpoint_analysis.json"])
        tier_b = json.loads(self.phase2["tier_b_endpoint_analysis.json"])
        self.assertEqual(capture["N"], 9)
        self.assertEqual(direct["N"], 32)
        self.assertEqual(tier_a_direct["N"], 24)
        self.assertEqual(tier_a_nondirect["N"], 11)
        self.assertEqual(tier_b["tier_b_direct"]["N"], 8)

    def test_only_incompatible_is_a_retrospective_blocker(self):
        direct = json.loads(self.phase2["direct_paper_safety_analysis.json"])
        self.assertTrue(direct["partial_and_unresolved_are_not_blockers"])
        self.assertEqual(len(direct["potential_false_blockers"]),
                         direct["endpoint_state_counts"]["INCOMPATIBLE"])

    def test_counterfactuals_do_not_activate_policy(self):
        data = json.loads(self.phase2["counterfactual_policy_comparison.json"])
        self.assertFalse(data["production_activation"])
        self.assertIsNone(data["selected_for_production"])
        for candidate in ("candidate_a", "candidate_b", "candidate_c"):
            effects = data[candidate]["effects"]
            self.assertEqual(effects["total_affected"] + effects["unaffected"], 70)

    def test_cross_module_is_descriptive_only(self):
        data = json.loads(self.phase2["cross_module_shadow_analysis.json"])
        self.assertFalse(data["precedence_implemented"])
        self.assertFalse(data["composite_score_created"])
        self.assertFalse(data["final_tier_rule_created"])

    def test_specific_rule_audit_is_zero_and_detects_injection(self):
        joined = run.join_after_freeze(self.frozen)
        self.assertEqual(run.heldout_specific_rule_audit(joined)["production_case_specific_rules"], 0)
        with tempfile.TemporaryDirectory(dir=run.ROOT) as directory:
            path = Path(directory) / "endpoint_rules.py"
            path.write_text("if case_id == 'heldout_v1_001':\n    pass\n")
            with patch.object(run, "PRODUCTION_FILES", [path]):
                self.assertGreater(run.heldout_specific_rule_audit(joined)["production_case_specific_rules"], 0)

    def test_output_membership_manifest_and_complete_replay(self):
        self.assertEqual(len(run.REQUIRED), 20)
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
        self.assertEqual(manifest["v23_alpha3_endpoint_semantics_shadow_sha256"],
                         run.alpha1.frozen.digest(run.alpha1.frozen.canonical_json(pairs)))
        self.assertEqual(run.generate_and_freeze(), outputs)


if __name__ == "__main__":
    unittest.main()
