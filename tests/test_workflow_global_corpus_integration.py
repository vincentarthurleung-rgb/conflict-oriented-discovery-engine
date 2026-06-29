import json
import tempfile
import unittest
from pathlib import Path
from code_engine.workflow.steps import run_abstract_l1_step, run_payload_step


class WorkflowGlobalCorpusTests(unittest.TestCase):
    def test_manifest_cache_report_and_no_global_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); run = root / "run"; artifacts = run / "artifacts"; artifacts.mkdir(parents=True)
            paper = {"paper_id": "OLD", "pmid": "1", "title": "MTOR paper", "journal": "J", "year": 2024, "abstract": "sirolimus affects mtor"}
            (artifacts / "acquisition_report.json").write_text(json.dumps({"candidate_papers": [paper], "reused_papers": [], "downloaded_papers": [], "warnings": []}))
            (artifacts / "domain_profile.json").write_text(json.dumps({"domain_id": "bio", "prompt_profile_id": "p"}))
            payload = run_payload_step(run_dir=run, execute=False, query="q", repository_root=root, global_corpus_dir=root / "corpus")
            self.assertTrue((artifacts / "run_paper_manifest.jsonl").exists())
            self.assertEqual(payload.counts["paper_dedup_total"], 1)
            self.assertFalse((root / "corpus/paper_registry/paper_registry.jsonl").exists())
            result = run_abstract_l1_step(run_dir=run, execute=False, api=False, max_papers=None, repository_root=root, global_corpus_dir=root / "corpus")
            self.assertTrue((artifacts / "abstract_l1_cache_report.json").exists())
            self.assertEqual(result.counts["abstract_l1_cache_miss_count"], 1)


if __name__ == "__main__": unittest.main()
