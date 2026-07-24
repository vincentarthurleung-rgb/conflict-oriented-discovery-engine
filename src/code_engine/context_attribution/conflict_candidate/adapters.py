from __future__ import annotations

from copy import deepcopy
from typing import Any

from ..layer_identity import layer_identity
from .identities import conflict_candidate_identity
from .models import ConflictCandidate

LEGACY_WEAK_CANDIDATE_ADAPTER_VERSION = (
    "legacy_weak_conflict_candidate_to_conflict_candidate_v1_adapter"
)


def _context_status(observation_id: str, statuses: dict[str, str]) -> str:
    status = statuses.get(observation_id, "unavailable")
    return status if status in {"validated", "failed"} else "unavailable"


def adapt_legacy_weak_candidate(
    payload: dict[str, Any], *, context_statuses: dict[str, str]
) -> ConflictCandidate:
    source = deepcopy(payload)
    observation_a = source["supporting_observation_ids"][0]
    observation_b = source["opposing_or_contextual_observation_ids"][0]
    preview_a = (source.get("supporting_observations_preview") or [{}])[0]
    preview_b = (source.get("opposing_observations_preview") or [{}])[0]
    claim_a_identity = layer_identity(
        "normalized_claim",
        "legacy_normalized_claim_identity_adapter_v1",
        {
            "observation_id": observation_a,
            "subject": preview_a.get("subject_raw"),
            "relation": preview_a.get("relation_raw"),
            "direction": preview_a.get("direction"),
            "object": preview_a.get("object_raw"),
        },
    )
    claim_b_identity = layer_identity(
        "normalized_claim",
        "legacy_normalized_claim_identity_adapter_v1",
        {
            "observation_id": observation_b,
            "subject": preview_b.get("subject_raw"),
            "relation": preview_b.get("relation_raw"),
            "direction": preview_b.get("direction"),
            "object": preview_b.get("object_raw"),
        },
    )
    canonical_edge_identity = layer_identity(
        "canonical_edge",
        "legacy_weak_candidate_edge_identity_adapter_v1",
        {
            "base_subject": source.get("base_subject"),
            "right_base_subject": source.get("right_base_subject"),
            "base_object": source.get("base_object"),
            "right_base_object": source.get("right_base_object"),
            "relation_family_match": source.get("relation_family_match"),
        },
    )
    status_a = _context_status(observation_a, context_statuses)
    status_b = _context_status(observation_b, context_statuses)
    readiness = (
        "context_ready"
        if status_a == status_b == "validated"
        else "context_unavailable"
        if status_a == status_b == "unavailable"
        else "context_partial"
    )
    projected = {
        "schema_version": "conflict_candidate_v1",
        "candidate_id": source["candidate_id"],
        "canonical_edge_identity": canonical_edge_identity,
        "observation_a_id": observation_a,
        "observation_b_id": observation_b,
        "claim_a_identity": claim_a_identity,
        "claim_b_identity": claim_b_identity,
        "disagreement_signal": {
            "candidate_type": source.get("candidate_type"),
            "direction_opposed": source.get("direction_opposed"),
            "left_direction": preview_a.get("direction"),
            "right_direction": preview_b.get("direction"),
        },
        "candidate_reason": list(
            source.get("reasons") or [source.get("candidate_type") or "legacy_candidate"]
        ),
        "candidate_generation_version": (
            "legacy_weak_conflict_candidate_generation_preserved_v1"
        ),
        "context_a_status": status_a,
        "context_b_status": status_b,
        "context_readiness": readiness,
        "provenance": {
            "adapter_version": LEGACY_WEAK_CANDIDATE_ADAPTER_VERSION,
            "legacy_candidate_preserved": True,
            "legacy_candidate_id": source["candidate_id"],
            "legacy_comparability_fields_non_authoritative": {
                key: deepcopy(source.get(key))
                for key in (
                    "comparability_score",
                    "comparability_label",
                    "comparability_reasons",
                    "non_comparability_reasons",
                    "context_match",
                )
                if key in source
            },
        },
        "validator_version": "conflict_candidate_validator_v1",
        "validation_status": "validated",
    }
    projected["conflict_candidate_identity"] = conflict_candidate_identity(projected)
    return ConflictCandidate.model_validate(projected)
