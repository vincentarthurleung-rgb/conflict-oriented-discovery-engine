"""LLM-assisted or deterministic natural-language research intake."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import Field

from code_engine.query.intent import ResearchIntent, parse_research_intent
from code_engine.query.seed_triples import SeedResearchTriple, build_seed_triples
from code_engine.schemas.models import CODEBaseModel


INTAKE_SYSTEM_PROMPT = """Parse the research request into JSON with keys:
research_intent, seed_triples, search_concepts, recommended_domains,
negative_filters, ambiguities. Seed triples are planning hypotheses only and
must never be labeled as paper evidence."""


class JSONExtractionClient(Protocol):
    def extract_json(self, prompt: str, **kwargs: Any) -> dict[str, Any]: ...


class ResearchIntakeResult(CODEBaseModel):
    research_intent: ResearchIntent
    seed_triples: list[SeedResearchTriple] = Field(default_factory=list)
    search_concepts: list[str] = Field(default_factory=list)
    recommended_domains: list[str] = Field(default_factory=list)
    negative_filters: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    parser_mode: str = "deterministic_fallback"
    api_calls_made: int = 0


def parse_research_intake(
    raw_query: str,
    *,
    llm_client: JSONExtractionClient | None = None,
    use_api: bool = False,
) -> ResearchIntakeResult:
    fallback = parse_research_intent(raw_query)
    if not use_api or llm_client is None:
        concepts = list(dict.fromkeys(
            fallback.primary_entities + fallback.secondary_entities
            + fallback.mechanism_entities + fallback.outcome_entities
            + ([fallback.disease_or_condition] if fallback.disease_or_condition else [])
        ))
        return ResearchIntakeResult(
            research_intent=fallback,
            seed_triples=build_seed_triples(fallback),
            search_concepts=concepts,
            recommended_domains=[fallback.domain_id],
            negative_filters=["editorial", "retracted publication"],
        )
    payload = llm_client.extract_json(f"{INTAKE_SYSTEM_PROMPT}\nUser request: {raw_query}")
    intent_data = {**fallback.model_dump(), **dict(payload.get("research_intent") or {})}
    intent = ResearchIntent.model_validate(intent_data)
    seeds = [SeedResearchTriple.model_validate(item) for item in payload.get("seed_triples", [])]
    if not seeds:
        seeds = build_seed_triples(intent)
    return ResearchIntakeResult(
        research_intent=intent,
        seed_triples=seeds,
        search_concepts=list(payload.get("search_concepts") or []),
        recommended_domains=list(payload.get("recommended_domains") or [intent.domain_id]),
        negative_filters=list(payload.get("negative_filters") or []),
        ambiguities=list(payload.get("ambiguities") or []),
        parser_mode="llm_assisted",
        api_calls_made=1,
    )
