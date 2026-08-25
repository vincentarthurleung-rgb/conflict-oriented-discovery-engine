import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/20260825_entity_integrity_consumer_gate_pair_context_requirements_v1_offline/artifacts"


def _json(name):
    return json.loads((ART / name).read_text(encoding="utf-8"))


def _rows(name):
    return [json.loads(line) for line in (ART / name).read_text(encoding="utf-8").splitlines() if line]


def test_all_required_offline_artifacts_exist():
    required = {
        "baseline.json", "entity_integrity_consumer_inventory.json",
        "entity_integrity_gate_results.jsonl", "entity_integrity_metric_reconciliation.json",
        "pair_context_consumer_contracts_v1.jsonl",
        "pair_context_requirement_profiles_v1.jsonl",
        "pair_context_requirement_activations_v1.jsonl",
        "pair_context_requirement_satisfaction_v1.jsonl", "pair_context_readiness_v1.jsonl",
        "pair_context_pair_consumer_matrix.json", "candidate_pipeline_eligibility_replay.jsonl",
        "pi3k_entity_gate_replay.json", "scientific_state_safety_audit.json",
        "reference_regression_recheck.json", "context_scope_safety_recheck.json",
        "production_leakage_audit.json", "autonomous_iteration_ledger.jsonl",
        "final_validation.json", "manifest.json", "summary.json",
    }
    assert required == {path.name for path in ART.iterdir() if path.is_file()}


def test_entity_gate_reconciles_claims_signals_and_noncritical_warnings():
    summary = _json("summary.json")["entity_integrity"]
    assert summary["consumer_count"] == 9
    assert (summary["claims_evaluated"], summary["claims_blocked"]) == (2291, 241)
    assert (summary["signals_evaluated"], summary["signals_blocked"]) == (2, 2)
    assert summary["noncritical_warnings_preserved"] == 15
    assert summary["historical_objects_modified"] is False


def test_blocked_rows_record_affected_field_role_and_reason():
    blocked = [
        row for row in _rows("entity_integrity_gate_results.jsonl")
        if not row["authoritative_for_scientific_promotion"]
    ]
    assert len(blocked) == 243
    assert all(row["affected_fields"] or row["upstream_claim_ids"] for row in blocked)
    assert all(row["blocking_reasons"] for row in blocked)
    assert all(row["historical_invalid_state_visible"] for row in blocked)


def test_both_metric_mismatches_have_exact_semantic_components():
    metrics = _json("entity_integrity_metric_reconciliation.json")
    assert metrics["claim_integrity_blocked_count"] == metrics["directly_affected_claim_count"] + 1
    assert metrics["extra_blocked_claim_count"] == 1
    assert sum(metrics["historical_canonical_identity_changed_components"].values()) == 327
    assert metrics["revision_candidate_count"] == 329
    assert metrics["revision_candidate_components"]["repaired_identity_unresolved"] == 2
    assert metrics["equality_forced"] is False


def test_pair_context_replay_is_complete_without_manufactured_requirements():
    pair = _json("summary.json")["pair_context"]
    assert (pair["pair_count"], pair["consumer_count"]) == (11, 5)
    assert (pair["pair_consumer_profile_count"], pair["dimension_evaluation_count"]) == (55, 440)
    assert pair["active_required_count"] == pair["active_conditional_count"] == 0
    assert pair["no_requirement_declared_count"] == 440
    assert (pair["ready_count"], pair["reviewable_count"], pair["blocked_count"]) == (0, 55, 0)
    assert (pair["pairs_with_active_requirements"], pair["pairs_without_active_requirements"]) == (0, 11)


def test_every_activation_has_auditable_authority_fields():
    activations = _rows("pair_context_requirement_activations_v1.jsonl")
    assert len(activations) == 440
    assert all(row["pair_id"] and row["consumer"] and row["dimension"] for row in activations)
    assert all(row["activation_class"] == row["activation_status"] for row in activations)
    assert all(row["trigger_type"] and row["trigger_evidence"] for row in activations)
    assert all(row["source_contract_ref"] and row["source_code_ref"] for row in activations)
    assert all(row["blocking_semantics"] for row in activations)


def test_no_requirement_is_reviewable_not_ready_or_blocked():
    states = Counter(row["status"] for row in _rows("pair_context_readiness_v1.jsonl"))
    assert states == {"reviewable_no_requirement_contract": 55}


def test_candidate_replay_keeps_11_and_existing_gate_states():
    replay = _rows("candidate_pipeline_eligibility_replay.jsonl")
    summary = _json("summary.json")["candidate_replay"]
    assert len(replay) == 11
    assert sum(row["claim_alignment_gate"] == "blocked_alignment" for row in replay) == 9
    assert sum(row["candidate_qualification_gate"] == "qualified" for row in replay) == 2
    assert Counter(row["l4_entry_state"] for row in replay) == {
        "blocked_candidate_unqualified": 9,
        "blocked_context_b_unavailable": 1,
        "ready": 1,
    }
    assert not any(row["historical_candidate_modified"] for row in replay)
    assert not any(row["formal_adjudication_performed"] for row in replay)
    assert [item["identity"] for item in summary["critical_weak_states"]] == [
        "weak-3ca", "weak-256", "ebd5", "17b", "41f",
    ]
    assert summary["critical_state_ids_used_in_production_rules"] is False


def test_pi3k_replay_preserves_fail_closed_and_manual_boundaries():
    replay = _json("pi3k_entity_gate_replay.json")
    assert [row["final_state"] for row in replay["signals"]] == [
        "blocked_claim_entity_integrity", "manual_scientific_review_required",
    ]
    assert replay["valid_bridge_candidate_count"] == replay["scientific_bridges_created"] == 0
    assert replay["aligned_group_count_before"] == replay["aligned_group_count_after"] == 0
    assert replay["qualified_candidate_count_before"] == replay["qualified_candidate_count_after"] == 0
    assert replay["formal_conflict_count_before"] == replay["formal_conflict_count_after"] == 0


def test_scientific_and_context_scope_safety_close_exactly():
    safety = _json("scientific_state_safety_audit.json")
    scope = _json("context_scope_safety_recheck.json")
    assert (safety["core_reference_exact_match_count"], safety["core_reference_fail_closed_match_count"], safety["core_reference_mismatch_count"]) == (33, 6, 0)
    assert safety["historical_assets_modified"] is False
    assert safety["candidate_count_before"] == safety["candidate_count_after"] == 11
    assert safety["formal_conflict_count_before"] == safety["formal_conflict_count_after"] == 0
    assert all(value == 0 for key, value in scope.items() if key.startswith("unsupported_cross_"))


def test_no_case_specific_production_leakage_or_external_effects():
    leakage = _json("production_leakage_audit.json")
    safety = _json("scientific_state_safety_audit.json")
    assert leakage["case_specific_production_rule_count"] == 0
    assert leakage["prohibited_literal_hits"] == []
    assert all(safety[key] == 0 for key in ("provider_calls", "api_calls", "network_calls", "downloads"))
    assert safety["credential_values_read"] is safety["provider_client_created"] is False
    assert safety["atlas_activated"] is safety["active_pointer_changed"] is False
    assert safety["variational_em_called"] is False


def test_manifest_hashes_all_generated_sidecars():
    manifest = _json("manifest.json")
    assert manifest["file_count"] == len(manifest["files"]) == 19
    for item in manifest["files"]:
        path = ROOT / item["path"]
        assert path.stat().st_size == item["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
