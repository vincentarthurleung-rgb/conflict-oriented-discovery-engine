"""Integrity tests for the beta.2 primary held-out-v2 network snapshot."""

from collections import Counter
import hashlib
import json
import unittest

from tools import run_search_plan_v23_beta_2_primary_heldout_v2_network_retrieval as run


class PrimaryHeldoutV2NetworkRetrievalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.run_dir = run.RUN
        cls.summary = cls.read_json("summary.json")

    @classmethod
    def read_json(cls, name):
        return json.loads((cls.run_dir / name).read_text(encoding="utf-8"))

    @classmethod
    def read_jsonl(cls, name):
        return [json.loads(line) for line in (cls.run_dir / name).read_text(encoding="utf-8").split("\n") if line]

    def test_six_roots_and_frozen_queries(self):
        roots = self.read_json("upstream_root_verification.json")
        self.assertTrue(roots["all_six_exact_roots_verified"])
        logs = self.read_jsonl("query_execution_log.jsonl")
        frozen = {row["query_id"]: row for row in run.load_jsonl(run.QUERIES_PATH)}
        self.assertEqual({row["query_id"] for row in logs}, set(frozen))
        for row in logs:
            self.assertEqual(row["exact_query_string"], frozen[row["query_id"]]["compiled_query"])
            self.assertEqual(row["frozen_query_sha256"], frozen[row["query_id"]]["query_sha256"])
            self.assertIsNone(row["error_state"])

    def test_metadata_snapshot_and_candidate_universe(self):
        manifest = self.read_json("network_metadata_snapshot_manifest.json")
        for name, expected in manifest["components"]:
            self.assertEqual(run.sha(run.ROOT / name), expected)
        self.assertEqual(run.aggregate(manifest["components"]), manifest["network_metadata_snapshot_sha256"])
        candidates = self.read_jsonl("primary_v2_metadata_candidates.jsonl")
        self.assertEqual(len(candidates), 1214)
        self.assertEqual(len({row["candidate_id"] for row in candidates}), 1214)
        self.assertTrue(all(row["metadata_depth"] <= 180 for row in candidates))
        self.assertTrue(all(row["query_provenance"] for row in candidates))

    def test_preacquisition_decisions_are_complete(self):
        candidates = self.read_jsonl("primary_v2_metadata_candidates.jsonl")
        ids = {row["candidate_id"] for row in candidates}
        for name in (
            "primary_v2_base_v22_dispositions.jsonl",
            "primary_v2_p0_decisions.jsonl",
            "primary_v2_p1_decisions.jsonl",
            "primary_v2_p2_decisions.jsonl",
            "primary_v2_policy_a_decisions.jsonl",
            "primary_v2_final_preacquisition_dispositions.jsonl",
        ):
            rows = self.read_jsonl(name)
            self.assertEqual(len(rows), len(candidates))
            self.assertEqual({row["candidate_id"] for row in rows}, ids)
        policy = self.read_jsonl("primary_v2_policy_a_decisions.jsonl")
        self.assertTrue(all(not row["tier_b_to_tier_a_promoted"] for row in policy))
        self.assertTrue(all(not row["hard_rejected_by_policy_a"] for row in policy))

    def test_selection_budget_and_pass_a_blinding(self):
        selected = self.read_jsonl("primary_v2_acquisition_selection.jsonl")
        counts = Counter(row["case_id"] for row in selected)
        self.assertTrue(all(count <= 10 for count in counts.values()))
        self.assertTrue(all(not row["fulltext_content_present"] for row in selected))
        views = self.read_jsonl("primary_v2_pass_a_blinded_views.jsonl")
        self.assertEqual(len(views), len(selected))
        allowed = {
            "artifact_schema_version", "review_id", "ScientificPropositionTargetV1",
            "title", "abstract", "publication_metadata",
            "frozen_preacquisition_retrieval_evidence",
        }
        forbidden = {
            "candidate_id", "case_id", "tier", "final_v23_beta_disposition",
            "base_v22_disposition", "gate_states", "P0_state", "P1_state", "P2_state",
            "query_id", "query_family", "query_rank", "candidate_rank", "fulltext", "adjudication",
        }
        for view in views:
            self.assertEqual(set(view), allowed)
            self.assertTrue(set(view).isdisjoint(forbidden))
            self.assertEqual(
                set(view["frozen_preacquisition_retrieval_evidence"]),
                {"metadata_resolution_status", "abstract_availability", "publication_type_authority", "identifier_resolution_status"},
            )
        expected = (self.run_dir / "primary_v2_pass_a_blinded_views_sha256").read_text().strip()
        self.assertEqual(run.sha(self.run_dir / "primary_v2_pass_a_blinded_views.jsonl"), expected)

    def test_fulltext_temporal_boundary_and_no_replacements(self):
        selection_sha = (self.run_dir / "primary_v2_acquisition_selection_sha256").read_text().strip()
        views_sha = (self.run_dir / "primary_v2_pass_a_blinded_views_sha256").read_text().strip()
        fulltexts = self.read_jsonl("primary_v2_fulltext_acquisition_manifest.jsonl")
        self.assertEqual(len(fulltexts), 60)
        for row in fulltexts:
            self.assertTrue(row["selection_frozen_before_download"])
            self.assertEqual(row["selection_sha256_at_download"], selection_sha)
            self.assertTrue(row["pass_a_views_frozen_before_download"])
            self.assertEqual(row["pass_a_views_sha256_at_download"], views_sha)
            self.assertFalse(row["replacement_performed"])
            self.assertEqual(row["acquisition_status"], "SUCCESS")

    def test_trace_validation_and_aggregate_root(self):
        trace = self.read_json("retrieval_provenance_trace.json")
        self.assertTrue(trace["all_selected_papers_have_complete_trace"])
        self.assertEqual(trace["selected_candidate_count"], trace["complete_trace_count"])
        validation = self.read_json("validation.json")
        self.assertEqual(validation["status"], "PASS")
        self.assertTrue(all(validation["checks"].values()))
        manifest = self.read_json("implementation_manifest.json")
        for name, expected in manifest["aggregate_components"]:
            self.assertEqual(run.sha(self.run_dir / name), expected)
        self.assertEqual(
            run.aggregate(manifest["aggregate_components"]),
            manifest["primary_heldout_v2_network_retrieval_sha256"],
        )

    def test_scientific_and_network_boundaries(self):
        self.assertEqual(self.summary["new_scientific_adjudication_calls"], 0)
        self.assertEqual(self.summary["provider_calls"], 0)
        self.assertEqual(self.summary["llm_calls"], 0)
        self.assertTrue(self.summary["retrieval_started"])
        self.assertFalse(self.summary["historical_assets_modified"])
        self.assertEqual(
            self.summary["network_calls"],
            self.summary["search_network_calls"]
            + self.summary["metadata_network_calls"]
            + self.summary["oa_lookup_network_calls"]
            + self.summary["fulltext_download_network_calls"],
        )


if __name__ == "__main__":
    unittest.main()
