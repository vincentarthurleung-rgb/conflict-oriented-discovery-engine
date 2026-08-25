import hashlib
import json
from collections import Counter
from pathlib import Path

from code_engine.extraction_assets.context.pair_scientific_compatibility_v1_candidate import (
    PairSemanticTriggerProjectionV1,
    ScientificDimensionSatisfactionPolicyV1,
    ScientificSemanticRoleInventoryV1,
)


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/20260825_pair_scientific_compatibility_boundary_v1_offline/artifacts"


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
        "scientific_semantic_role_inventory.jsonl",
        "scientific_dimension_satisfaction_policies.jsonl",
        "alignment_semantic_coverage_audit.jsonl",
        "eligible_pair_scientific_compatibility_audit.json",
        "pair_semantic_trigger_projection_before_after.jsonl",
        "trigger_projection_gap_resolution_summary.json",
        "requirement_ownership_audit.json",
        "l4b_v3_v4_candidate_comparison.json",
        "candidate_pair_replay_v4.jsonl",
        "entity_integrity_gate_recheck.json",
        "scientific_state_safety_audit.json",
        "production_leakage_audit.json",
        "autonomous_iteration_ledger.jsonl",
        "final_validation.json",
        "manifest.json",
        "summary.json",
    }


def test_policy_and_role_inventory_validate_and_cover_all_pairs():
    policies = [
        ScientificDimensionSatisfactionPolicyV1.model_validate(row)
        for row in _rows("scientific_dimension_satisfaction_policies.jsonl")
    ]
    inventory = [
        ScientificSemanticRoleInventoryV1.model_validate(row)
        for row in _rows("scientific_semantic_role_inventory.jsonl")
    ]
    assert len(policies) == 5
    assert {row.policy for row in policies} == {
        "resolution_only",
        "compatibility_required",
        "upstream_alignment_required",
        "not_decision_relevant",
        "semantic_role_unresolved",
    }
    assert len(inventory) == 220
    assert len({(row.pair_id, row.dimension_or_semantic) for row in inventory}) == 220
    assert Counter(row.scientific_role for row in inventory) == {
        "proposition_alignment_critical": 121,
        "context_explanatory": 55,
        "comparison_compatibility_critical": 33,
        "explicitly_not_decision_relevant": 11,
    }


def test_alignment_coverage_audit_exposes_core_semantic_gaps_without_mutation():
    rows = _rows("alignment_semantic_coverage_audit.jsonl")
    assert len(rows) == 154
    assert all(row["historical_alignment_modified"] is False for row in rows)
    assert all(row["l4b_re_adjudication_performed"] is False for row in rows)
    assert all(row["string_difference_used_as_incompatibility"] is False for row in rows)
    eligible = _json("eligible_pair_scientific_compatibility_audit.json")
    assert eligible["pair_count"] == 2
    for pair in eligible["pairs"]:
        assert pair["historical_alignment_state"] == "aligned"
        assert pair["overall_outcome"] == "alignment_semantic_coverage_gap"
        assert pair["l4b_v4_candidate_state"] == (
            "reviewable_scientific_compatibility_unresolved"
        )
        assert pair["measurement_target_compatibility"]["outcome"] == (
            "alignment_semantic_coverage_gap"
        )
        assert pair["experimental_contrast"]["outcome"] == (
            "experimental_contrast_compatibility_unresolved"
        )
        assert pair["scientifically_incompatible_concluded"] is False


def test_all_29_projection_gaps_are_classified_without_forcing_materialization():
    projections = [
        PairSemanticTriggerProjectionV1.model_validate(row)
        for row in _rows("pair_semantic_trigger_projection_before_after.jsonl")
    ]
    assert len(projections) == 29
    assert Counter(row.before_coverage_state for row in projections) == {
        "present_upstream_but_not_materialized": 21,
        "partially_materialized": 8,
    }
    assert Counter(row.gap_resolution_state for row in projections) == {
        "repaired_by_deterministic_projection": 13,
        "not_required_after_role_audit": 11,
        "cannot_project_missing_structured_authority": 5,
    }
    repaired = [
        row for row in projections
        if row.gap_resolution_state == "repaired_by_deterministic_projection"
    ]
    assert all(row.dimension in {"biological_model", "disease"} for row in repaired)
    assert all(row.source_fact_ids and row.authority_refs for row in repaired)
    assert not any(row.free_text_inference_used for row in projections)
    assert not any(row.fuzzy_scientific_inference_used for row in projections)
    assert not any(row.llm_used for row in projections)


def test_v4_replay_preserves_gates_and_does_not_optimize_pair_outcomes():
    rows = _rows("candidate_pair_replay_v4.jsonl")
    comparison = _json("l4b_v3_v4_candidate_comparison.json")
    assert len(rows) == 11
    assert Counter(row["l4b_v4_candidate_state"] for row in rows) == {
        "blocked_upstream_alignment": 9,
        "reviewable_scientific_compatibility_unresolved": 2,
    }
    assert comparison["v4_comparable_count"] == 0
    assert all(row["historical_state_preserved"] for row in rows)
    assert not any(row["alignment_modified"] for row in rows)
    assert not any(row["candidate_modified"] for row in rows)
    assert not any(row["formal_modified"] for row in rows)


def test_requirement_ownership_is_simplified_conceptually_not_destructively():
    audit = _json("requirement_ownership_audit.json")
    assert audit["audited_legacy_shape"]["evaluation_cell_count"] == 440
    assert audit["scientifically_necessary_as_independent_requirement_engines"] is False
    assert audit["destructive_refactor_performed"] is False
    assert audit["legacy_compatibility_preserved"] is True
    assert audit["preferred_candidate_ownership"] == {
        "claim_alignment_and_qualification": "proposition compatibility",
        "l4a": "descriptive Context Difference",
        "l4b": "scientific compatibility and required explanatory Context sufficiency",
        "divergence": "explanation eligibility and evaluation only",
        "formal": "read-only upstream result consumption",
    }


def test_entity_pi3k_formal_and_runtime_safety_are_exact():
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
    assert safety["f389_adjudicated"] is False
    f389 = safety["pi3k"]["signals"][1]
    assert f389["initial_experiment_candidate_count"] == 18
    assert f389["deterministically_excluded_count"] == 11
    assert f389["scientifically_plausible_candidate_count"] == 5
    assert f389["insufficient_evidence_candidate_count"] == 2
    assert f389["final_state"] == "manual_scientific_review_required"
    assert leakage["prohibited_literal_hits"] == []
    assert leakage["hardcoded_pair_id_rule_count"] == 0
    assert all(safety[key] == 0 for key in (
        "provider_calls", "api_calls", "network_calls", "downloads"
    ))


def test_summary_metrics_close_exactly():
    metrics = _json("summary.json")["metrics"]
    assert metrics == {
        "pair_count": 11,
        "semantic_inventory_count": 220,
        "policy_count": 5,
        "alignment_audit_unit_count": 154,
        "eligible_pair_count": 2,
        "projection_gap_unit_count": 29,
        "projection_repaired_count": 13,
        "projection_missing_authority_count": 5,
        "projection_semantic_role_unresolved_count": 0,
        "projection_ambiguous_count": 0,
        "projection_not_required_count": 11,
        "l4b_v3_comparable_count": 0,
        "l4b_v4_comparable_count": 0,
        "l4b_v4_reviewable_count": 2,
        "l4b_v4_upstream_blocked_count": 9,
        "l4b_v4_scientifically_incompatible_count": 0,
    }


def test_final_validation_has_no_new_failures():
    final = _json("final_validation.json")
    assert final["status"] == "completed"
    assert final["new_failure_ids"] == []
    assert final["compileall"] == final["git_diff_check"] == "passed"
    assert final["final_failure_ids"] == final["baseline_failure_ids"]
    assert final["full_suite_failure_count"] == len(final["baseline_failure_ids"]) == 5


def test_manifest_hashes_every_generated_artifact_except_itself():
    manifest = _json("manifest.json")
    assert manifest["file_count"] == len(manifest["files"]) == 16
    for item in manifest["files"]:
        path = ROOT / item["path"]
        assert path.stat().st_size == item["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
