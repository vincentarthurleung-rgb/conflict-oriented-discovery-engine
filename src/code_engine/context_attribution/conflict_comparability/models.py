from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator

CONFLICT_COMPARABILITY_SCHEMA_VERSION = "conflict_comparability_assessment_v1"


class ConflictComparabilityAssessment(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        title="Conflict Comparability Assessment v1",
        json_schema_extra={
            "$id": "https://conflict-oriented-discovery-engine.local/schemas/conflict_comparability_assessment_v1"
        },
    )

    schema_version: Literal[
        "conflict_comparability_assessment_v1"
    ] = CONFLICT_COMPARABILITY_SCHEMA_VERSION
    candidate_id: str
    conflict_candidate_identity: str
    context_difference_identity: str
    source_difference_validation_status: Literal["validated", "rejected"]
    comparability_policy_identity: str | None = None
    adjudication_identity: str | None = None
    assessment_status: Literal[
        "not_assessed",
        "pending_policy",
        "pending_human_adjudication",
        "validated",
        "rejected",
        "insufficient_information",
    ]
    comparability_class: Literal[
        "comparable",
        "conditionally_comparable",
        "non_comparable",
        "insufficient_information",
    ] | None = None
    rationale: str
    provenance: dict[str, Any]
    conflict_comparability_identity: str
    validator_version: Literal[
        "conflict_comparability_validator_v1"
    ] = "conflict_comparability_validator_v1"
    validation_status: Literal["unvalidated", "validated", "rejected"]

    @model_validator(mode="after")
    def assessment_contract(self):
        if self.assessment_status == "validated":
            if self.comparability_class is None:
                raise ValueError("validated_comparability_requires_class")
            if not (self.comparability_policy_identity or self.adjudication_identity):
                raise ValueError("validated_comparability_requires_authority")
        elif self.comparability_class is not None:
            raise ValueError("nonvalidated_comparability_class_forbidden")
        return self
