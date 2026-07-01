"""LLM-backed, schema-validated search intent planning."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import Field, model_validator

from code_engine.schemas.models import CODEBaseModel

PROMPT_PROFILE_ID = "semantic_search_intent_v1"
PROMPT_VERSION = "1.0"


class SearchEntity(CODEBaseModel):
    name: str
    aliases: list[str] = Field(default_factory=list)
    type: str = "unknown"

    @model_validator(mode="after")
    def include_name(self):
        self.aliases = list(dict.fromkeys([self.name, *self.aliases]))
        return self


class SearchRelation(CODEBaseModel):
    name: str
    family: str = "unknown"
    directional: bool = False


class SearchContext(CODEBaseModel):
    domain: str = "general_biomedical"
    terms: list[str] = Field(default_factory=list)


class SearchSeedTriple(CODEBaseModel):
    subject: SearchEntity
    relation: SearchRelation
    object: SearchEntity
    context: SearchContext = Field(default_factory=SearchContext)


class IntentQuery(CODEBaseModel):
    query: str
    purpose: Literal["direct_relation", "mechanism", "context_only", "broad_recall", "validation_only"] = "direct_relation"
    must_include_subject: bool = True
    must_include_object: bool = True
    allowed_for_l1_acquisition: bool = False


class SemanticSearchIntent(CODEBaseModel):
    mode: Literal["llm", "deterministic_fallback"] = "llm"
    confidence: float = 0.0
    manual_review_required: bool = False
    seed_triple: SearchSeedTriple
    query_groups: dict[str, list[IntentQuery]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    planner_prompt_profile_id: str = PROMPT_PROFILE_ID
    planner_prompt_version: str = PROMPT_VERSION
    planner_prompt_hash: str = ""
    llm_search_intent_used: bool = True
    deterministic_search_fallback_used: bool = False
    allow_deterministic_search_fallback: bool = False
    real_api_run_with_uncertain_search_intent: bool = False
    api_calls_made: int = 0

    @model_validator(mode="after")
    def normalize_groups(self):
        normalized = {}
        for group, queries in self.query_groups.items():
            normalized[group] = [item.model_copy(update={"purpose": group}) if item.purpose != group and group in IntentQuery.model_fields["purpose"].annotation.__args__ else item for item in queries]
        self.query_groups = normalized
        return self


def build_search_intent_prompt(user_query: str, domain_id: str, seed_triple: dict[str, Any],
                               paper_year_filter: dict[str, Any] | None = None,
                               pilot_profile: str | None = None) -> str:
    pilot = "Explicit ketamine pilot: ketamine and BDNF aliases may be used when grounded." if pilot_profile == "ketamine" else "No pilot-specific examples or assumptions."
    return f"""You are a biomedical Search Intent Planner.
Return one JSON object only. Preserve the seed subject and seed object in every L1 acquisition query.
Do not permit object-only, context-only, broad-recall, or validation-only queries for L1 acquisition.
If relation is ambiguous, use the most conservative biomedical relation family and lower confidence.
Use only common biomedical aliases. Do not invent disease subtypes.
Output seed_triple with subject/name/aliases/type, relation/name/family/directional,
object/name/aliases/type, context/domain/terms; and query_groups named direct_relation,
mechanism, context_only, broad_recall, validation_only. Every query needs query, purpose,
must_include_subject, must_include_object, allowed_for_l1_acquisition.
Domain: {domain_id}
Runtime year filter: {json.dumps(paper_year_filter or {}, sort_keys=True)}
Existing canonical seed triple: {json.dumps(seed_triple, ensure_ascii=False, sort_keys=True)}
{pilot}
User query: {user_query}"""


def plan_semantic_search_intent(user_query: str, *, domain_id: str, seed_triple: dict[str, Any],
                                llm_client: Any, paper_year_filter: dict[str, Any] | None = None,
                                pilot_profile: str | None = None) -> SemanticSearchIntent:
    prompt = build_search_intent_prompt(user_query, domain_id, seed_triple, paper_year_filter, pilot_profile)
    payload = llm_client.extract_json(prompt)
    value = SemanticSearchIntent.model_validate(payload)
    value.planner_prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    value.mode = "llm"; value.llm_search_intent_used = True; value.api_calls_made = 1
    return value


__all__ = ["SemanticSearchIntent", "build_search_intent_prompt", "plan_semantic_search_intent"]
