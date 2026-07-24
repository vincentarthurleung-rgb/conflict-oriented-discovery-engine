from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CONTEXT_DIFFERENCE_SCHEMA_VERSION = "context_difference_v1"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FactorDifference(StrictModel):
    factor_id: str = Field(min_length=1)
    status: Literal["same", "different", "missing_a", "missing_b", "missing_both"]
    claim_a_value: str | None
    claim_b_value: str | None
    claim_a_anchor_ids: list[str] = Field(default_factory=list)
    claim_b_anchor_ids: list[str] = Field(default_factory=list)
    comparison_rationale: str = Field(min_length=1)
    provenance: dict[str, Any]
    difference_confidence_suggestion: float | None = Field(
        default=None, ge=0, le=1
    )
    missing_information_description: str | None = None

    @model_validator(mode="after")
    def nullable_status_contract(self):
        if self.claim_a_value == "" or self.claim_b_value == "":
            raise ValueError("context_difference_empty_string_forbidden")
        present = (self.claim_a_value is not None, self.claim_b_value is not None)
        expected = {
            "same": (True, True),
            "different": (True, True),
            "missing_a": (False, True),
            "missing_b": (True, False),
            "missing_both": (False, False),
        }[self.status]
        if present != expected:
            raise ValueError(f"context_difference_status_value_mismatch:{self.status}")
        return self


class ContextDifference(StrictModel):
    model_config = ConfigDict(
        extra="forbid",
        title="Conflict Context Difference v1",
        json_schema_extra={
            "$id": "https://conflict-oriented-discovery-engine.local/schemas/context_difference_v1"
        },
    )

    schema_version: Literal["context_difference_v1"] = CONTEXT_DIFFERENCE_SCHEMA_VERSION
    candidate_id: str
    conflict_candidate_identity: str
    observation_a_id: str
    observation_b_id: str
    claim_a_identity: str
    claim_b_identity: str
    observation_context_a_identity: str
    observation_context_b_identity: str
    factor_registry_identity: str
    prompt_identity: str | None = None
    factor_differences: list[FactorDifference]
    provenance: dict[str, Any]
    context_difference_identity: str
    validator_version: Literal[
        "context_difference_validator_v1"
    ] = "context_difference_validator_v1"
    validation_status: Literal["validated", "rejected"]
