import json, tempfile, unittest
from pathlib import Path
from code_engine.workflow.steps import run_fulltext_escalation_step

class FulltextEscalationYearTests(unittest.TestCase):
    def test_out_of_range_candidate_is_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp); a = run / "artifacts"; a.mkdir()
            (a / "conflict_focus_set.jsonl").write_text(json.dumps({"candidate_id": "C", "paper_ids": ["P1", "P2"]}) + "\n")
            (a / "graph_conflict_candidates.jsonl").write_text(""); (a / "relation_evidence_bundles.jsonl").write_text("")
            (a / "acquisition_report.json").write_text(json.dumps({"candidate_papers": [{"paper_id": "P1", "publication_year": 2015}, {"paper_id": "P2", "publication_year": 2018}]}))
            result = run_fulltext_escalation_step(run_dir=run, l1_mode="progressive_fulltext", enable_fulltext_escalation=True,
                paper_year_filter={"paper_year_from": 2016, "paper_year_to": 2020})
            self.assertEqual(result.summary["selected_paper_count"], 1)
            self.assertEqual(result.summary["fulltext_candidates_excluded_by_year_filter"], 1)

if __name__ == "__main__": unittest.main()
