"""Focused checks for seven-paper supplemental neutral review packaging."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260908_search_plan_v22_depth180_supplemental_relevance_packaging_v1_offline"
SOURCE = ROOT / "runs/20260908_search_plan_v22_depth180_supplemental_oa_acquisition_v1/fulltext_manifest.jsonl"
FIELDS = ["relevance_state", "acquisition_decision", "matched_target_components",
          "mismatched_target_components", "fulltext_resolved_fields", "remaining_unresolved_fields",
          "contaminant_class", "rationale", "confidence"]


def jl(path): return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x]
def j(name): return json.loads((RUN/name).read_text(encoding="utf-8"))
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class SupplementalPackagingTests(unittest.TestCase):
    def test_exact_source_packet_and_markdown_bijection(self):
        acquired, packets = jl(SOURCE), jl(RUN/"supplemental_review_packets.jsonl")
        markdown = (RUN/"supplemental_review_batch.md").read_text(encoding="utf-8")
        self.assertEqual(len(acquired), len(packets))
        self.assertEqual(len(packets), 7)
        self.assertEqual([(x["case_id"],x["pmid"],x["pmcid"]) for x in acquired],
                         [(x["case_id"],x["publication_identity"]["pmid"],x["publication_identity"]["pmcid"]) for x in packets])
        self.assertEqual([x["packet_id"] for x in packets], re.findall(r"^### Packet (\S+)$", markdown, re.M))
        self.assertEqual([x["packet_id"] for x in packets], [f"rrsuppv1_{i:04d}" for i in range(1,8)])

    def test_depths_cases_and_combined_balance(self):
        balance = j("depth_case_balance.json")
        self.assertEqual(balance["supplemental_case_counts"], {"spv2_003":2,"spv2_016":2,"spv2_017":3})
        self.assertEqual(balance["supplemental_metadata_depths"], {
            "spv2_017":[152,156,158], "spv2_016":[162,163], "spv2_003":[157,171]})
        self.assertTrue(balance["all_metadata_depths_between_151_and_180"])
        self.assertEqual(balance["expected_combined_case_counts_after_supplemental_adjudication"],
                         {"spv2_003":3,"spv2_016":3,"spv2_017":3})
        self.assertEqual(balance["expected_combined_total_after_supplemental_adjudication"], 9)

    def test_neutral_blank_forms(self):
        packets = jl(RUN/"supplemental_review_packets.jsonl")
        blanks = jl(RUN/"blank_supplemental_adjudications.jsonl")
        markdown = (RUN/"supplemental_review_batch.md").read_text(encoding="utf-8")
        self.assertEqual(blanks, [x["adjudication"] for x in packets])
        self.assertTrue(all(x["relevance_state"] is None and x["acquisition_decision"] is None and
                            x["confidence"] is None and x["reviewer_type"] is None for x in blanks))
        for field in FIELDS: self.assertEqual(markdown.count(f"\n{field}:\n"), 7)
        neutrality = j("neutrality_audit.json")
        self.assertEqual(neutrality["prefilled_adjudication_fields"], 0)
        self.assertEqual(neutrality["neutrality_violations"], 0)
        self.assertFalse(neutrality["supplemental_relevance_metrics_calculated"])

    def test_source_traces_and_deterministic_excerpts(self):
        inventory = jl(RUN/"source_identity_inventory.jsonl")
        packets = jl(RUN/"supplemental_review_packets.jsonl")
        self.assertTrue(all(sha(ROOT/x["fulltext_ref"]) == x["fulltext_sha256"] for x in inventory))
        self.assertEqual(sum(len(x["fulltext_evidence_packet"]["excerpts"]) for x in packets), 41)
        for packet in packets:
            for excerpt in packet["fulltext_evidence_packet"]["excerpts"]:
                self.assertEqual(hashlib.sha256(excerpt["text"].encode()).hexdigest(), excerpt["text_sha256"])

    def test_validation_manifest_and_offline_boundary(self):
        validation = j("validation.json")
        self.assertEqual(validation["status"], "PASS")
        self.assertTrue(all(validation["checks"].values()))
        summary = j("summary.json")
        self.assertTrue(summary["supplemental_review_ready_for_adjudication"])
        self.assertFalse(summary["supplemental_relevance_metrics_calculated"])
        self.assertFalse(summary["budget_decision_updated"])
        for key in ["network_calls","provider_calls","llm_calls","downloads","extraction_calls"]:
            self.assertEqual(summary[key], 0)
        self.assertFalse(summary["historical_assets_modified"])
        manifest = j("manifest.json")
        self.assertEqual(manifest["required_artifact_count"], 11)
        self.assertTrue(all(sha(RUN/x["path"]) == x["sha256"] for x in manifest["files"]))


if __name__ == "__main__": unittest.main()
