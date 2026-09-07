"""Independent, offline checks of the candidate gates and frozen-corpus replay."""
from __future__ import annotations

import ast
from collections import defaultdict
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
ENGINE_PATH = ROOT / "tools/search_plan_v22_candidate_gates.py"
RUN = ROOT / "runs/20260907_search_plan_v22_failure_decomposition_counterfactual_replay_offline"
PACK = ROOT / "runs/20260906_retrieval_relevance_audit_packaging_v1_offline"
OVERLAYS = [ROOT / f"runs/20260907_retrieval_relevance_adjudication_batch_{i:02d}_v1_offline" for i in range(1, 6)]
ACCEPTABLE = {"JUSTIFIED", "BORDERLINE_BUT_JUSTIFIED"}
REQUIRED = {
    "baseline_metrics.json", "adjudication_overlay_integrity.json", "failure_inventory.jsonl",
    "failure_decomposition_summary.json", "evidence_mode_detectability_audit.jsonl",
    "evidence_mode_gate_candidate.json", "context_plausibility_gate_candidate.json",
    "endpoint_plausibility_gate_candidate.json", "relation_plausibility_gate_candidate.json",
    "tier_a_v22_candidate_contract.json", "tier_b_v22_candidate_contract.json",
    "reject_v22_candidate_contract.json", "counterfactual_gate_inputs.jsonl",
    "counterfactual_gate_outputs.jsonl", "label_leakage_audit.json",
    "counterfactual_evaluation.json", "counterfactual_case_metrics.jsonl",
    "incremental_gate_ablation.jsonl", "gate_overlap_audit.json",
    "query_family_failure_contribution.jsonl", "query_variant_failure_contribution.jsonl",
    "retrieval_depth_quality_curve.jsonl", "search_plan_v22_candidate_contract.json",
    "heldout_validation_requirements.json", "scientific_state_safety_audit.json",
    "production_leakage_audit.json", "final_validation.json", "manifest.json", "summary.json",
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


class GenericGateTests(unittest.TestCase):
    """Synthetic records exercise scientific rules without any adjudication data."""

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("offline_v22_test_engine", ENGINE_PATH)
        cls.engine = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.engine)

    def fixture(self, abstract=None, **changes):
        source = {
            "title": "SIGNALX investigation",
            "abstract": abstract or "We investigated SIGNALX in cancer cells. SIGNALX reduced cell viability.",
            "publication_types": ["Journal Article"],
            "target": {
                "subject_surfaces": ["SIGNALX"],
                "endpoint_surfaces": ["cell viability"],
                "context_surfaces": ["cancer cells"],
                "endpoint_requirement": "cell viability",
                "measurement_requirement": "cell viability measurement",
                "relation_requirement": "regulation",
                "therapy_identity_requirement": "not required",
                "primary_evidence_required": True,
                "primary_requirement_authority": "synthetic test policy",
            },
        }
        source.update(changes)
        return source

    def evaluate(self, source=None):
        return self.engine.evaluate(source or self.fixture())

    def test_explicit_primary_context_endpoint_relation_pass(self):
        result = self.evaluate()
        self.assertEqual(result["state"], "TIER_A")
        self.assertEqual(result["gates"]["evidence_mode"]["state"], "PRIMARY_EVIDENCE_PLAUSIBLE")
        self.assertEqual(result["gates"]["relation"]["state"], "RELATION_DIRECTLY_PLAUSIBLE")
        self.assertFalse(result["proposition_compatibility_inferred"])

    def test_reliable_review_metadata_respects_primary_evidence_policy(self):
        source = self.fixture(publication_types=["Journal Article", "Review"])
        result = self.evaluate(source)
        self.assertEqual(result["state"], "REJECT")
        self.assertIn("evidence_mode", result["reject_gate_names"])
        self.assertEqual(result["gates"]["evidence_mode"]["authority"], "publication_type_metadata")
        source["target"]["primary_evidence_required"] = False
        allowed = self.evaluate(source)
        self.assertNotEqual(allowed["state"], "REJECT")
        self.assertNotIn("evidence_mode", allowed["reject_gate_names"])
        self.assertEqual(allowed["gates"]["evidence_mode"]["state"], "NON_PRIMARY_EVIDENCE_DETECTED")

    def test_journal_article_alone_does_not_establish_primary_evidence(self):
        result = self.evaluate(self.fixture("SIGNALX reduced cell viability in cancer cells."))
        self.assertEqual(result["gates"]["evidence_mode"]["state"], "EVIDENCE_MODE_UNRESOLVED")
        self.assertEqual(result["state"], "TIER_B")
        self.assertIn("evidence_mode", result["unresolved_fields_requiring_fulltext"])

    def test_review_self_declaration_is_detected_but_citation_is_not(self):
        declared = self.evaluate(self.fixture("This review summarizes how SIGNALX regulates cell viability in cancer cells."))
        self.assertEqual(declared["gates"]["evidence_mode"]["state"], "NON_PRIMARY_EVIDENCE_DETECTED")
        self.assertEqual(declared["state"], "REJECT")
        cited = self.evaluate(self.fixture("Earlier reviews discussed SIGNALX. We investigated SIGNALX in cancer cells. SIGNALX reduced cell viability."))
        self.assertEqual(cited["gates"]["evidence_mode"]["state"], "PRIMARY_EVIDENCE_PLAUSIBLE")
        self.assertNotEqual(cited["state"], "REJECT")
        title_only = self.evaluate(self.fixture(title="Review of SIGNALX studies"))
        self.assertNotEqual(title_only["gates"]["evidence_mode"]["state"], "NON_PRIMARY_EVIDENCE_DETECTED")

    def test_inconsistent_or_unreliable_metadata_uses_abstract(self):
        for options in ({"publication_types": ["Review", "Randomized Controlled Trial"]},
                        {"publication_types": ["Review"], "publication_types_reliable": False}):
            with self.subTest(options=options):
                result = self.evaluate(self.fixture(**options))
                self.assertEqual(result["gates"]["evidence_mode"]["state"], "PRIMARY_EVIDENCE_PLAUSIBLE")
                self.assertEqual(result["gates"]["evidence_mode"]["authority"], "deterministic_abstract_self_description")
                self.assertNotIn("evidence_mode", result["reject_gate_names"])

    def test_missing_context_is_unresolved_not_mismatch(self):
        result = self.evaluate(self.fixture("We investigated SIGNALX. SIGNALX reduced cell viability."))
        self.assertEqual(result["gates"]["context"]["state"], "CONTEXT_UNRESOLVED")
        self.assertEqual(result["state"], "TIER_B")
        self.assertNotIn("context", result["reject_gate_names"])

    def test_missing_endpoint_is_unresolved_not_mismatch_or_topic_tier_b(self):
        result = self.evaluate(self.fixture("We investigated SIGNALX expression in cancer cells."))
        self.assertEqual(result["gates"]["endpoint"]["state"], "ENDPOINT_UNRESOLVED")
        self.assertNotIn("endpoint", result["reject_gate_names"])
        self.assertNotIn(result["state"], {"TIER_A", "TIER_B", "REJECT"})
        self.assertFalse(result["acquisition_eligible"])

    def test_positive_foreign_context_and_endpoint_are_mismatches(self):
        context = self.evaluate(self.fixture("We investigated SIGNALX during spinal cord injury. SIGNALX reduced the viability of neurons."))
        self.assertEqual(context["gates"]["context"]["state"], "CONTEXT_MISMATCH_ESTABLISHED")
        self.assertEqual(context["state"], "REJECT")
        endpoint = self.evaluate(self.fixture("We investigated SIGNALX in cancer patients. SIGNALX was associated with overall survival."))
        self.assertEqual(endpoint["gates"]["endpoint"]["state"], "ENDPOINT_MISMATCH_ESTABLISHED")
        self.assertEqual(endpoint["state"], "REJECT")

    def test_explicit_baseline_viability_is_not_changed_tolerance(self):
        source = self.fixture("We investigated SIGNALX in cancer cells. SIGNALX reduced baseline cell viability.")
        source["target"].update(endpoint_surfaces=["adaptation"], endpoint_requirement="changed tolerance adaptation")
        result = self.evaluate(source)
        self.assertEqual(result["gates"]["endpoint"]["state"], "ENDPOINT_MISMATCH_ESTABLISHED")
        self.assertEqual(result["state"], "REJECT")

    def test_cooccurrence_is_tier_b_and_resolution_reason_is_explicit(self):
        result = self.evaluate(self.fixture("We investigated SIGNALX in cancer cells. Cell viability was measured separately."))
        self.assertEqual(result["gates"]["relation"]["state"], "RELATION_REQUIRES_FULLTEXT")
        self.assertEqual(result["state"], "TIER_B")
        self.assertTrue(result["known_plausible_fields"])
        self.assertIn("relation", result["unresolved_fields_requiring_fulltext"])
        self.assertEqual(set(result["why_fulltext_can_resolve"]), set(result["unresolved_fields_requiring_fulltext"]))
        self.assertTrue(all(reason.strip() for reason in result["why_fulltext_can_resolve"].values()))

    def test_negative_result_is_not_proposition_incompatibility(self):
        source = self.fixture("We investigated SIGNALX in cancer cells. SIGNALX did not reduce cell viability.")
        result = self.evaluate(source)
        self.assertNotEqual(result["gates"]["relation"]["state"], "RELATION_MISMATCH_ESTABLISHED")
        self.assertNotIn("relation", result["reject_gate_names"])
        self.assertFalse(result["proposition_compatibility_inferred"])

    def test_positive_alternative_ownership_does_not_pass_as_direct_relation(self):
        source = self.fixture("We investigated SIGNALX in cancer cells. Cell viability was controlled solely by OTHER, independently of SIGNALX.")
        result = self.evaluate(source)
        self.assertEqual(result["gates"]["relation"]["state"], "RELATION_MISMATCH_ESTABLISHED")
        self.assertEqual(result["state"], "REJECT")
        self.assertIn("relation", result["reject_gate_names"])

    def test_known_fatal_mismatch_never_becomes_tier_b(self):
        source = self.fixture("This review discusses SIGNALX. Cell viability in cancer cells is considered separately.")
        result = self.evaluate(source)
        self.assertEqual(result["gates"]["relation"]["state"], "RELATION_REQUIRES_FULLTEXT")
        self.assertEqual(result["state"], "REJECT")
        self.assertFalse(result["unresolved_fields_requiring_fulltext"])
        self.assertFalse(result["why_fulltext_can_resolve"])

    def test_subject_rename_and_unread_identifier_metadata_do_not_change_decisions(self):
        original = self.fixture()
        renamed = json.loads(json.dumps(original).replace("SIGNALX", "GENERICZ"))
        renamed["target"].update({"packet_id": "irrelevant-identifier", "pmid": "00000000", "case_id": "other-case"})
        first, second = self.evaluate(original), self.evaluate(renamed)
        self.assertEqual(first["state"], second["state"])
        self.assertEqual(first["reject_gate_names"], second["reject_gate_names"])
        self.assertEqual({name: gate["state"] for name, gate in first["gates"].items()},
                         {name: gate["state"] for name, gate in second["gates"].items()})

    def test_inputs_with_labels_ids_or_fulltext_are_rejected(self):
        for field in ("relevance_state", "acquisition_decision", "contaminant_class", "reviewer_rationale", "confidence", "packet_id", "pmid", "case_id", "fulltext"):
            with self.subTest(field=field):
                source = self.fixture()
                source[field] = "untrusted input"
                with self.assertRaises(ValueError):
                    self.evaluate(source)

    def test_evidence_is_exact_preacquisition_span_or_metadata(self):
        fixtures = [self.fixture(), self.fixture(publication_types=["Review"]),
                    self.fixture("We investigated SIGNALX during spinal cord injury. SIGNALX reduced the viability of neurons.")]
        for source in fixtures:
            result = self.evaluate(source)
            for gate in result["gates"].values():
                for evidence in gate["evidence"]:
                    self.assertTrue(evidence["authority"])
                    if evidence["field"] == "publication_types":
                        self.assertEqual(source["publication_types"][evidence["index"]], evidence["quote"])
                    else:
                        self.assertIn(evidence["field"], {"title", "abstract"})
                        self.assertGreater(evidence["end"], evidence["start"])
                        self.assertEqual(source[evidence["field"]][evidence["start"]:evidence["end"]], evidence["quote"])

    def test_pure_evaluation_performs_no_io_and_preserves_input(self):
        source = self.fixture()
        before = deepcopy(source)
        expected = self.evaluate(source)
        with patch("builtins.open", side_effect=AssertionError("file IO forbidden")), \
             patch.object(Path, "open", side_effect=AssertionError("path IO forbidden")), \
             patch.object(socket, "socket", side_effect=AssertionError("network forbidden")):
            self.assertEqual(self.evaluate(source), expected)
        self.assertEqual(source, before)
        parsed = ast.parse(ENGINE_PATH.read_text(encoding="utf-8"))
        imported = {node.module for node in ast.walk(parsed) if isinstance(node, ast.ImportFrom)}
        imported |= {name.name for node in ast.walk(parsed) if isinstance(node, ast.Import) for name in node.names}
        self.assertTrue(imported <= {"__future__", "re", "typing"}, imported)


class OutputBoundaryTests(unittest.TestCase):
    def test_historical_output_target_is_refused_before_work(self):
        pilot = ROOT / "runs/20260906_search_plan_v21_retrieval_calibration_pilot_v1"
        inventory = lambda: {
            str(p.relative_to(pilot)): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in pilot.rglob("*") if p.is_file()
        }
        before = inventory()
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/generate_search_plan_v22_counterfactual_offline.py"), "--output", str(pilot)],
            cwd=ROOT, capture_output=True, text=True, timeout=5, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("historical outputs cannot be overwritten", result.stderr)
        self.assertFalse(result.stdout)
        self.assertEqual(inventory(), before)


class FrozenReplayArtifactTests(unittest.TestCase):
    """Evaluation tests read labels only after the replay artifacts exist."""

    @classmethod
    def setUpClass(cls):
        if not (RUN / "manifest.json").exists():
            raise unittest.SkipTest("Run artifacts have not yet been generated")
        cls.inputs = read_jsonl(RUN / "counterfactual_gate_inputs.jsonl")
        cls.outputs = read_jsonl(RUN / "counterfactual_gate_outputs.jsonl")
        cls.labels = [row for base in OVERLAYS for row in read_jsonl(base / "adjudications.jsonl")]
        cls.label_by_id = {row["packet_id"]: row for row in cls.labels}

    def assert_rate(self, actual, numerator, denominator):
        self.assertEqual(actual["numerator"], numerator)
        self.assertEqual(actual["denominator"], denominator)
        if denominator:
            self.assertAlmostEqual(actual["value"], numerator / denominator)
        else:
            self.assertIsNone(actual["value"])

    def check_metrics(self, metrics, rows, tier_key):
        self.assertEqual(metrics["paper_count"], len(rows))
        groups = {
            "tier_a": [r for r in rows if r[tier_key] == "TIER_A"],
            "tier_b": [r for r in rows if r[tier_key] == "TIER_B"],
            "overall": rows,
        }
        for prefix, group in groups.items():
            labels = [self.label_by_id[r["packet_id"]] for r in group]
            self.assert_rate(metrics[f"{prefix}_direct_relevance_rate"],
                             sum(r["relevance_state"] == "DIRECTLY_RELEVANT" for r in labels), len(labels))
            justification = "overall_acquisition_justification_rate" if prefix == "overall" else f"{prefix}_justification_rate"
            self.assert_rate(metrics[justification], sum(r["acquisition_decision"] == "JUSTIFIED" for r in labels), len(labels))
            if prefix != "tier_b":
                acceptability = "overall_acquisition_acceptability_rate" if prefix == "overall" else f"{prefix}_acceptability_rate"
                self.assert_rate(metrics[acceptability], sum(r["acquisition_decision"] in ACCEPTABLE for r in labels), len(labels))
        tier_b_labels = [self.label_by_id[r["packet_id"]] for r in groups["tier_b"]]
        self.assert_rate(metrics["tier_b_utility_rate"],
                         sum(r["acquisition_decision"] in ACCEPTABLE and bool(r["fulltext_resolved_fields"]) for r in tier_b_labels),
                         len(tier_b_labels))

    def test_exact_overlay_and_output_bijection(self):
        expected = {r["packet_id"] for r in read_jsonl(PACK / "review_unit_inventory.jsonl")}
        self.assertEqual(len(expected), 79)
        for rows in (self.inputs, self.outputs, self.labels):
            self.assertEqual(len(rows), 79)
            self.assertEqual({r["packet_id"] for r in rows}, expected)
        self.assertTrue(all(isinstance(r["confidence"], str) for r in self.labels))

    def test_baseline_and_counterfactual_metrics_recomputed_from_original_labels(self):
        self.check_metrics(read_json(RUN / "baseline_metrics.json"), self.inputs, "original_tier")
        evaluation = read_json(RUN / "counterfactual_evaluation.json")
        retained = [r for r in self.outputs if r["state"] in {"TIER_A", "TIER_B"}]
        rejected = [r for r in self.outputs if r["state"] == "REJECT"]
        self.assertEqual(len(retained) + len(rejected), 79)
        self.assertEqual(evaluation["retained_count"], len(retained))
        self.assertEqual(evaluation["rejected_count"], len(rejected))
        self.check_metrics(evaluation["retained_set_metrics"], retained, "state")
        direct_retained = sum(self.label_by_id[r["packet_id"]]["relevance_state"] == "DIRECTLY_RELEVANT" for r in retained)
        direct_rejected = sum(self.label_by_id[r["packet_id"]]["relevance_state"] == "DIRECTLY_RELEVANT" for r in rejected)
        self.assertEqual(direct_retained + direct_rejected, 25)
        self.assert_rate(evaluation["calibration_set_direct_relevant_retention"], direct_retained, 25)
        self.assertEqual(evaluation["true_literature_recall"], "not_estimable")

    def test_tier_b_ledgers_and_positive_rejection_reasons(self):
        for row in self.outputs:
            with self.subTest(packet=row["packet_id"]):
                if row["state"] == "REJECT":
                    self.assertTrue(row["reject_gate_names"])
                elif row["state"] == "TIER_B":
                    self.assertFalse(row["reject_gate_names"])
                    self.assertTrue(row["known_plausible_fields"])
                    self.assertTrue(row["unresolved_fields_requiring_fulltext"])
                    self.assertTrue(row["why_fulltext_can_resolve"])
                else:
                    self.assertEqual(row["state"], "TIER_A")
                    self.assertFalse(row["reject_gate_names"])

    def test_removed_label_classes_are_distinct_from_gate_triggers(self):
        evaluations = [read_json(RUN / "counterfactual_evaluation.json")]
        evaluations += read_jsonl(RUN / "incremental_gate_ablation.jsonl")
        outputs = {r["packet_id"]: r for r in self.outputs}
        for evaluation in evaluations:
            rejected = set(evaluation["rejected_packet_ids"])
            labels = [self.label_by_id[p] for p in rejected]
            self.assertEqual(evaluation["wrong_evidence_mode_rejected"],
                             sum(r["relevance_state"] == "WRONG_EVIDENCE_MODE" for r in labels))
            self.assertEqual(evaluation["wrong_endpoint_rejected"],
                             sum(r["relevance_state"] == "WRONG_ENDPOINT" for r in labels))
            self.assertEqual(evaluation["wrong_context_unit_rejected"],
                             sum(r["contaminant_class"] == "wrong_biological_unit" for r in labels))
            self.assertEqual(evaluation["wrong_relation_rejected"],
                             sum(r["contaminant_class"] == "association_vs_functional_relation" for r in labels))
            for name, count in evaluation["gate_triggered_rejections"].items():
                self.assertEqual(count, sum(name in outputs[p]["reject_gate_names"] for p in rejected))

    def test_all_gate_evidence_spans_and_preacquisition_hashes_resolve(self):
        inputs = {r["packet_id"]: r for r in self.inputs}
        checked_paths = set()
        for output in self.outputs:
            original = inputs[output["packet_id"]]
            scientific = original["scientific_input"]
            self.assertEqual(output["scientific_input_sha256"], hashlib.sha256(
                json.dumps(scientific, sort_keys=True, ensure_ascii=False).encode()).hexdigest())
            self.assertEqual(output["pre_acquisition_evidence_refs"], original["pre_acquisition_evidence_refs"])
            for gate in output["gates"].values():
                for evidence in gate["evidence"]:
                    self.assertTrue(evidence["authority"])
                    field = evidence["field"]
                    if field == "publication_types":
                        self.assertEqual(scientific[field][evidence["index"]], evidence["quote"])
                    else:
                        self.assertIn(field, {"title", "abstract"})
                        self.assertGreaterEqual(evidence["start"], 0)
                        self.assertLessEqual(evidence["end"], len(scientific[field]))
                        self.assertGreater(evidence["end"], evidence["start"])
                        self.assertEqual(scientific[field][evidence["start"]:evidence["end"]], evidence["quote"])
            for source in output["pre_acquisition_evidence_refs"].values():
                self.assertNotIn("fulltext", source["path"].lower())
                if source["path"] not in checked_paths:
                    self.assertEqual(hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest(), source["sha256"])
                    checked_paths.add(source["path"])
        self.assertTrue(checked_paths)

    def test_query_diagnostics_preserve_linkage_and_overlapping_counts(self):
        inputs = {r["packet_id"]: r for r in self.inputs}
        outputs = {r["packet_id"]: r for r in self.outputs}
        for group in ("family", "variant"):
            rows = read_jsonl(RUN / f"query_{group}_failure_contribution.jsonl")
            keys = [(r["case_id"], r[f"query_{group}_id"]) for r in rows]
            self.assertEqual(len(set(keys)), len(keys))
            for row in rows:
                expected_ids = {
                    packet for packet, item in inputs.items()
                    if item["case_id"] == row["case_id"] and row[f"query_{group}_id"] in item[f"query_{group}_ids"]
                }
                self.assertEqual(set(row["packet_ids"]), expected_ids)
                self.assertEqual(row["linked_adjudicated_acquisitions"], len(expected_ids))
                direct = sum(self.label_by_id[p]["relevance_state"] == "DIRECTLY_RELEVANT" for p in expected_ids)
                rejected_noise = sum(outputs[p]["state"] == "REJECT" and self.label_by_id[p]["acquisition_decision"] == "NOT_JUSTIFIED" for p in expected_ids)
                self.assertEqual(row["linked_directly_relevant"], direct)
                self.assertEqual(row["rejected_not_justified"], rejected_noise)
                self.assertEqual(row["counterfactual_retained"], sum(outputs[p]["state"] in {"TIER_A", "TIER_B"} for p in expected_ids))
                self.assertEqual(row["mostly_rejected_noise_in_audited_acquisitions"], bool(expected_ids) and rejected_noise > len(expected_ids) / 2)
                self.assertEqual(row["zero_observed_direct_value"], bool(expected_ids) and direct == 0)
                self.assertEqual(row["no_adjudicated_acquisition_not_zero_literature_value"], not expected_ids)
                self.assertEqual(row["only_review_contamination"], bool(expected_ids) and all(self.label_by_id[p]["contaminant_class"] == "review_only" for p in expected_ids))

    def test_depth_preserves_unobserved_tail_and_cumulative_counts(self):
        trajectories = read_jsonl(RUN / "retrieval_depth_quality_curve.jsonl")
        by_case = defaultdict(list)
        for row in trajectories:
            by_case[row["case_id"]].append(row)
        self.assertEqual(len(by_case), 8)
        self.assertEqual(sum(r["adjudication_observed"] for r in trajectories), 79)
        for rows in by_case.values():
            self.assertEqual([r["metadata_first_seen_depth"] for r in rows], list(range(1, len(rows) + 1)))
            direct = not_justified = audited = 0
            for row in rows:
                audited += row["adjudication_observed"]
                direct += row["relevance_state"] == "DIRECTLY_RELEVANT"
                not_justified += row["acquisition_decision"] == "NOT_JUSTIFIED"
                self.assertEqual(row["cumulative_adjudicated"], audited)
                self.assertEqual(row["cumulative_observed_direct"], direct)
                self.assertEqual(row["cumulative_observed_not_justified"], not_justified)
                self.assertFalse(row["saturation_inferred"])
                if not row["adjudication_observed"]:
                    self.assertIsNone(row["relevance_state"])
                    self.assertIsNone(row["acquisition_decision"])
                if row["metadata_first_seen_depth"] > 30:
                    self.assertFalse(row["adjudication_observed"])
                    self.assertEqual(row["depth_31_to_60_direct_yield"], "UNOBSERVED_ABSTRACT_SCREENING_CEILING_30")

    def test_ablation_and_overlap_are_set_arithmetic(self):
        rows_by_id = {r["packet_id"]: r for r in self.outputs}
        stages = read_jsonl(RUN / "incremental_gate_ablation.jsonl")
        previous = set()
        for stage in stages:
            rejected = set(stage["rejected_packet_ids"])
            self.assertEqual(stage["incrementally_removed_count"], len(rejected - previous))
            self.assertEqual(set(stage["incrementally_removed_packet_ids"]), rejected - previous)
            if stage["enabled_gates"] != "all":
                self.assertEqual(rejected, {r["packet_id"] for r in self.outputs if set(r["reject_gate_names"]) & set(stage["enabled_gates"])})
            previous = rejected
        overlap = read_json(RUN / "gate_overlap_audit.json")
        for row in overlap["pairwise_overlap"]:
            self.assertEqual(row["count"], sum(set(row["gates"]) <= set(r["reject_gate_names"]) for r in rows_by_id.values()))
        self.assertFalse(overlap["causal_independence_claimed"])

    def test_gate_worker_is_label_and_fulltext_isolated(self):
        audit = read_json(RUN / "label_leakage_audit.json")
        self.assertFalse(audit["runtime_label_access"])
        self.assertFalse(audit["fulltext_read_during_gate_execution"])
        self.assertEqual(audit["gate_code_sha256_before_label_read"], audit["gate_code_sha256_after_evaluation"])
        self.assertEqual(audit["gate_outputs_sha256_before_label_read"], audit["gate_outputs_sha256_after_evaluation"])
        self.assertEqual(audit["worker_io_audit"]["evaluate_calls"], 79)
        self.assertEqual(set(audit["worker_io_audit"]["file_reads"]), {"counterfactual_gate_inputs.jsonl"})
        self.assertFalse(audit["worker_io_audit"]["forbidden_reads"])
        self.assertEqual(audit["worker_io_audit"]["network_events"], 0)
        self.assertFalse(audit["gate_source_label_field_mentions"])
        self.assertTrue(audit["replayed_after_label_read_identical"])

    def test_required_artifacts_and_hashes(self):
        self.assertFalse(REQUIRED - {p.name for p in RUN.iterdir() if p.is_file()})
        manifest = read_json(RUN / "manifest.json")
        self.assertEqual(manifest["required_artifact_count"], len(REQUIRED))
        indexed = {r["path"] for r in manifest["files"]}
        self.assertEqual(len(indexed), len(manifest["files"]))
        self.assertTrue(REQUIRED - {"manifest.json"} <= indexed)
        for entry in manifest["files"]:
            path = RUN / entry["path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry["sha256"])
            self.assertEqual(path.stat().st_size, entry["bytes"])
        validation = read_json(RUN / "final_validation.json")
        self.assertEqual(validation["status"], "PASS")
        self.assertTrue(all(validation["checks"].values()))
        safety = read_json(RUN / "scientific_state_safety_audit.json")
        for name in ("network_calls", "provider_calls", "llm_calls", "downloads"):
            self.assertEqual(safety[name], 0)
        self.assertFalse(safety["historical_assets_modified"])
        self.assertFalse(safety["production_behavior_modified"])
        self.assertEqual(safety["search_plan_v22_activation_state"], "candidate_not_activated")


if __name__ == "__main__":
    unittest.main()
