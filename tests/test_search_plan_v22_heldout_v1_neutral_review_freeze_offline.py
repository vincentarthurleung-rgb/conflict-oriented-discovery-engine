"""Focused invariants for the held-out v1 neutral review corpus freeze."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/20260909_search_plan_v22_heldout_v1_network_retrieval/neutral_review_packets.jsonl"
RUN = ROOT / "runs/20260910_search_plan_v22_heldout_v1_neutral_review_freeze_offline"
EXPECTED_PROTOCOL = "2aac90361272de64eb055099602ae68e696c760628fec3835c0f29eca63ca127"
EXPECTED_CASE_COUNTS = [10, 10, 10, 10, 7, 3, 10, 10]
FIELDS = [
    "relevance_state", "acquisition_decision", "matched_target_components",
    "mismatched_target_components", "fulltext_resolved_fields", "remaining_unresolved_fields",
    "contaminant_class", "rationale", "confidence",
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def objsha(value):
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def j(name):
    return json.loads((RUN / name).read_text(encoding="utf-8"))


def jl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line]


class HeldoutNeutralReviewFreezeTests(unittest.TestCase):
    def test_canonical_copy_and_bijection(self):
        frozen = RUN / "frozen_neutral_review_packets.jsonl"
        self.assertEqual(SOURCE.read_bytes(), frozen.read_bytes())
        source, copied = jl(SOURCE), jl(frozen)
        self.assertEqual(source, copied)
        self.assertEqual(len(source), 70)
        self.assertEqual(len({row["packet_id"] for row in copied}), 70)
        identities = {
            (row["case_id"], row["publication_identity"]["pmid"], row["publication_identity"]["pmcid"])
            for row in copied
        }
        self.assertEqual(len(identities), 70)
        bijection = j("source_packet_bijection.json")
        self.assertTrue(bijection["source_packet_bijection"])
        self.assertTrue(bijection["acquired_fulltext_bijection"])
        self.assertEqual((bijection["missing_count"], bijection["extra_count"], bijection["duplicate_count"]), (0, 0, 0))
        self.assertTrue(all(row["exact_line_match"] for row in jl(RUN / "packet_hash_manifest.jsonl")))

    def test_case_distribution_and_batches(self):
        packets = jl(SOURCE)
        counts = Counter(row["case_id"] for row in packets)
        self.assertEqual([counts[f"heldout_v1_{index:03d}"] for index in range(1, 9)], EXPECTED_CASE_COUNTS)
        assignments = jl(RUN / "review_batch_assignment.jsonl")
        self.assertEqual(len(assignments), 70)
        self.assertEqual(len({row["packet_id"] for row in assignments}), 70)
        for batch_number in range(1, 6):
            batch_id = f"batch_{batch_number:02d}"
            rows = [row for row in assignments if row["batch_id"] == batch_id]
            self.assertEqual(len(rows), 14)
            for case_id in ["heldout_v1_001", "heldout_v1_002", "heldout_v1_003", "heldout_v1_004", "heldout_v1_007", "heldout_v1_008"]:
                self.assertEqual(sum(row["case_id"] == case_id for row in rows), 2)
            self.assertTrue(all(not row["scientific_content_used"] and not row["future_labels_used"] for row in rows))
        expected_aux = {
            "batch_01": [("heldout_v1_005", 1), ("heldout_v1_006", 1)],
            "batch_02": [("heldout_v1_005", 2), ("heldout_v1_006", 2)],
            "batch_03": [("heldout_v1_005", 3), ("heldout_v1_006", 3)],
            "batch_04": [("heldout_v1_005", 4), ("heldout_v1_005", 5)],
            "batch_05": [("heldout_v1_005", 6), ("heldout_v1_005", 7)],
        }
        for batch_id, expected in expected_aux.items():
            actual = [(row["case_id"], row["case_source_order"]) for row in assignments
                      if row["batch_id"] == batch_id and row["case_id"] in {"heldout_v1_005", "heldout_v1_006"}]
            self.assertEqual(actual, expected)

    def test_markdown_order_structure_and_blanks(self):
        assignments = jl(RUN / "review_batch_assignment.jsonl")
        case_rank = {f"heldout_v1_{index:03d}": index for index in range(1, 9)}
        for batch_number in range(1, 6):
            batch_id = f"batch_{batch_number:02d}"
            markdown = (RUN / f"heldout_review_batch_{batch_number:02d}.md").read_text(encoding="utf-8")
            ids = re.findall(r"^### Packet (\S+)$", markdown, re.M)
            expected = [row["packet_id"] for row in sorted(
                (row for row in assignments if row["batch_id"] == batch_id),
                key=lambda row: row["within_batch_order"],
            )]
            self.assertEqual(ids, expected)
            ordered_rows = sorted(
                (row for row in assignments if row["batch_id"] == batch_id),
                key=lambda row: row["within_batch_order"],
            )
            self.assertEqual(
                [(case_rank[row["case_id"]], row["case_source_order"]) for row in ordered_rows],
                sorted((case_rank[row["case_id"]], row["case_source_order"]) for row in ordered_rows),
            )
            self.assertEqual(markdown.count("\nMetadata depth: "), 14)
            self.assertEqual(markdown.count("\nQuery family / variant: "), 14)
            for field in FIELDS:
                self.assertEqual(markdown.count(f"\n{field}:\n"), 14)

    def test_blank_schema_and_neutrality(self):
        blanks = jl(RUN / "blank_adjudications_all.jsonl")
        source_ids = [row["packet_id"] for row in jl(SOURCE)]
        self.assertEqual([row["packet_id"] for row in blanks], source_ids)
        self.assertEqual(len(blanks), 70)
        for row in blanks:
            for key in ["relevance_state", "acquisition_decision", "contaminant_class", "reviewer_rationale", "confidence", "reviewer_type", "reviewer_id_or_label", "timestamp", "publication_id"]:
                self.assertIsNone(row[key])
            for key in ["matched_target_components", "mismatched_target_components", "fulltext_resolved_fields", "remaining_unresolved_fields"]:
                self.assertEqual(row[key], [])
        compatibility = j("schema_compatibility.json")
        self.assertEqual(compatibility["status"], "COMPATIBLE_VIA_LOSSLESS_RENDERER_ADAPTER")
        self.assertTrue(compatibility["renderer_reused"])
        self.assertFalse(compatibility["fulltext_excerpts_reextracted"])
        neutrality = j("neutrality_audit.json")
        self.assertEqual(neutrality["prefilled_adjudication_fields"], 0)
        self.assertEqual(neutrality["neutrality_violations"], 0)

    def test_freeze_hash_manifest_and_protocol_boundary(self):
        freeze = j("freeze_manifest.json")
        self.assertEqual(freeze["heldout_v1_protocol_sha256"], EXPECTED_PROTOCOL)
        self.assertEqual(
            freeze["heldout_v1_review_corpus_sha256"],
            objsha([(row["path"], sha(RUN / row["path"])) for row in freeze["components"]]),
        )
        self.assertTrue(all(sha(RUN / row["path"]) == row["sha256"] for row in freeze["components"]))
        manifest = j("manifest.json")
        self.assertEqual(manifest["required_artifact_count"], 22)
        self.assertTrue(manifest["all_required_present"])
        self.assertTrue(all(sha(RUN / row["path"]) == row["sha256"] for row in manifest["files"]))
        validation = j("validation.json")
        self.assertEqual(validation["status"], "PASS")
        self.assertTrue(all(validation["checks"].values()))

    def test_descriptive_summary_and_safety(self):
        descriptive = j("retrieval_corpus_descriptive_summary.json")
        self.assertEqual(
            [descriptive[key] for key in ["metadata_total", "tier_a_candidate_total", "tier_b_candidate_total", "reject_total", "gate_abstain_total", "oa_acquired_total", "neutral_packet_total"]],
            [1072, 142, 772, 125, 33, 70, 70],
        )
        self.assertEqual(descriptive["natural_exhaustion"], {"heldout_v1_004": 148, "heldout_v1_005": 11, "heldout_v1_006": 13})
        self.assertFalse(descriptive["heldout_relevance_metrics_calculated"])
        summary = j("summary.json")
        self.assertTrue(summary["neutral_review_corpus_frozen"])
        self.assertTrue(summary["review_batches_ready"])
        self.assertFalse(summary["heldout_primary_adjudication_started"])
        self.assertFalse(summary["heldout_primary_results_frozen"])
        for name in ["summary.json", "scientific_state_safety_audit.json", "validation.json"]:
            data = j(name)
            for key in ["network_calls", "provider_calls", "llm_calls", "downloads", "extraction_calls"]:
                self.assertEqual(data[key], 0)
            self.assertFalse(data["historical_assets_modified"])


if __name__ == "__main__":
    unittest.main()
