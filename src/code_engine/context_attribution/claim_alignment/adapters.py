from __future__ import annotations

from typing import Any

from ..conflict_candidate.models import ConflictCandidate
from ..layer_identity import layer_identity
from .identities import claim_alignment_identity
from .models import AlignedClaimGroup

LEGACY_ALIGNMENT_ADAPTER_VERSION = "legacy_candidate_claim_alignment_adapter_v1"


def _dimension(
    name: str, value: str | None, status: str, basis: str
) -> dict[str, str | None]:
    return {
        "dimension": name,
        "canonical_value": value if status == "resolved" else None,
        "resolution_status": status,
        "basis": basis,
    }


def align_legacy_candidate_endpoints(
    source: dict[str, Any], *, candidate: ConflictCandidate
) -> tuple[AlignedClaimGroup, dict[str, Any]]:
    """Read-only migration assessment from existing canonical candidate facts."""
    subject_match = source.get("subject_family_match")
    relation_match = source.get("relation_family_match")
    object_match = source.get("object_family_match")
    left_process = source.get("object_process_type")
    right_process = source.get("right_object_process_type")
    direction_opposed = source.get("direction_opposed") is True

    signature = {
        "canonical_subject_identity": _dimension(
            "canonical_subject_identity",
            source.get("base_subject") if subject_match == "exact" else None,
            "resolved" if subject_match == "exact" else "unresolved",
            "legacy canonical subject family",
        ),
        "canonical_relation_identity": _dimension(
            "canonical_relation_identity",
            "directional_relation" if relation_match == "same" else None,
            "resolved" if relation_match == "same" else "unresolved",
            "legacy relation-family comparison",
        ),
        "canonical_object_endpoint_identity": _dimension(
            "canonical_object_endpoint_identity",
            source.get("object_family")
            if object_match in {"exact", "alias"}
            else None,
            "resolved" if object_match in {"exact", "alias"} else "unresolved",
            "legacy object-family canonicalization",
        ),
        "observation_result_semantic_level": _dimension(
            "observation_result_semantic_level",
            left_process
            if left_process
            and left_process != "unknown"
            and left_process == right_process
            else None,
            "resolved"
            if left_process
            and left_process != "unknown"
            and left_process == right_process
            else "unresolved",
            "endpoint process-type compatibility",
        ),
        "measurement_endpoint_type": _dimension(
            "measurement_endpoint_type",
            left_process
            if left_process
            and left_process != "unknown"
            and left_process == right_process
            else None,
            "resolved"
            if left_process
            and left_process != "unknown"
            and left_process == right_process
            else "unresolved",
            "structured measurement/process metadata only",
        ),
        "outcome_category": _dimension(
            "outcome_category",
            "signed_directional_outcome" if direction_opposed else None,
            "resolved" if direction_opposed else "unresolved",
            "existing direction-disagreement representation",
        ),
        "intervention_target_identity": _dimension(
            "intervention_target_identity",
            source.get("base_subject") if subject_match == "exact" else None,
            "resolved" if subject_match == "exact" else "unresolved",
            "existing intervention subject identity",
        ),
        "direction_interpretation": _dimension(
            "direction_interpretation",
            "signed_direction" if direction_opposed else None,
            "resolved" if direction_opposed else "unresolved",
            "direction semantic type, not direction value",
        ),
        "temporal_interpretation": _dimension(
            "temporal_interpretation",
            None,
            "unresolved",
            "no normalized temporal identity in legacy candidate",
        ),
        "quantity_unit_compatibility": _dimension(
            "quantity_unit_compatibility",
            None,
            "not_applicable",
            "legacy candidate is not a quantitative disagreement",
        ),
    }
    dimensions = [
        {
            "dimension": "canonical_subject_identity",
            "status": "aligned" if subject_match == "exact" else "unresolved",
            "basis": f"subject_family_match={subject_match}",
        },
        {
            "dimension": "canonical_relation_identity",
            "status": "aligned" if relation_match == "same" else "unaligned",
            "basis": f"relation_family_match={relation_match}",
        },
        {
            "dimension": "canonical_object_endpoint_identity",
            "status": (
                "aligned"
                if object_match == "exact"
                else "partially_aligned"
                if object_match == "alias"
                else "unaligned"
            ),
            "basis": f"object_family_match={object_match}",
        },
        {
            "dimension": "observation_result_semantic_level",
            "status": (
                "aligned"
                if left_process
                and left_process != "unknown"
                and left_process == right_process
                else "unresolved"
            ),
            "basis": f"process_types={left_process},{right_process}",
        },
        {
            "dimension": "measurement_endpoint_type",
            "status": (
                "aligned"
                if left_process
                and left_process != "unknown"
                and left_process == right_process
                else "unresolved"
            ),
            "basis": "no inference beyond structured process types",
        },
        {
            "dimension": "direction_interpretation",
            "status": "aligned" if direction_opposed else "unresolved",
            "basis": "both endpoints use signed direction semantics",
        },
    ]
    critical = [item["status"] for item in dimensions[:5]]
    if "unaligned" in critical:
        alignment_status = "unaligned"
    elif any(status in {"partially_aligned", "unresolved"} for status in critical):
        alignment_status = "partially_aligned"
    elif all(status == "aligned" for status in critical):
        alignment_status = "aligned"
    else:
        alignment_status = "insufficient_information"
    unresolved = [
        item["dimension"]
        for item in dimensions
        if item["status"] in {"partially_aligned", "unresolved", "unaligned"}
    ]
    payload = {
        "schema_version": "aligned_claim_group_v1",
        "alignment_id": layer_identity(
            "alignment_record",
            "alignment_record_id_v1",
            {
                "member_claim_identities": [
                    candidate.claim_a_identity,
                    candidate.claim_b_identity,
                ]
            },
        ),
        "member_observation_ids": [
            candidate.observation_a_id,
            candidate.observation_b_id,
        ],
        "member_claim_identities": [
            candidate.claim_a_identity,
            candidate.claim_b_identity,
        ],
        "l2_normalization_identities": [
            candidate.claim_a_identity,
            candidate.claim_b_identity,
        ],
        "canonical_proposition_signature": signature,
        "alignment_status": alignment_status,
        "alignment_basis": [
            "read_only_migration_from_existing_endpoint_claim_and_edge_facts",
            "unresolved_dimensions_are_not_auto_aligned",
        ],
        "alignment_dimensions": dimensions,
        "unresolved_alignment_dimensions": unresolved,
        "context_readiness_by_member": {
            candidate.observation_a_id: candidate.context_a_status,
            candidate.observation_b_id: candidate.context_b_status,
        },
        "provenance": {
            "adapter_version": LEGACY_ALIGNMENT_ADAPTER_VERSION,
            "legacy_candidate_id": candidate.candidate_id,
            "historical_candidate_preserved": True,
            "canonical_edge_modified": False,
            "free_text_hashed_as_canonical_identity": False,
        },
        "validator_version": "claim_alignment_validator_v1",
        "validation_status": "validated",
    }
    payload["claim_alignment_identity"] = claim_alignment_identity(payload)
    record = AlignedClaimGroup.model_validate(payload)
    return record, {
        "candidate_id": candidate.candidate_id,
        "claim_alignment_identity": record.claim_alignment_identity,
        "alignment_status": record.alignment_status,
        "historical_candidate_preserved": True,
        "source_candidate_modified": False,
    }
