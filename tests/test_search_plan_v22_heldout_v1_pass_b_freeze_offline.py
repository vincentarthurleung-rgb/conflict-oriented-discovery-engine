"""Structural, immutable, no-metrics checks for the frozen PASS B import."""
from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import patch

from tools import freeze_search_plan_v22_heldout_v1_pass_b_offline as m


class PassBFreezeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected_ids = [row["packet_id"] for row in
                            m.read_jsonl(m.CORPUS_RUN / "frozen_neutral_review_packets.jsonl")]
        cls.records = []
        for path in m.INPUTS:
            rows, _ = m.parse_submission(path.read_bytes())
            cls.records.extend(rows)

    def test_five_inputs_are_exact_frozen_batches(self):
        self.assertEqual(len(self.records), 70)
        observed = []
        for index, path in enumerate(m.INPUTS, 1):
            rows, _ = m.parse_submission(path.read_bytes())
            frozen = (m.WORKSPACE / f"heldout_relevance_blind_batch_{index:02d}.md").read_text()
            import re
            expected = re.findall(r"^### Packet (\S+)$", frozen, flags=re.MULTILINE)
            self.assertEqual([row["packet_id"] for row in rows], expected)
            observed.extend(expected)
        self.assertEqual({*observed}, {*self.expected_ids})

    def test_parser_preserves_scalar_and_list_values(self):
        raw = ("packet_id: p\nrelevance_state: DIRECTLY_RELEVANT\n"
               "matched_target_components: [subject, exact phrase]\n"
               "mismatched_target_components: []\nfulltext_resolved_fields: [field: detail]\n"
               "remaining_unresolved_fields: []\ncontaminant_class:\n"
               "rationale:  Keep: punctuation  \nconfidence: high\n"
               "reviewer_type: model_retrieval_adjudicator\n").encode()
        rows, _ = m.parse_submission(raw)
        self.assertEqual(rows[0]["matched_target_components"], ["subject", "exact phrase"])
        self.assertEqual(rows[0]["fulltext_resolved_fields"], ["field: detail"])
        self.assertEqual(rows[0]["rationale"], " Keep: punctuation  ")
        self.assertEqual(rows[0]["contaminant_class"], "")

    def test_schema_and_identity_reject_without_repair(self):
        valid = m.validate_records(self.records, self.expected_ids)
        self.assertEqual([row["packet_id"] for row in valid], self.expected_ids)
        for field, invalid in [("relevance_state", "DIRECT"), ("contaminant_class", "other"),
                               ("confidence", "HIGH"), ("reviewer_type", "human"), ("rationale", "")]:
            rows = copy.deepcopy(self.records)
            rows[0][field] = invalid
            with self.assertRaises(RuntimeError):
                m.validate_records(rows, self.expected_ids)
            self.assertEqual(rows[0][field], invalid)
        for rows in [self.records[:-1], self.records + [self.records[0]],
                     self.records[:-1] + [self.records[0]]]:
            with self.assertRaises(RuntimeError):
                m.validate_records(rows, self.expected_ids)

    def test_root_mismatch_stops_before_input_parse(self):
        with patch.object(m, "verify_aggregate_root", side_effect=RuntimeError("root mismatch")):
            with patch.object(m, "parse_submission") as parser:
                with self.assertRaises(RuntimeError):
                    m.generate()
                parser.assert_not_called()

    def test_workspace_and_frozen_sources_verified(self):
        verification = m.verify_workspace()
        self.assertEqual(verification["status"], "PASS")
        self.assertTrue(verification["source_blind_batches_byte_identical"])
        self.assertFalse(verification["symlinks_present"])
        self.assertEqual((verification["packet_count"], verification["batch_count"],
                          verification["batch_size"]), (70, 5, 14))

    def test_offline_replay_hash_and_metrics_embargo(self):
        before = m.protected_state()
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            first, second = m.generate(), m.generate()
        self.assertEqual(first, second)
        self.assertEqual(before, m.protected_state())
        corpus = first["pass_b_relevance_adjudications.jsonl"]
        freeze = json.loads(first["freeze_manifest.json"])
        self.assertEqual(m.digest(corpus), freeze["heldout_v1_pass_b_relevance_adjudications_sha256"])
        summary = json.loads(first["summary.json"])
        self.assertFalse(summary["heldout_metrics_calculated"])
        self.assertFalse(summary["relevance_distribution_reported"])
        self.assertFalse(summary["pass_a_pass_b_merged"])
        for key in m.ZERO_CALLS:
            self.assertEqual(summary[key], 0)
        validation = json.loads(first["validation.json"])
        self.assertEqual(validation["status"], "PASS")
        self.assertTrue(all(validation["checks"].values()))


if __name__ == "__main__":
    unittest.main()
