import json
import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.steps import run_abstract_conflict_screening_step, run_l2_abstract_step


class ConflictQueryOnlyGateTests(unittest.TestCase):
    def test_query_only_observation_never_reaches_conflict_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp); artifacts = run / "artifacts"; artifacts.mkdir()
            intent = {"seed_triple": {"subject": {"name": "metformin", "aliases": ["metformin"]},
                      "relation": {"name": "activates", "family": "activates"},
                      "object": {"name": "AMPK", "aliases": ["AMPK"]}, "context": {"terms": ["cancer"]}}}
            claim = {"claim_id": "C1", "paper_id": "P1", "subject_raw": "metformin", "object_raw": "AMPK",
                     "relation_raw": "activation", "direction": "increase", "confidence": .9,
                     "evidence_sentence": "Therapeutic activation of AMPK by metformin could inhibit cyst enlargement.",
                     "query_record": {"query": "metformin AMPK cancer", "context_strict": True}}
            (artifacts / "semantic_search_intent.json").write_text(json.dumps(intent))
            (artifacts / "domain_profile.json").write_text(json.dumps({"domain_id": "general_biomedical"}))
            (artifacts / "abstract_l1_claims.jsonl").write_text(json.dumps(claim) + "\n")
            (artifacts / "acquisition_report.json").write_text(json.dumps({"candidate_papers": [{"paper_id": "P1", "title": "ADPKD TAME-PKD clinical trial"}]}))
            l2 = run_l2_abstract_step(run_dir=run, execute=False, api=False, network=False)
            conflict = run_abstract_conflict_screening_step(run_dir=run, min_abstract_evidence_count=1)
            self.assertEqual(l2.summary["core_canonical_observation_count"], 0)
            self.assertEqual(l2.summary["context_query_only_downgraded_from_core_count"], 1)
            self.assertEqual(conflict.counts["abstract_conflict_candidate_count"], 0)


if __name__ == "__main__": unittest.main()
