from __future__ import annotations

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CTX = ROOT / "runs/20260816_hif1a_experimental_context_gap_closure_v2_offline/artifacts"
E2E = ROOT / "runs/20260816_full_line_single_case_e2e_validation_v1_offline/artifacts"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def lines(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


@pytest.mark.parametrize("name", [
    "context_gap_baseline_inventory_v2.json", "context_scope_records_v1.jsonl",
    "context_scope_validation.json", "context_field_candidates_v2.jsonl",
    "context_field_validated_v2.jsonl", "context_composition_v2.jsonl",
    "context_inheritance_candidates.jsonl", "context_inheritance_accepted.jsonl",
    "context_inheritance_rejected.jsonl", "context_scope_closure_audit.jsonl",
    "context_gap_classification_v2.jsonl", "context_provider_requirement_candidates.jsonl",
    "context_coverage_before_after.json", "context_coverage_by_category.csv",
    "context_readiness_v2_candidates.jsonl", "context_robustness_matrix.json",
    "context_negative_regression_results.jsonl", "context_scientific_state_safety_audit.json",
    "context_gap_closure_v2_summary.json", "context_gap_closure_v2_manifest.json",
])
def test_required_context_artifact_exists(name):
    assert (CTX / name).is_file()


@pytest.mark.parametrize("name", [
    "case_selection_candidates.json", "case_selection_decision.json", "frozen_case_input.json",
    "frozen_case_search_plan.json", "stage_execution_ledger.jsonl", "stage_execution_summary.json",
    "core_object_counts.json", "context_object_counts.json", "conflict_object_counts.json",
    "evidence_trace.json", "evidence_trace.md", "case_robustness_audit.json",
    "provider_boundary_audit.json", "scientific_state_transition.json",
    "full_line_case_summary.json", "full_line_case_report.md", "full_line_case_manifest.json",
])
def test_required_e2e_artifact_exists(name):
    assert (E2E / name).is_file()


@pytest.mark.parametrize("scenario", [
    "same_document_same_experiment_same_arm", "same_document_same_experiment_different_arm",
    "same_document_different_experiment", "same_figure_different_panel",
    "same_figure_different_timepoint", "same_genotype_different_dose",
    "same_treatment_different_duration", "same_measurement_different_cohort",
    "same_sentence_two_groups", "same_paragraph_multiple_controls",
    "similar_wording_different_papers", "missing_child_explicit_sibling",
    "one_arm_explicit_other_absent",
])
def test_negative_matrix_matches_expected_decision(scenario):
    result = next(row for row in lines(CTX / "context_negative_regression_results.jsonl")
                  if row["scenario"] == scenario)
    assert result["match"] is True


def test_scope_hierarchy_is_complete_and_orphan_free():
    audit = load(CTX / "context_scope_validation.json")
    assert set(audit["scope_type_counts"]) == {
        "document", "experiment", "arm", "observation", "measurement", "result"
    }
    assert audit["scope_count"] == audit["unique_scope_identity_count"] == 1896
    assert audit["orphan_scope_count"] == 0


def test_scientific_and_provider_boundaries_are_preserved():
    audit = load(CTX / "context_scientific_state_safety_audit.json")
    assert audit["protected_hashes_before"] == audit["protected_hashes_after"]
    assert (audit["candidate_count_before"], audit["candidate_count_after"]) == (11, 11)
    assert (audit["formal_conflict_count_before"], audit["formal_conflict_count_after"]) == (0, 0)
    assert [audit[key] for key in ("provider_calls", "api_calls", "network_calls", "downloads")] == [0, 0, 0, 0]


def test_all_stages_have_allowed_explicit_statuses():
    ledger = lines(E2E / "stage_execution_ledger.jsonl")
    allowed = {"completed", "not_applicable", "blocked", "skipped_by_design", "cache_replayed", "failed"}
    assert len(ledger) == 22
    assert {row["stage_id"] for row in ledger} == {f"S{index}" for index in range(22)}
    assert all(row["status"] in allowed and row["reason"] for row in ledger)


def test_evidence_trace_and_no_forced_scientific_success():
    trace = load(E2E / "evidence_trace.json")
    assert len(trace["steps"]) == 12
    assert all({"object_id", "source_evidence_refs", "authority", "status", "reason"} <= row.keys()
               for row in trace["steps"])
    summary = load(E2E / "full_line_case_summary.json")
    assert summary["qualified_candidate_count"] == summary["formal_conflict_confirmed_count"] == 0
    assert summary["natural_pipeline_boundary"].startswith("S15")


def test_report_answers_all_twenty_two_questions():
    report = (E2E / "full_line_case_report.md").read_text(encoding="utf-8")
    assert all(f"{index}. " in report for index in range(1, 23))


def test_reference_material_is_not_a_production_dependency():
    source = (ROOT / "src/code_engine/extraction_assets/context/closure_v2.py").read_text(encoding="utf-8")
    assert "reference_inputs" not in source and "reference_answer" not in source
