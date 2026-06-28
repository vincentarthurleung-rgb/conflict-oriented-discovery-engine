"""Non-semantic validation of Scientific Encoder output."""

from __future__ import annotations

import re

from code_engine.domain.models import DomainProfile
from code_engine.encoder.models import SemanticIntakeResult


INJECTION_FRAGMENTS = ("ignore previous", "system prompt", "developer message", "<script", "drop table")


def sanitize_semantic_query(value: str) -> tuple[str, list[str]]:
    raw = " ".join(str(value or "").split())
    if not raw or any(fragment in raw.casefold() for fragment in INJECTION_FRAGMENTS):
        return "", ["unsafe_or_empty_query_removed"]
    clean = re.sub(r"[^\w\s()\[\]\"'*,.+:/-]", " ", raw, flags=re.UNICODE)
    clean = " ".join(clean.split())[:500]
    return clean, (["query_sanitized"] if clean != raw or len(raw) > 500 else [])


def verify_semantic_intake_result(result: SemanticIntakeResult, allowed_domain_ids: set[str], domain_profiles: dict[str, DomainProfile]) -> SemanticIntakeResult:
    warnings = list(result.verification_warnings)
    routing = result.domain_routing
    if routing.domain_id not in allowed_domain_ids or routing.domain_id not in domain_profiles:
        routing.domain_id = "general_biomedical"
        routing.domain_profile_id = "general_biomedical"
        routing.subdomain_id = None
        routing.confidence = min(routing.confidence, 0.5)
        warnings.append("invalid_domain_id_downgraded_to_general_biomedical")
    else:
        profile = domain_profiles[routing.domain_id]
        routing.domain_profile_id = profile.profile_id
        routing.subdomain_id = profile.subdomain_id
    routing.confidence = max(0.0, min(1.0, float(routing.confidence or 0.0)))
    result.research_intent.confidence = max(0.0, min(1.0, float(result.research_intent.confidence or 0.0)))
    if min(routing.confidence, result.research_intent.confidence) < 0.6:
        routing.requires_manual_review = True
        warnings.append("semantic_confidence_below_review_threshold")
    for triple in result.seed_triples:
        triple.is_evidence = False
        if triple.source not in {"llm_semantic_intake", "deterministic_degraded_fallback", "semantic_intake_repair"}:
            triple.source = "llm_semantic_intake"
            warnings.append("seed_triple_source_repaired_to_planning_source")
    sanitized, seen = [], set()
    for query in result.recommended_search_queries:
        clean, query_warnings = sanitize_semantic_query(query)
        warnings.extend(query_warnings)
        if clean and clean.casefold() not in seen:
            sanitized.append(clean)
            seen.add(clean.casefold())
    result.recommended_search_queries = sanitized
    result.domain_routing = routing
    result.research_intent.domain_routing = routing
    result.verified = True
    result.verification_warnings = list(dict.fromkeys(warnings))
    return result
