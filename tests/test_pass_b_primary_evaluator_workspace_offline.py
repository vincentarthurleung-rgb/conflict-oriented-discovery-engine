"""Focused isolation and byte-identity checks for the PASS B workspace."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tools import create_pass_b_primary_evaluator_workspace_offline as m


class PassBWorkspaceTests(unittest.TestCase):
    def test_generated_workspace_is_minimal_and_blind(self):
        content, audit_bytes = m.generate()
        audit = json.loads(audit_bytes)
        self.assertEqual(set(content), m.WORKSPACE_NAMES)
        self.assertEqual((audit["packet_count"], audit["unique_packet_count"]), (70, 70))
        self.assertEqual((audit["batch_count"], audit["batch_size"]), (5, 14))
        for key in ["unblinded_review_batches_present", "pass_a_material_present",
                    "tier_material_present", "gate_material_present", "metrics_present",
                    "unblinded_packet_files_present"]:
            self.assertFalse(audit[key])
        self.assertEqual(audit["prefilled_relevance_labels"], 0)
        self.assertEqual(audit["prefilled_acquisition_labels"], 0)

    def test_physical_batch_bytes_and_rubric_are_exact(self):
        content, _ = m.generate()
        self.assertEqual(content["pass_b_evaluator_instruction.md"], m.RUBRIC.read_bytes())
        for name in m.BATCH_NAMES:
            self.assertEqual(content[name], (m.BLINDED_RUN / name).read_bytes())

    def test_manifest_hashes_and_self_hash_convention(self):
        content, audit_bytes = m.generate()
        manifest = json.loads(content["evaluator_workspace_manifest.json"])
        rows = {row["path"]: row for row in manifest["files"]}
        for name in m.CONTENT_NAMES:
            self.assertEqual(rows[name]["sha256"], hashlib.sha256(content[name]).hexdigest())
            self.assertEqual(rows[name]["sha256_scope"], "exact_file_bytes")
        self_hash = rows["evaluator_workspace_manifest.json"]["sha256"]
        rows["evaluator_workspace_manifest.json"]["sha256"] = None
        self.assertEqual(self_hash, m.digest(m.canonical(manifest)))
        audit = json.loads(audit_bytes)
        self.assertEqual(audit["manifest_actual_file_sha256"],
                         hashlib.sha256(content["evaluator_workspace_manifest.json"]).hexdigest())

    def test_offline_replay_and_no_source_mutation(self):
        before = m.protected_state()
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            first = m.generate()
            second = m.generate()
        self.assertEqual(first, second)
        self.assertEqual(before, m.protected_state())

    def test_existing_material_is_fail_closed(self):
        with patch.object(m, "sha", side_effect=lambda path: "0" * 64):
            with self.assertRaises(RuntimeError):
                m.generate()


if __name__ == "__main__":
    unittest.main()
