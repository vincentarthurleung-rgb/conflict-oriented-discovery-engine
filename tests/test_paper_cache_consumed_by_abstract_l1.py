import json
import hashlib
import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.steps import run_abstract_l1_step, run_fulltext_l1_step


class PaperCacheConsumedByAbstractL1Tests(unittest.TestCase):
    def test_copy_in_claims_are_consumed_without_client_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp); artifacts = run / "artifacts"; imported = artifacts / "cache_imports/paper_P"
            imported.mkdir(parents=True)
            (artifacts / "acquisition_report.json").write_text(json.dumps({"candidate_papers": [{"paper_id": "P", "canonical_paper_id": "P", "abstract": "A"}]}))
            (artifacts / "domain_profile.json").write_text(json.dumps({"domain_id": "general", "prompt_profile_id": "p"}))
            (artifacts / "run_paper_manifest.jsonl").write_text(json.dumps({"paper_id": "P", "canonical_paper_id": "P"}) + "\n")
            (imported / "abstract_l1_claims.jsonl").write_text(json.dumps({"claim_id": "C", "paper_id": "P"}) + "\n")
            (imported / "cache_record.json").write_text(json.dumps({
                "canonical_paper_id": "P", "cache_record_id": "R", "reuse_allowed": True,
                "prompt_template_hash": "p", "l1_schema_version": "abstract_claim_v1",
                "model_provider": "none", "model_name": "none",
                "model_fingerprint": hashlib.sha256(b"builtins.NoneType").hexdigest(),
                "domain_profile": "general",
                "resolver_registry_hash": hashlib.sha256(b"domain_neutral_registry").hexdigest(),
                "query_independent": True,
            }))
            result = run_abstract_l1_step(run_dir=run, execute=False, api=False, max_papers=None,
                                          l1_mode="abstract_screening", repository_root=run)
            claims = [json.loads(line) for line in (artifacts / "abstract_l1_claims.jsonl").read_text().splitlines()]
            self.assertEqual([item["claim_id"] for item in claims], ["C"])
            self.assertTrue(result.summary["paper_cache_consumed_by_l1"])
            self.assertEqual(result.summary["estimated_api_calls_saved"], 1)

    def test_query_specific_copy_in_is_consumed_by_fulltext_l1(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp); artifacts = run / "artifacts"; imported = artifacts / "cache_imports/paper_P"
            imported.mkdir(parents=True)
            seed = {"subject": "s"}
            (run / "run_state.json").write_text(json.dumps({"run_id": "R", "summary": {"triple_metadata": {"triple_id": "T", "query_hash": "Q", "seed_triple": seed}}}))
            (artifacts / "fulltext_acquisition_records.jsonl").write_text(json.dumps({"paper_id": "P", "canonical_paper_id": "P", "selected_for_fulltext": True, "fulltext_available": True, "acquisition_status": "available", "full_text": "Metformin increased AMPK in cancer cells."}) + "\n")
            (artifacts / "abstract_conflict_candidates.jsonl").write_text(json.dumps({"candidate_id": "C", "subject_name": "Metformin", "object_name": "AMPK"}) + "\n")
            (artifacts / "domain_profile.json").write_text(json.dumps({"domain_id": "general", "prompt_profile_id": "p"}))
            (artifacts / "run_paper_manifest.jsonl").write_text(json.dumps({"paper_id": "P", "canonical_paper_id": "P"}) + "\n")
            (imported / "fulltext_l1_claims.jsonl").write_text(json.dumps({"claim_id": "FC", "paper_id": "P"}) + "\n")
            (imported / "cache_record.json").write_text(json.dumps({
                "canonical_paper_id": "P", "cache_record_id": "FR", "reuse_allowed": True,
                "prompt_template_hash": "p", "l1_schema_version": "fulltext_evidence_v1",
                "model_provider": "none", "model_name": "none",
                "model_fingerprint": hashlib.sha256(b"builtins.NoneType").hexdigest(),
                "domain_profile": "general", "resolver_registry_hash": hashlib.sha256(b"domain_neutral_registry").hexdigest(),
                "query_independent": False, "query_hash": "Q", "triple_id": "T",
            }))
            result = run_fulltext_l1_step(run_dir=run, execute=False, api=False, repository_root=run,
                                          l1_mode="progressive_fulltext", enable_fulltext_escalation=True,
                                          l1_task_cache_enabled=False)
            claims = [json.loads(line) for line in (artifacts / "fulltext_l1_claims.jsonl").read_text().splitlines()]
            self.assertEqual([item["claim_id"] for item in claims], ["FC"])
            self.assertTrue(result.summary["paper_cache_consumed_by_l1"])


if __name__ == "__main__": unittest.main()
