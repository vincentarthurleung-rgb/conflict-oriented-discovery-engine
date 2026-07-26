"""Fail-closed Factor→Measurement application resolution."""
from __future__ import annotations

from typing import Any

from .identities import core_identity
from .source_authority import source_not_reported_allowed


def resolve_factor_application(
    *,
    observation: dict[str, Any],
    factors: list[dict[str, Any]],
    measurements: list[dict[str, Any]],
    results: list[dict[str, Any]],
    existing_linkages: list[dict[str, Any]],
    source_relation_refs: list[dict[str, Any]],
    scope_audit: dict[str, Any],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    explicit_pairs = {
        (row["source_ref"], row["target_ref"])
        for row in existing_linkages
        if row.get("relation_type") == "factor_applies_to_measurement"
        and row.get("authority_status") in {"authoritative", "deterministic"}
    }
    explicit_pairs.update(
        (row["factor_ref"], row["measurement_ref"])
        for row in source_relation_refs
        if row.get("relation_explicit") and row.get("source_anchor_verified")
    )
    type_not_required = observation.get("observation_type") in {
        "descriptive_measurement", "non_experimental_claim"
    }
    if explicit_pairs:
        status = "deterministically_resolved"
    elif type_not_required:
        status = "not_required_by_type_policy"
    elif len(factors) > 1 and (
        len(measurements) > 1 or source_not_reported_allowed(scope_audit)
    ):
        status = "annotation_required"
    elif not source_not_reported_allowed(scope_audit):
        status = "source_scope_insufficient"
    elif scope_audit.get("source_not_reported_authorized"):
        status = "source_not_reported"
    else:
        status = "unresolved"
    payload = {
        "observation_identity": observation.get("source_observation_identity", observation["identity"]),
        "resolution_status": status,
        "resolved_application_pairs": [
            {"factor_ref": pair[0], "measurement_ref": pair[1]}
            for pair in sorted(explicit_pairs)
        ],
        "candidate_factor_refs": sorted(f["identity"] for f in factors),
        "measurement_refs": sorted(m["identity"] for m in measurements),
        "single_measurement_only_used_as_authority": False,
        "default_all_to_all_created": False,
        "source_scope_identity": scope_audit["identity"],
        "creates_scientific_link": status == "deterministically_resolved",
        "provider_candidate": False,
        "provider_reextraction_required": False,
        "automatic_execution_authorized": False,
        "provider_call_authorized": False,
        "network_call_authorized": False,
        "budget_authorization_present": False,
        "provenance": provenance,
        "schema_version": "source_grounded_factor_measurement_application_resolution_v1",
    }
    payload["identity"] = core_identity(
        "source_grounded_factor_measurement_application_resolution_v1",
        {k: v for k, v in payload.items() if k != "provenance"},
    )
    return payload
