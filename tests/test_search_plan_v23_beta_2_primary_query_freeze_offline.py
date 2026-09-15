"""Focused integrity tests for the beta.2 primary held-out-v2 query freeze."""

from collections import Counter
import hashlib
import json
from pathlib import Path
import unittest

from tools import freeze_search_plan_v23_beta_2_primary_heldout_v2_queries_offline as freeze


class PrimaryHeldoutV2QueryFreezeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.run_dir = freeze.RUN
        cls.bindings = cls.read_jsonl("primary_heldout_v2_query_bindings.jsonl")
        cls.slots = cls.read_jsonl("primary_heldout_v2_family_slots.jsonl")
        cls.queries = cls.read_jsonl("primary_heldout_v2_frozen_queries.jsonl")
        cls.summary = cls.read_json("summary.json")

    @classmethod
    def read_json(cls, name):
        return json.loads((cls.run_dir / name).read_text(encoding="utf-8"))

    @classmethod
    def read_jsonl(cls, name):
        return [json.loads(line) for line in (cls.run_dir / name).read_text(encoding="utf-8").splitlines() if line]

    def test_all_five_frozen_roots_verify(self):
        result = freeze.verify_upstream_roots()
        self.assertTrue(result["all_five_exact_roots_verified"])
        self.assertTrue(result["verified_before_query_layer_import"])
        self.assertEqual(
            {name: row["actual_sha256"] for name, row in result["roots"].items()},
            freeze.EXPECTED_ROOTS,
        )

    def test_binding_status_contract_and_no_core_failure(self):
        self.assertEqual([row["case_id"] for row in self.bindings], freeze.CASE_IDS)
        self.assertEqual(len(self.bindings), 8)
        allowed = {"RESOLVED", "EMPTY_AUTHORIZED", "UNRESOLVED_CORE"}
        for row in self.bindings:
            self.assertTrue(row["core_binding_valid"])
            self.assertEqual(row["unresolved_core_fields"], [])
            self.assertTrue(set(row["field_statuses"].values()) <= allowed)
            for field in row["compiler_facing_fields"].values():
                for term in field["value"]:
                    self.assertEqual(term["authorization_status"], "AUTHORIZED")
                    self.assertNotIn(term["provenance_kind"], freeze.FORBIDDEN_PROVENANCE)

    def test_exactly_48_slots_in_canonical_order(self):
        expected = [
            (case_id, family_id, case_index, family_index)
            for case_index, case_id in enumerate(freeze.CASE_IDS, 1)
            for family_index, family_id in enumerate(freeze.FAMILY_ORDER, 1)
        ]
        actual = [
            (row["case_id"], row["family_id"], row["canonical_case_index"], row["canonical_family_index"])
            for row in self.slots
        ]
        self.assertEqual(actual, expected)
        self.assertEqual(len(self.slots), 48)

    def test_applicability_and_compilation_boundaries(self):
        states = Counter(row["family_applicability"] for row in self.slots)
        self.assertEqual(states, {"APPLICABLE": 32, "NOT_APPLICABLE": 16})
        self.assertNotIn("INVALID_REQUIRED_INPUT", states)
        for row in self.slots:
            if row["family_applicability"] == "APPLICABLE":
                self.assertTrue(row["family_builder_invoked"])
                self.assertTrue(row["compiled_query"])
                self.assertTrue(row["query_sha256"])
            else:
                self.assertFalse(row["family_builder_invoked"])
                self.assertIsNone(row["compiled_query"])
                self.assertIsNone(row["query_sha256"])
                self.assertTrue(row["missing_optional_authorities"])
        family_a = [row for row in self.slots if row["family_id"] == "A"]
        self.assertEqual(len(family_a), 8)
        self.assertTrue(all(row["family_applicability"] == "APPLICABLE" for row in family_a))

    def test_frozen_query_identity_hash_and_provenance(self):
        self.assertEqual(len(self.queries), 32)
        self.assertEqual(len({row["query_id"] for row in self.queries}), 32)
        for row in self.queries:
            self.assertEqual(row["query_id"], f"primary_v2_{row['case_id']}_{row['family_id']}")
            self.assertEqual(
                row["query_sha256"],
                hashlib.sha256(row["compiled_query"].encode("utf-8")).hexdigest(),
            )
            self.assertTrue(row["term_provenance"])
            self.assertEqual(row["term_provenance"], row["all_bound_inputs_used"])
            self.assertTrue(all(term["authorization_status"] == "AUTHORIZED" for term in row["term_provenance"]))

    def test_collision_and_trace_audits_pass(self):
        collision = self.read_json("query_collision_audit.json")
        self.assertEqual(collision["status"], "PASS")
        for key in (
            "duplicate_family_slot_ids",
            "duplicate_query_ids",
            "empty_executable_queries",
            "applicable_slots_missing_compiled_query",
            "not_applicable_slots_containing_compiled_query",
            "unauthorized_term_provenance",
        ):
            self.assertEqual(collision[key], 0)
        trace = self.read_json("target_to_query_trace.json")
        self.assertTrue(trace["target_to_query_trace_complete"])
        self.assertEqual(trace["trace_count"], len(self.queries))

    def test_manifest_root_and_required_membership(self):
        manifest = self.read_json("freeze_manifest.json")
        for name, expected in manifest["aggregate_components"]:
            self.assertEqual(hashlib.sha256((self.run_dir / name).read_bytes()).hexdigest(), expected)
        actual = hashlib.sha256(freeze.canonical(manifest["aggregate_components"])).hexdigest()
        self.assertEqual(actual, manifest["primary_heldout_v2_query_freeze_sha256"])
        self.assertEqual(set(path.name for path in self.run_dir.iterdir()), freeze.REQUIRED)
        self.assertTrue(all(path.is_file() and not path.is_symlink() for path in self.run_dir.iterdir()))

    def test_offline_and_immutable_summary(self):
        for key in ("network_calls", "provider_calls", "downloads", "retrieval_calls", "candidate_records_seen"):
            self.assertEqual(self.summary[key], 0)
        self.assertFalse(self.summary["retrieval_started"])
        self.assertFalse(self.summary["historical_assets_modified"])
        self.assertFalse(self.summary["primary_targets_modified"])
        self.assertFalse(self.summary["binding_v1_1_modified"])
        self.assertFalse(self.summary["applicability_v1_modified"])
        self.assertFalse(self.summary["modular_compiler_modified"])


if __name__ == "__main__":
    unittest.main()
