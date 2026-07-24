from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

FORMAL_CONFLICT_DECISION_SCHEMA_VERSION = "formal_conflict_decision_v1"


class FormalConflictDecision(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        title="Formal Conflict Decision Staging v1",
        json_schema_extra={
            "$id": "https://conflict-oriented-discovery-engine.local/schemas/formal_conflict_decision_v1"
        },
    )

    schema_version: Literal[
        "formal_conflict_decision_v1"
    ] = FORMAL_CONFLICT_DECISION_SCHEMA_VERSION
    authority_scope: Literal["staging_only"] = "staging_only"
    candidate_id: str
    conflict_candidate_identity: str
    context_difference_identity: str | None
    conflict_comparability_identity: str | None
    decision_status: Literal[
        "candidate_only",
        "blocked_context_unavailable",
        "blocked_difference_unvalidated",
        "blocked_comparability_pending",
        "non_comparable",
        "conditionally_comparable",
        "insufficient_information",
        "context_explained_divergence",
        "formal_conflict_confirmed",
    ]
    formal_conflict_confirmed: bool
    rationale: str
    formal_gate_policy_identity: str
    scientific_decision_version: str
    provenance: dict[str, Any]
    formal_conflict_decision_identity: str
    validator_version: Literal[
        "formal_conflict_judgment_validator_v1"
    ] = "formal_conflict_judgment_validator_v1"
    validation_status: Literal["validated", "rejected"]
