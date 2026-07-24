from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

CONFLICT_CANDIDATE_SCHEMA_VERSION = "conflict_candidate_v1"


class ConflictCandidate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        title="Conflict Candidate v1",
        json_schema_extra={
            "$id": "https://conflict-oriented-discovery-engine.local/schemas/conflict_candidate_v1"
        },
    )

    schema_version: Literal["conflict_candidate_v1"] = CONFLICT_CANDIDATE_SCHEMA_VERSION
    candidate_id: str = Field(min_length=1)
    canonical_edge_identity: str = Field(min_length=1)
    observation_a_id: str = Field(min_length=1)
    observation_b_id: str = Field(min_length=1)
    claim_a_identity: str = Field(min_length=1)
    claim_b_identity: str = Field(min_length=1)
    disagreement_signal: dict[str, Any]
    candidate_reason: list[str] = Field(min_length=1)
    candidate_generation_version: str = Field(min_length=1)
    context_a_status: Literal["validated", "failed", "unavailable"]
    context_b_status: Literal["validated", "failed", "unavailable"]
    context_readiness: Literal[
        "context_ready", "context_partial", "context_unavailable"
    ]
    provenance: dict[str, Any]
    conflict_candidate_identity: str
    validator_version: Literal[
        "conflict_candidate_validator_v1"
    ] = "conflict_candidate_validator_v1"
    validation_status: Literal["validated", "rejected"]
