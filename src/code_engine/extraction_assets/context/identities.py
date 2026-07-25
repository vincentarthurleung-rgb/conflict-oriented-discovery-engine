"""Stable contract and case identities for experimental context assets."""
from __future__ import annotations

from typing import Any

from ..identities import sha256_json, stable_identity

CONTRACT_NAMES = (
    "experimental_context_candidate", "experiment_context_scope",
    "source_context_envelope", "experimental_context_field_registry",
    "context_field_evidence", "context_value_state_basis", "context_value_origin",
    "observation_context_scope_link", "context_scope_propagation_policy",
    "validated_observation_context", "context_normalization", "context_consolidation",
    "context_asset_scoped_authority", "historical_context_asset_inventory",
    "historical_context_asset_migration", "context_asset_coverage_ledger",
    "context_completeness_profile", "context_asset_remediation_v2",
    "context_asset_multi_axis_readiness", "context_provider_call_policy",
    "experimental_context_asset_orchestration",
    "research_grade_observation_context_extraction",
)


def context_asset_identity(kind: str, payload: dict[str, Any]) -> str:
    return stable_identity(kind, payload, exclude={"run_path", "absolute_path", "timestamp"})


def contract_identity(name: str) -> dict[str, Any]:
    if name not in CONTRACT_NAMES:
        raise ValueError(f"unknown context contract: {name}")
    contract_name = (
        "context_asset_remediation_contract_identity_v2"
        if name == "context_asset_remediation_v2"
        else name + "_contract_identity_v1"
    )
    canonical = {
        "contract_name": contract_name,
        "identity_algorithm": "sha256_canonical_json_v1",
        "immutable_revision_policy": True,
        "derived_reasoning_allowed": False,
        "provider_execution_authorized": False,
    }
    digest = sha256_json(canonical)
    return {
        "schema_version": "experimental_context_contract_identity_v1",
        "contract_name": canonical["contract_name"],
        "canonical_payload": canonical,
        "identity_sha256": digest,
        "recomputed_sha256": digest,
        "identity_match": True,
    }
