"""Auditable models for type-aware and relation-aware normalization."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from code_engine.schemas.models import CODEBaseModel


NormalizationStatus = Literal["resolved", "ambiguous", "unresolved_fallback", "rejected", "empty_or_invalid"]


class EntityRelation(CODEBaseModel):
    predicate: str
    object: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: str = ""
    source: str = "local_curated_registry"


class NormalizationCandidate(CODEBaseModel):
    canonical_id: str
    canonical_name: str
    entity_type: str
    semantic_level: str
    aliases: list[str] = Field(default_factory=list)
    external_ids: dict[str, Any] = Field(default_factory=dict)
    relations: list[EntityRelation] = Field(default_factory=list)
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    source: str = "local_curated_registry"
    match_type: str = "registry_exact"
    warnings: list[str] = Field(default_factory=list)


class NormalizationDecision(CODEBaseModel):
    raw_text: str
    normalized_surface: str
    canonical_id: str = ""
    canonical_name: str = ""
    entity_type: str = "unknown"
    semantic_level: str = "unknown"
    external_ids: dict[str, Any] = Field(default_factory=dict)
    relations: list[EntityRelation] = Field(default_factory=list)
    normalization_status: NormalizationStatus
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    resolver: str = "resolver_cascade_v1"
    match_type: str = "uppercase_fallback"
    candidates: list[NormalizationCandidate] = Field(default_factory=list)
    decision_reason: str = ""
    allow_high_confidence_graph_use: bool = False
    warnings: list[str] = Field(default_factory=list)
    domain_id: str = "general_biomedical"
    entity_registry_profile: str = "general_entity_resolution_hub"
    resolver_policy_id: str = "conservative_resolver_v2"
    domain_specific_resolution_used: bool = False
    domain_resolution_warnings: list[str] = Field(default_factory=list)
    candidate_count: int = 0
    candidate_provider_names: list[str] = Field(default_factory=list)
    selected_candidate_id: str | None = None
    entity_resolution_status: str = "unresolved"
    requires_manual_review: bool = False
    audit_ref: str | None = None
    # --- Cleaner integration fields ---
    selected_source: str = ""  # "external_after_cleaning", "curated", "cache", "llm_unverified", etc.
    selected_cleaned_surface: str = ""  # cleaned surface from LLM/deterministic cleaner
    original_surface: str = ""  # original mention before any cleaning
    external_verification_provider: str = ""  # provider name that verified the cleaned entity
    rejection_reason: str = ""  # reason if adjudicator rejected
    cleaner_trace: dict[str, Any] | None = None  # full cleaner audit trace
