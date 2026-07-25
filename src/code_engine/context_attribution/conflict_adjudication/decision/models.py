from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class ConflictAdjudicationDecision(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        title="Conflict Adjudication Decision v1",
        json_schema_extra={
            "$id": "https://conflict-oriented-discovery-engine.local/schemas/conflict_adjudication_decision_v1"
        },
    )

    schema_version: Literal[
        "conflict_adjudication_decision_v1"
    ] = "conflict_adjudication_decision_v1"
    authority_scope: Literal["staging_only"] = "staging_only"
    pair_id: str
    claim_alignment_identity: str
    contradiction_signal_identity: str
    conflict_candidate_identity: str
    candidate_qualification_identity: str | None = None
    candidate_qualification_status: str | None = None
    context_difference_identity: str | None
    context_difference_binding_identity: str | None
    comparability_assessment_bundle_identity: str | None
    divergence_explanation_bundle_identity: str | None
    factor_attribution_bundle_identity: str | None
    formal_gate_policy_identity: str
    adjudication_status: Literal[
        "candidate_only",
        "blocked_alignment_unvalidated",
        "blocked_contradiction_unvalidated",
        "blocked_candidate_unqualified",
        "blocked_context_unavailable",
        "blocked_difference_unvalidated",
        "blocked_attribution_pending",
        "non_comparable",
        "insufficient_information",
        "context_explained_divergence",
        "conditionally_comparable_disagreement",
        "unresolved_disagreement",
        "formal_conflict_confirmed",
    ]
    formal_conflict_confirmed: bool
    rationale: str
    conflict_adjudication_decision_identity: str
    provenance: dict[str, Any]
    validator_version: Literal[
        "conflict_adjudication_validator_v1"
    ] = "conflict_adjudication_validator_v1"
    validation_status: Literal["validated", "rejected"]
