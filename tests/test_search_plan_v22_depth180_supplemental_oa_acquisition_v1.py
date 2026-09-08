"""Focused checks for the exact seven-paper supplemental OA acquisition."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260908_search_plan_v22_depth180_supplemental_oa_acquisition_v1"
PLAN = ROOT / "runs/20260908_search_plan_v22_depth180_relevance_adjudication_v1_offline/supplemental_151_180_selection_plan.jsonl"


def jl(path): return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x]
def j(name): return json.loads((RUN/name).read_text(encoding="utf-8"))
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class SupplementalAcquisitionTests(unittest.TestCase):
    def test_exact_plan_identity_and_order(self):
        plan, attempts = jl(PLAN), jl(RUN/"acquisition_attempts.jsonl")
        expected = [(x["case_id"], x["pmid"], x["preserved_pmcid"]) for x in plan]
        actual = [(x["case_id"], x["pmid"], x["pmcid"]) for x in attempts]
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), len(set(actual)))
        self.assertEqual(len(actual), 7)
        self.assertEqual(j("baseline.json")["source_selection_plan_sha256"], sha(PLAN))

    def test_all_articles_and_identities_valid(self):
        rows = jl(RUN/"fulltext_manifest.jsonl")
        self.assertEqual(len(rows), 7)
        for row in rows:
            path = ROOT / row["snapshot_ref"]
            self.assertEqual(sha(path), row["content_hash"])
            self.assertTrue(row["pmc_article_present"])
            self.assertTrue(row["pmid_identity_valid"])
            self.assertIsNotNone(ET.parse(path).getroot())

    def test_network_scope_exact(self):
        audit = j("network_usage_audit.json")
        self.assertEqual(audit["network_request_count"], 7)
        self.assertEqual(audit["successful_network_response_count"], 7)
        self.assertEqual(audit["failed_network_attempt_count"], 0)
        self.assertEqual(audit["pubmed_search_calls"], 0)
        self.assertEqual(audit["metadata_calls"], 0)
        self.assertEqual(audit["replacement_discovery_calls"], 0)
        self.assertEqual(audit["requested_pmcids"], audit["authorized_pmcids"])
        self.assertTrue(audit["allowed_service_only"])

    def test_safety_and_summary(self):
        summary = j("summary.json")
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["fulltext_acquired_count"], 7)
        self.assertEqual(summary["retrieval_failure_count"], 0)
        self.assertFalse(summary["selection_changed"])
        self.assertEqual(summary["replacement_count"], 0)
        self.assertEqual((summary["provider_calls"], summary["llm_calls"], summary["extraction_calls"]), (0, 0, 0))
        self.assertFalse(summary["historical_assets_modified"])
        safety = j("scientific_state_safety_audit.json")
        self.assertFalse(safety["new_pubmed_search_performed"])
        self.assertFalse(safety["metadata_depth_extended"])
        self.assertFalse(safety["replacement_papers_discovered_or_used"])

    def test_validation_and_manifest(self):
        validation = j("validation.json")
        self.assertEqual(validation["status"], "PASS")
        self.assertTrue(all(validation["checks"].values()))
        manifest = j("manifest.json")
        self.assertEqual(manifest["required_artifact_count"], 9)
        self.assertTrue(all(sha(RUN/x["path"]) == x["sha256"] for x in manifest["files"]))
        self.assertTrue(all(sha(ROOT/x["path"]) == x["sha256"] for x in manifest["retrieval_assets"]))


if __name__ == "__main__": unittest.main()
