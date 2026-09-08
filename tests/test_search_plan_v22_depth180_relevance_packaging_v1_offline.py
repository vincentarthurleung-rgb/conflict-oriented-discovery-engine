"""Focused checks for the depth-180 neutral review package."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/20260907_search_plan_v22_recall_tail_probe_v2_depth180/tail_review_packets.jsonl"
RUN = ROOT / "runs/20260907_search_plan_v22_depth180_relevance_packaging_v1_offline"
FIELDS = ["relevance_state", "acquisition_decision", "matched_target_components",
          "mismatched_target_components", "fulltext_resolved_fields", "remaining_unresolved_fields",
          "contaminant_class", "rationale", "confidence"]


def jl(path): return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x]
def j(name): return json.loads((RUN/name).read_text(encoding="utf-8"))
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Depth180PackagingTests(unittest.TestCase):
    def test_bijection_and_blank_forms(self):
        source, blanks = jl(SOURCE), jl(RUN/"blank_adjudications.jsonl")
        markdown = (RUN/"tail_depth180_review_batch.md").read_text(encoding="utf-8")
        ids = [x["packet_id"] for x in source]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 17)
        self.assertEqual(ids, re.findall(r"^### Packet (\S+)$", markdown, re.M))
        self.assertEqual(ids, [x["packet_id"] for x in blanks])
        for field in FIELDS: self.assertEqual(markdown.count(f"\n{field}:\n"), 17)

    def test_depth_and_lineage_preserved(self):
        source = jl(SOURCE); markdown = (RUN/"tail_depth180_review_batch.md").read_text(encoding="utf-8")
        self.assertEqual([int(x) for x in re.findall(r"^Metadata depth: (\d+)$", markdown, re.M)],
                         [x["retrieval_provenance"]["metadata_depth"] for x in source])
        inventory = j("source_packet_inventory.json")["records"]
        for packet, row in zip(source, inventory):
            self.assertEqual(row["case_id"], packet["case_id"])
            self.assertEqual(row["tier_state"], packet["pre_acquisition_evidence"]["tier_state"])
            self.assertEqual(row["query_variants"], packet["retrieval_provenance"]["query_variants"])

    def test_distribution_and_source_traces(self):
        distribution = j("depth_distribution.json")
        self.assertEqual(distribution["121_150_packet_count"], 15)
        self.assertEqual(distribution["151_180_packet_count"], 2)
        inventory = j("source_packet_inventory.json")
        self.assertEqual(inventory["source_sha256"], sha(SOURCE))
        self.assertTrue(all(x["source_trace_complete"] for x in inventory["records"]))

    def test_neutrality_compatibility_and_validation(self):
        neutrality = j("neutrality_audit.json")
        self.assertEqual(neutrality["neutrality_violations"], 0)
        self.assertEqual(neutrality["prefilled_adjudication_fields"], 0)
        self.assertEqual(j("schema_compatibility.json")["status"], "COMPATIBLE_VIA_LOSSLESS_RENDERER_ADAPTER")
        validation = j("validation.json")
        self.assertEqual(validation["status"], "PASS")
        self.assertTrue(all(validation["checks"].values()))

    def test_manifest_and_offline_safety(self):
        manifest = j("manifest.json")
        self.assertEqual(manifest["required_artifact_count"], 9)
        self.assertTrue(all(sha(RUN/x["path"]) == x["sha256"] for x in manifest["files"]))
        summary = j("summary.json")
        for key in ["network_calls", "provider_calls", "llm_calls", "downloads", "extraction_calls"]:
            self.assertEqual(summary[key], 0)
        self.assertFalse(summary["historical_assets_modified"])


if __name__ == "__main__": unittest.main()
