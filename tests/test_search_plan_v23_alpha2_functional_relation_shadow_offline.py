"""Integrity, phase separation, and replay tests for v2.3-alpha2."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from code_engine.search.historical_manifest_verifier import verify_frozen_manifest
from tools import run_search_plan_v23_alpha2_functional_relation_shadow_offline as run


class FunctionalRelationShadowIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.phase1, cls.decisions, cls.digest = run.build_phase1()
        cls.frozen, cls.frozen_digest = run.load_frozen_phase1()
        cls.joined = run.join_development_labels(cls.frozen)
        cls.phase2, cls.summary = run.build_phase2(cls.frozen, cls.frozen_digest)

    def test_upstream_roots_and_alpha1_1_are_exact(self):
        roots = run.alpha1.verify_all_roots()
        self.assertTrue(all(item["match"] for item in roots.values()))
        alpha1_1 = run.verify_alpha1_1_root()
        self.assertEqual(alpha1_1["root"], run.ALPHA1_1_ROOT)
        self.assertEqual(alpha1_1["shadow_decisions_sha256"], run.ALPHA1_1_SHADOW)

    def test_phase1_is_70_unique_preacquisition_records(self):
        self.assertEqual(len(self.decisions), 70)
        self.assertEqual(len({row["packet_id"] for row in self.decisions}), 70)
        forbidden = {"tier", "relevance_state", "contaminant_class", "evaluator_rationale"}
        for row in self.decisions:
            self.assertFalse(set(row) & forbidden)
            self.assertTrue(row["decision"]["preacquisition_only"])
            self.assertTrue(row["shadow_only"])

    def test_phase1_does_not_call_phase2_join(self):
        with patch.object(run, "join_development_labels", side_effect=AssertionError("label leak")):
            run.build_phase1()

    def test_phase1_replay_and_frozen_bytes_are_identical(self):
        again, decisions, digest = run.build_phase1()
        self.assertEqual(self.phase1, again)
        self.assertEqual(self.decisions, decisions)
        self.assertEqual(self.digest, digest)
        body = b"".join(run.alpha1.frozen.canonical_json(row) + b"\n" for row in self.frozen)
        self.assertEqual(body, self.phase1["v23_alpha2_relation_shadow_decisions.jsonl"])
        self.assertEqual(self.frozen_digest, self.digest)

    def test_decision_schema_and_exact_state_vocabulary(self):
        required = {
            "packet_id", "applicable", "applicability", "target_subject",
            "target_relation_family", "target_endpoint", "evidence_state", "evidence_role",
            "subject_perturbation_specificity", "response_link_state",
            "observed_subject_surfaces", "observed_endpoint_surfaces", "perturbation_polarity",
            "endpoint_response_direction", "direction_compatibility", "reason_codes",
            "source_evidence_spans_or_sentences", "resolver_status", "policy_version",
            "registry_version_if_any", "decision_mode", "preacquisition_only",
        }
        self.assertEqual(set(run.EVIDENCE_STATES), {
            "DIRECT_FUNCTIONAL", "FUNCTIONAL_CHAIN", "ASSOCIATION_ONLY", "BACKGROUND_ONLY",
            "MULTI_TARGET_AMBIGUOUS", "UNRESOLVED",
        })
        self.assertTrue(all(required <= set(row["decision"]) for row in self.decisions))

    def test_required_retrospective_totals(self):
        failure = json.loads(self.phase2["functional_relation_failure_capture.json"])
        direct = json.loads(self.phase2["direct_paper_safety_analysis.json"])
        tier_a_direct = json.loads(self.phase2["tier_a_direct_safety_analysis.json"])
        tier_a_nondirect = json.loads(self.phase2["tier_a_nondirect_analysis.json"])
        tier_b = json.loads(self.phase2["tier_b_relation_analysis.json"])
        self.assertEqual(failure["N"], 24)
        self.assertEqual(direct["N"], 32)
        self.assertEqual(tier_a_direct["N"], 24)
        self.assertEqual(tier_a_nondirect["N"], 11)
        self.assertEqual(tier_b["tier_b_direct"]["N"], 8)

    def test_counterfactuals_are_nonactivating_and_arithmetic_is_exact(self):
        data = json.loads(self.phase2["counterfactual_policy_comparison.json"])
        self.assertFalse(data["production_activation"])
        self.assertIsNone(data["selected_for_production"])
        for candidate in ("candidate_a", "candidate_b", "candidate_c"):
            effects = data[candidate]["effects"]
            self.assertEqual(effects["papers_affected"] + effects["unaffected_papers"], 70)

    def test_specific_rule_audit_is_zero_and_detects_injection(self):
        self.assertEqual(run.heldout_specific_rule_audit(self.joined)["production_case_specific_rules"], 0)
        with tempfile.TemporaryDirectory(dir=run.ROOT) as directory:
            path = Path(directory) / "production.py"
            path.write_text("if case_id == 'heldout_v1_001':\n    pass\n")
            with patch.object(run, "PRODUCTION_FILES", [path]):
                self.assertGreater(
                    run.heldout_specific_rule_audit(self.joined)["production_case_specific_rules"], 0
                )

    def test_output_membership_and_physical_files_are_exact(self):
        self.assertEqual({path.name for path in run.RUN.iterdir()}, run.REQUIRED)
        self.assertTrue(all(path.is_file() and not path.is_symlink() for path in run.RUN.iterdir()))

    def test_manifest_aggregate_is_nonrecursive_and_exact(self):
        outputs = {name: (run.RUN / name).read_bytes() for name in run.REQUIRED}
        manifest = json.loads(outputs["implementation_manifest.json"])
        expected = run.REQUIRED - {"implementation_manifest.json", "summary.json"}
        self.assertEqual({row["path"] for row in manifest["aggregate_components"]}, expected)
        pairs = []
        for row in manifest["aggregate_components"]:
            self.assertEqual(row["sha256"], run.alpha1.frozen.digest(outputs[row["path"]]))
            pairs.append([row["path"], row["sha256"]])
        self.assertEqual(
            manifest["v23_alpha2_functional_relation_shadow_sha256"],
            run.alpha1.frozen.digest(run.alpha1.frozen.canonical_json(pairs)),
        )

    def test_frozen_historical_manifest_verifies_without_current_repo_enumeration(self):
        result = verify_frozen_manifest(
            run.RUN, root_field="v23_alpha2_functional_relation_shadow_sha256"
        )
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["current_repository_membership_enumerated"])


if __name__ == "__main__":
    unittest.main()
