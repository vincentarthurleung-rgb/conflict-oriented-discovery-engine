"""Candidate-only Machine Reuse Readiness v3."""
from __future__ import annotations

from typing import Any

from .identities import core_identity


def evaluate_readiness_v3_candidate(
    *, observation_identity: str, structured_revision_identity: str,
    comparator_status: str | None, factor_application_status: str | None,
    method_status: str | None, context_available: bool,
    v2_readiness_identity: str, provenance: dict[str, Any],
) -> dict[str, Any]:
    annotation = "annotation_required"
    if factor_application_status in {"source_scope_insufficient", "source_not_reported"} or comparator_status in {
        "source_scope_insufficient", "source_not_reported"
    }:
        status = "structured_core_blocked_source_gap"
    elif factor_application_status in {"unresolved", "rejected"} or comparator_status in {"unresolved", "rejected"}:
        status = "structured_core_blocked_linkage_unresolved"
    elif annotation in {factor_application_status, comparator_status}:
        status = "machine_reusable_with_annotation_pending"
    elif not context_available:
        status = "machine_reusable_with_context_limitations"
    elif method_status and method_status != "deterministically_resolved":
        status = "machine_reusable_with_method_limitations"
    else:
        status = "machine_reusable_candidate"
    payload = {
        "observation_identity": observation_identity,
        "structured_observation_revision_identity": structured_revision_identity,
        "status": status,
        "comparator_resolution_status": comparator_status,
        "factor_application_resolution_status": factor_application_status,
        "method_resolution_status": method_status,
        "v2_readiness_identity": v2_readiness_identity,
        "candidate_only": True,
        "active_v2_replaced": False,
        "downstream_recomputation_candidate": True,
        "human_gold": False,
        "formal_authority": False,
        "provenance": provenance,
        "schema_version": "experimental_observation_machine_reuse_readiness_v3_candidate",
    }
    payload["identity"] = core_identity(
        "experimental_observation_machine_reuse_readiness_v3_candidate",
        {k: v for k, v in payload.items() if k != "provenance"},
    )
    return payload
