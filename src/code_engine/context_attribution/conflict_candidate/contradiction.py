from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator

from ..claim_alignment.models import AlignedClaimGroup
from ..layer_identity import layer_identity
from .models import ConflictCandidate

CONTRADICTION_SIGNAL_SCHEMA_VERSION = "contradiction_signal_v1"
CONTRADICTION_SIGNAL_VALIDATOR_VERSION = "contradiction_signal_validator_v1"
CONTRADICTION_SIGNAL_IDENTITY_VERSION = "contradiction_signal_identity_v1"


class ContradictionSignal(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        title="Contradiction Signal v1",
        json_schema_extra={
            "$id": "https://conflict-oriented-discovery-engine.local/schemas/contradiction_signal_v1"
        },
    )

    schema_version: Literal[
        "contradiction_signal_v1"
    ] = CONTRADICTION_SIGNAL_SCHEMA_VERSION
    contradiction_signal_id: str
    alignment_identity: str
    observation_a_id: str
    observation_b_id: str
    signal_type: Literal[
        "opposite_direction",
        "incompatible_outcome",
        "inconsistent_result_category",
        "quantitative_disagreement",
        "unresolved_disagreement",
    ]
    claim_a_normalized_result: str | None
    claim_b_normalized_result: str | None
    claim_a_direction: str | None
    claim_b_direction: str | None
    signal_status: Literal[
        "validated", "candidate", "rejected", "insufficient_information"
    ]
    signal_basis: list[str]
    signal_provenance: dict[str, Any]
    contradiction_signal_identity: str
    validator_version: Literal[
        "contradiction_signal_validator_v1"
    ] = CONTRADICTION_SIGNAL_VALIDATOR_VERSION
    validation_status: Literal["validated", "rejected"]

    @model_validator(mode="after")
    def validated_signal_has_sources(self):
        if self.signal_status == "validated" and (
            not self.claim_a_direction or not self.claim_b_direction
        ):
            raise ValueError("validated_contradiction_requires_direction_sources")
        return self


def contradiction_signal_identity(payload: dict[str, Any]) -> str:
    return layer_identity(
        "contradiction_signal",
        CONTRADICTION_SIGNAL_IDENTITY_VERSION,
        {
            key: payload[key]
            for key in (
                "alignment_identity",
                "observation_a_id",
                "observation_b_id",
                "signal_type",
                "claim_a_normalized_result",
                "claim_b_normalized_result",
                "claim_a_direction",
                "claim_b_direction",
                "signal_status",
                "validator_version",
            )
        },
    )


def project_legacy_contradiction_signal(
    source: dict[str, Any],
    *,
    candidate: ConflictCandidate,
    alignment: AlignedClaimGroup,
) -> ContradictionSignal:
    preview_a = (source.get("supporting_observations_preview") or [{}])[0]
    preview_b = (source.get("opposing_observations_preview") or [{}])[0]
    direction_a = preview_a.get("direction")
    direction_b = preview_b.get("direction")
    opposed = (
        source.get("direction_opposed") is True
        and direction_a in {"positive", "negative"}
        and direction_b in {"positive", "negative"}
        and direction_a != direction_b
    )
    status = "validated" if opposed else "insufficient_information"
    signal_type = "opposite_direction" if opposed else "unresolved_disagreement"
    payload = {
        "schema_version": "contradiction_signal_v1",
        "contradiction_signal_id": layer_identity(
            "contradiction_signal_record",
            "contradiction_signal_record_id_v1",
            {
                "alignment_identity": alignment.claim_alignment_identity,
                "candidate_id": candidate.candidate_id,
            },
        ),
        "alignment_identity": alignment.claim_alignment_identity,
        "observation_a_id": candidate.observation_a_id,
        "observation_b_id": candidate.observation_b_id,
        "signal_type": signal_type,
        "claim_a_normalized_result": direction_a,
        "claim_b_normalized_result": direction_b,
        "claim_a_direction": direction_a,
        "claim_b_direction": direction_b,
        "signal_status": status,
        "signal_basis": [
            "legacy candidate direction_opposed flag",
            "normalized endpoint direction values",
        ],
        "signal_provenance": {
            "source": "read_only_legacy_candidate_migration",
            "candidate_id": candidate.candidate_id,
            "raw_provider_effect_consumed": False,
            "comparability_consumed": False,
            "explanation_derived": False,
        },
        "validator_version": "contradiction_signal_validator_v1",
        "validation_status": "validated" if opposed else "rejected",
    }
    payload["contradiction_signal_identity"] = contradiction_signal_identity(payload)
    return ContradictionSignal.model_validate(payload)


def validate_contradiction_signal(
    payload: ContradictionSignal | dict[str, Any],
    *,
    alignment: AlignedClaimGroup,
) -> tuple[ContradictionSignal, list[str]]:
    value = (
        payload
        if isinstance(payload, ContradictionSignal)
        else ContradictionSignal.model_validate(payload)
    )
    errors: list[str] = []
    if value.alignment_identity != alignment.claim_alignment_identity:
        errors.append("contradiction_alignment_identity_mismatch")
    if value.observation_a_id != alignment.member_observation_ids[0]:
        errors.append("contradiction_observation_a_mismatch")
    if value.observation_b_id != alignment.member_observation_ids[1]:
        errors.append("contradiction_observation_b_mismatch")
    if value.signal_type == "opposite_direction" and not (
        value.claim_a_direction in {"positive", "negative"}
        and value.claim_b_direction in {"positive", "negative"}
        and value.claim_a_direction != value.claim_b_direction
    ):
        errors.append("opposite_direction_not_supported")
    if value.contradiction_signal_identity != contradiction_signal_identity(
        value.model_dump()
    ):
        errors.append("contradiction_signal_identity_mismatch")
    return value, errors
