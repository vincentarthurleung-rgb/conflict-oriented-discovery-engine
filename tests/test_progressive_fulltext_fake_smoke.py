import json
import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.orchestrator import run_workflow


class FakeL1:
    def extract_json(self, prompt, **_):
        direction = "decrease" if "decreased" in prompt else "increase"
        return {"claims": [{"subject_raw": "ketamine", "subject_type": "compound",
                            "relation_raw": direction, "object_raw": "BDNF", "object_type": "gene",
                            "direction": direction, "relation_family": "affects", "polarity_type": "effect",
                            "evidence_sentence": f"Ketamine {direction}d BDNF in human cells."}]}


class ProgressiveFulltextFakeSmokeTests(unittest.TestCase):
    def test_current_run_reaches_conflict_gated_fulltext_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "run"
            run_workflow("ketamine BDNF depression", run_dir=root, until="acquisition",
                         l1_mode="progressive_fulltext", enable_fulltext_escalation=True,
                         pilot_profile="ketamine", allow_uncertain_intake=True,
                         global_corpus_dir=Path(tmp) / "corpus", merge_knowledge_store=False)
            papers = [{"paper_id": f"P{i}", "canonical_paper_id": f"P{i}", "pmid": str(i),
                       "pmcid": f"PMC{i}", "title": f"Paper {i}", "publication_year": 2010 + i,
                       "abstract": "Ketamine decreased BDNF." if i == 1 else "Ketamine increased BDNF."}
                      for i in range(1, 4)]
            artifacts = root / "artifacts"
            (artifacts / "acquisition_report.json").write_text(json.dumps({"candidate_papers": papers, "reused_papers": [], "downloaded_papers": [], "initial_fulltext_download_count": 0}))
            state_payload = json.loads((root / "run_state.json").read_text())
            state_payload["steps"]["acquisition"]["status"] = "completed"
            (root / "run_state.json").write_text(json.dumps(state_payload))
            fulltext = Path(tmp) / "P1.txt"
            fulltext.write_text("Results. Ketamine increased BDNF in human cells.")

            def availability(item):
                yes = str(item.get("pmid")) == "1" or item["canonical_paper_id"] == "P1"
                return {"fulltext_available": yes, "open_access": yes,
                        "availability_source": "pmc" if yes else "not_available",
                        "fulltext_status": "available" if yes else "not_available",
                        "reason": "fake_resolution", **({"full_text_path": str(fulltext)} if yes else {})}

            state = run_workflow(
                resume=root, until="report", execute=True, api=True, network=True,
                l1_mode="progressive_fulltext", enable_fulltext_escalation=True,
                pilot_profile="ketamine", allow_uncertain_intake=True,
                l1_llm_client=FakeL1(), fulltext_availability_resolver=availability,
                global_corpus_dir=Path(tmp) / "corpus", merge_knowledge_store=False,
            )
            self.assertGreater(state.steps["evidence_graph_core"].summary["graph_conflict_candidate_count"], 0)
            self.assertEqual(state.steps["fulltext_acquisition"].summary["selected_available_count"], 1)
            self.assertEqual(state.steps["fulltext_l1"].summary["fulltext_claim_count"], 1)
            for name in ("relation_evidence_bundles.jsonl", "graph_conflict_candidates.jsonl",
                         "fulltext_escalation_candidates.jsonl", "fulltext_availability_records.jsonl",
                         "fulltext_l1_claims.jsonl", "l2_fulltext_summary.json",
                         "fulltext_conflict_confirmation_summary.json", "hypothesis_hyperedges.jsonl",
                         "conflict_evidence_timelines.jsonl"):
                self.assertTrue((artifacts / name).exists(), name)
            self.assertTrue((root / "final_report.md").exists())
            self.assertTrue((root / "triple_card.json").exists())


if __name__ == "__main__": unittest.main()
