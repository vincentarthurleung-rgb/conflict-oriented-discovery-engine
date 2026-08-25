import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/20260825_l4b_pair_comparability_semantics_v1_offline/artifacts"


def _json(name):
    return json.loads((ART / name).read_text(encoding="utf-8"))


def _rows(name):
    return [
        json.loads(line)
        for line in (ART / name).read_text(encoding="utf-8").splitlines()
        if line
    ]


def test_all_required_offline_artifacts_exist():
    required = {
        "baseline.json",
        "l4b_semantics_contract_snapshot.json",
        "context_dimension_registry_snapshot.json",
        "pair_context_requirement_profiles_v2.jsonl",
        "pair_context_requirement_activations_v2.jsonl",
        "pair_context_requirement_satisfaction_v2.jsonl",
        "l4a_l4b_separation_audit.json",
        "l4b_comparability_results_v1.jsonl",
        "l4b_divergence_handoff_candidates.jsonl",
        "pair_context_v1_v2_comparison.json",
        "candidate_pair_replay_v2.jsonl",
        "pi3k_pipeline_state_replay.json",
        "scientific_state_safety_audit.json",
        "reference_regression_recheck.json",
        "context_scope_safety_recheck.json",
        "entity_integrity_gate_recheck.json",
        "production_leakage_audit.json",
        "autonomous_iteration_ledger.jsonl",
        "final_validation.json",
        "manifest.json",
        "summary.json",
    }
    assert required == {path.name for path in ART.iterdir() if path.is_file()}


def test_contract_is_authoritative_and_implementation_references_it():
    snapshot = _json("l4b_semantics_contract_snapshot.json")
    contract = ROOT / snapshot["contract_path"]
    production = ROOT / "src/code_engine/extraction_assets/context/pair_requirements_v2.py"
    assert contract.is_file()
    assert hashlib.sha256(contract.read_bytes()).hexdigest() == snapshot["contract_sha256"]
    assert "required_to_be_resolved_not_required_to_match" == snapshot["required_semantics"]
    assert snapshot["resolved_states"] == ["matched", "different"]
    assert snapshot["contract_path"] in production.read_text(encoding="utf-8")


def test_existing_registry_is_reused_as_eight_dimensions_and_nineteen_fields():
    registry = _json("context_dimension_registry_snapshot.json")
    assert registry["registry_reused_without_competing_taxonomy"] is True
    assert registry["active_dimension_count"] == len(registry["dimensions"]) == 8
    assert registry["active_field_count"] == 19
    assert sum(len(row["satisfying_fields"]) for row in registry["dimensions"]) == 19
    assert registry["registry_membership_does_not_imply_requirement"] is True


def test_pair_consumer_profiles_and_dimension_evaluations_are_complete():
    profiles = _rows("pair_context_requirement_profiles_v2.jsonl")
    activations = _rows("pair_context_requirement_activations_v2.jsonl")
    satisfactions = _rows("pair_context_requirement_satisfaction_v2.jsonl")
    assert len(profiles) == 55
    assert len({(row["pair_id"], row["consumer"]) for row in profiles}) == 55
    assert len(activations) == len(satisfactions) == 440
    assert len({(row["pair_id"], row["consumer"], row["dimension"]) for row in activations}) == 440
    assert all(row["semantics_contract_id"] == "l4b_pair_comparability_semantics_v1" for row in profiles)


def test_actual_pairs_have_no_deterministic_trigger_and_missingness_does_not_activate():
    activations = _rows("pair_context_requirement_activations_v2.jsonl")
    assert Counter(row["primary_role"] for row in activations) == {
        "not_decision_relevant": 440
    }
    assert all(row["trigger_fact_ids"] == [] for row in activations)
    assert all(row["trigger_families"] == [] for row in activations)
    assert not any(row["missingness_created_relevance"] for row in activations)
    assert not any(row["llm_output_created_relevance"] for row in activations)


def test_satisfaction_does_not_treat_non_relevance_as_missing_requirement():
    satisfaction = _rows("pair_context_requirement_satisfaction_v2.jsonl")
    assert Counter(row["satisfaction_status"] for row in satisfaction) == {
        "not_applicable": 440
    }
    assert all(row["resolved_for_comparison"] is False for row in satisfaction)


def test_l4b_replay_enforces_upstream_gate_and_positive_no_requirement_state():
    results = _rows("l4b_comparability_results_v1.jsonl")
    assert len(results) == 11
    assert Counter(row["l4b_state"] for row in results) == {
        "blocked_upstream_alignment": 9,
        "comparable_no_context_sensitive_requirement": 2,
    }
    for row in results:
        if row["l4b_state"].startswith("blocked_upstream_"):
            assert row["comparable"] is None
            assert row["authoritative_l4b_result"] is False
        else:
            assert row["comparable"] is True
            assert row["authoritative_l4b_result"] is True
        assert row["formal_conflict_generated"] is False
        assert row["divergence_explanation_decided"] is False


def test_per_pair_replay_reports_all_required_audit_fields():
    rows = _rows("candidate_pair_replay_v2.jsonl")
    required = {
        "upstream_eligibility",
        "activated_comparison_required_dimensions",
        "activated_divergence_explanatory_dimensions",
        "requirement_unresolved_dimensions",
        "matched_required_dimensions",
        "different_required_dimensions",
        "unresolved_required_dimensions",
        "source_scope_blockers",
        "l4b_state",
        "divergence_handoff_candidates",
    }
    assert len(rows) == 11
    assert all(required <= row.keys() for row in rows)
    assert all(row["historical_state_preserved"] for row in rows)
    assert not any(row["candidate_modified"] for row in rows)
    assert not any(row["alignment_modified"] for row in rows)
    assert not any(row["formal_modified"] for row in rows)


def test_historical_critical_states_are_preserved_with_v2_sidecar_distinction():
    rows = _rows("candidate_pair_replay_v2.jsonl")
    by_candidate = {row["candidate_id"]: row for row in rows}
    weak_3ca = next(row for key, row in by_candidate.items() if key.startswith("weak-3ca"))
    weak_256 = next(row for key, row in by_candidate.items() if key.startswith("weak-256"))
    ebd5 = next(row for key, row in by_candidate.items() if key.startswith("weak-ebd5"))
    assert (weak_3ca["historical_context_entry_state"], weak_3ca["historical_difference_authority_state"]) == (
        "ready", "ready_not_materialized"
    )
    assert weak_3ca["l4b_state"] == "comparable_no_context_sensitive_requirement"
    assert (weak_256["historical_context_entry_state"], weak_256["historical_difference_authority_state"]) == (
        "blocked_context_b_unavailable", "blocked_entry"
    )
    assert weak_256["l4b_state"] == "comparable_no_context_sensitive_requirement"
    assert ebd5["l4b_state"] == "blocked_upstream_alignment"
    assert ebd5["historical_difference_authority_state"] == "diagnostic_only"
    critical = {row["identity"]: row for row in _json("summary.json")["critical_historical_states"]}
    assert critical["17b"]["state"] == critical["41f"]["state"] == "fail_closed_policy_coverage_failure"


def test_l4a_l4b_divergence_and_formal_layers_remain_separate():
    audit = _json("l4a_l4b_separation_audit.json")
    assert audit["l4a_is_descriptive"] is True
    assert audit["l4a_missing_dimension_blocks_pair"] is False
    assert audit["l4a_owns_comparability_authority"] is False
    assert audit["l4b_owns_comparability_requirements"] is True
    assert audit["l4b_generates_formal_conflict"] is False
    assert len(audit["rows"]) == 11
    assert all(row["l4a_absence_did_not_activate_requirement"] for row in audit["rows"])
    assert _rows("l4b_divergence_handoff_candidates.jsonl") == []


def test_metrics_close_exactly_without_optimizing_for_activation():
    metrics = _json("summary.json")["metrics"]
    assert (metrics["pair_count"], metrics["consumer_count"], metrics["pair_consumer_profile_count"]) == (11, 5, 55)
    assert metrics["dimension_evaluation_count"] == 440
    assert metrics["comparison_required_activation_count"] == 0
    assert metrics["divergence_explanatory_activation_count"] == 0
    assert metrics["not_decision_relevant_count"] == 440
    assert metrics["requirement_unresolved_count"] == 0
    assert all(metrics[key] == 0 for key in (
        "required_matched_count", "required_different_count", "required_unresolved_count",
        "required_ambiguous_count", "required_source_scope_insufficient_count",
    ))
    assert metrics["l4b_comparable_count"] == 2
    assert metrics["l4b_comparable_with_context_divergence_count"] == 0
    assert metrics["l4b_reviewable_count"] == metrics["l4b_blocked_count"] == 0
    assert metrics["l4b_upstream_blocked_count"] == 9
    assert metrics["pairs_with_comparison_requirements"] == 0
    assert metrics["pairs_with_divergence_explanatory_dimensions"] == 0
    assert metrics["pairs_with_no_context_sensitive_requirement"] == 11
    assert metrics["divergence_handoff_candidate_count"] == 0


def test_pi3k_remains_at_entity_and_manual_boundaries():
    replay = _json("pi3k_pipeline_state_replay.json")
    assert [row["final_state"] for row in replay["signals"]] == [
        "blocked_claim_entity_integrity",
        "manual_scientific_review_required",
    ]
    manual = replay["signals"][1]
    assert (
        manual["initial_experiment_candidate_count"],
        manual["deterministically_excluded_count"],
        manual["scientifically_plausible_candidate_count"],
        manual["insufficient_evidence_candidate_count"],
    ) == (18, 11, 5, 2)
    assert manual["human_response_exists"] is manual["experiment_auto_selected"] is False
    assert replay["valid_bridge_candidate_count"] == replay["scientific_bridges_created"] == 0
    assert replay["aligned_group_count_before"] == replay["aligned_group_count_after"] == 0
    assert replay["qualified_candidate_count_before"] == replay["qualified_candidate_count_after"] == 0
    assert replay["formal_conflict_count_before"] == replay["formal_conflict_count_after"] == 0


def test_entity_reference_context_and_historical_safety_close_exactly():
    entity = _json("entity_integrity_gate_recheck.json")
    reference = _json("reference_regression_recheck.json")
    scope = _json("context_scope_safety_recheck.json")
    safety = _json("scientific_state_safety_audit.json")
    assert entity["claims_blocked_before"] == entity["claims_blocked_after"] == 241
    assert entity["signals_blocked_before"] == entity["signals_blocked_after"] == 2
    assert entity["blocked_claims_protected_from_l4b"] is True
    assert (reference["core_reference_exact_match_count"], reference["core_reference_fail_closed_match_count"], reference["core_reference_mismatch_count"]) == (33, 6, 0)
    assert all(value == 0 for key, value in scope.items() if key.startswith("unsupported_cross_"))
    assert safety["protected_hashes_before"] == safety["protected_hashes_after"]
    assert safety["candidate_count_before"] == safety["candidate_count_after"] == 11
    assert safety["formal_conflict_count_before"] == safety["formal_conflict_count_after"] == 0
    assert safety["historical_assets_modified"] is False
    assert safety["candidate_pairs_modified"] is False
    assert safety["formal_v3_modified"] is False


def test_no_case_specific_production_rules_or_external_effects():
    leakage = _json("production_leakage_audit.json")
    safety = _json("scientific_state_safety_audit.json")
    assert leakage["case_specific_production_rule_count"] == 0
    assert leakage["hardcoded_pair_id_rule_count"] == 0
    assert leakage["hardcoded_pi3k_rule_count"] == 0
    assert leakage["hardcoded_entity_rule_count"] == 0
    assert leakage["prohibited_literal_hits"] == []
    assert all(safety[key] == 0 for key in ("provider_calls", "api_calls", "network_calls", "downloads"))
    assert safety["credential_values_read"] is safety["provider_client_created"] is False
    assert safety["atlas_activated"] is safety["active_pointer_changed"] is False
    assert safety["variational_em_called"] is False


def test_final_validation_has_no_new_failures():
    final = _json("final_validation.json")
    assert final["status"] == "completed"
    assert final["new_failure_ids"] == []
    assert final["compileall"] == final["git_diff_check"] == "passed"
    assert final["full_suite_failure_count"] == len(final["baseline_failure_ids"]) == 5
    assert final["final_failure_ids"] == final["baseline_failure_ids"]
    assert final["full_suite_deselected_count"] == 3


def test_manifest_hashes_all_generated_sidecars_except_itself():
    manifest = _json("manifest.json")
    assert manifest["file_count"] == len(manifest["files"]) == 20
    for item in manifest["files"]:
        path = ROOT / item["path"]
        assert path.stat().st_size == item["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
