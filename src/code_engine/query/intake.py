"""LLM-assisted or deterministic natural-language research intake."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import Field

from code_engine.encoder.models import SemanticSearchConcept, SemanticSeedTriple
from code_engine.encoder.semantic_intake import run_semantic_intake
from code_engine.query.intent import ResearchIntent, research_intent_from_semantic
from code_engine.domain.models import default_domain_profiles
from code_engine.schemas.models import CODEBaseModel


INTAKE_SYSTEM_PROMPT = """Parse the research request into JSON with keys:
research_intent, seed_triples, search_concepts, recommended_domains,
negative_filters, ambiguities. Seed triples are planning hypotheses only and
must never be labeled as paper evidence."""


class JSONExtractionClient(Protocol):
    def extract_json(self, prompt: str, **kwargs: Any) -> dict[str, Any]: ...


class ResearchIntakeResult(CODEBaseModel):
    research_intent: ResearchIntent
    seed_triples: list[SemanticSeedTriple] = Field(default_factory=list)
    search_concepts: list[str] = Field(default_factory=list)
    recommended_domains: list[str] = Field(default_factory=list)
    negative_filters: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    parser_mode: str = "deterministic_fallback"
    api_calls_made: int = 0
    semantic_mode: str = "deterministic_degraded"
    semantic_confidence: float = 0.0
    requires_manual_review: bool = True
    semantic_warnings: list[str] = Field(default_factory=list)
    recommended_search_queries: list[str] = Field(default_factory=list)
    semantic_search_concepts: list[SemanticSearchConcept] = Field(default_factory=list)
    semantic_intake: dict[str, Any] = Field(default_factory=dict)
    unified_seed_triple: dict[str, Any] = Field(default_factory=dict)


def parse_research_intake(
    raw_query: str,
    *,
    llm_client: JSONExtractionClient | None = None,
    use_api: bool = False,
    execute: bool | None = None,
    model_name: str | None = None,
) -> ResearchIntakeResult:
    # ``execute=None`` preserves the old direct-test client injection contract;
    # workflow callers always pass an explicit execution decision.
    active_execute = bool(use_api and llm_client is not None) if execute is None else execute
    semantic = run_semantic_intake(raw_query, default_domain_profiles(), api=use_api, execute=active_execute, model_name=model_name, llm_client=llm_client)
    intent = research_intent_from_semantic(semantic.research_intent)
    return ResearchIntakeResult(
        research_intent=intent, seed_triples=semantic.seed_triples,
        search_concepts=[item.text for item in semantic.search_concepts],
        recommended_domains=[semantic.domain_routing.domain_id], negative_filters=semantic.negative_filters,
        ambiguities=semantic.ambiguities, parser_mode="llm_assisted" if semantic.semantic_mode == "llm_semantic" else "deterministic_fallback",
        api_calls_made=semantic.api_calls_made, semantic_mode=semantic.semantic_mode,
        semantic_confidence=min(semantic.research_intent.confidence, semantic.domain_routing.confidence),
        requires_manual_review=semantic.domain_routing.requires_manual_review,
        semantic_warnings=list(dict.fromkeys(semantic.warnings + semantic.verification_warnings)),
        recommended_search_queries=semantic.recommended_search_queries,
        semantic_search_concepts=semantic.search_concepts, semantic_intake=semantic.model_dump(),
    )
