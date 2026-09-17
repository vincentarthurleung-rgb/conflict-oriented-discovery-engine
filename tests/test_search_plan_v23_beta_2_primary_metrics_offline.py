"""Focused tests for primary held-out-v2 merge and metric unblinding."""

import hashlib
import json
import unittest
from unittest.mock import patch

from tools import calculate_search_plan_v23_beta_2_primary_heldout_v2_metrics_offline as metrics


class PrimaryHeldoutV2MetricsTests(unittest.TestCase):
    def test_all_roots_and_metrics_spec_lineage_verify(self):
        value = metrics.verify_all_roots()
        self.assertEqual(value["status"], "PASS")
        self.assertTrue(value["all_roots_match"])
        self.assertFalse(value["metrics_spec_v2_modified"])

    def test_merge_is_exact_one_to_one(self):
        rows, audit = metrics.build_merged_records()
        self.assertEqual(len(rows), 60)
        self.assertEqual(len({row["candidate_id"] for row in rows}), 60)
        self.assertEqual(audit["missing_PASS_A"], 0)
        self.assertEqual(audit["missing_PASS_B"], 0)
        self.assertEqual(audit["duplicate_candidate_ids"], 0)
        self.assertEqual(audit["cross_pass_identity_conflicts"], 0)

    def test_metric_replay_is_byte_identical_and_offline(self):
        roots = metrics.verify_all_roots()
        protected = metrics.protected_state()
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            first = metrics.build_metric_outputs(roots, protected)
            second = metrics.build_metric_outputs(roots, protected)
        self.assertEqual(first, second)
        self.assertEqual(set(first), metrics.REQUIRED_OUTPUTS)
        self.assertEqual(protected, metrics.protected_state())

    def test_primary_and_contaminant_metrics_match_frozen_predicates(self):
        summary = json.loads((metrics.RUN / "summary.json").read_bytes())
        primary = summary["primary_metrics"]
        self.assertEqual((primary["overall_direct_relevance"]["n"], primary["overall_direct_relevance"]["N"]), (2, 60))
        self.assertEqual((primary["overall_acquisition_justification"]["n"], primary["overall_acquisition_justification"]["N"]), (1, 60))
        self.assertEqual((primary["overall_acquisition_acceptability"]["n"], primary["overall_acquisition_acceptability"]["N"]), (2, 60))
        contaminant = summary["contaminant_metrics"]
        self.assertEqual(contaminant["biological_unit_contamination_rate"]["n"], 27)
        self.assertEqual(contaminant["functional_relation_contamination_rate"]["n"], 12)
        self.assertEqual(contaminant["endpoint_contamination_rate"]["n"], 8)

    def test_zero_denominator_cases_are_undefined(self):
        values = json.loads((metrics.RUN / "per_case_metrics.json").read_bytes())
        for case_id, metadata in (("heldout_v2_104", 180), ("heldout_v2_107", 0)):
            self.assertEqual(values[case_id]["adjudicated_acquired_N"], 0)
            self.assertEqual(values[case_id]["direct"]["status"], "UNDEFINED_ZERO_DENOMINATOR")
            self.assertIsNone(values[case_id]["direct"]["fraction"])
            self.assertEqual(values[case_id]["structural_retrieval"], {"metadata": metadata, "selected": 0, "acquired": 0})

    def test_first_contributing_family_uses_frozen_first_seen_order(self):
        trace = {row["candidate_id"]: row for row in json.loads(
            (metrics.RETRIEVAL / "retrieval_provenance_trace.json").read_bytes()
        )["traces"]}
        rows = metrics.load_jsonl(metrics.RUN / metrics.MERGED_NAME)
        for row in rows:
            self.assertEqual(
                row["first_contributing_query_family_id"],
                trace[row["candidate_id"]]["frozen_query_provenance"][0]["family_id"],
            )

    def test_aggregate_root_covers_exact_components(self):
        manifest = json.loads((metrics.RUN / "implementation_manifest.json").read_bytes())
        pairs = []
        for name, expected in manifest["aggregate_components"]:
            actual = metrics.sha(metrics.RUN / name)
            self.assertEqual(actual, expected)
            pairs.append([name, actual])
        self.assertEqual(
            hashlib.sha256(metrics.canonical(pairs)).hexdigest(),
            manifest["primary_heldout_v2_metrics_unblinding_sha256"],
        )


if __name__ == "__main__":
    unittest.main()
