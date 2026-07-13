import json
import os
import tempfile
import unittest
from pathlib import Path

from code_engine.fulltext.reasoning_trace import (
    consolidate_context_for_trace,
    retrieve_claim_centered_passages,
    run_fulltext_context_consolidation_stage,
    run_fulltext_reasoning_trace_stage,
)
from code_engine.fulltext.fulltext_l1_extractor import run_fulltext_l1_extraction
from code_engine.integration.atlas_handoff import build_handoff_manifest
from code_engine.system_b.adapters.fulltext_reentry_v5 import FulltextReentryV5Adapter


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


class FulltextReasoningTraceTests(unittest.TestCase):
    def claim(self):
        return {
            "claim_id": "ft_claim_1",
            "case_id": "case",
            "paper_id": "P1",
            "pmid": "1",
            "pmcid": "PMC1",
            "source_scope": "full_text",
            "subject": "NUSAP1",
            "predicate": "promotes",
            "object": "proliferation",
            "polarity": "positive",
            "evidence_sentence": "NUSAP1 promoted proliferation.",
            "context": {"cell_type": "HCT116"},
        }

    def article(self):
        return {
            "sections": [
                {"section_title": "Results", "text": "NUSAP1 was silenced using siRNA. NUSAP1 promoted proliferation. Proliferation decreased after knockdown. Re-expression rescued proliferation."},
                {"section_title": "Methods", "text": "Cells were transfected for 48 h and measured by CCK-8 assay with control siRNA."},
                {"section_title": "Discussion", "text": "Collectively, these results suggest that NUSAP1 supports proliferation."},
            ]
        }

    def extractor(self, prompt, context):
        payload = json.loads(prompt.split("PAYLOAD: ", 1)[1])
        by_text = {p["text"]: p["sentence_ids"][0] for p in payload["passages"]}
        return {
            "trace_status": "complete",
            "reasoning_steps": [
                {"role": "loss_of_function", "reported_text": "NUSAP1 was silenced using siRNA.", "sentence_ids": [by_text["NUSAP1 was silenced using siRNA."]], "provenance_type": "reported"},
                {"role": "observation", "reported_text": "Proliferation decreased after knockdown.", "sentence_ids": [by_text["Proliferation decreased after knockdown."]], "provenance_type": "reported"},
                {"role": "rescue_experiment", "reported_text": "Re-expression rescued proliferation.", "sentence_ids": [by_text["Re-expression rescued proliferation."]], "provenance_type": "reported"},
                {"role": "author_interpretation", "reported_text": "Collectively, these results suggest that NUSAP1 supports proliferation.", "sentence_ids": [by_text["Collectively, these results suggest that NUSAP1 supports proliferation."]], "provenance_type": "reported"},
            ],
            "author_conclusion": {},
            "experimental_context": {
                "cell_type": ["HCT116"],
                "intervention_type": ["siRNA"],
                "intervention_target": ["NUSAP1"],
                "control_group": ["control siRNA"],
                "duration": ["48 h"],
                "assay_method": ["CCK-8 assay"],
                "measured_endpoint": ["proliferation"],
            },
        }

    def test_retrieval_is_claim_centered_and_keeps_sentence_ids(self):
        passages, _ = retrieve_claim_centered_passages(self.claim(), self.article(), {"paper_id": "P1", "pmcid": "PMC1"})
        self.assertTrue(passages)
        self.assertTrue(all(row["paper_id"] == "P1" for row in passages))
        self.assertTrue(all(row["sentence_ids"] for row in passages))
        texts = [row["text"] for row in passages]
        self.assertIn("NUSAP1 promoted proliferation.", texts)

    def test_trace_does_not_modify_claim_and_rejects_unanchored_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = os.getcwd()
            os.chdir(tmp)
            try:
                run = Path("run"); artifacts = run / "artifacts"
                write_jsonl(artifacts / "l35_fulltext_l1_claims.jsonl", [self.claim()])
                write_jsonl(artifacts / "l35_fulltext_oa_candidate_papers.jsonl", [{"paper_id": "P1", "pmid": "1", "pmcid": "PMC1"}])
                write_json(artifacts / "fulltext/pmc_oa/PMC1/article_text.json", self.article())
                summary = run_fulltext_reasoning_trace_stage(run, api_enabled=True, network_enabled=True, extractor=self.extractor)
                self.assertEqual(summary["reasoning_complete_count"], 1)
                trace = json.loads((artifacts / "fulltext_reasoning_traces.jsonl").read_text().splitlines()[0])
                self.assertEqual(self.claim()["subject"], "NUSAP1")
                self.assertEqual(trace["claim_id"], "ft_claim_1")
                self.assertTrue(all(step["sentence_ids"] for step in trace["reasoning_steps"]))
                self.assertTrue(trace["strength_profile"]["has_rescue_experiment"])
            finally:
                os.chdir(old)

    def test_context_consolidation_separates_claim_and_evidence_context(self):
        trace = {
            "reasoning_trace_id": "rt1",
            "trace_status": "complete",
            "reasoning_steps": [{"sentence_ids": ["s1"]}],
            "experimental_context": {"duration": ["48 h"], "assay_method": ["CCK-8"]},
            "strength_profile": {"has_intervention": True},
        }
        row = consolidate_context_for_trace(self.claim(), trace)
        self.assertEqual(row["claim_scoped_context"]["cell_type"], ["HCT116"])
        self.assertEqual(row["evidence_chain_context"]["duration"], ["48 h"])
        self.assertEqual(row["field_provenance"]["duration"][0]["source"], "reasoning_trace")

    def test_cache_hit_on_second_run_without_api_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = os.getcwd()
            os.chdir(tmp)
            try:
                for dirname in ("run1", "run2"):
                    artifacts = Path(dirname) / "artifacts"
                    write_jsonl(artifacts / "l35_fulltext_l1_claims.jsonl", [self.claim()])
                    write_jsonl(artifacts / "l35_fulltext_oa_candidate_papers.jsonl", [{"paper_id": "P1", "pmid": "1", "pmcid": "PMC1"}])
                    write_json(artifacts / "fulltext/pmc_oa/PMC1/article_text.json", self.article())
                first = run_fulltext_reasoning_trace_stage("run1", api_enabled=True, network_enabled=True, extractor=self.extractor)
                second = run_fulltext_reasoning_trace_stage("run2", api_enabled=True, network_enabled=True, extractor=lambda *_: (_ for _ in ()).throw(RuntimeError("should not call")))
                self.assertEqual(first["api_call_count"], 1)
                self.assertEqual(second["cache_hit_count"], 1)
                self.assertEqual(second["api_call_count"], 0)
            finally:
                os.chdir(old)

    def test_fulltext_l1_shared_cache_hit_across_run_directories(self):
        class Client:
            def __init__(self, fail=False):
                self.calls = 0
                self.fail = fail
            def extract_json(self, *args, **kwargs):
                self.calls += 1
                if self.fail:
                    raise RuntimeError("should not call provider")
                return {"claims":[{"subject":"A","predicate":"activates","object":"B","polarity":"positive","evidence_sentence":"A activates B.","confidence":0.9}]}
        with tempfile.TemporaryDirectory() as tmp:
            old = os.getcwd()
            os.chdir(tmp)
            try:
                for run in ("run1", "run2"):
                    artifacts = Path(run) / "artifacts"
                    write_jsonl(artifacts / "candidates.jsonl", [{"case_id":"case","pmid":"1","pmcid":"PMC1","paper_id":"1","subject":"A","object":"B","conflict_relation":"activates"}])
                    write_json(artifacts / "fulltext/pmc_oa/PMC1/article_text.json", {"sections":[{"section_title":"Results","text":"A activates B. A activates B again."}]})
                first_client = Client()
                first = run_fulltext_l1_extraction(run_dir=Path("run1"), fulltext_candidates_path=Path("run1/artifacts/candidates.jsonl"), parsed_articles_dir=Path("run1/artifacts/fulltext/pmc_oa"), l1_provider="mock", l1_model="m1", api_enabled=True, network_enabled=True, client=first_client)
                second_client = Client(fail=True)
                second = run_fulltext_l1_extraction(run_dir=Path("run2"), fulltext_candidates_path=Path("run2/artifacts/candidates.jsonl"), parsed_articles_dir=Path("run2/artifacts/fulltext/pmc_oa"), l1_provider="mock", l1_model="m1", api_enabled=True, network_enabled=True, client=second_client)
                self.assertEqual(first["summary"]["api_calls_made"], 1)
                self.assertEqual(second["summary"]["cache_hits"], 1)
                self.assertEqual(second["summary"]["api_calls_made"], 0)
                self.assertEqual(second_client.calls, 0)
            finally:
                os.chdir(old)

    def test_handoff_optional_artifacts_and_adapter_do_not_create_conflict_edges(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp) / "runs"; run = runs / "r1"; artifacts = run / "artifacts"
            for lane in ("fulltext_core_seed_observations", "fulltext_seed_neighborhood_observations", "fulltext_reviewable_relations", "fulltext_off_seed_relations"):
                write_jsonl(artifacts / f"{lane}.jsonl", [])
            row = {**self.claim(), "evidence_lane": "core_seed_relation", "relation_class": "causal_regulation", "conflict_eligible": False, "exploratory_graph_eligible": True, "direction": "positive"}
            write_jsonl(artifacts / "fulltext_core_seed_observations.jsonl", [row])
            write_jsonl(artifacts / "l35_fulltext_l1_claims.jsonl", [self.claim()])
            write_jsonl(artifacts / "fulltext_reasoning_traces.jsonl", [{"claim_id": "ft_claim_1", "reasoning_trace_id": "rt1", "trace_status": "complete", "reasoning_steps": [], "strength_profile": {"has_intervention": True}}])
            write_jsonl(artifacts / "fulltext_context_consolidations.jsonl", [{"claim_id": "ft_claim_1", "consolidated_context": {"intervention_type": ["siRNA"]}, "field_provenance": {}}])
            write_json(artifacts / "fulltext_reasoning_trace_summary.json", {"eligible_fulltext_claim_count": 1})
            write_json(artifacts / "fulltext_context_consolidation_summary.json", {"consolidation_count": 1})
            write_json(run / "fulltext_reentry_manifest.json", {"status": "completed", "network_used": False, "api_used": False, "case_id": "case", "input_fulltext_claim_count": 1, "core_seed_relation_count": 1, "seed_neighborhood_mechanism_count": 0, "reviewable_context_relation_count": 0, "off_seed_relation_count": 0, "exploratory_graph_eligible_count": 1, "conflict_eligible_count": 0})
            write_jsonl(artifacts / "fulltext_reentry_audit.jsonl", [{"exploratory_graph_eligible": True, "conflict_eligible": False}])
            manifest = build_handoff_manifest(run, runs_root=runs)
            self.assertIn("fulltext_reasoning_traces", manifest["artifacts"])
            self.assertIn("reasoning_traces", manifest["available_capabilities"])
            projected = FulltextReentryV5Adapter().project({"manifest": manifest, "run_dir": run, "manifest_hash": "h"}, prediction_run_id="pred")
            self.assertEqual(len(projected["conflict_predictions"]), 0)
            self.assertEqual(len(projected["exploratory_triples"]), 1)
            self.assertEqual(projected["context_rows"][0]["intervention_type"], "siRNA")
            self.assertEqual(projected["dossier_evidence"][0]["reasoning_trace"]["reasoning_trace_id"], "rt1")


if __name__ == "__main__":
    unittest.main()
