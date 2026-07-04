"""Contracts for semantic intake and domain routing."""

from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator, model_validator
from code_engine.schemas.models import CODEBaseModel


class _NullableListsModel(CODEBaseModel):
    """Treat JSON null like an omitted value for list-shaped LLM fields."""

    @field_validator("*", mode="before")
    @classmethod
    def normalize_nullable_lists(cls, value: Any, info):
        field = cls.model_fields.get(info.field_name)
        if value is None and field is not None and field.default_factory is list:
            return []
        return value

class SemanticIntakeRequest(CODEBaseModel):
    query: str
    language: str | None = None
    available_domain_profiles: list[dict[str, Any]] = Field(default_factory=list)
    allowed_domain_ids: list[str] = Field(default_factory=list)
    mode: str = "dry_run"
    api_enabled: bool = False
    model_name: str | None = None


class DomainRoutingDecision(_NullableListsModel):
    domain_id: str = "general_biomedical"
    subdomain_id: str | None = None
    domain_profile_id: str = "general_biomedical"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    alternative_domains: list[dict[str, Any]] = Field(default_factory=list)
    reasoning_summary: str = ""
    ambiguities: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    requires_manual_review: bool = False


class SemanticResearchIntent(_NullableListsModel):
    raw_user_input: str
    language: str = "unknown"
    task_type: str = "unknown"
    research_goal: str = ""
    primary_entities: list[str] = Field(default_factory=list)
    secondary_entities: list[str] = Field(default_factory=list)
    disease_or_condition: list[str] = Field(default_factory=list)
    mechanism_entities: list[str] = Field(default_factory=list)
    comparison_entities: list[str] = Field(default_factory=list)
    outcome_entities: list[str] = Field(default_factory=list)
    intervention_entities: list[str] = Field(default_factory=list)
    context_terms: list[str] = Field(default_factory=list)
    domain_routing: DomainRoutingDecision = Field(default_factory=DomainRoutingDecision)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    ambiguities: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SemanticSeedTriple(_NullableListsModel):
    triple_id: str
    subject: str
    relation: str
    object: str
    subject_type: str | None = None
    object_type: str | None = None
    purpose: str = "literature_search_planning"
    source: str = "llm_semantic_intake"
    is_evidence: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_evidence_boundary(self):
        self.is_evidence = False
        if self.source not in {"llm_semantic_intake", "deterministic_degraded_fallback", "semantic_intake_repair"}:
            self.source = "llm_semantic_intake"
        if "seed_triple_not_evidence" not in self.warnings:
            self.warnings.append("seed_triple_not_evidence")
        return self


class SemanticSearchConcept(_NullableListsModel):
    concept_id: str
    text: str
    concept_type: str = "entity"
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    source: str = "llm_semantic_intake"
    warnings: list[str] = Field(default_factory=list)


class SemanticIntakeResult(_NullableListsModel):
    research_intent: SemanticResearchIntent
    domain_routing: DomainRoutingDecision
    seed_triples: list[SemanticSeedTriple] = Field(default_factory=list)
    search_concepts: list[SemanticSearchConcept] = Field(default_factory=list)
    recommended_search_queries: list[str] = Field(default_factory=list)
    negative_filters: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    raw_llm_response_ref: str | None = None
    verified: bool = False
    verification_warnings: list[str] = Field(default_factory=list)
    semantic_mode: str = "deterministic_degraded"
    api_calls_made: int = 0

    @model_validator(mode="after")
    def align_routing(self):
        self.research_intent.domain_routing = self.domain_routing
        return self
