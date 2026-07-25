"""Lossless-by-reference experimental-core projection v2."""
from __future__ import annotations

from typing import Any

from .identities import core_identity


PROJECTION_CONTRACT = "experimental_core_projection_contract_identity_v2"


def build_projection(
    observation: dict[str, Any],
    *,
    readiness_ref: str,
    source_projection_v1_ref: str | None = None,
) -> dict[str, Any]:
    """Project a structured observation without copying scientific payloads."""
    payload = {
        "source_observation_identity": observation["source_observation_identity"],
        "structured_observation_revision_identity": observation["identity"],
        "observation_type": observation["observation_type"],
        "experiment_scope_identity": observation.get("experiment_scope_identity"),
        "experimental_factor_refs": list(observation["experimental_factor_ids"]),
        "measurement_refs": list(observation["measurement_ids"]),
        "observed_result_refs": list(observation["observed_result_ids"]),
        "linkage_refs": list(observation["linkage_record_ids"]),
        "context_asset_ref": observation.get("context_asset_identity"),
        "evidence_chain_ref": observation.get("evidence_chain_identity"),
        "structural_integrity_ref": observation.get("structural_integrity_identity"),
        "machine_reuse_readiness_ref": readiness_ref,
        "projection_contract_identity": PROJECTION_CONTRACT,
        "source_projection_v1_ref": source_projection_v1_ref,
        "projection_loss_repair_revision_refs": [],
        "lossless_by_reference": True,
        "summary_is_authoritative": False,
        "immutable": True,
        "provenance": {
            "producer": "experimental_core_projection_repair_offline",
            "producer_version": "v1",
            "source_artifact_refs": [observation["identity"]],
            "deterministic_rule_refs": [PROJECTION_CONTRACT],
            "limitations": [],
            "offline": True,
        },
        "schema_version": "experimental_core_projection_v2",
    }
    identity = core_identity("experimental_core_projection_v2", payload)
    return {"projection_revision_id": identity, "identity": identity, **payload}


def build_compatibility_sidecar(
    projection: dict[str, Any], *, historical_projection_identity: str | None,
    missing_component_types: list[str],
) -> dict[str, Any]:
    recovered = (
        projection["experimental_factor_refs"] + projection["measurement_refs"]
        + projection["observed_result_refs"] + projection["linkage_refs"]
    )
    payload = {
        "historical_projection_identity": historical_projection_identity,
        "structured_observation_identity": projection["structured_observation_revision_identity"],
        "missing_component_types": sorted(missing_component_types),
        "recovered_component_refs": recovered,
        "projection_v2_identity": projection["identity"],
        "compatibility_status": (
            "historical_projection_loss_repaired_by_sidecar"
            if missing_component_types else "fully_referenced"
        ),
        "historical_content_unchanged": True,
        "provenance": projection["provenance"],
        "schema_version": "experimental_core_projection_compatibility_sidecar_v1",
    }
    payload["identity"] = core_identity(
        "experimental_core_projection_compatibility_sidecar_v1", payload
    )
    return payload
