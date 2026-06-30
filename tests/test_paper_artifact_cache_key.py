import json
import tempfile
import unittest
from pathlib import Path

from code_engine.corpus.paper_artifact_cache import (
    build_paper_artifact_cache_index_from_runs,
    copy_cached_artifact_into_run,
    lookup_paper_artifact,
    new_cache_record,
    store_cache_record,
)


FP = {
    "prompt_template_hash": "p1", "l1_schema_version": "s1", "model_provider": "fake",
    "model_name": "m1", "model_fingerprint": "mf1", "domain_profile": "general",
    "resolver_registry_hash": "r1",
}


class PaperArtifactCacheTests(unittest.TestCase):
    def test_strict_hit_copy_in_and_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source" / "abstract_l1_claims.jsonl"
            source.parent.mkdir()
            source.write_text('{"claim":"x"}\n')
            index = root / "index.jsonl"
            record = new_cache_record(
                canonical_paper_id="paper-1", artifact_type="abstract_l1_claims",
                task_family="abstract_l1", source_artifact_path=source,
                query_independent=True, safe_for_cross_query_reuse=True, **FP,
            )
            self.assertTrue(record.reuse_allowed)
            store_cache_record(record, index)
            hit = lookup_paper_artifact(
                canonical_paper_id="paper-1", artifact_type="abstract_l1_claims",
                task_family="abstract_l1", index_path=index, query_independent=True, **FP,
            )
            self.assertIsNotNone(hit)
            copied = copy_cached_artifact_into_run(hit, root / "current")
            self.assertTrue(copied["copied_into_current_run"])
            self.assertTrue(Path(copied["current_artifact_path"]).is_file())
            self.assertNotEqual(Path(copied["current_artifact_path"]), source)
            mismatch = {**FP, "model_fingerprint": "different"}
            self.assertIsNone(lookup_paper_artifact(
                canonical_paper_id="paper-1", artifact_type="abstract_l1_claims",
                task_family="abstract_l1", index_path=index, query_independent=True, **mismatch,
            ))

    def test_query_specific_and_reasoning_are_not_cross_reused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "abstract_l1_claims.jsonl"
            source.write_text("{}\n")
            index = root / "index.jsonl"
            record = new_cache_record(
                canonical_paper_id="paper-1", artifact_type="abstract_l1_claims",
                task_family="abstract_l1", source_artifact_path=source,
                query_independent=False, safe_for_cross_query_reuse=True,
                query_hash="q1", triple_id="t1", **FP,
            )
            store_cache_record(record, index)
            self.assertIsNone(lookup_paper_artifact(
                canonical_paper_id="paper-1", artifact_type="abstract_l1_claims",
                task_family="abstract_l1", index_path=index, query_independent=False,
                query_hash="q2", triple_id="t2", **FP,
            ))
            reasoning = root / "graph_reasoning_traces.jsonl"
            reasoning.write_text("{}\n")
            blocked = new_cache_record(
                canonical_paper_id="paper-1", artifact_type="raw_payload", task_family="x",
                source_artifact_path=reasoning, query_independent=True,
                safe_for_cross_query_reuse=True, **FP,
            )
            self.assertFalse(blocked.reuse_allowed)

    def test_history_builder_does_not_trust_incomplete_or_reasoning_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifacts = root / "runs" / "old" / "artifacts"
            artifacts.mkdir(parents=True)
            (artifacts / "payload_report.json").write_text("{}")
            (artifacts / "graph_reasoning_traces.jsonl").write_text("{}\n")
            index = root / "index.jsonl"
            report = build_paper_artifact_cache_index_from_runs(root / "runs", index, dry_run=False)
            self.assertEqual(report["candidate_record_count"], 1)
            self.assertEqual(report["reusable_record_count"], 0)
            self.assertEqual(report["reasoning_artifacts_skipped"], 1)
            record = json.loads(index.read_text().splitlines()[0])
            self.assertIn("missing_required_fingerprint", record["warnings"])


if __name__ == "__main__":
    unittest.main()
