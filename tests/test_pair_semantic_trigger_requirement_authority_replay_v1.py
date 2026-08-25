import hashlib
import json
from collections import Counter
from pathlib import Path

from code_engine.extraction_assets.context.pair_requirements_v3_candidate import (
    PairContextRequirementActivationV3Candidate,
    PairContextRequirementSatisfactionV3Candidate,
    PairSemanticTriggerCoverageV1,
    PairSemanticTriggerFactV1,
    UpstreamTriggerProjectionGapV1,
)


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/20260825_pair_semantic_trigger_coverage_requirement_authority_v1_offline/artifacts"


def _json(name):
    return json.loads((ART / name).read_text(encoding="utf-8"))


def _rows(name):
    return [
        json.loads(line)
        for line in (ART / name).read_text(encoding="utf-8").splitlines()
        if line
    ]


def test_all_required_offline_artifacts_exist():
    assert {path.name for path in ART.iterdir() if path.is_file()} == {
        "baseline.json",
        "pair_semantic_trigger_facts_v1.jsonl",
        "pair_semantic_trigger_coverage_v1.jsonl",
        "upstream_trigger_projection_gaps_v1.jsonl",
        "pair_context_requirement_activations_v3_candidate.jsonl",
        "pair_context_requirement_satisfaction_v3_candidate.jsonl",
        "l4b_v2_v3_comparison.json",
        "candidate_pair_replay_v3.jsonl",
        "weak_eligible_pair_trigger_audit.json",
        "entity_integrity_gate_recheck.json",
        "scientific_state_safety_audit.json",
        "production_leakage_audit.json",
        "autonomous_iteration_ledger.jsonl",
        "final_validation.json",
        "manifest.json",
        "summary.json",
    }


def test_fact_coverage_and_projection_gap_rows_validate_strictly():
    facts = [PairSemanticTriggerFactV1.model_validate(row) for row in _rows(
        "pair_semantic_trigger_facts_v1.jsonl"
    )]
    coverage = [PairSemanticTriggerCoverageV1.model_validate(row) for row in _rows(
        "pair_semantic_trigger_coverage_v1.jsonl"
    )]
    gaps = [UpstreamTriggerProjectionGapV1.model_validate(row) for row in _rows(
        "upstream_trigger_projection_gaps_v1.jsonl"
    )]
    assert len(facts) == len(gaps) == 133
    assert len({row.trigger_fact_id for row in facts}) == 133
    assert len(coverage) == 88
    assert len({(row.pair_id, row.dimension) for row in coverage}) == 88
    assert all(row.resolved_in_v3_candidate_sidecar for row in gaps)
    assert not any("weak-" in row.reason for row in facts)


def test_coverage_states_remain_disjoint_and_metrics_close():
    coverage = _rows("pair_semantic_trigger_coverage_v1.jsonl")
    counts = Counter(row["coverage_state"] for row in coverage)
    assert counts == {
        "fully_materialized": 33,
        "partially_materialized": 8,
        "present_upstream_but_not_materialized": 21,
        "absent_from_current_structured_assets": 26,
    }
    metrics = _json("summary.json")["metrics"]
    assert metrics["pair_count"] == 11
    assert metrics["dimension_count"] == 8
    assert metrics["pair_dimension_count"] == 88
    assert metrics["trigger_fact_count"] == 133
    assert metrics["fully_materialized_trigger_unit_count"] == counts["fully_materialized"]
    assert metrics["partially_materialized_trigger_unit_count"] == counts["partially_materialized"]
    assert metrics["upstream_fact_not_materialized_count"] == counts["present_upstream_but_not_materialized"]
    assert metrics["trigger_fact_absent_count"] == counts["absent_from_current_structured_assets"]
    assert metrics["trigger_fact_ambiguous_count"] == 0
    assert metrics["explicit_not_applicable_count"] == 0


def test_all_440_v2_irrelevance_rows_are_reclassified_with_positive_authority_semantics():
    activations = [PairContextRequirementActivationV3Candidate.model_validate(row) for row in _rows(
        "pair_context_requirement_activations_v3_candidate.jsonl"
    )]
    satisfaction = [PairContextRequirementSatisfactionV3Candidate.model_validate(row) for row in _rows(
        "pair_context_requirement_satisfaction_v3_candidate.jsonl"
    )]
    assert len(activations) == len(satisfaction) == 440
    assert len({(row.pair_id, row.consumer, row.dimension) for row in activations}) == 440
    assert Counter(row.activation_state for row in activations) == {
        "comparison_required": 33,
        "not_applicable": 88,
        "requirement_unresolved": 319,
    }
    assert not any(row.activation_state == "explicit_not_decision_relevant" for row in activations)
    assert all(
        row.authority_refs
        for row in activations
        if row.activation_state == "not_applicable"
    )
    assert all(
        row.satisfaction_status.startswith("not_evaluated_")
        for row in satisfaction
        if row.activation_state == "requirement_unresolved"
    )


def test_candidate_replay_preserves_upstream_gates_and_removes_unjustified_comparability():
    rows = _rows("candidate_pair_replay_v3.jsonl")
    assert len(rows) == 11
    assert Counter(row["l4b_v3_candidate_state"] for row in rows) == {
        "blocked_upstream_alignment": 9,
        "reviewable_requirement_semantics_unresolved": 2,
    }
    assert Counter(row["l4b_v2_state"] for row in rows) == {
        "blocked_upstream_alignment": 9,
        "comparable_no_context_sensitive_requirement": 2,
    }
    assert all(row["historical_state_preserved"] for row in rows)
    assert not any(row["candidate_modified"] for row in rows)
    assert not any(row["alignment_modified"] for row in rows)
    assert not any(row["formal_modified"] for row in rows)


def test_two_eligible_pairs_have_actual_core_triggers_and_unresolved_authority():
    audit = _json("weak_eligible_pair_trigger_audit.json")
    assert audit["pair_count"] == 2
    assert audit["production_pair_id_rule_used"] is False
    by_id = {row["candidate_id"]: row for row in audit["pairs"]}
    first = next(row for key, row in by_id.items() if key.startswith("weak-3ca"))
    second = next(row for key, row in by_id.items() if key.startswith("weak-256"))
    for row in (first, second):
        assert row["comparison_required_dimensions"] == [
            "intervention", "measurement", "experimental_design"
        ]
        assert row["requirement_unresolved_dimensions"] == [
            "biological_model", "disease", "genotype", "localization", "temporal"
        ]
        assert row["l4b_v2_state"] == "comparable_no_context_sensitive_requirement"
        assert row["l4b_v3_candidate_state"] == "reviewable_requirement_semantics_unresolved"
        assert row["comparable_no_context_sensitive_requirement_justified"] is False
        assert any(fact["trigger_eligible"] for fact in row["structured_trigger_facts"])
    assert first["historical_context_entry_state"] == "ready"
    assert first["historical_difference_authority_state"] == "ready_not_materialized"
    assert second["historical_context_entry_state"] == "blocked_context_b_unavailable"
    assert second["historical_difference_authority_state"] == "blocked_entry"
    assert second["audit_determination"] == (
        "upstream_trigger_materialization_gap_and_requirement_semantics_unresolved"
    )


def test_scientific_entity_pi3k_and_external_effect_safety_are_exact():
    entity = _json("entity_integrity_gate_recheck.json")
    safety = _json("scientific_state_safety_audit.json")
    leakage = _json("production_leakage_audit.json")
    assert entity["claims_blocked_before"] == entity["claims_blocked_after"] == 241
    assert entity["signals_blocked_before"] == entity["signals_blocked_after"] == 2
    assert safety["core_reference_exact_match_count"] == 33
    assert safety["core_reference_fail_closed_match_count"] == 6
    assert safety["core_reference_mismatch_count"] == 0
    assert safety["candidate_count_before"] == safety["candidate_count_after"] == 11
    assert safety["formal_conflict_count_before"] == safety["formal_conflict_count_after"] == 0
    assert safety["protected_hashes_before"] == safety["protected_hashes_after"]
    assert safety["scientific_bridges_created"] == 0
    assert safety["pi3k"]["signals"][1]["initial_experiment_candidate_count"] == 18
    assert safety["pi3k"]["signals"][1]["deterministically_excluded_count"] == 11
    assert safety["pi3k"]["signals"][1]["scientifically_plausible_candidate_count"] == 5
    assert safety["pi3k"]["signals"][1]["insufficient_evidence_candidate_count"] == 2
    assert leakage["prohibited_literal_hits"] == []
    assert leakage["hardcoded_pair_id_rule_count"] == 0
    assert all(safety[key] == 0 for key in (
        "provider_calls", "api_calls", "network_calls", "downloads"
    ))


def test_summary_metrics_report_all_requested_counts():
    metrics = _json("summary.json")["metrics"]
    assert metrics == {
        "pair_count": 11,
        "dimension_count": 8,
        "pair_dimension_count": 88,
        "trigger_fact_count": 133,
        "fully_materialized_trigger_unit_count": 33,
        "partially_materialized_trigger_unit_count": 8,
        "upstream_fact_not_materialized_count": 21,
        "trigger_fact_absent_count": 26,
        "trigger_fact_ambiguous_count": 0,
        "explicit_not_applicable_count": 0,
        "comparison_required_count": 33,
        "divergence_explanatory_count": 0,
        "explicit_not_decision_relevant_count": 0,
        "not_applicable_count": 88,
        "requirement_unresolved_count": 319,
        "pairs_with_supported_trigger_facts": 11,
        "pairs_with_upstream_unmaterialized_facts": 11,
        "pairs_with_requirement_unresolved": 11,
        "l4b_v2_comparable_count": 2,
        "l4b_v3_comparable_count": 0,
        "l4b_v3_reviewable_count": 2,
        "l4b_v3_blocked_count": 0,
        "l4b_v3_upstream_blocked_count": 9,
    }


def test_final_validation_has_no_new_failures():
    final = _json("final_validation.json")
    assert final["status"] == "completed"
    assert final["new_failure_ids"] == []
    assert final["compileall"] == final["git_diff_check"] == "passed"
    assert final["final_failure_ids"] == final["baseline_failure_ids"]
    assert final["full_suite_failure_count"] == len(final["baseline_failure_ids"]) == 5


def test_manifest_hashes_all_generated_sidecars_except_itself():
    manifest = _json("manifest.json")
    assert manifest["file_count"] == len(manifest["files"]) == 15
    for item in manifest["files"]:
        path = ROOT / item["path"]
        assert path.stat().st_size == item["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
