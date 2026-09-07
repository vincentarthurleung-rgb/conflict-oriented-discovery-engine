"""Focused offline checks for tail relevance-review rendering."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/20260907_search_plan_v22_recall_tail_probe_v1/tail_review_packets.jsonl"
RUN = ROOT / "runs/20260907_search_plan_v22_recall_tail_relevance_packaging_v1_offline"
REQUIRED = {"tail_review_batch.md", "blank_tail_adjudications.jsonl", "source_packet_inventory.json",
            "schema_compatibility.json", "neutrality_audit.json", "validation.json", "manifest.json", "summary.json"}
FORM_FIELDS = ["relevance_state", "acquisition_decision", "matched_target_components",
               "mismatched_target_components", "fulltext_resolved_fields", "remaining_unresolved_fields",
               "contaminant_class", "rationale", "confidence"]


def jl(path): return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").split("\n") if x]
def j(name): return json.loads((RUN / name).read_text(encoding="utf-8"))
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class TailReviewPackagingTests(unittest.TestCase):
    def test_exact_bijection_and_order(self):
        source = jl(SOURCE); blanks = jl(RUN / "blank_tail_adjudications.jsonl")
        markdown = (RUN / "tail_review_batch.md").read_text(encoding="utf-8")
        markdown_ids = re.findall(r"^### Packet (\S+)$", markdown, re.M)
        ids = [x["packet_id"] for x in source]
        self.assertEqual(len(ids), len(set(ids)) if ids else 0)
        self.assertEqual(len(ids), 15)
        self.assertEqual(ids, markdown_ids)
        self.assertEqual(ids, [x["packet_id"] for x in blanks])

    def test_markdown_uses_previous_blank_form(self):
        markdown = (RUN / "tail_review_batch.md").read_text(encoding="utf-8")
        for field in FORM_FIELDS: self.assertEqual(markdown.count(f"\n{field}:\n"), 15)
        self.assertNotIn("\nreviewer_type:", markdown)
        self.assertEqual(markdown.count("\nFulltext excerpts:\n[no deterministic target-anchor excerpt found]\n"), 15)

    def test_blank_schema_and_neutrality(self):
        source = jl(SOURCE); blanks = jl(RUN / "blank_tail_adjudications.jsonl")
        previous_schema = json.loads((ROOT / "runs/20260906_retrieval_relevance_audit_packaging_v1_offline/retrieval_relevance_adjudication_v1.schema.json").read_text())
        self.assertTrue(all(set(x) == set(previous_schema["required"]) for x in blanks))
        self.assertEqual(blanks, [x["adjudication"] for x in source])
        audit = j("neutrality_audit.json")
        self.assertEqual(audit["neutrality_violations"], 0)
        self.assertEqual(audit["prefilled_adjudication_fields"], 0)

    def test_source_inventory_and_traces(self):
        source = jl(SOURCE); inventory = j("source_packet_inventory.json")
        self.assertEqual(inventory["source_sha256"], sha(SOURCE))
        self.assertEqual(inventory["ordered_packet_ids"], [x["packet_id"] for x in source])
        for record, packet in zip(inventory["records"], source):
            self.assertTrue(record["source_trace_complete"])
            self.assertEqual(sha(ROOT / record["abstract_snapshot_ref"]), record["abstract_snapshot_sha256"])
            self.assertEqual(sha(ROOT / record["fulltext_ref"]), record["fulltext_sha256"])
            self.assertEqual(record["fulltext_excerpt_count"], len(packet["fulltext_evidence_packet"]["excerpts"]))

    def test_required_files_manifest_and_safety(self):
        self.assertFalse(REQUIRED - {p.name for p in RUN.iterdir() if p.is_file()})
        manifest = j("manifest.json")
        self.assertEqual(manifest["required_artifact_count"], 8)
        for row in manifest["files"]: self.assertEqual(sha(RUN / row["path"]), row["sha256"])
        validation = j("validation.json")
        self.assertEqual(validation["status"], "PASS")
        self.assertTrue(all(validation["checks"].values()))
        summary = j("summary.json")
        for field in ["network_calls", "provider_calls", "llm_calls", "downloads", "extraction_calls"]:
            self.assertEqual(summary[field], 0)
        self.assertFalse(summary["historical_assets_modified"])


if __name__ == "__main__": unittest.main()
