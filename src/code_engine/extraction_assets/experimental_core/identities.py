"""Stable identities for experimental-core records and contracts."""
from __future__ import annotations

from typing import Any

from ..identities import sha256_json, stable_identity

CONTRACT_NAMES = (
    "observation_type_cardinality_policy",
    "structured_experimental_observation",
    "experimental_factor_record",
    "measurement_record",
    "observed_result_record",
    "experimental_observation_linkage",
    "experimental_core_stage_trace",
    "experimental_core_first_loss_diagnosis",
    "experimental_observation_atomicity",
    "experimental_core_recovery",
    "experimental_observation_structural_integrity",
    "experimental_observation_machine_reuse",
    "experimental_core_remediation",
    "experimental_core_orchestration",
    "research_grade_observation_context_extraction_v2",
    "experimental_core_projection_v2",
    "experimental_core_projection_compatibility",
    "observed_result_comparison_semantics",
    "comparative_result_link_recovery",
    "comparative_link_candidate_edge",
    "measurement_method_recovery",
    "measurement_method_context_link",
    "measurement_method_missing_reason",
    "experimental_linkage_completeness_v2",
    "experimental_linkage_metric_reconciliation",
    "experimental_observation_machine_reuse_v2",
    "experimental_core_projection_readiness",
    "experimental_core_remediation_v2",
    "projection_v2_downstream_compatibility",
    "experimental_core_projection_repair_orchestration",
    "source_grounded_resolution_envelope",
    "source_resolution_scope_completeness",
    "comparator_unresolved_set_reconciliation",
    "source_grounded_comparator_resolution",
    "source_grounded_factor_measurement_resolution",
    "source_grounded_measurement_method_resolution",
    "source_resolution_provider_candidate_policy",
    "experimental_linkage_annotation_target",
    "measurement_method_annotation_target",
    "experimental_annotation_pilot_selection",
    "experimental_annotation_gold_candidate_policy",
    "source_reingestion_requirement",
    "experimental_core_remediation_v3",
    "experimental_observation_machine_reuse_v3_candidate",
    "source_grounded_resolution_orchestration",
)

CONTRACT_IDENTITY_NAMES = {
    "experimental_core_projection_v2": "experimental_core_projection_contract_identity_v2",
    "experimental_core_projection_compatibility": "experimental_core_projection_compatibility_contract_identity_v1",
    "observed_result_comparison_semantics": "observed_result_comparison_semantics_contract_identity_v1",
    "comparative_result_link_recovery": "comparative_result_link_recovery_contract_identity_v1",
    "comparative_link_candidate_edge": "comparative_link_candidate_edge_contract_identity_v1",
    "measurement_method_recovery": "measurement_method_recovery_contract_identity_v1",
    "measurement_method_context_link": "measurement_method_context_link_contract_identity_v1",
    "measurement_method_missing_reason": "measurement_method_missing_reason_contract_identity_v1",
    "experimental_linkage_completeness_v2": "experimental_linkage_completeness_contract_identity_v2",
    "experimental_linkage_metric_reconciliation": "experimental_linkage_metric_reconciliation_contract_identity_v1",
    "experimental_observation_machine_reuse_v2": "experimental_observation_machine_reuse_contract_identity_v2",
    "experimental_core_projection_readiness": "experimental_core_projection_readiness_contract_identity_v1",
    "experimental_core_remediation_v2": "experimental_core_remediation_contract_identity_v2",
    "projection_v2_downstream_compatibility": "projection_v2_downstream_compatibility_contract_identity_v1",
    "experimental_core_projection_repair_orchestration": "experimental_core_projection_repair_orchestration_contract_identity_v1",
    "source_grounded_resolution_envelope": "source_grounded_resolution_envelope_contract_identity_v1",
    "source_resolution_scope_completeness": "source_resolution_scope_completeness_contract_identity_v1",
    "comparator_unresolved_set_reconciliation": "comparator_unresolved_set_reconciliation_contract_identity_v2",
    "source_grounded_comparator_resolution": "source_grounded_comparator_resolution_contract_identity_v2",
    "source_grounded_factor_measurement_resolution": "source_grounded_factor_measurement_resolution_contract_identity_v1",
    "source_grounded_measurement_method_resolution": "source_grounded_measurement_method_resolution_contract_identity_v2",
    "source_resolution_provider_candidate_policy": "source_resolution_provider_candidate_policy_contract_identity_v1",
    "experimental_linkage_annotation_target": "experimental_linkage_annotation_target_contract_identity_v1",
    "measurement_method_annotation_target": "measurement_method_annotation_target_contract_identity_v1",
    "experimental_annotation_pilot_selection": "experimental_annotation_pilot_selection_contract_identity_v1",
    "experimental_annotation_gold_candidate_policy": "experimental_annotation_gold_candidate_policy_contract_identity_v1",
    "source_reingestion_requirement": "source_reingestion_requirement_contract_identity_v1",
    "experimental_core_remediation_v3": "experimental_core_remediation_contract_identity_v3",
    "experimental_observation_machine_reuse_v3_candidate": "experimental_observation_machine_reuse_contract_identity_v3_candidate",
    "source_grounded_resolution_orchestration": "source_grounded_resolution_orchestration_contract_identity_v1",
}


def core_identity(kind: str, payload: dict[str, Any]) -> str:
    return stable_identity(
        kind, payload,
        exclude={"absolute_path", "run_path", "timestamp", "git_status"},
    )


def contract_identity(name: str) -> dict[str, Any]:
    if name not in CONTRACT_NAMES:
        raise ValueError(f"unknown experimental-core contract: {name}")
    contract_name = CONTRACT_IDENTITY_NAMES.get(
        name, f"{name}_contract_identity{'' if name.endswith('_v2') else '_v1'}"
    )
    canonical = {
        "contract_name": contract_name,
        "identity_algorithm": "sha256_canonical_json_v1",
        "immutable_revision_policy": True,
        "historical_mutation_allowed": False,
        "derived_conflict_reasoning_allowed": False,
        "provider_call_authorized": False,
        "network_call_authorized": False,
    }
    digest = sha256_json(canonical)
    return {
        "schema_version": "experimental_core_contract_identity_v1",
        "contract_name": canonical["contract_name"],
        "canonical_payload": canonical,
        "identity_sha256": digest,
        "recomputed_sha256": digest,
        "identity_match": True,
    }
