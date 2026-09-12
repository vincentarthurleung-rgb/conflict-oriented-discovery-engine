"""Focused tests for frozen held-out v1 primary metrics unblinding."""

import hashlib
import json
import unittest
from unittest.mock import patch

from tools import calculate_search_plan_v22_heldout_v1_primary_metrics_offline as metrics


class PrimaryMetricsTests(unittest.TestCase):
    def test_root_failure_stops_before_primary_read(self):
        with patch.object(metrics, "verify_all_roots", side_effect=RuntimeError("root mismatch")):
            with patch.object(metrics, "read_jsonl") as reader:
                with self.assertRaises(RuntimeError):
                    metrics.generate()
                reader.assert_not_called()

    def test_replay_is_byte_identical_and_offline(self):
        before = metrics.protected_hashes()
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            first = metrics.generate()
            second = metrics.generate()
        self.assertEqual(first, second)
        self.assertEqual(before, metrics.protected_hashes())
        self.assertEqual(set(first), metrics.REQUIRED_OUTPUTS)

    def test_metric_hash_covers_exact_result_components(self):
        outputs = metrics.generate()
        manifest = json.loads(outputs["manifest.json"])
        components = manifest["metric_result_components"]
        self.assertEqual([item["path"] for item in components], metrics.METRIC_RESULT_COMPONENTS)
        pairs = []
        for item in components:
            self.assertEqual(item["sha256"], hashlib.sha256(outputs[item["path"]]).hexdigest())
            pairs.append((item["path"], item["sha256"]))
        self.assertEqual(
            manifest["heldout_v1_primary_metrics_sha256"],
            metrics.digest(metrics.canonical_json(pairs)),
        )

    def test_distributions_are_complete_and_partition_70(self):
        outputs = metrics.generate()
        for name, categories in [
            ("relevance_distribution.json", metrics.RELEVANCE_STATES),
            ("acquisition_distribution.json", metrics.ACQUISITION_DECISIONS),
            ("contaminant_distribution.json", metrics.CONTAMINANT_CLASSES),
        ]:
            value = json.loads(outputs[name])
            self.assertEqual(list(value["categories"]), sorted(categories))
            self.assertEqual(sum(item["count"] for item in value["categories"].values()), 70)

    def test_under_specified_metrics_and_heuristics_fail_closed(self):
        outputs = metrics.generate()
        primary = json.loads(outputs["primary_metrics.json"])
        self.assertEqual(
            primary["overall_acquisition_acceptability"]["status"],
            "NOT_EVALUABLE_FROM_FROZEN_DEFINITION",
        )
        tiers = json.loads(outputs["tier_metrics.json"])
        self.assertEqual(
            tiers["TIER_B"]["utility_proxy"]["status"],
            "NOT_EVALUABLE_FROM_FROZEN_DEFINITION",
        )
        heuristics = json.loads(outputs["engineering_heuristics.json"])
        self.assertTrue(
            all(
                item["status"] == "NOT_EVALUABLE_FROM_FROZEN_DEFINITION"
                for item in heuristics["heuristics"]
            )
        )
        audit = json.loads(outputs["metric_definition_audit.json"])
        self.assertEqual(audit["posthoc_primary_metric_definitions_added"], 0)
        self.assertTrue(audit["all_numeric_primary_results_have_posthoc_choice_required_false"])

    def test_ambiguity_case_counts_are_frozen(self):
        outputs = metrics.generate()
        summary = json.loads(outputs["summary.json"])
        self.assertEqual(summary["ambiguity_case_counts"], {"LOW": 2, "MEDIUM": 2, "HIGH": 4})


if __name__ == "__main__":
    unittest.main()
