from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SemanticDimension(StrictModel):
    dimension_id: str
    canonical_identity: str | None
    canonical_value: str | None
    status: Literal["resolved", "unresolved", "not_applicable"]
    source_paths: list[str]


class PropositionCoreView(StrictModel):
    schema_version: Literal["proposition_core_view_v2"] = "proposition_core_view_v2"
    normalized_claim_identity: str
    canonical_subject_identity: str | None
    canonical_relation_family: str | None
    canonical_endpoint_identity: str | None
    outcome_variable_identity: str | None
    proposition_core_dimensions: list[SemanticDimension]
    unresolved_core_dimensions: list[str]
    normalization_identities: list[str]
    proposition_core_identity: str


class ContradictionResultView(StrictModel):
    schema_version: Literal["contradiction_result_view_v1"] = "contradiction_result_view_v1"
    observation_id: str
    normalized_result_identity: str
    direction: str | None
    sign: str | None
    polarity: str | None
    qualitative_outcome: str | None
    quantitative_effect: str | None
    result_category: str | None
    evidence_anchor_ids: list[str]
    contradiction_result_identity: str


class ContextEnvelopeRef(StrictModel):
    schema_version: Literal["context_envelope_ref_v1"] = "context_envelope_ref_v1"
    observation_id: str
    observation_context_identity: str | None
    context_status: str
    context_readiness: str
    failed_factor_ids: list[str]
    unavailable_factor_ids: list[str]
    context_envelope_ref_identity: str


class GranularityQualificationView(StrictModel):
    schema_version: Literal["granularity_qualification_view_v1"] = "granularity_qualification_view_v1"
    observation_id: str
    qualifier_dimensions: list[SemanticDimension]
    bridge_status: Literal["required", "not_required", "unresolved"]
    unresolved_dimensions: list[str]
    granularity_qualification_identity: str


class ObservationSemanticViews(StrictModel):
    schema_version: Literal["observation_semantic_views_v1"] = "observation_semantic_views_v1"
    observation_id: str
    proposition_core_view: PropositionCoreView
    contradiction_result_view: ContradictionResultView
    context_envelope_ref: ContextEnvelopeRef
    granularity_qualification_view: GranularityQualificationView
    observation_semantic_views_identity: str
    provenance: dict[str, Any] = Field(default_factory=dict)
