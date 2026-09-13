"""Integrity, conservative mapping, and offline replay of development artifacts."""

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import freeze_search_plan_v22_to_v23_error_analysis_offline as analysis


def adjudication(state="RELATED_BUT_WRONG_PROPOSITION", contaminant="", mismatched=None, unresolved=None):
    return {"relevance_state": state, "contaminant_class": contaminant,
            "mismatched_target_components": mismatched or [], "remaining_unresolved_fields": unresolved or []}


class FailureMappingTests(unittest.TestCase):
    def test_biological_unit_is_not_automatically_an_intervention_error(self):
        result, trace = analysis.failure_families(adjudication(
            "WRONG_ENTITY", "wrong_biological_unit", ["context_qualifiers"]))
        self.assertEqual(result, ["BIOLOGICAL_UNIT_MISMATCH"])
        self.assertEqual(trace[0]["source_field"], "contaminant_class")
        result, _ = analysis.failure_families(adjudication(
            "WRONG_ENTITY", "wrong_biological_unit", ["subject", "context_qualifiers"]))
        self.assertIn("ENTITY_OR_INTERVENTION_MISMATCH", result)

    def test_unresolved_unit_does_not_become_proven_unit_mismatch(self):
        result, _ = analysis.failure_families(adjudication(
            "PLAUSIBLY_RELEVANT_FULLTEXT_REQUIRED", unresolved=["current-study biological unit"]))
        self.assertEqual(result, ["INSUFFICIENT_SPECIFICITY"])
        result, _ = analysis.failure_families(adjudication(mismatched=["context_qualifiers"]))
        self.assertEqual(result, ["OTHER_FROZEN_RELEVANCE_FAILURE"])

    def test_relation_mismatch_alone_does_not_assert_direction(self):
        result, _ = analysis.failure_families(adjudication(mismatched=["relation_family"]))
        self.assertEqual(result, ["FUNCTIONAL_RELATION_UNRESOLVED"])
        result, _ = analysis.failure_families(adjudication(mismatched=["subject role"]))
        self.assertEqual(result, ["PROPOSITION_DIRECTION_OR_ROLE_MISMATCH"])

    def test_mapping_ignores_rationale_target_tier_case_and_unrecognized_words(self):
        source = adjudication(mismatched=["measurement_property_endpoint"])
        before = copy.deepcopy(source)
        expected = analysis.failure_families(source)
        source.update({"rationale": "wrong biological unit; causation", "case_id": "invented",
                       "tier": "TIER_A", "title": "functional relationship", "target": {}})
        self.assertEqual(analysis.failure_families(source), expected)
        for key in before:
            self.assertEqual(source[key], before[key])
        result, _ = analysis.failure_families(adjudication(mismatched=["subjective", "relation_family_unknown"]))
        self.assertEqual(result, ["OTHER_FROZEN_RELEVANCE_FAILURE"])

    def test_direct_and_overlapping_categories_and_null_contaminant(self):
        self.assertEqual(analysis.failure_families(adjudication("DIRECTLY_RELEVANT")), ([], []))
        result, _ = analysis.failure_families(adjudication("WRONG_ENDPOINT", "wrong_endpoint", ["relation_family"]))
        self.assertEqual(result, ["FUNCTIONAL_RELATION_UNRESOLVED", "ENDPOINT_MISMATCH"])
        result, _ = analysis.failure_families(adjudication("WRONG_ENDPOINT", None))
        self.assertEqual(result, ["ENDPOINT_MISMATCH"])


class RootAndReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            cls.outputs = analysis.generate()

    def test_each_of_seven_hash_mismatches_prevents_analysis(self):
        for key in analysis.frozen.EXPECTED_ROOTS:
            with self.subTest(root=key), patch.dict(analysis.frozen.EXPECTED_ROOTS, {key: "0" * 64}):
                with patch.object(analysis.frozen, "read_jsonl") as read, patch.object(analysis, "build_analysis") as build:
                    with self.assertRaises(RuntimeError):
                        analysis.generate()
                    read.assert_not_called()
                    build.assert_not_called()
        with patch.object(analysis, "METRICS_HASH", "0" * 64):
            with patch.object(analysis, "build_analysis") as build:
                with self.assertRaises(RuntimeError):
                    analysis.generate()
                build.assert_not_called()

    def test_component_tamper_rejected_even_if_declared_root_is_correct(self):
        original = analysis.frozen.sha256
        corrupt = analysis.frozen.RUN / "metric_definition_audit.json"
        with patch.object(analysis.frozen, "sha256", side_effect=lambda path: "f" * 64 if path == corrupt else original(path)):
            with self.assertRaisesRegex(RuntimeError, "component mismatch"):
                analysis.verify_roots()

    def test_matrix_recovers_all_primary_fields_and_csv_types(self):
        records = analysis.frozen.read_jsonl(analysis.frozen.PRIMARY / "heldout_v1_primary_results.jsonl")
        rows = [json.loads(line) for line in self.outputs["heldout_v1_v23_development_error_matrix.jsonl"].splitlines()]
        self.assertEqual(analysis.from_csv(self.outputs["heldout_v1_v23_development_error_matrix.csv"]), rows)
        self.assertEqual([row["packet_id"] for row in rows], [row["packet_id"] for row in records])
        self.assertTrue(analysis.validate_outputs(self.outputs, rows, records)["frozen_primary_fields_preserved_exactly"])
        changed = copy.deepcopy(rows)
        changed[0]["acquisition_confidence"] = "changed"
        with self.assertRaisesRegex(RuntimeError, "changed frozen"):
            analysis.validate_outputs(self.outputs, changed, records)
        weird = [{"text": 'commas, quotes " and line\nbreak β', "none": None, "array": [],
                  "bool": False, "nested": {"a": [1, True, ""]}}]
        self.assertEqual(analysis.from_csv(analysis.to_csv(weird)), weird)

    def test_csv_packet_loss_and_duplicate_input_rejected(self):
        records = analysis.frozen.read_jsonl(analysis.frozen.PRIMARY / "heldout_v1_primary_results.jsonl")
        with self.assertRaises(RuntimeError):
            analysis.frozen.validate_records(records[:-1] + [records[0]])
        rows = analysis.make_matrix(records)
        changed = dict(self.outputs)
        changed["heldout_v1_v23_development_error_matrix.csv"] = analysis.to_csv(rows[:-1])
        with self.assertRaisesRegex(RuntimeError, "CSV records differ"):
            analysis.validate_outputs(changed, rows, records)

    def test_family_counts_traceable_and_original_secondary_labels_unchanged(self):
        mapping = json.loads(self.outputs["development_failure_mapping.json"])
        rows = [json.loads(line) for line in self.outputs["heldout_v1_v23_development_error_matrix.jsonl"].splitlines()]
        for family in analysis.FAMILIES:
            selected = [row for row in rows if family in row["development_failure_families"]]
            summary = mapping["family_counts"][family]
            self.assertEqual(summary["packet_count"], len(selected))
            self.assertEqual(sum(summary["by_tier"].values()), len(selected))
            self.assertEqual(sum(summary["by_case"].values()), len(selected))
            self.assertEqual(sum(summary["by_ambiguity"].values()), len(selected))
        bio = json.loads(self.outputs["biological_unit_error_analysis.json"])
        self.assertEqual(bio["summary"]["packet_count"], 21)
        self.assertEqual(bio["summary"]["by_tier"], {"TIER_A": 5, "TIER_B": 16})
        protocol = json.loads(self.outputs["v23_metrics_protocol_requirements.json"])
        self.assertEqual(protocol["frozen_v1_heuristic_statuses_preserved"],
                         analysis.frozen.read_json(analysis.frozen.RUN / "engineering_heuristics.json"))

    def test_requirements_supported_and_no_candidate_taxonomy_implemented(self):
        requirements = json.loads(self.outputs["v23_search_plan_design_requirements.json"])["requirements"]
        self.assertEqual([item["priority"] for item in requirements], ["P0", "P1", "P2", "P3"])
        for item in requirements:
            self.assertEqual(item["affected_packet_count"], len(set(item["observed_failure_evidence"]["packet_ids"])))
            self.assertTrue(item["implementation_not_started"])
            self.assertFalse(item["candidate_taxonomy_validated"])

    def test_all_artifacts_marked_and_hash_covers_results_audits(self):
        self.assertEqual(set(self.outputs), analysis.REQUIRED)
        manifest = json.loads(self.outputs["manifest.json"])
        self.assertEqual({item["path"] for item in manifest["components"]}, analysis.REQUIRED - {"manifest.json", "summary.json"})
        pairs = []
        for item in manifest["components"]:
            self.assertEqual(item["sha256"], analysis.frozen.digest(self.outputs[item["path"]]))
            pairs.append([item["path"], item["sha256"]])
        self.assertEqual(manifest["v22_to_v23_error_analysis_sha256"], analysis.frozen.digest(analysis.frozen.canonical_json(pairs)))
        for name, content in self.outputs.items():
            if name.endswith(".json"):
                self.assertEqual(json.loads(content)["analysis_status"], analysis.STATUS)
            elif name.endswith(".md"):
                self.assertIn(("analysis_status = " + analysis.STATUS).encode(), content)

    def test_offline_replay_and_protected_files_unchanged(self):
        before = analysis.protected_hashes()
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            self.assertEqual(analysis.generate(), self.outputs)
        self.assertEqual(before, analysis.protected_hashes())

    def test_existing_changed_file_refused_without_overwrite(self):
        with tempfile.TemporaryDirectory() as parent:
            destination = Path(parent) / "output"
            analysis.write_or_verify({"file": b"original"}, destination)
            analysis.write_or_verify({"file": b"original"}, destination)
            with self.assertRaisesRegex(RuntimeError, "no overwrite"):
                analysis.write_or_verify({"file": b"different"}, destination)
            self.assertEqual((destination / "file").read_bytes(), b"original")


if __name__ == "__main__":
    unittest.main()
