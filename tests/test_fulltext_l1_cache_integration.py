import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from code_engine.corpus.corpus_cache import compute_text_hash
from code_engine.corpus.l1_task_cache import L1TaskCacheRecord, L1TaskSignature, build_l1_task_cache_key, store_l1_task_cache_record
from code_engine.workflow.steps import run_fulltext_l1_step


class FailFulltextClient:
    def extract_json(self, prompt):
        raise AssertionError("full-text cache hit must not call LLM")


class FulltextCacheIntegrationTests(unittest.TestCase):
    def test_selected_span_hit_and_changed_content_miss(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); run = root / "run"; artifacts = run / "artifacts"; artifacts.mkdir(parents=True)
            paper = {"paper_id": "OLD", "canonical_paper_id": "P", "title": "T", "journal": "J", "sections": [{"section_id": "R", "title": "Results", "text": "Sirolimus inhibited mTOR in mouse cells."}]}
            (artifacts / "acquisition_report.json").write_text(json.dumps({"candidate_papers": [paper]}))
            (artifacts / "abstract_conflict_candidates.jsonl").write_text(json.dumps({"candidate_id": "C", "subject_name": "sirolimus", "object_name": "mTOR", "claim_ids": []}) + "\n")
            (artifacts / "fulltext_escalation_papers.jsonl").write_text(json.dumps({"paper_id": "OLD", "candidate_id": "C"}) + "\n")
            (artifacts / "domain_profile.json").write_text(json.dumps({"domain_id": "bio", "prompt_profile_id": "profile"}))
            (artifacts / "run_paper_manifest.jsonl").write_text(json.dumps({"original_paper_id": "OLD", "paper_id": "OLD", "canonical_paper_id": "P", "title": "T", "journal": "J"}) + "\n")
            run_fulltext_l1_step(run_dir=run, execute=False, api=False, repository_root=root, l1_mode="progressive_fulltext", enable_fulltext_escalation=True, l1_task_cache_enabled=False)
            span = json.loads((artifacts / "selected_fulltext_spans.jsonl").read_text())
            signature = L1TaskSignature(task_family="fulltext_evidence_extraction", source_scope="span", canonical_paper_id="P", content_hash=compute_text_hash(span["text"]), schema_version="fulltext_evidence_v1", prompt_profile_id="profile", prompt_fingerprint="profile", model_name="FailFulltextClient", domain_id="bio", l1_mode="progressive_fulltext")
            now = datetime.now(timezone.utc).isoformat(); key = build_l1_task_cache_key(signature)
            evidence = {"evidence_id": "E", "paper_id": "OLD", "evidence_span_id": span["span_id"], "source_scope": "full_text"}
            store_l1_task_cache_record(L1TaskCacheRecord(task_cache_key=key, signature=signature, status="stored", artifact_refs={"evidence_records": [evidence], "claims": []}, evidence_count=1, created_at=now, updated_at=now, run_ids=["ORIGINAL"]), root / "corpus/l1_task_cache")
            hit = run_fulltext_l1_step(run_dir=run, execute=True, api=True, repository_root=root, l1_mode="progressive_fulltext", enable_fulltext_escalation=True, l1_llm_client=FailFulltextClient(), global_corpus_dir=root / "corpus")
            self.assertEqual(hit.counts["fulltext_l1_cache_hit_count"], 1)
            paper["sections"][0]["text"] = "Sirolimus activated mTOR in human cells."
            (artifacts / "acquisition_report.json").write_text(json.dumps({"candidate_papers": [paper]}))
            miss = run_fulltext_l1_step(run_dir=run, execute=False, api=False, repository_root=root, l1_mode="progressive_fulltext", enable_fulltext_escalation=True, global_corpus_dir=root / "corpus")
            self.assertEqual(miss.counts["fulltext_l1_cache_miss_count"], 1)


if __name__ == "__main__": unittest.main()
