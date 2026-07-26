"""Post-triage remediation classification; planning only."""
from __future__ import annotations

from typing import Any

from .identities import core_identity

STATUS_MAP = {
    "deterministically_resolved": "resolved_offline",
    "not_required_by_type_policy": "resolved_offline",
    "annotation_required": "annotation_required",
    "source_not_reported": "source_not_reported",
    "source_scope_insufficient": "source_reingestion_required",
    "optional_enrichment": "optional_enrichment",
    "provider_candidate": "provider_candidate",
    "unresolved": "unresolved",
    "rejected": "unresolved",
}


def plan_remediation_v3(
    *, target_type: str, target_identity: str, observation_identity: str,
    source_block_identity: str | None, resolution_status: str,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    classification = STATUS_MAP[resolution_status]
    payload = {
        "target_type": target_type,
        "target_identity": target_identity,
        "observation_identity": observation_identity,
        "source_block_identity": source_block_identity,
        "requirement_classification": classification,
        "resolution_status": resolution_status,
        "deduplication_key": f"{source_block_identity or observation_identity}:{target_type}:{classification}",
        "provider_reextraction_required": False,
        "provider_reextraction_candidate": classification == "provider_candidate",
        "source_reingestion_required": classification == "source_reingestion_required",
        "automatic_execution_authorized": False,
        "provider_call_authorized": False,
        "network_call_authorized": False,
        "budget_authorization_present": False,
        "historical_requirement_unchanged": True,
        "provenance": provenance,
        "schema_version": "experimental_core_remediation_requirement_v3",
    }
    payload["identity"] = core_identity(
        "experimental_core_remediation_requirement_v3",
        {k: v for k, v in payload.items() if k != "provenance"},
    )
    return payload


def source_reingestion_requirement(
    *, target_identity: str, observation_identity: str, source_document_identity: str | None,
    source_block_identity: str | None, missing_components: list[str],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "target_identity": target_identity,
        "observation_identity": observation_identity,
        "source_document_identity": source_document_identity,
        "source_block_identity": source_block_identity,
        "missing_source_components": sorted(set(missing_components)),
        "requirement_status": "planned_not_executed",
        "provider_extraction_substitute": False,
        "reingestion_executed": False,
        "network_call_authorized": False,
        "provenance": provenance,
        "schema_version": "source_reingestion_requirement_v1",
    }
    payload["identity"] = core_identity(
        "source_reingestion_requirement_v1",
        {k: v for k, v in payload.items() if k != "provenance"},
    )
    return payload
