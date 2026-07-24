from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator


class FactorDivergenceExplanation(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        title="Factor Divergence Explanation v1",
        json_schema_extra={
            "$id": "https://conflict-oriented-discovery-engine.local/schemas/factor_divergence_explanation_v1"
        },
    )

    schema_version: Literal[
        "factor_divergence_explanation_v1"
    ] = "factor_divergence_explanation_v1"
    pair_id: str
    context_difference_identity: str
    context_difference_binding_identity: str
    contradiction_signal_identity: str
    factor_id: str
    assessment_status: Literal[
        "not_assessed",
        "pending_policy",
        "pending_human_adjudication",
        "assessed",
        "insufficient_information",
        "rejected",
    ]
    explanatory_effect: Literal[
        "not_explanatory",
        "potentially_explanatory",
        "sufficiently_explanatory",
    ] | None = None
    explanation_policy_identity: str | None = None
    adjudication_identity: str | None = None
    rationale: str
    provenance: dict[str, Any]
    factor_divergence_explanation_identity: str
    validator_version: Literal[
        "factor_divergence_explanation_validator_v1"
    ] = "factor_divergence_explanation_validator_v1"
    validation_status: Literal["unvalidated", "validated", "rejected"]

    @model_validator(mode="after")
    def state_contract(self):
        if self.assessment_status == "assessed":
            if self.explanatory_effect is None:
                raise ValueError("assessed_explanation_requires_effect")
            if not (self.explanation_policy_identity or self.adjudication_identity):
                raise ValueError("assessed_explanation_requires_authority")
        elif self.explanatory_effect is not None:
            raise ValueError("pending_or_insufficient_explanation_effect_must_be_null")
        if (
            self.explanatory_effect == "sufficiently_explanatory"
            and not (self.explanation_policy_identity or self.adjudication_identity)
        ):
            raise ValueError("sufficient_explanation_requires_authority")
        return self
