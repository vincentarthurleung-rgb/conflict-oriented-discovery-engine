import json
import tempfile
import unittest
from pathlib import Path

from code_engine.fulltext.candidate_selection import FulltextSelectionPolicy, assess_scientific_relevance, classify_oa_candidate, select_conflict_related_papers
from code_engine.fulltext.stage import run_l35_pmc_oa_stage


class RelevanceFirstOATests(unittest.TestCase):
    def test_candidate_tiers_and_context_gate(self):
        policy = FulltextSelectionPolicy()
        high = assess_scientific_relevance({"selection_score": .9, "anchor_strength": "strong"}, policy)
        self.assertTrue(classify_oa_candidate(high, oa_available=True, selected=True)["selected_for_fulltext_l1"])
        self.assertEqual(classify_oa_candidate(high, oa_available=False)["candidate_tier"], "high_relevance_non_oa")
        low = assess_scientific_relevance({"selection_score": .9, "anchor_strength": "weak"}, policy)
        blocked = classify_oa_candidate(low, oa_available=True, selected=True)
        self.assertEqual(blocked["candidate_tier"], "low_relevance_oa")
        self.assertFalse(blocked["selected_for_fulltext_l1"])
        self.assertIn("low_relevance_oa_backfill_blocked", blocked["blocked_reasons"])
        context = assess_scientific_relevance({"selection_score": .9, "anchor_strength": "strong", "context_only_match": True}, policy)
        self.assertFalse(context["relevance_passed"])
        linked = assess_scientific_relevance({"selection_score": .56, "anchor_strength": "medium", "selection_source": "anchored_reviewable", "linked_observation_ids": ["obs"]}, policy)
        self.assertTrue(linked["relevance_passed"])

    def test_scientific_pool_expands_beyond_execution_quota(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            rows = [{"paper_id": str(i), "selection_score": .9 - i / 1000, "anchor_strength": "strong"} for i in range(30)]
            (root / "fulltext_discovery_escalation_candidates.jsonl").write_text("".join(json.dumps(x) + "\n" for x in rows))
            result = select_conflict_related_papers(root, max_papers=20)
            self.assertEqual(result["scientific_candidate_count"], 30)
            self.assertEqual(result["max_fulltext_papers"], 20)

    def test_no_relevant_oa_status_and_no_backfill(self):
        with tempfile.TemporaryDirectory() as td:
            run = Path(td); artifacts = run / "artifacts"; artifacts.mkdir()
            rows = [
                {"paper_id": "high", "pmcid": "PMC1", "selection_score": .9, "anchor_strength": "strong"},
                {"paper_id": "low", "pmcid": "PMC2", "selection_score": .2, "anchor_strength": "weak"},
            ]
            (artifacts / "fulltext_discovery_escalation_candidates.jsonl").write_text("".join(json.dumps(x) + "\n" for x in rows))
            def oa(url):
                if "PMC2" in url:
                    return b'<OA><records><record license="CC"><link format="xml" href="https://www.ncbi.nlm.nih.gov/a.xml"/></record></records></OA>'
                return b'<OA><error code="idIsNotOpenAccess">no</error></OA>'
            summary = run_l35_pmc_oa_stage(run, enabled=True, network_enabled=True, oa_transport=oa)
            self.assertEqual(summary["status"], "completed_no_relevant_oa")
            self.assertEqual(summary["low_relevance_oa_backfill_blocked_count"], 1)
            self.assertEqual(summary["selected_fulltext_count"], 0)

    def test_relevant_oa_after_twentieth_candidate_is_selected(self):
        with tempfile.TemporaryDirectory() as td:
            run = Path(td); artifacts = run / "artifacts"; artifacts.mkdir()
            rows = [{"paper_id": str(i), "pmcid": f"PMC{i}", "selection_score": .9, "anchor_strength": "strong"} for i in range(25)]
            (artifacts / "fulltext_discovery_escalation_candidates.jsonl").write_text("".join(json.dumps(x) + "\n" for x in rows))
            def oa(url):
                return (b'<OA><records><record license="CC"><link format="xml" href="https://www.ncbi.nlm.nih.gov/a.xml"/></record></records></OA>'
                        if "PMC24" in url else b'<OA><error code="idIsNotOpenAccess">no</error></OA>')
            summary = run_l35_pmc_oa_stage(run, enabled=True, network_enabled=True, oa_transport=oa, download_transport=lambda _: b"<article/>")
            self.assertEqual(summary["relevant_oa_candidate_count"], 1)
            candidates = [json.loads(x) for x in (artifacts / "l35_fulltext_candidate_papers.jsonl").read_text().splitlines()]
            self.assertTrue(candidates[-1]["selected_for_fulltext_l1"])
            records = [json.loads(x) for x in (artifacts / "l35_fulltext_discovery_execution_records.jsonl").read_text().splitlines()]
            self.assertEqual(len(records), 1)
            self.assertTrue(records[0]["download_attempted"])
            self.assertEqual(summary["download_attempted_count"], 1)
            self.assertEqual(summary["selected_fulltext_count"], len(records))

    def test_selected_oa_download_failure_has_concrete_execution_diagnostic(self):
        with tempfile.TemporaryDirectory() as td:
            run=Path(td); artifacts=run/"artifacts"; artifacts.mkdir()
            row={"paper_id":"paper-a","pmid":"paper-a","pmcid":"PMC-A","selection_score":.9,"anchor_strength":"strong"}
            (artifacts/"fulltext_discovery_escalation_candidates.jsonl").write_text(json.dumps(row)+"\n")
            oa=lambda _: b'<OA><records><record license="CC"><link format="xml" href="https://www.ncbi.nlm.nih.gov/a.xml"/></record></records></OA>'
            summary=run_l35_pmc_oa_stage(run,enabled=True,network_enabled=True,oa_transport=oa,download_transport=lambda _: b"not xml")
            record=json.loads((artifacts/"l35_fulltext_discovery_execution_records.jsonl").read_text().strip())
            self.assertEqual(record["download_status"],"success")
            self.assertEqual(record["parse_status"],"failed")
            self.assertEqual(record["blocking_reason"],"jats_parse_failed")
            self.assertEqual(summary["selected_oa_without_download_attempt_count"],0)


if __name__ == "__main__":
    unittest.main()
