"""LLM-backed, schema-validated search intent planning."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from code_engine.schemas.models import CODEBaseModel

PROMPT_PROFILE_ID = "semantic_search_intent_v1"
PROMPT_VERSION = "1.0"


class SearchIntentValidationError(ValueError):
    def __init__(self, error_type: str, message: str, *, raw_response: Any = None, parsed_json_type: str = "dict"):
        super().__init__(message); self.error_type = error_type; self.raw_response = raw_response; self.parsed_json_type = parsed_json_type


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
    planner_prompt_chars: int = 0
    search_intent_schema_valid: bool = True
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


def validate_search_intent_json(obj: Any) -> SemanticSearchIntent:
    if not isinstance(obj, dict):
        raise SearchIntentValidationError("response_not_object", "Search intent response must be a JSON object", raw_response=obj, parsed_json_type=type(obj).__name__)
    if "seed_triple" not in obj:
        raise SearchIntentValidationError("search_intent_schema_validation_failed", "Search intent schema requires seed_triple", raw_response=obj)
    if "query_groups" not in obj or not isinstance(obj.get("query_groups"), dict):
        raise SearchIntentValidationError("search_intent_schema_validation_failed", "Search intent schema requires query_groups object", raw_response=obj)
    try:
        return SemanticSearchIntent.model_validate({key: value for key, value in obj.items() if not key.startswith("__")})
    except Exception as exc:
        raise SearchIntentValidationError("search_intent_schema_validation_failed", f"Search intent schema validation failed: {exc}", raw_response=obj) from exc


def _redact(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    text = re.sub(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s\"']+", r"\1[REDACTED]", text)
    text = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "[REDACTED]", text)
    return text


def write_search_intent_diagnostic(run_dir: str | Path | None, *, exc: Exception, prompt: str,
                                   raw_response: Any = None, fallback_used: bool = False,
                                   provider: str | None = None, model: str | None = None) -> dict[str, Any]:
    raw = raw_response if raw_response is not None else getattr(exc, "raw_response", None)
    record = {"stage": "semantic_search_intent", "provider": provider or getattr(exc, "provider", None),
              "model": model or getattr(exc, "model", None), "error_type": getattr(exc, "error_type", "search_intent_schema_validation_failed"),
              "error_message": str(exc)[:1000], "parsed_json_type": getattr(exc, "parsed_json_type", "unknown"),
              "raw_response_excerpt": _redact(raw)[:1000] if raw is not None else "", "raw_response_path": "",
              "prompt_hash": hashlib.sha256(prompt.encode()).hexdigest(), "prompt_chars": len(prompt),
              "recoverable": False, "fallback_used": fallback_used, "timestamp": datetime.now(timezone.utc).isoformat()}
    if run_dir is not None:
        artifacts = Path(run_dir) / "artifacts"; raw_dir = artifacts / "search_intent_raw_responses"
        artifacts.mkdir(parents=True, exist_ok=True); raw_dir.mkdir(parents=True, exist_ok=True)
        raw_path = raw_dir / f"semantic_search_intent_{record['prompt_hash'][:12]}.txt"
        raw_path.write_text(_redact(raw) if raw is not None else "", encoding="utf-8"); record["raw_response_path"] = str(raw_path)
        with (artifacts / "search_intent_parse_errors.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def plan_semantic_search_intent(user_query: str, *, domain_id: str, seed_triple: dict[str, Any],
                                llm_client: Any, paper_year_filter: dict[str, Any] | None = None,
                                pilot_profile: str | None = None, run_dir: str | Path | None = None) -> SemanticSearchIntent:
    prompt = build_search_intent_prompt(user_query, domain_id, seed_triple, paper_year_filter, pilot_profile)
    try:
        payload = llm_client.extract_json(prompt)
        raw_response = payload.pop("__json_raw_response", payload) if isinstance(payload, dict) else payload
        value = validate_search_intent_json(payload)
    except Exception as exc:
        write_search_intent_diagnostic(run_dir, exc=exc, prompt=prompt, raw_response=locals().get("raw_response"))
        raise
    value.planner_prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    value.planner_prompt_chars = len(prompt); value.search_intent_schema_valid = True
    value.mode = "llm"; value.llm_search_intent_used = True; value.api_calls_made = 1
    return value


__all__ = ["SearchIntentValidationError", "SemanticSearchIntent", "build_search_intent_prompt", "plan_semantic_search_intent", "validate_search_intent_json", "write_search_intent_diagnostic"]
