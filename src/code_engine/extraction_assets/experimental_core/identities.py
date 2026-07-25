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
)


def core_identity(kind: str, payload: dict[str, Any]) -> str:
    return stable_identity(
        kind, payload,
        exclude={"absolute_path", "run_path", "timestamp", "git_status"},
    )


def contract_identity(name: str) -> dict[str, Any]:
    if name not in CONTRACT_NAMES:
        raise ValueError(f"unknown experimental-core contract: {name}")
    suffix = "" if name.endswith("_v2") else "_v1"
    canonical = {
        "contract_name": f"{name}_contract_identity{suffix}",
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

