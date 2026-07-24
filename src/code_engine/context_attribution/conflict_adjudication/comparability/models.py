from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator


class FactorComparabilityAssessment(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        title="Factor Comparability Assessment v1",
        json_schema_extra={
            "$id": "https://conflict-oriented-discovery-engine.local/schemas/factor_comparability_assessment_v1"
        },
    )

    schema_version: Literal[
        "factor_comparability_assessment_v1"
    ] = "factor_comparability_assessment_v1"
    pair_id: str
    context_difference_identity: str
    context_difference_binding_identity: str
    factor_id: str
    factor_registry_identity: str
    assessment_status: Literal[
        "not_assessed",
        "pending_policy",
        "pending_human_adjudication",
        "validated",
        "rejected",
        "insufficient_information",
    ]
    effect_assessment_status: Literal[
        "assessed", "unknown", "not_applicable"
    ] | None = None
    comparability_severity: Literal[
        "none", "minor", "major", "blocking"
    ] | None = None
    comparability_policy_identity: str | None = None
    adjudication_identity: str | None = None
    rationale: str
    provenance: dict[str, Any]
    factor_comparability_identity: str
    validator_version: Literal[
        "factor_comparability_validator_v1"
    ] = "factor_comparability_validator_v1"
    validation_status: Literal["unvalidated", "validated", "rejected"]

    @model_validator(mode="after")
    def state_contract(self):
        if self.assessment_status == "validated":
            if self.effect_assessment_status is None:
                raise ValueError("validated_comparability_requires_epistemic_status")
            if not (self.comparability_policy_identity or self.adjudication_identity):
                raise ValueError("validated_comparability_requires_authority")
            if (
                self.effect_assessment_status == "assessed"
                and self.comparability_severity is None
            ):
                raise ValueError("assessed_comparability_requires_severity")
            if (
                self.effect_assessment_status != "assessed"
                and self.comparability_severity is not None
            ):
                raise ValueError("nonassessed_comparability_severity_forbidden")
        elif (
            self.effect_assessment_status is not None
            or self.comparability_severity is not None
        ):
            raise ValueError("pending_comparability_effect_must_be_null")
        return self
