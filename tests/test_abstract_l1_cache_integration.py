import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from code_engine.corpus.corpus_cache import compute_text_hash
from code_engine.corpus.l1_task_cache import L1TaskCacheRecord, L1TaskSignature, build_l1_task_cache_key, store_l1_task_cache_record
from code_engine.workflow.steps import run_abstract_l1_step


class FailClient:
    def extract_json(self, prompt):
        raise AssertionError("cache hit must not invoke LLM")


class AbstractCacheIntegrationTests(unittest.TestCase):
    def test_hit_rewrites_current_run_provenance_and_force_bypasses(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); run = root / "run"; artifacts = run / "artifacts"; artifacts.mkdir(parents=True)
            abstract = "sirolimus affects mtor"; canonical = "P"
            paper = {"paper_id": "OLD", "canonical_paper_id": canonical, "abstract": abstract, "title": "T", "journal": "J"}
            (artifacts / "acquisition_report.json").write_text(json.dumps({"candidate_papers": [paper]}))
            (artifacts / "domain_profile.json").write_text(json.dumps({"domain_id": "bio", "prompt_profile_id": "profile"}))
            (artifacts / "run_paper_manifest.jsonl").write_text(json.dumps({"original_paper_id": "OLD", "paper_id": "OLD", "canonical_paper_id": canonical, "title": "T", "journal": "J"}) + "\n")
            signature = L1TaskSignature(task_family="abstract_claim_screening", source_scope="abstract", canonical_paper_id=canonical, content_hash=compute_text_hash(abstract), schema_version="abstract_claim_v1", prompt_profile_id="profile", prompt_fingerprint="profile", model_name="FailClient", domain_id="bio", l1_mode="abstract_screening")
            now = datetime.now(timezone.utc).isoformat(); key = build_l1_task_cache_key(signature)
            claim = {"claim_id": "C", "paper_id": "OLD", "source_scope": "abstract"}
            store_l1_task_cache_record(L1TaskCacheRecord(task_cache_key=key, signature=signature, status="stored", artifact_refs={"claims": [claim]}, claim_count=1, created_at=now, updated_at=now, run_ids=["ORIGINAL"]), root / "corpus/l1_task_cache")
            result = run_abstract_l1_step(run_dir=run, execute=True, api=True, max_papers=None, l1_mode="abstract_screening", l1_llm_client=FailClient(), repository_root=root, global_corpus_dir=root / "corpus")
            current = json.loads((artifacts / "abstract_l1_claims.jsonl").read_text())
            self.assertEqual(result.counts["abstract_l1_cache_hit_count"], 1)
            self.assertTrue(current["reused_from_cache"])
            self.assertEqual(current["original_run_id"], "ORIGINAL")
            forced = run_abstract_l1_step(run_dir=run, execute=False, api=False, max_papers=None, repository_root=root, global_corpus_dir=root / "corpus", force_reprocess_l1=True)
            self.assertEqual(forced.counts["abstract_l1_cache_hit_count"], 0)


if __name__ == "__main__": unittest.main()
