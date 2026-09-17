"""Focused tests for the offline v2.3-beta.2 primary failure autopsy."""

import hashlib
import json
import unittest
from unittest.mock import patch

from tools import analyze_search_plan_v24_dev_primary_failure_autopsy_offline as autopsy


class PrimaryFailureAutopsyTests(unittest.TestCase):
    @staticmethod
    def load(name):
        return json.loads((autopsy.RUN / name).read_bytes())

    def test_authoritative_roots_verify(self):
        authority = autopsy.verify_authority()
        self.assertEqual(authority["status"], "PASS")
        self.assertEqual(authority["primary_v2_merged_results_sha256"], autopsy.EXPECTED_MERGED)
        self.assertEqual(authority["primary_heldout_v2_metrics_unblinding_sha256"], autopsy.EXPECTED_METRICS)

    def test_replay_is_byte_identical_and_offline(self):
        authority = autopsy.verify_authority()
        protected = autopsy.protected_state()
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            first = autopsy.build_outputs(authority, protected)
            second = autopsy.build_outputs(authority, protected)
        self.assertEqual(first, second)
        self.assertEqual(set(first), autopsy.REQUIRED_OUTPUTS)
        self.assertEqual(protected, autopsy.protected_state())

    def test_all_non_direct_records_have_nonexclusive_decomposition(self):
        rows = autopsy.load_jsonl(autopsy.RUN / "paper_level_failure_decomposition.jsonl")
        self.assertEqual(len(rows), 60)
        non_direct = [row for row in rows if row["pass_b_relevance_state"] != "DIRECTLY_RELEVANT"]
        self.assertEqual(len(non_direct), 58)
        self.assertTrue(all(row["development_failure_dimensions"] for row in non_direct))
        self.assertTrue(all(set(row["development_failure_dimensions"]) <= set(autopsy.DIMENSIONS) for row in non_direct))
        self.assertTrue(any(len(row["development_failure_dimensions"]) > 1 for row in non_direct))

    def test_family_a_and_first_seen_are_separate(self):
        family_a = self.load("query_family_failure_autopsy.json")["families"]["A"]
        self.assertEqual(family_a["any_contributing"]["paper_N"], 36)
        self.assertEqual(family_a["any_contributing"]["pass_b_relevance_distribution"]["DIRECTLY_RELEVANT"], 0)
        self.assertEqual(family_a["first_seen"]["paper_N"], 35)
        self.assertTrue(family_a["any_contributing"]["overlapping_count_not_precision"])
        self.assertEqual(family_a["structural_core_failure"], "TOPIC_INTERSECTION_WITHOUT_RELATION")

    def test_direct_paper_module_anchor_facts(self):
        expected = {
            "heldout_v2_102:pmid:28565847": ("INCOMPATIBLE", "UNRESOLVED", "EXACT"),
            "heldout_v2_105:pmid:27023784": ("UNRESOLVED", "UNRESOLVED", "EXACT"),
        }
        audits = {
            module: {row["candidate_id"]: row for row in self.load(f"{module.lower()}_failure_autopsy.json")["direct_paper_audit"]}
            for module in ("P0", "P1", "P2")
        }
        for candidate_id, states in expected.items():
            self.assertEqual(tuple(audits[module][candidate_id]["state"] for module in ("P0", "P1", "P2")), states)

    def test_zero_yield_paths_are_frozen_and_no_queries_rerun(self):
        zero = self.load("zero_yield_case_autopsy.json")
        path_104 = zero["heldout_v2_104"]["deterministic_path"]
        self.assertEqual(path_104[0], {"stage": "deduplicated_metadata", "N": 180})
        self.assertEqual(path_104[1]["distribution"], {"ABSTAIN": 142, "REJECT": 38})
        self.assertEqual(path_104[-1], {"stage": "selected_acquired", "selected": 0, "acquired": 0})
        queries_107 = zero["heldout_v2_107"]["queries"]
        self.assertEqual(len(queries_107), 4)
        self.assertTrue(all(row["response_status"] == 200 and row["response_record_count"] == 0 for row in queries_107))
        self.assertFalse(zero["queries_broadened_or_rerun"])

    def test_acquisition_relationship_and_no_clean_raw_separator(self):
        value = self.load("acquisition_failure_autopsy.json")
        self.assertEqual(value["frozen_relationship"]["NOT_JUSTIFIED_plus_DIRECT"], 0)
        self.assertEqual(value["frozen_relationship"]["JUSTIFIED_or_BORDERLINE_plus_DIRECT"], 2)
        self.assertEqual(value["frozen_relationship"]["NOT_JUSTIFIED_plus_NON_DIRECT"], 58)
        self.assertFalse(value["clean_raw_feature_separator_found"])
        self.assertEqual(value["observable_feature_prevalence"]["P2_EXACT"], {"direct_N": 2, "non_direct_N": 8})

    def test_aggregate_root_and_status(self):
        validation = self.load("validation.json")
        pairs = []
        for name, expected in validation["aggregate_components"]:
            actual = autopsy.sha(autopsy.RUN / name)
            self.assertEqual(actual, expected)
            pairs.append([name, actual])
        root = hashlib.sha256(autopsy.canonical(pairs)).hexdigest()
        self.assertEqual(root, validation["search_plan_v24_primary_failure_autopsy_sha256"])
        summary = self.load("summary.json")
        self.assertEqual(root, summary["search_plan_v24_primary_failure_autopsy_sha256"])
        self.assertTrue(summary["v23_beta2_primary_evaluation_failed"])
        self.assertTrue(summary["v23_beta2_remains_frozen"])
        self.assertFalse(summary["v24_algorithm_changes_implemented"])


if __name__ == "__main__":
    unittest.main()
