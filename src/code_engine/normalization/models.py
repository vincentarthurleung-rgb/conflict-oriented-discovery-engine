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

