"""LLM-first semantic intake orchestration."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from code_engine.domain.models import DomainProfile
from code_engine.encoder.fallback import deterministic_degraded_intake
from code_engine.encoder.models import SemanticIntakeRequest, SemanticIntakeResult
from code_engine.encoder.prompts import build_semantic_intake_prompt
from code_engine.encoder.repair import repair_json_response
from code_engine.encoder.scientific_encoder import create_default_scientific_encoder_client
from code_engine.encoder.semantic_verifier import verify_semantic_intake_result


def _profile_summary(profile: DomainProfile) -> dict[str, Any]:
    return {
        "domain_id": profile.domain_id, "subdomain_id": profile.subdomain_id,
        "profile_id": profile.profile_id, "display_name": profile.display_name,
        "description": profile.description, "key_entity_types": list(profile.key_entity_types),
        "key_relation_types": list(profile.key_relation_types), "key_evidence_types": list(profile.key_evidence_types),
    }


def _upgrade_legacy_intake_payload(payload: dict[str, Any], query: str, profiles: dict[str, DomainProfile]) -> dict[str, Any]:
    """Accept the pre-semantic intake client contract at the API boundary only."""

    intent = dict(payload.get("research_intent") or {})
    if "domain_routing" in payload and "raw_user_input" in intent:
        return payload
    from code_engine.domain.router import DomainRouter
    profile = DomainRouter(list(profiles.values())).route_deterministic_fallback(query)
    confidence = float(intent.get("confidence", 0.7))
    routing = {"domain_id": profile.domain_id, "subdomain_id": profile.subdomain_id, "domain_profile_id": profile.profile_id, "confidence": confidence, "alternative_domains": [], "reasoning_summary": "Legacy client payload adapted at compatibility boundary.", "ambiguities": [], "warnings": ["legacy_intake_payload_adapted"], "requires_manual_review": confidence < 0.6}
    concepts = payload.get("search_concepts") or []
    return {
        "research_intent": {"raw_user_input": query, "language": "zh" if any("\u4e00" <= char <= "\u9fff" for char in query) else "en", "task_type": intent.get("task_type", "unknown"), "research_goal": intent.get("research_goal", "semantic encoding"), "primary_entities": intent.get("primary_entities", concepts[:1]), "secondary_entities": intent.get("secondary_entities", concepts[1:]), "disease_or_condition": intent.get("disease_or_condition", []), "mechanism_entities": intent.get("mechanism_entities", []), "comparison_entities": intent.get("comparison_entities", []), "outcome_entities": intent.get("outcome_entities", []), "intervention_entities": intent.get("intervention_entities", []), "context_terms": intent.get("context_terms", []), "domain_routing": routing, "confidence": confidence, "ambiguities": [], "warnings": ["legacy_intake_payload_adapted"]},
        "domain_routing": routing,
        "seed_triples": payload.get("seed_triples", []),
        "search_concepts": [{"concept_id": f"legacy-{index}", "text": item if isinstance(item, str) else item.get("text", ""), "concept_type": "entity", "importance": 0.5} for index, item in enumerate(concepts)],
        "recommended_search_queries": payload.get("recommended_search_queries", []),
        "negative_filters": payload.get("negative_filters", []), "ambiguities": payload.get("ambiguities", []),
        "warnings": ["legacy_intake_payload_adapted"], "verified": False,
    }


def run_semantic_intake(
    query: str, domain_profiles: list[DomainProfile], api: bool = False, execute: bool = False,
    model_name: str | None = None, fallback_mode: str = "deterministic_degraded",
    *, llm_client: Any | None = None,
) -> SemanticIntakeResult:
    profiles = {profile.domain_id: profile for profile in domain_profiles}
    allowed = set(profiles)
    if not (execute and api):
        if fallback_mode != "deterministic_degraded":
            raise ValueError(f"Unsupported fallback_mode: {fallback_mode}")
        return verify_semantic_intake_result(deterministic_degraded_intake(query, allowed), allowed, profiles)
    injected_client = llm_client is not None
    client = llm_client or create_default_scientific_encoder_client()
    api_call_cost = int(getattr(client, "api_call_cost", 0 if injected_client else 1))
    request = SemanticIntakeRequest(query=query, available_domain_profiles=[_profile_summary(profile) for profile in domain_profiles], allowed_domain_ids=sorted(allowed), mode="execute", api_enabled=True, model_name=model_name)
    try:
        raw = client.extract_json(build_semantic_intake_prompt(request), **({"model": model_name} if model_name else {}))
    except Exception as exc:
        result = deterministic_degraded_intake(query, allowed)
        result.warnings.extend([f"LLM semantic intake failed; deterministic fallback used: {type(exc).__name__}"])
        result.api_calls_made = api_call_cost
        return verify_semantic_intake_result(result, allowed, profiles)
    payload, repair_calls, repair_warnings = repair_json_response(raw, client=client, execute=True, api=True)
    if payload is None:
        result = deterministic_degraded_intake(query, allowed)
        result.warnings.extend(repair_warnings + ["LLM semantic intake failed; deterministic fallback used."])
        result.api_calls_made = api_call_cost * (1 + repair_calls)
        return verify_semantic_intake_result(result, allowed, profiles)
    payload = _upgrade_legacy_intake_payload(payload, query, profiles)
    try:
        result = SemanticIntakeResult.model_validate(payload)
    except ValidationError as exc:
        result = deterministic_degraded_intake(query, allowed)
        result.warnings.extend(["LLM semantic intake schema invalid; deterministic fallback used.", str(exc)])
        result.api_calls_made = api_call_cost * (1 + repair_calls)
        return verify_semantic_intake_result(result, allowed, profiles)
    result.research_intent.raw_user_input = query
    result.semantic_mode = "llm_semantic"
    result.api_calls_made = api_call_cost * (1 + repair_calls)
    result.verification_warnings.extend(repair_warnings)
    return verify_semantic_intake_result(result, allowed, profiles)
