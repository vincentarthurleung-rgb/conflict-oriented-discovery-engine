from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

OBSERVATION_CONTEXT_SCHEMA_VERSION = "observation_context_v1"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ObservationContextFact(StrictModel):
    factor_id: str = Field(min_length=1)
    status: Literal["explicit", "inferred_from_local_chain", "unknown", "conflicting"]
    raw_value: str | None = None
    normalized_value: str | None = None
    evidence_anchor_ids: list[str] = Field(default_factory=list)
    token_span: dict[str, Any] | None = None
    source_chain_node_ids: list[str] = Field(default_factory=list)
    raw_components: list[dict[str, Any]] = Field(default_factory=list)
    inference_rule: str | None = None
    composition_rule: str | None = None
    composition_provenance: list[dict[str, Any]] = Field(default_factory=list)
    normalization_provenance: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def fact_contract(self):
        if self.raw_value == "" or self.normalized_value == "":
            raise ValueError("observation_context_empty_string_forbidden")
        if self.status == "unknown" and any(
            (
                self.raw_value,
                self.normalized_value,
                self.evidence_anchor_ids,
                self.token_span,
                self.source_chain_node_ids,
                self.raw_components,
                self.inference_rule,
                self.composition_rule,
                self.composition_provenance,
            )
        ):
            raise ValueError("unknown_observation_context_fact_must_be_empty")
        if self.status == "explicit" and (
            self.token_span is None or not self.evidence_anchor_ids
        ):
            raise ValueError("explicit_observation_context_fact_requires_span")
        if self.status == "inferred_from_local_chain" and (
            not self.raw_components
            or not self.source_chain_node_ids
            or not self.inference_rule
        ):
            raise ValueError("inferred_observation_context_fact_requires_provenance")
        return self


class ObservationContext(StrictModel):
    model_config = ConfigDict(
        extra="forbid",
        title="Observation Context v1",
        json_schema_extra={
            "$id": "https://conflict-oriented-discovery-engine.local/schemas/observation_context_v1"
        },
    )

    schema_version: Literal["observation_context_v1"] = OBSERVATION_CONTEXT_SCHEMA_VERSION
    observation_id: str = Field(min_length=1)
    normalized_claim_identity: str = Field(min_length=1)
    canonical_subject: str = Field(min_length=1)
    canonical_relation: str = Field(min_length=1)
    canonical_object: str = Field(min_length=1)
    normalized_polarity: str = Field(min_length=1)
    evidence_chain_identity: str = Field(min_length=1)
    token_catalog_identity: str = Field(min_length=1)
    anchor_set_identity: str = Field(min_length=1)
    registry_identity: str = Field(min_length=1)
    composition_identity: str = Field(min_length=1)
    facts: list[ObservationContextFact]
    provenance: dict[str, Any]
    observation_context_identity: str
    validator_version: Literal[
        "observation_context_validator_v1"
    ] = "observation_context_validator_v1"
    validation_status: Literal["validated", "rejected"]
