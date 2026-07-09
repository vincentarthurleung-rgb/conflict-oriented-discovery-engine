import json
import tempfile
import unittest
from pathlib import Path

from code_engine.fulltext.candidate_bridge import canonical_fulltext_candidates
from code_engine.fulltext.stage import run_l35_pmc_oa_stage


OA_XML = b'<OA><records><record license="CC"><link format="xml" href="https://www.ncbi.nlm.nih.gov/a.xml"/></record></records></OA>'
JATS = b"<article><body><sec><title>Results</title><p>A bridge result.</p></sec></body></article>"


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class FulltextCandidateBridgeTests(unittest.TestCase):
    def test_bridge_consumes_discovery_l35_and_plan_sources(self):
        with tempfile.TemporaryDirectory() as td:
            artifacts = Path(td)
            (artifacts / "fulltext_discovery_escalation_candidates.jsonl").write_text(
                json.dumps({"paper_id": "a", "pmid": "1", "pmcid": "PMC1", "selection_score": .9}) + "\n"
            )
            (artifacts / "l35_fulltext_discovery_candidate_papers.jsonl").write_text(
                json.dumps({"paper_id": "b", "pmid": "2", "pmcid": "PMC2", "selection_score": .9}) + "\n"
            )
            (artifacts / "fulltext_escalation_plan.json").write_text(json.dumps({
                "selected": [{"paper_id": "c", "pmid": "3", "pmcid": "PMC3", "selection_score": .9}]
            }))
            candidates, conflicts = canonical_fulltext_candidates(artifacts)
            self.assertFalse(conflicts)
            self.assertEqual({x["pmid"] for x in candidates}, {"1", "2", "3"})

    def test_valid_pmcid_is_diagnosed_and_retrieved_from_discovery_file(self):
        with tempfile.TemporaryDirectory() as td:
            run = Path(td); artifacts = run / "artifacts"; artifacts.mkdir()
            candidate = {"paper_id": "p1", "pmid": "111", "pmcid": "PMC111", "selection_score": .9, "anchor_strength": "strong"}
            (artifacts / "fulltext_discovery_escalation_candidates.jsonl").write_text(json.dumps(candidate) + "\n")
            summary = run_l35_pmc_oa_stage(run, enabled=True, network_enabled=True, oa_transport=lambda _: OA_XML, download_transport=lambda _: JATS)
            self.assertGreater(summary["resource_diagnostics_count"], 0)
            self.assertEqual(len(rows(artifacts / "l35_fulltext_oa_resource_diagnostics.jsonl")), 1)
            self.assertEqual(len(rows(artifacts / "l35_fulltext_retrieval_results.jsonl")), 1)
            audit = rows(artifacts / "fulltext_candidate_bridge_audit.jsonl")[0]
            self.assertTrue(audit["passed_to_oa_diagnostics"])
            self.assertTrue(audit["passed_to_retrieval"])
            availability = json.loads((artifacts / "fulltext_availability_summary.json").read_text())
            self.assertEqual(availability["candidate_count"], 1)
            self.assertEqual(availability["retrieval_attempt_count"], 1)

    def test_missing_pmcid_is_counted_and_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            run = Path(td); artifacts = run / "artifacts"; artifacts.mkdir()
            candidate = {"paper_id": "p1", "pmid": "111", "selection_score": .9, "anchor_strength": "strong"}
            (artifacts / "fulltext_discovery_escalation_candidates.jsonl").write_text(json.dumps(candidate) + "\n")
            run_l35_pmc_oa_stage(run, enabled=True, network_enabled=True)
            audit = rows(artifacts / "fulltext_candidate_bridge_audit.jsonl")[0]
            self.assertEqual(audit["skip_reason"], "missing_pmcid")
            availability = json.loads((artifacts / "fulltext_availability_summary.json").read_text())
            self.assertEqual(availability["candidate_missing_pmcid_count"], 1)
            self.assertEqual(availability["skip_reason_counts"]["missing_pmcid"], 1)

    def test_conflicting_pmcid_for_same_pmid_is_audited_and_not_retrieved(self):
        with tempfile.TemporaryDirectory() as td:
            run = Path(td); artifacts = run / "artifacts"; artifacts.mkdir()
            left = {"paper_id": "p1", "pmid": "111", "pmcid": "PMC111", "title": "Same", "selection_score": .9, "anchor_strength": "strong"}
            right = {"paper_id": "p1b", "pmid": "111", "pmcid": "PMC222", "title": "Same", "selection_score": .9, "anchor_strength": "strong"}
            (artifacts / "fulltext_discovery_escalation_candidates.jsonl").write_text(json.dumps(left) + "\n")
            (artifacts / "l35_fulltext_discovery_candidate_papers.jsonl").write_text(json.dumps(right) + "\n")
            run_l35_pmc_oa_stage(run, enabled=True, network_enabled=True, oa_transport=lambda _: OA_XML, download_transport=lambda _: JATS)
            audit = rows(artifacts / "fulltext_candidate_bridge_audit.jsonl")[0]
            self.assertEqual(audit["pmcid_integrity_status"], "conflict")
            self.assertEqual(audit["skip_reason"], "pmcid_conflict")
            self.assertEqual(rows(artifacts / "l35_fulltext_retrieval_results.jsonl"), [])
            conflict = rows(artifacts / "pmcid_integrity_audit.jsonl")[0]
            self.assertEqual(conflict["candidate_pmcids"], ["PMC111", "PMC222"])
            availability = json.loads((artifacts / "fulltext_availability_summary.json").read_text())
            self.assertEqual(availability["candidate_with_pmcid_count"], 1)
            self.assertEqual(availability["pmcid_conflict_count"], 1)

    def test_l35_only_candidate_with_pmcid_reaches_diagnostics(self):
        with tempfile.TemporaryDirectory() as td:
            run = Path(td); artifacts = run / "artifacts"; artifacts.mkdir()
            candidate = {"paper_id": "wnt-like", "pmid": "222", "pmcid": "PMC222", "selection_score": .9, "anchor_strength": "strong"}
            (artifacts / "l35_fulltext_discovery_candidate_papers.jsonl").write_text(json.dumps(candidate) + "\n")
            run_l35_pmc_oa_stage(run, enabled=True, network_enabled=True, oa_transport=lambda _: OA_XML, download_transport=lambda _: JATS)
            self.assertEqual(len(rows(artifacts / "l35_fulltext_oa_resource_diagnostics.jsonl")), 1)
            self.assertGreater(json.loads((artifacts / "fulltext_availability_summary.json").read_text())["candidate_count"], 0)


if __name__ == "__main__":
    unittest.main()
