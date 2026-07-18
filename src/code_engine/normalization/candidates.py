"""Provider-neutral entity resolution contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from code_engine.schemas.models import CODEBaseModel


EntityResolutionStatus = Literal["resolved_curated", "resolved_external_grounded", "resolved_cache", "ambiguous", "unresolved", "external_resolution_pending", "manual_review_required", "external_lookup_not_enabled", "external_provider_not_configured", "llm_suggestion_ungrounded", "error"]


class EntityCandidate(CODEBaseModel):
    surface: str
    normalized_surface: str
    candidate_id: str | None = None
    canonical_id: str | None = None
    canonical_name: str | None = None
    entity_type: str | None = None
    semantic_level: str | None = None
    source: str
    provider_name: str
    provider_record_id: str | None = None
    external_ids: dict[str, Any] = Field(default_factory=dict)
    aliases: list[str] = Field(default_factory=list)
    match_type: str = "provider_candidate"
    match_score: float = Field(default=0.0, ge=0.0, le=1.0)
    type_score: float = Field(default=0.0, ge=0.0, le=1.0)
    source_reliability: float = Field(default=0.0, ge=0.0, le=1.0)
    context_score: float = Field(default=0.0, ge=0.0, le=1.0)
    overall_score: float = Field(default=0.0, ge=0.0, le=1.0)
    requires_external_grounding: bool = False
    is_grounded: bool = False
    is_curated: bool = False
    is_llm_suggested: bool = False
    supporting_context: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    raw_provider_payload_ref: str | None = None
    species_context: str | None = None
    candidate_species: str | None = None
    species_match_score: float = Field(default=0.0, ge=0.0, le=1.0)
    species_match_status: str = "unknown"
    mention_granularity: str | None = None
    candidate_granularity: str | None = None
    granularity_match_score: float = Field(default=0.0, ge=0.0, le=1.0)
    granularity_status: str = "unknown"
    label_match_score: float = Field(default=0.0, ge=0.0, le=1.0)
    alias_match_score: float = Field(default=0.0, ge=0.0, le=1.0)
    normalized_string_score: float = Field(default=0.0, ge=0.0, le=1.0)
    entity_type_score: float = Field(default=0.0, ge=0.0, le=1.0)
    assay_context_score: float = Field(default=0.0, ge=0.0, le=1.0)
    source_priority_score: float = Field(default=0.0, ge=0.0, le=1.0)
    obsolete_penalty: float = Field(default=0.0, ge=0.0, le=1.0)
    final_score: float = Field(default=0.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def enforce_llm_boundary(self):
        if self.is_llm_suggested:
            self.is_grounded = False
            self.is_curated = False
            self.requires_external_grounding = True
            self.overall_score = min(self.overall_score, 0.45)
            if "llm_suggestion_requires_external_grounding" not in self.warnings:
                self.warnings.append("llm_suggestion_requires_external_grounding")
        return self


class EntityResolutionRequest(CODEBaseModel):
    surface: str
    context_text: str | None = None
    domain_id: str | None = None
    entity_registry_profile: str | None = None
    resolver_policy_id: str | None = None
    allowed_entity_types: list[str] = Field(default_factory=list)
    l1_entity_type_hint: str | None = None
    paper_id: str | None = None
    claim_id: str | None = None
    observation_id: str | None = None
    endpoint_role: str | None = None
    species_context: str | None = None
    species_context_status: str = "unknown"
    mention_granularity: str | None = None
    assay_context: str | None = None
    measurement_dimension: str | None = None
    network_enabled: bool = False
    api_enabled: bool = False
    execute: bool = False


class EntityResolutionResult(CODEBaseModel):
    request: EntityResolutionRequest
    candidates: list[EntityCandidate] = Field(default_factory=list)
    selected_candidate: EntityCandidate | None = None
    normalization_status: EntityResolutionStatus = "unresolved"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    decision_reason: str
    allow_high_confidence_graph_use: bool = False
    requires_manual_review: bool = False
    warnings: list[str] = Field(default_factory=list)
    audit_ref: str | None = None
