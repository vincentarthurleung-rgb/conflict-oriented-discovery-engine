"""LLM-backed, schema-validated search intent planning."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from code_engine.schemas.models import CODEBaseModel

PROMPT_PROFILE_ID = "semantic_search_intent_v1"
PROMPT_VERSION = "1.0"

QUERY_GROUPS = ("direct_relation", "mechanism", "context_only", "broad_recall", "validation_only")
_ALLOWED_DEFAULT = {"direct_relation": True, "mechanism": True, "context_only": False,
                    "broad_recall": False, "validation_only": False}


def resolve_search_intent_confidence(raw_intent_confidence: Any = None,
                                     semantic_intake_confidence: Any = None,
                                     seed_triple_confidence: Any = None, *,
                                     schema_valid: bool, llm_search_intent_used: bool,
                                     allowed_l1_query_count: int) -> tuple[float, str]:
    """Resolve an auditable confidence without treating successful planning as failure."""
    if not schema_valid or not llm_search_intent_used:
        return 0.0, "failed_zero"
    for value, source in ((raw_intent_confidence, "llm_response_confidence"),
                          (semantic_intake_confidence, "semantic_intake_confidence"),
                          (seed_triple_confidence, "seed_triple_confidence")):
        if isinstance(value, (int, float)) and not isinstance(value, bool) and float(value) > 0:
            return round(max(0.0, min(1.0, float(value))), 4), source
    if allowed_l1_query_count > 0:
        return 0.6, "schema_valid_guarded_default"
    return 0.0, "failed_zero"


@dataclass
class SearchIntentNormalizationResult:
    normalized: dict[str, Any]
    warnings: list[str]
    repairs: list[dict[str, Any]]

    @property
    def normalization_applied(self) -> bool:
        return bool(self.repairs)


def normalize_search_intent_response(obj: dict[str, Any]) -> SearchIntentNormalizationResult:
    """Repair bounded, auditable LLM formatting variants before strict validation."""
    if not isinstance(obj, dict):
        raise TypeError("Search intent normalization requires a dict")
    value = deepcopy(obj); repairs: list[dict[str, Any]] = []; warnings: list[str] = []

    def repair(field: str, old: Any, new: Any, reason: str) -> None:
        repairs.append({"field": field, "from": old, "to": new, "reason": reason})
        warnings.append(f"search_intent_{reason}")

    seed = value.get("seed_triple")
    if isinstance(seed, dict):
        for role in ("subject", "object"):
            entity = seed.get(role)
            if isinstance(entity, dict):
                aliases = entity.get("aliases")
                if aliases is None:
                    entity["aliases"] = []; repair(f"seed_triple.{role}.aliases", None, [], "aliases_defaulted")
                elif isinstance(aliases, str):
                    entity["aliases"] = [aliases]; repair(f"seed_triple.{role}.aliases", aliases, [aliases], "aliases_string_normalized")
                if not entity.get("type"):
                    old = entity.get("type"); entity["type"] = "unknown"
                    repair(f"seed_triple.{role}.type", old, "unknown", "entity_type_defaulted")
        context = seed.get("context")
        if isinstance(context, list):
            seed["context"] = {"terms": context}
            repair("seed_triple.context", context, seed["context"], "context_list_normalized")
        elif isinstance(context, dict) and "context_terms" in context:
            old = context.pop("context_terms")
            if "terms" not in context: context["terms"] = old
            repair("seed_triple.context.context_terms", old, context.get("terms"), "context_terms_normalized")
        relation = seed.get("relation")
        if isinstance(relation, dict):
            old = relation.get("directional")
            if not isinstance(old, bool):
                token = str(old or "").strip().casefold().replace(" → ", "->").replace("→", "->")
                true_tokens = {"true", "yes", "y", "1", "directional", "directed", "subject>object",
                               "subject->object", "subject_to_object", "drug->target"}
                false_tokens = {"false", "no", "n", "0", "none", "undirected", "non_directional", "not directional"}
                ambiguous = token in {"bidirectional", "both", "object>subject", "object->subject"}
                if token in true_tokens or ambiguous or ("->" in token and token not in false_tokens):
                    new, reason = True, "directional_string_normalized"
                    if ambiguous: warnings.append("search_intent_directionality_ambiguous_or_bidirectional")
                elif token in false_tokens:
                    new, reason = False, "directional_string_normalized"
                else:
                    family = str(relation.get("family") or relation.get("name") or "").casefold()
                    new = any(word in family for word in ("activate", "inhibit", "upregulat", "downregulat", "cause", "promot", "suppress"))
                    reason = "directional_defaulted_from_relation_family"
                relation["directional"] = new
                repair("seed_triple.relation.directional", old, new, reason)

    groups = value.get("query_groups")
    if not isinstance(groups, dict) and isinstance(value.get("queries"), list) and isinstance(seed, dict):
        subject = str(((seed.get("subject") or {}).get("name") or "")).casefold()
        object_ = str(((seed.get("object") or {}).get("name") or "")).casefold()
        if subject and object_:
            recovered = {name: [] for name in QUERY_GROUPS}
            for item in value["queries"]:
                text = str(item.get("query") if isinstance(item, dict) else item)
                recovered["direct_relation" if subject in text.casefold() and object_ in text.casefold() else "broad_recall"].append(item)
            groups = value["query_groups"] = recovered
            repair("query_groups", None, recovered, "query_groups_recovered_from_queries")
    if isinstance(groups, dict):
        for group in QUERY_GROUPS:
            items = groups.get(group)
            if items is None:
                groups[group] = []; repair(f"query_groups.{group}", None, [], "query_group_defaulted")
                continue
            if not isinstance(items, list):
                old_items = items; groups[group] = items = [items]
                repair(f"query_groups.{group}", old_items, items, "query_group_wrapped_as_list")
            normalized_items = []
            for index, item in enumerate(items):
                if isinstance(item, str):
                    old = item; item = {"query": item}
                    repair(f"query_groups.{group}.{index}", old, item, "query_string_normalized")
                if not isinstance(item, dict):
                    normalized_items.append(item); continue
                old = item.get("purpose")
                if old != group:
                    item["purpose"] = group
                    repair(f"query_groups.{group}.{index}.purpose", old, group, "purpose_normalized_from_query_group")
                old_allowed = item.get("allowed_for_l1_acquisition")
                if isinstance(old_allowed, str) and old_allowed.strip().casefold() in {"true", "false", "yes", "no", "1", "0"}:
                    new_allowed = old_allowed.strip().casefold() in {"true", "yes", "1"}
                    item["allowed_for_l1_acquisition"] = new_allowed
                    repair(f"query_groups.{group}.{index}.allowed_for_l1_acquisition", old_allowed, new_allowed, "allowed_for_l1_boolean_normalized")
                elif isinstance(old_allowed, int) and not isinstance(old_allowed, bool) and old_allowed in (0, 1):
                    item["allowed_for_l1_acquisition"] = bool(old_allowed)
                    repair(f"query_groups.{group}.{index}.allowed_for_l1_acquisition", old_allowed, bool(old_allowed), "allowed_for_l1_boolean_normalized")
                elif not isinstance(old_allowed, bool):
                    item["allowed_for_l1_acquisition"] = _ALLOWED_DEFAULT[group]
                    repair(f"query_groups.{group}.{index}.allowed_for_l1_acquisition", old_allowed, _ALLOWED_DEFAULT[group], "allowed_for_l1_defaulted_from_query_group")
                normalized_items.append(item)
            groups[group] = normalized_items
    return SearchIntentNormalizationResult(value, list(dict.fromkeys(warnings)), repairs)


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
    context_strict: bool = False
    allowed_for_context_specific_core: bool = False


class SemanticSearchIntent(CODEBaseModel):
    mode: Literal["llm", "deterministic_fallback"] = "llm"
    confidence: float = 0.0
    confidence_source: str = "failed_zero"
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
    normalization_applied: bool = False
    normalization_repair_count: int = 0
    normalization_warnings: list[str] = Field(default_factory=list)
    search_intent_schema_valid_after_normalization: bool = True

    @model_validator(mode="after")
    def normalize_groups(self):
        normalized = {}
        for group, queries in self.query_groups.items():
            normalized[group] = [item.model_copy(update={"purpose": group}) if item.purpose != group and group in IntentQuery.model_fields["purpose"].annotation.__args__ else item for item in queries]
        self.query_groups = normalized
        return self


def build_search_intent_prompt(user_query: str, domain_id: str, seed_triple: dict[str, Any],
                               paper_year_filter: dict[str, Any] | None = None,
                               pilot_profile: str | None = None, discovery_mode: bool = False) -> str:
    pilot = "Explicit ketamine pilot: ketamine and BDNF aliases may be used when grounded." if pilot_profile == "ketamine" else "No pilot-specific examples or assumptions."
    discovery = """DISCOVERY MODE: The goal is discovery-oriented retrieval, not verification of the user's stated belief.
Do not collapse a contrastive statement into one directional seed object. Use a neutral relation such as
associated_with, involved_in, modulates, has_context_dependent_role_in, participates_in, or affects.
Preserve both contrast sides as context terms. Generate multiple direction-neutral acquisition strategies:
entity/object core coverage, mechanism context, and context coverage. Map them into direct_relation and
mechanism groups under the current schema. Optional conflict hints may use context-only, but must not dominate.
Directional claims must be extracted from retrieved papers later, not asserted by acquisition queries.""" if discovery_mode else "Standard semantic search planning mode."
    return f"""You are a biomedical Search Intent Planner.
Return JSON object only. Preserve the seed subject and seed object in every L1 acquisition query.
Do not permit object-only, context-only, broad-recall, or validation-only queries for L1 acquisition.
If the user query contains disease, phenotype, tissue, cell, species, or experimental context, preserve it.
Generate both context-strict direct queries (subject + object + context aliases) and seed mechanism
background queries (subject + object; context optional). Background queries remain useful for acquisition
but are not context-specific core evidence. Never silently drop user context terms.
If relation is ambiguous, use the most conservative biomedical relation family and lower confidence.
Use only common biomedical aliases. Do not invent disease subtypes.
Output seed_triple with subject/name/aliases/type, relation/name/family/directional,
object/name/aliases/type, context/domain/terms; and query_groups named direct_relation,
mechanism, context_only, broad_recall, validation_only. Every query needs query, purpose,
must_include_subject, must_include_object, allowed_for_l1_acquisition.
seed_triple.relation.directional MUST be boolean true or false; never write "subject>object".
Query purpose MUST be exactly one of: direct_relation, mechanism, context_only, broad_recall,
validation_only. Do not put explanatory prose in purpose; use rationale or notes instead.
Domain: {domain_id}
Runtime year filter: {json.dumps(paper_year_filter or {}, sort_keys=True)}
Existing canonical seed triple: {json.dumps(seed_triple, ensure_ascii=False, sort_keys=True)}
{pilot}
{discovery}
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
                                pilot_profile: str | None = None, run_dir: str | Path | None = None,
                                discovery_mode: bool = False) -> SemanticSearchIntent:
    prompt = build_search_intent_prompt(user_query, domain_id, seed_triple, paper_year_filter, pilot_profile, discovery_mode)
    try:
        payload = llm_client.extract_json(prompt)
        raw_response = payload.get("__json_raw_response", payload) if isinstance(payload, dict) else payload
        clean_payload = {key: val for key, val in payload.items() if key != "__json_raw_response"} if isinstance(payload, dict) else payload
        result = normalize_search_intent_response(clean_payload)
        value = validate_search_intent_json(result.normalized)
    except Exception as exc:
        if run_dir is not None:
            report = {"normalization_applied": bool(locals().get("result") and result.normalization_applied),
                      "repair_count": len(result.repairs) if locals().get("result") else 0,
                      "warnings": result.warnings if locals().get("result") else [],
                      "repairs": result.repairs if locals().get("result") else [],
                      "search_intent_schema_valid_after_normalization": False}
            artifacts = Path(run_dir) / "artifacts"; artifacts.mkdir(parents=True, exist_ok=True)
            (artifacts / "search_intent_normalization_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        write_search_intent_diagnostic(run_dir, exc=exc, prompt=prompt, raw_response=locals().get("raw_response"))
        raise
    value.normalization_applied = result.normalization_applied
    value.normalization_repair_count = len(result.repairs)
    value.normalization_warnings = result.warnings
    value.warnings = list(dict.fromkeys([*value.warnings, *result.warnings]))
    value.search_intent_schema_valid_after_normalization = True
    value.confidence, value.confidence_source = resolve_search_intent_confidence(
        clean_payload.get("confidence") if isinstance(clean_payload, dict) and "confidence" in clean_payload else None,
        None, seed_triple.get("confidence") if isinstance(seed_triple, dict) else None,
        schema_valid=True, llm_search_intent_used=True, allowed_l1_query_count=0,
    )
    if run_dir is not None:
        report = {"normalization_applied": result.normalization_applied, "repair_count": len(result.repairs),
                  "warnings": result.warnings, "repairs": result.repairs,
                  "search_intent_schema_valid_after_normalization": True}
        artifacts = Path(run_dir) / "artifacts"; artifacts.mkdir(parents=True, exist_ok=True)
        (artifacts / "search_intent_normalization_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    value.planner_prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    value.planner_prompt_chars = len(prompt); value.search_intent_schema_valid = True
    value.mode = "llm"; value.llm_search_intent_used = True; value.api_calls_made = 1
    return value


__all__ = ["SearchIntentNormalizationResult", "SearchIntentValidationError", "SemanticSearchIntent", "build_search_intent_prompt", "normalize_search_intent_response", "plan_semantic_search_intent", "resolve_search_intent_confidence", "validate_search_intent_json", "write_search_intent_diagnostic"]
