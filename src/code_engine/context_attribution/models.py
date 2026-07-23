from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

EXTRACTION_SCHEMA_VERSION = "observation_context_extraction_v3"
PAIR_SCHEMA_VERSION = "context_pair_attribution_v2"

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class ContextFactor(StrictModel):
    factor_id: str
    raw_value: str
    normalized_value: str | None = None
    status: Literal["explicit", "inferred_from_local_chain", "unknown", "conflicting"]
    evidence_anchor_ids: list[str] = Field(default_factory=list)
    source_chain_node_ids: list[str] = Field(default_factory=list)
    inference_rule: str | None = None
    normalized_candidate: str | None = None
    normalization_status: Literal[
        "not_requested", "resolved_identity", "resolved_controlled",
        "resolved_supplied", "unresolved_candidate", "not_applicable",
    ] = "not_requested"
    normalization_provenance: dict = Field(default_factory=dict)
    evidence_text: str | None = None
    authoritative_evidence: list[dict] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def unknown_is_empty(self):
        if self.status == "unknown" and (self.raw_value.casefold() != "unknown" or self.normalized_value not in {None, "unknown"}):
            raise ValueError("unknown_factor_must_not_be_canonicalized")
        return self

class ContextExtraction(StrictModel):
    schema_version: Literal["observation_context_extraction_v3"] = EXTRACTION_SCHEMA_VERSION
    observation_id: str
    domain_profiles: list[str] = Field(min_length=1)
    input_mode: Literal["abstract_sentence_only", "fulltext_evidence_chain"]
    context_factors: list[ContextFactor]
    missing_critical_information: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provenance: dict = Field(default_factory=dict)
    extraction_identity: str | None = None
    validation_status: Literal["unvalidated", "validated", "rejected", "reviewable"] = "unvalidated"

    @model_validator(mode="before")
    @classmethod
    def read_v2_artifacts(cls, value):
        if isinstance(value, dict) and value.get("schema_version") == "observation_context_extraction_v2":
            value = {**value, "schema_version": EXTRACTION_SCHEMA_VERSION}
        return value

class FactorComparison(StrictModel):
    factor_id: str
    claim_a_value: str
    claim_b_value: str
    status: Literal["same", "equivalent", "different", "missing_a", "missing_b", "missing_both", "conflicting"]
    comparability_effect: Literal["none", "minor", "major", "blocking", "unknown"]
    explanatory_strength: Literal["none", "low", "medium", "high", "unknown"]
    claim_a_anchor_ids: list[str] = Field(default_factory=list)
    claim_b_anchor_ids: list[str] = Field(default_factory=list)
    reason: str

class ContextPairAttribution(StrictModel):
    schema_version: Literal["context_pair_attribution_v2"] = PAIR_SCHEMA_VERSION
    pair_id: str
    claim_a_observation_id: str
    claim_b_observation_id: str
    comparability: Literal["comparable", "conditionally_comparable", "non_comparable", "insufficient_information"]
    factor_comparisons: list[FactorComparison]
    primary_explanatory_factors: list[str] = Field(default_factory=list)
    missing_critical_information: list[str] = Field(default_factory=list)
    reasoning_summary: str
    confidence: float = Field(ge=0, le=1)
    comparison_identity: str | None = None
    validation_status: Literal["unvalidated", "validated", "rejected", "reviewable"] = "unvalidated"
