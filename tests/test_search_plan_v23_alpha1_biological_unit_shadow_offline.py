"""Outcome separation, integrity, and replay tests for v2.3-alpha1 shadow analysis."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import run_search_plan_v23_alpha1_biological_unit_shadow_offline as shadow


class OutcomeBlindPhaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.phase1, cls.decisions = shadow.build_phase1()

    def test_phase1_has_exactly_70_unique_allowlisted_inputs(self):
        inputs = shadow.parse_preacquisition_batches()
        self.assertEqual(len(inputs), 70)
        self.assertEqual(len({row["packet_id"] for row in inputs}), 70)
        self.assertTrue(all(set(row) == shadow.ALLOWED_PHASE1_INPUT_KEYS for row in inputs))
        self.assertTrue(all(not (set(row) & shadow.FORBIDDEN_PHASE1_KEYS) for row in inputs))

    def test_shadow_records_do_not_contain_phase2_labels(self):
        self.assertEqual(len(self.decisions), 70)
        for row in self.decisions:
            self.assertFalse(set(row) & shadow.FORBIDDEN_PHASE1_KEYS)
            self.assertEqual(row["phase"], shadow.PHASE1_STATUS)
            self.assertTrue(row["decision"]["preacquisition_only"])
            self.assertTrue(row["shadow_only"])

    def test_phase1_replay_is_byte_identical(self):
        again, decisions = shadow.build_phase1()
        self.assertEqual(self.phase1, again)
        self.assertEqual(self.decisions, decisions)
        self.assertEqual(
            self.phase1["v23_alpha1_shadow_decisions_sha256"].decode().strip(),
            shadow.frozen.digest(self.phase1["v23_alpha1_shadow_decisions.jsonl"]),
        )

    def test_policy_and_registry_snapshots_are_physical_bytes(self):
        self.assertEqual(self.phase1["biological_unit_registry_snapshot.json"],
                         shadow.frozen.pretty_json(shadow._load(shadow.REGISTRY_PATH)))
        self.assertEqual(self.phase1["biological_unit_policy_snapshot.json"],
                         shadow.frozen.pretty_json(shadow._load(shadow.POLICY_PATH)))

    def test_label_loader_is_not_called_by_phase1(self):
        with patch.object(shadow, "join_development_labels", side_effect=AssertionError("phase2 leak")):
            shadow.build_phase1()


class IntegrityAndAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.phase1, cls.generated = shadow.build_phase1()
        cls.joined = shadow.join_development_labels(cls.generated)

    def test_error_analysis_root_and_all_upstreams_verify(self):
        self.assertTrue(shadow.verify_error_analysis_root()["match"])
        self.assertTrue(all(item["match"] for item in shadow.verify_all_roots().values()))

    def test_wrong_root_stops_before_phase1_input_parse(self):
        with patch.object(shadow, "ERROR_ANALYSIS_HASH", "0" * 64), \
             patch.object(shadow, "parse_preacquisition_batches") as parse:
            with self.assertRaisesRegex(RuntimeError, "root mismatch"):
                shadow.verify_all_roots()
            parse.assert_not_called()

    def test_component_tamper_is_rejected(self):
        manifest = shadow._load(shadow.ERROR_RUN / "manifest.json")
        corrupt = shadow.ERROR_RUN / manifest["components"][0]["path"]
        original = shadow.frozen.sha256
        with patch.object(shadow.frozen, "sha256",
                          side_effect=lambda path: "f" * 64 if path == corrupt else original(path)):
            with self.assertRaisesRegex(RuntimeError, "component mismatch"):
                shadow.verify_error_analysis_root()

    def test_phase2_join_is_packet_identity_only_and_complete(self):
        self.assertEqual(len(self.joined), 70)
        self.assertEqual(
            [row["packet_id"] for row in self.joined],
            [row["packet_id"] for row in self.generated],
        )

    def test_required_subsets_and_counterfactual_arithmetic(self):
        capture = shadow.build_failure_capture(self.joined)
        direct = shadow.build_direct_safety(self.joined)
        counterfactual = shadow.build_counterfactual(self.joined)
        self.assertEqual(capture["N"], 21)
        self.assertEqual(direct["N"], 32)
        for group in [counterfactual["all_papers"], counterfactual["direct_papers"],
                      counterfactual["wrong_biological_unit"], *counterfactual["by_tier"].values(),
                      *counterfactual["by_case"].values()]:
            self.assertEqual(group["retained"] + group["rejected"], group["total"])
            self.assertEqual(len(group["retained_packet_ids"]), group["retained"])
            self.assertEqual(len(group["rejected_packet_ids"]), group["rejected"])

    def test_production_heldout_specific_rule_audit_is_zero(self):
        audit = shadow.heldout_specific_rule_audit(self.joined)
        self.assertEqual(audit["production_case_specific_rules"], 0)
        self.assertEqual(audit["findings"], [])

    def test_audit_detects_injected_case_specific_production_token(self):
        with tempfile.TemporaryDirectory(dir=shadow.ROOT) as directory:
            path = Path(directory) / "production.py"
            path.write_text("if case_id == 'heldout_v1_001':\n    pass\n")
            with patch.object(shadow, "PRODUCTION_FILES", [path]):
                audit = shadow.heldout_specific_rule_audit(self.joined)
            self.assertGreater(audit["production_case_specific_rules"], 0)

    def test_phase2_replay_is_byte_identical(self):
        phase2_a, summary_a = shadow.build_phase2(self.generated, "a" * 64)
        phase2_b, summary_b = shadow.build_phase2(self.generated, "a" * 64)
        self.assertEqual(phase2_a, phase2_b)
        self.assertEqual(summary_a, summary_b)

    def test_final_manifest_hash_covers_nonrecursive_result_components(self):
        phase2, summary = shadow.build_phase2(self.generated, "a" * 64)
        roots = {"test": {"match": True}}
        outputs = shadow.build_final_outputs(self.phase1, phase2, summary, roots, {}, {})
        self.assertEqual(set(outputs), shadow.REQUIRED)
        manifest = json.loads(outputs["implementation_manifest.json"])
        self.assertEqual(
            {item["path"] for item in manifest["aggregate_components"]},
            shadow.REQUIRED - {"implementation_manifest.json", "summary.json"},
        )
        pairs = []
        for item in manifest["aggregate_components"]:
            self.assertEqual(item["sha256"], shadow.frozen.digest(outputs[item["path"]]))
            pairs.append([item["path"], item["sha256"]])
        self.assertEqual(manifest["v23_alpha1_biological_unit_shadow_sha256"],
                         shadow.frozen.digest(shadow.frozen.canonical_json(pairs)))

    def test_complete_output_build_replays_byte_identically(self):
        phase2_a, summary_a = shadow.build_phase2(self.generated, "a" * 64)
        phase2_b, summary_b = shadow.build_phase2(self.generated, "a" * 64)
        first = shadow.build_final_outputs(self.phase1, phase2_a, summary_a, {}, {}, {})
        second = shadow.build_final_outputs(self.phase1, phase2_b, summary_b, {}, {}, {})
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
