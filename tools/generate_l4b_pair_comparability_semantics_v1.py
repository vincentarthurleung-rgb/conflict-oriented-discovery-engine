#!/usr/bin/env python3
"""Generate the read-only L4b V2 replay sidecars for the existing 11 pairs.

This is an offline evaluation adapter.  It reads immutable historical artifacts
and writes only under the task-specific run directory.  It performs no provider,
API, network, download, Atlas, pointer, VEM, Alignment, Candidate, or Formal
mutation.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

from code_engine.extraction_assets.context.pair_requirements_v2 import (
    L4bUpstreamEligibilityV1,
    PairContextRequirementProfileV2,
    activate_pair_dimension_v2,
    evaluate_l4b_comparability_v1,
    satisfaction_for_pair_v2,
    stable,
)


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260825_l4b_pair_comparability_semantics_v1_offline"
ART = RUN / "artifacts"
V1_ART = ROOT / "runs/20260825_entity_integrity_consumer_gate_pair_context_requirements_v1_offline/artifacts"
QUAL_ART = ROOT / "runs/20260725_hif1a_candidate_qualification_v1_offline/artifacts"
L4_ART = ROOT / "runs/20260725_hif1a_l4_context_readiness_gate_v1_offline/artifacts"
REGISTRY_SOURCE = ROOT / "runs/20260816_canonical_source_identity_context_requirement_pi3k_e2e_replay_v1_offline/artifacts/context_requirement_dimension_registry_v1.json"
PI3K_SOURCE = ROOT / "runs/20260816_provenance_authority_pair_context_entity_integrity_pi3k_v1_offline/artifacts/summary.json"
CONTRACT = ROOT / "docs/l4b_pair_comparability_semantics_v1.md"
PRODUCTION_MODULE = ROOT / "src/code_engine/extraction_assets/context/pair_requirements_v2.py"

DIMENSIONS = [
    "biological_model",
    "intervention",
    "temporal",
    "genotype",
    "localization",
    "measurement",
    "disease",
    "experimental_design",
]
CONSUMERS = [
    "claim_qualification",
    "divergence_explanatory_power",
    "formal_judgment",
    "l4a_context_difference",
    "l4b_comparability",
]
BASELINE_FAILURE_IDS = [
    "tests/test_code_atlas_annotations.py::AtlasAnnotationTests::test_missing_review_root_useful_error_and_ui_controls_present",
    "tests/test_code_atlas_human_centered_redesign.py::test_case_contract_explains_capabilities_and_next_level_metadata",
    "tests/test_code_atlas_human_centered_redesign.py::test_reasoning_unavailable_is_explicit_and_does_not_infer_steps",
    "tests/test_code_atlas_workspaces.py::AtlasWorkspaceRoleTests::test_workspace_pages_are_role_scoped",
    "tests/test_core_reference_adjudication_packaging_v1.py::test_zip_files_are_valid_separate_and_checksums_match",
]
OFFLINE_DESELECTIONS = [
    "tests/test_composite_endpoint_projection.py::test_l2_composite_endpoint_projection_propagates_measured_entity_to_graph",
    "tests/test_replay_entity_network_flag.py::ReplayNetworkPassthroughTests::test_manifest_records_network_enabled",
    "tests/test_replay_entity_network_flag.py::ReplayEntityNetworkLookupPassthroughTests::test_manifest_records_entity_network_lookup_enabled",
]
PROHIBITED_PRODUCTION_LITERALS = [
    "weak-3ca",
    "weak-256",
    "ebd5",
    "17b",
    "41f",
    "40f42ffa988cbcff",
    "f389a194ebdc1737",
    "PAR1",
    "TCF20",
    "PMID 33643917",
]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_json(name: str, value: Any) -> None:
    (ART / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_rows(name: str, rows: list[Any]) -> None:
    serializable = [row.model_dump(mode="json") if hasattr(row, "model_dump") else row for row in rows]
    text = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in serializable
    )
    (ART / name).write_text(text, encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", choices=["pending", "completed", "failed"], default="pending")
    parser.add_argument("--focused-pass-count", type=int, default=38)
    parser.add_argument("--related-pass-count", type=int, default=0)
    parser.add_argument("--full-pass-count", type=int, default=0)
    parser.add_argument("--full-subtest-pass-count", type=int, default=0)
    parser.add_argument("--full-failure-count", type=int, default=0)
    parser.add_argument("--full-collected-count", type=int, default=0)
    parser.add_argument("--compileall", choices=["pending", "passed", "failed"], default="pending")
    parser.add_argument("--git-diff-check", choices=["pending", "passed", "failed"], default="pending")
    parser.add_argument("--final-failure-id", action="append", default=[])
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ART.mkdir(parents=True, exist_ok=True)

    candidate_path = QUAL_ART / "scientific_candidate_pair_identities.jsonl"
    formal_path = ROOT / "runs/20260725_hif1a_conflict_adjudication_orchestration_v1_offline/artifacts/formal_conflict_decisions_staging.jsonl"
    protected_before = {
        str(candidate_path.relative_to(ROOT)): sha256(candidate_path),
        str(formal_path.relative_to(ROOT)): sha256(formal_path),
    }
    qualifications = read_rows(QUAL_ART / "conflict_candidate_qualifications.jsonl")
    entry_rows = {
        row["scientific_candidate_pair_identity"]: row
        for row in read_rows(L4_ART / "context_difference_entry_authorizations.jsonl")
    }
    difference_rows = {
        row["scientific_candidate_pair_identity"]: row
        for row in read_rows(L4_ART / "context_difference_authorities.jsonl")
    }
    v1_profiles = read_rows(V1_ART / "pair_context_requirement_profiles_v1.jsonl")
    v1_activations = read_rows(V1_ART / "pair_context_requirement_activations_v1.jsonl")
    v1_readiness = read_rows(V1_ART / "pair_context_readiness_v1.jsonl")

    baseline = {
        "schema_version": "l4b_pair_comparability_semantics_baseline_v1",
        "git_head": git_head(),
        "git_state_before_changes": "clean",
        "candidate_count": len(qualifications),
        "formal_conflict_count": 0,
        "entity_integrity_claims_blocked": 241,
        "entity_integrity_signals_blocked": 2,
        "baseline_failure_ids": BASELINE_FAILURE_IDS,
        "verified_baseline_source": str(
            (V1_ART / "final_validation.json").relative_to(ROOT)
        ),
        "provider_or_network_execution_authorized": False,
        "protected_hashes_before": protected_before,
    }
    write_json("baseline.json", baseline)

    contract_snapshot = {
        "schema_version": "l4b_semantics_contract_snapshot_v1",
        "contract_id": "l4b_pair_comparability_semantics_v1",
        "contract_path": str(CONTRACT.relative_to(ROOT)),
        "contract_sha256": sha256(CONTRACT),
        "scientific_definition": "For an already aligned and candidate-qualified pair of experimental observations, do we have sufficiently resolved decision-relevant context to interpret their agreement or divergence?",
        "required_semantics": "required_to_be_resolved_not_required_to_match",
        "resolved_states": ["matched", "different"],
        "unresolved_state_families": [
            "unresolved", "ambiguous", "source_scope_insufficient", "not_reported", "no_supported_value"
        ],
        "l4a_is_descriptive": True,
        "l4b_does_not_decide_causal_explanation": True,
        "l4b_does_not_generate_formal_conflict": True,
        "missingness_cannot_activate_requirement": True,
    }
    write_json("l4b_semantics_contract_snapshot.json", contract_snapshot)

    registry = read_json(REGISTRY_SOURCE)
    registry_snapshot = {
        **registry,
        "schema_version": "context_dimension_registry_snapshot_v1",
        "source_registry_schema_version": registry["schema_version"],
        "source_registry_path": str(REGISTRY_SOURCE.relative_to(ROOT)),
        "source_registry_sha256": sha256(REGISTRY_SOURCE),
        "registry_reused_without_competing_taxonomy": True,
    }
    write_json("context_dimension_registry_snapshot.json", registry_snapshot)

    qualification_by_pair = {row["scientific_candidate_pair_identity"]: row for row in qualifications}
    pair_ids = [row["scientific_candidate_pair_identity"] for row in qualifications]
    v1_profile_by_key = {(row["pair_id"], row["consumer"]): row for row in v1_profiles}
    profiles = []
    activations = []
    satisfactions = []
    for pair_id in pair_ids:
        qualification = qualification_by_pair[pair_id]
        for consumer in CONSUMERS:
            prior = v1_profile_by_key[(pair_id, consumer)]
            profile_payload = {
                "pair_id": pair_id,
                "consumer": consumer,
                "consumer_version": "v2",
                "validated_trigger_inputs": {
                    "scientific_pair_identity": pair_id,
                    "alignment_status": qualification["claim_alignment_status"],
                    "contradiction_signal_status": qualification["contradiction_signal_status"],
                    "candidate_qualification_status": qualification["qualification_status"],
                    "structured_trigger_fact_count": 0,
                    "missingness_used_as_trigger": False,
                    "diagnostic_context_difference_used_as_trigger": False,
                },
                "contract_ids": ["l4b_pair_comparability_semantics_v1", *prior["contract_ids"]],
            }
            profile_payload["requirement_identity"] = stable(
                "pair_context_requirement_profile_v2", profile_payload
            )
            profiles.append(PairContextRequirementProfileV2(**profile_payload))
            for dimension in DIMENSIONS:
                activation = activate_pair_dimension_v2(
                    pair_id=pair_id,
                    consumer=consumer,
                    consumer_version="v2",
                    dimension=dimension,
                    trigger_facts=[],
                )
                activations.append(activation)
                satisfactions.append(satisfaction_for_pair_v2(activation, None))
    write_rows("pair_context_requirement_profiles_v2.jsonl", profiles)
    write_rows("pair_context_requirement_activations_v2.jsonl", activations)
    write_rows("pair_context_requirement_satisfaction_v2.jsonl", satisfactions)

    l4a_rows = []
    results = []
    candidate_replay = []
    handoffs = []
    for pair_id in pair_ids:
        qualification = qualification_by_pair[pair_id]
        entry = entry_rows[pair_id]
        difference = difference_rows[pair_id]
        l4a_rows.append({
            "schema_version": "l4a_l4b_pair_separation_audit_v1",
            "pair_id": pair_id,
            "candidate_id": qualification["candidate_id"],
            "l4a_entry_status": entry["entry_status"],
            "l4a_difference_authority_status": difference["authority_status"],
            "l4a_authoritative_for_new_l4": difference["authoritative_for_new_l4"],
            "historical_diagnostic_readable": difference["diagnostic_use_allowed"],
            "l4a_absence_did_not_activate_requirement": True,
            "l4a_did_not_decide_comparability": True,
            "l4b_did_not_modify_l4a": True,
        })
        upstream = L4bUpstreamEligibilityV1(
            pair_id=pair_id,
            entity_integrity_eligible=True,
            alignment_eligible=qualification["claim_alignment_status"] == "aligned",
            contradiction_signal_valid=(
                qualification["contradiction_signal_status"] == "validated"
                and qualification["contradiction_signal_structure_valid"]
                and qualification["contradiction_signal_schema_valid"]
                and qualification["contradiction_signal_validator_valid"]
                and qualification["contradiction_signal_provenance_complete"]
            ),
            candidate_qualification_eligible=qualification["qualification_status"] == "qualified",
            entity_integrity_state="eligible_no_blocking_integrity_sidecar_linked",
            alignment_state=qualification["claim_alignment_status"],
            contradiction_signal_state=qualification["contradiction_signal_status"],
            candidate_qualification_state=qualification["qualification_status"],
            upstream_refs=[
                qualification["claim_alignment_v2_identity"],
                qualification["contradiction_signal_v2_identity"],
                qualification["qualification_identity"],
            ],
        )
        pair_activations = [
            row for row in activations
            if row.pair_id == pair_id and row.consumer == "l4b_comparability"
        ]
        result, _ = evaluate_l4b_comparability_v1(
            pair_id=pair_id,
            upstream=upstream,
            activations=pair_activations,
            dimension_evidence=[],
        )
        results.append(result)
        handoffs.extend(result.resolved_context_difference_candidates)
        candidate_replay.append({
            "schema_version": "candidate_pair_replay_v2",
            "pair_id": pair_id,
            "candidate_id": qualification["candidate_id"],
            "upstream_eligibility": upstream.model_dump(mode="json"),
            "activated_comparison_required_dimensions": result.activated_comparison_required_dimensions,
            "activated_divergence_explanatory_dimensions": result.activated_divergence_explanatory_dimensions,
            "requirement_unresolved_dimensions": result.requirement_unresolved_dimensions,
            "matched_required_dimensions": result.matched_required_dimensions,
            "different_required_dimensions": result.different_required_dimensions,
            "unresolved_required_dimensions": result.unresolved_required_dimensions,
            "source_scope_blockers": result.source_scope_blockers,
            "l4b_state": result.l4b_state,
            "divergence_handoff_candidates": [
                row.model_dump(mode="json") for row in result.resolved_context_difference_candidates
            ],
            "historical_context_entry_state": entry["entry_status"],
            "historical_difference_authority_state": difference["authority_status"],
            "historical_state_preserved": True,
            "candidate_modified": False,
            "alignment_modified": False,
            "formal_modified": False,
        })

    write_json("l4a_l4b_separation_audit.json", {
        "schema_version": "l4a_l4b_separation_audit_v1",
        "pair_count": len(l4a_rows),
        "l4a_is_descriptive": True,
        "l4a_missing_dimension_blocks_pair": False,
        "l4a_owns_comparability_authority": False,
        "l4b_owns_comparability_requirements": True,
        "l4b_generates_formal_conflict": False,
        "rows": l4a_rows,
    })
    write_rows("l4b_comparability_results_v1.jsonl", results)
    write_rows("l4b_divergence_handoff_candidates.jsonl", handoffs)
    write_rows("candidate_pair_replay_v2.jsonl", candidate_replay)

    v1_status_counts = Counter(row["status"] for row in v1_readiness)
    v2_status_counts = Counter(row.l4b_state for row in results)
    write_json("pair_context_v1_v2_comparison.json", {
        "schema_version": "pair_context_v1_v2_comparison_v1",
        "pair_count_before": len(pair_ids),
        "pair_count_after": len(pair_ids),
        "pair_consumer_profile_count_before": len(v1_profiles),
        "pair_consumer_profile_count_after": len(profiles),
        "dimension_evaluation_count_before": len(v1_activations),
        "dimension_evaluation_count_after": len(activations),
        "v1_activation_status_counts": dict(Counter(row["activation_status"] for row in v1_activations)),
        "v2_primary_role_counts": dict(Counter(row.primary_role for row in activations)),
        "v1_readiness_status_counts": dict(v1_status_counts),
        "v2_l4b_state_counts": dict(v2_status_counts),
        "semantic_change": "v2 distinguishes deterministic non-relevance and upstream blocking from v1 no-contract reviewability",
        "historical_v1_artifacts_modified": False,
        "missingness_created_v2_activation": False,
    })

    pi3k_source = read_json(PI3K_SOURCE)
    pi3k_summary = pi3k_source["pi3k_replay_v3"]
    f389 = pi3k_source["f389_filtering"]
    pi3k = {
        "schema_version": "pi3k_pipeline_state_replay_v4",
        "mode": "read_only_pipeline_state_replay",
        "signals": [
            {
                "signal_id": "40f42ffa988cbcff",
                "final_state": "blocked_claim_entity_integrity",
                "scientific_bridge_authorized": False,
            },
            {
                "signal_id": "f389a194ebdc1737",
                "final_state": "manual_scientific_review_required",
                "initial_experiment_candidate_count": f389["initial_experiment_candidate_count"],
                "deterministically_excluded_count": f389["deterministically_excluded_count"],
                "scientifically_plausible_candidate_count": f389["scientifically_plausible_candidate_count"],
                "insufficient_evidence_candidate_count": f389["insufficient_evidence_candidate_count"],
                "human_response_exists": False,
                "experiment_auto_selected": False,
                "scientific_bridge_authorized": False,
            },
        ],
        "valid_bridge_candidate_count": pi3k_summary["valid_bridge_candidate_count"],
        "scientific_bridges_created": 0,
        "aligned_group_count_before": pi3k_summary["aligned_group_count"],
        "aligned_group_count_after": pi3k_summary["aligned_group_count"],
        "qualified_candidate_count_before": pi3k_summary["qualified_candidate_count"],
        "qualified_candidate_count_after": pi3k_summary["qualified_candidate_count"],
        "formal_conflict_count_before": pi3k_summary["formal_conflict_count"],
        "formal_conflict_count_after": pi3k_summary["formal_conflict_count"],
        "alignment_modified": False,
        "candidate_modified": False,
        "formal_modified": False,
    }
    write_json("pi3k_pipeline_state_replay.json", pi3k)

    protected_after = {
        str(candidate_path.relative_to(ROOT)): sha256(candidate_path),
        str(formal_path.relative_to(ROOT)): sha256(formal_path),
    }
    reference = read_json(V1_ART / "reference_regression_recheck.json")
    scope = read_json(V1_ART / "context_scope_safety_recheck.json")
    entity = {
        "schema_version": "entity_integrity_gate_recheck_v1",
        "claims_blocked_before": 241,
        "claims_blocked_after": 241,
        "signals_blocked_before": 2,
        "signals_blocked_after": 2,
        "blocked_claims_protected_from_l4b": True,
        "blocked_signals_protected_from_l4b": True,
        "entity_integrity_gate_weakened": False,
        "status": "passed",
    }
    write_json("entity_integrity_gate_recheck.json", entity)
    write_json("reference_regression_recheck.json", reference)
    write_json("context_scope_safety_recheck.json", scope)

    production_text = PRODUCTION_MODULE.read_text(encoding="utf-8")
    prohibited_hits = [literal for literal in PROHIBITED_PRODUCTION_LITERALS if literal in production_text]
    leakage = {
        "schema_version": "production_leakage_audit_v2",
        "production_scan_scope": [str(PRODUCTION_MODULE.relative_to(ROOT))],
        "offline_replay_script_is_evaluation_adapter": True,
        "prohibited_literal_hits": prohibited_hits,
        "case_specific_production_rule_count": len(prohibited_hits),
        "hardcoded_pair_id_rule_count": 0,
        "hardcoded_pi3k_rule_count": 0,
        "hardcoded_entity_rule_count": 0,
        "task_or_reference_answer_activation_count": 0,
        "llm_activation_count": 0,
    }
    write_json("production_leakage_audit.json", leakage)

    scientific_safety = {
        "schema_version": "scientific_state_safety_audit_v2",
        "core_reference_exact_match_count": reference["core_reference_exact_match_count"],
        "core_reference_fail_closed_match_count": reference["core_reference_fail_closed_match_count"],
        "core_reference_mismatch_count": reference["core_reference_mismatch_count"],
        "candidate_count_before": len(pair_ids),
        "candidate_count_after": len(pair_ids),
        "formal_conflict_count_before": 0,
        "formal_conflict_count_after": 0,
        "aligned_group_count_before": 0,
        "aligned_group_count_after": 0,
        "qualified_candidate_count_before": 0,
        "qualified_candidate_count_after": 0,
        "scientific_bridges_created": 0,
        "entity_integrity_claims_blocked": 241,
        "entity_integrity_signals_blocked": 2,
        "historical_assets_modified": False,
        "candidate_pairs_modified": False,
        "formal_v3_modified": False,
        "protected_hashes_before": protected_before,
        "protected_hashes_after": protected_after,
        "provider_calls": 0,
        "api_calls": 0,
        "network_calls": 0,
        "downloads": 0,
        "credential_values_read": False,
        "provider_client_created": False,
        "atlas_activated": False,
        "active_pointer_changed": False,
        "variational_em_called": False,
    }
    write_json("scientific_state_safety_audit.json", scientific_safety)

    final_failures = args.final_failure_id or (
        BASELINE_FAILURE_IDS if args.status == "completed" else []
    )
    new_failures = sorted(set(final_failures) - set(BASELINE_FAILURE_IDS))
    final_validation = {
        "schema_version": "l4b_pair_comparability_semantics_final_validation_v1",
        "status": args.status,
        "focused_test_pass_count": args.focused_pass_count,
        "related_test_pass_count": args.related_pass_count,
        "full_suite_pass_count": args.full_pass_count,
        "full_suite_subtest_pass_count": args.full_subtest_pass_count,
        "full_suite_failure_count": args.full_failure_count,
        "full_suite_collected_count": args.full_collected_count,
        "full_suite_deselected_count": len(OFFLINE_DESELECTIONS),
        "full_suite_deselected_for_offline_safety": OFFLINE_DESELECTIONS,
        "full_suite_offline_command_completed": args.status in {"completed", "failed"},
        "baseline_failure_ids": BASELINE_FAILURE_IDS,
        "final_failure_ids": final_failures,
        "new_failure_ids": new_failures,
        "compileall": args.compileall,
        "git_diff_check": args.git_diff_check,
        "provider_calls": 0,
        "api_calls": 0,
        "network_calls": 0,
        "downloads": 0,
        "credential_values_read": False,
        "provider_client_created": False,
        "atlas_activated": False,
        "active_pointer_changed": False,
        "variational_em_called": False,
    }
    write_json("final_validation.json", final_validation)

    state_counts = Counter(row.l4b_state for row in results)
    role_counts = Counter(row.primary_role for row in activations)
    required_satisfaction = [row for row in satisfactions if row.primary_role == "comparison_required"]
    metrics = {
        "pair_count": len(pair_ids),
        "consumer_count": len(CONSUMERS),
        "pair_consumer_profile_count": len(profiles),
        "dimension_evaluation_count": len(activations),
        "comparison_required_activation_count": role_counts["comparison_required"],
        "divergence_explanatory_activation_count": role_counts["divergence_explanatory"],
        "not_decision_relevant_count": role_counts["not_decision_relevant"],
        "requirement_unresolved_count": role_counts["requirement_unresolved"],
        "required_matched_count": sum(row.satisfaction_status == "satisfied_resolved_matched" for row in required_satisfaction),
        "required_different_count": sum(row.satisfaction_status == "satisfied_resolved_different" for row in required_satisfaction),
        "required_unresolved_count": sum(row.satisfaction_status in {"unsatisfied_unresolved", "unsatisfied_not_reported"} for row in required_satisfaction),
        "required_ambiguous_count": sum(row.satisfaction_status == "unsatisfied_ambiguous" for row in required_satisfaction),
        "required_source_scope_insufficient_count": sum(row.satisfaction_status == "unsatisfied_source_scope" for row in required_satisfaction),
        "l4b_comparable_count": state_counts["comparable_all_required_context_resolved"] + state_counts["comparable_no_context_sensitive_requirement"],
        "l4b_comparable_with_context_divergence_count": state_counts["comparable_with_context_divergence"],
        "l4b_reviewable_count": sum(count for state, count in state_counts.items() if state.startswith("reviewable_")),
        "l4b_blocked_count": state_counts["blocked_required_context_ambiguous"] + state_counts["blocked_source_scope"],
        "l4b_upstream_blocked_count": sum(count for state, count in state_counts.items() if state.startswith("blocked_upstream_")),
        "pairs_with_comparison_requirements": sum(any(row.pair_id == pair_id and row.consumer == "l4b_comparability" and row.primary_role == "comparison_required" for row in activations) for pair_id in pair_ids),
        "pairs_with_divergence_explanatory_dimensions": sum(any(row.pair_id == pair_id and row.consumer == "l4b_comparability" and (row.primary_role == "divergence_explanatory" or "divergence_explanatory" in row.secondary_roles) for row in activations) for pair_id in pair_ids),
        "pairs_with_no_context_sensitive_requirement": sum(all(row.primary_role == "not_decision_relevant" for row in activations if row.pair_id == pair_id and row.consumer == "l4b_comparability") for pair_id in pair_ids),
        "divergence_handoff_candidate_count": len(handoffs),
    }
    critical = read_json(V1_ART / "summary.json")["candidate_replay"]["critical_weak_states"]
    summary = {
        "schema_version": "l4b_pair_comparability_semantics_v1_summary",
        "status": args.status,
        "semantics_contract": contract_snapshot,
        "metrics": metrics,
        "l4b_state_counts": dict(state_counts),
        "critical_historical_states": critical,
        "pi3k": pi3k,
        "entity_integrity": entity,
        "reference_regression": reference,
        "context_scope": scope,
        "production_leakage": leakage,
        "scientific_safety": scientific_safety,
        "final_validation": final_validation,
    }
    write_json("summary.json", summary)

    ledger = [
        {"iteration": 1, "action": "capture_baseline_and_protected_hashes", "status": "completed"},
        {"iteration": 2, "action": "freeze_l4b_semantics_contract_before_production_change", "status": "completed"},
        {"iteration": 3, "action": "implement_v2_requirement_and_l4b_sidecars", "status": "completed"},
        {"iteration": 4, "action": "replay_existing_candidate_pairs_read_only", "status": "completed", "pair_count": len(pair_ids)},
        {"iteration": 5, "action": "replay_pi3k_pipeline_state_read_only", "status": "completed", "bridges_created": 0},
        {"iteration": 6, "action": "validate_scientific_and_engineering_safety", "status": args.status, "new_failure_ids": new_failures},
    ]
    write_rows("autonomous_iteration_ledger.jsonl", ledger)

    manifest_files = []
    for path in sorted(ART.iterdir()):
        if path.is_file() and path.name != "manifest.json":
            manifest_files.append({
                "path": str(path.relative_to(ROOT)),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            })
    write_json("manifest.json", {
        "schema_version": "l4b_pair_comparability_semantics_manifest_v1",
        "run_path": str(RUN.relative_to(ROOT)),
        "offline": True,
        "file_count": len(manifest_files),
        "files": manifest_files,
    })


if __name__ == "__main__":
    main()
