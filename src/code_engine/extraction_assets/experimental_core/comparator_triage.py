"""Deterministic comparator triage over authoritative source text."""
from __future__ import annotations

import re
from typing import Any

from .identities import core_identity
from .source_authority import source_not_reported_allowed

COMPARISON_PATTERNS = (
    r"\bcompared\s+(?:with|to)\s+(?P<term>[^,.;:]+)",
    r"\b(?:versus|vs\.?|against|relative\s+to)\s+(?P<term>[^,.;:]+)",
    r"\bfrom\s+(?P<term>baseline)\b",
    r"\bafter\s+(?:versus|vs\.?|compared\s+(?:with|to))\s+(?P<term>before)\b",
)
NEGATED_COMPARISON = re.compile(r"\b(?:not|neither|without)\b.{0,24}\b(?:compared|versus|vs\.?)\b", re.I)


def _factor_text(factor: dict[str, Any]) -> str:
    return str(
        factor.get("raw_text") or factor.get("extracted_value")
        or factor.get("canonical_value") or ""
    ).strip()


def resolve_comparator(
    *,
    result: dict[str, Any],
    factors: list[dict[str, Any]],
    source_texts: list[str],
    scope_audit: dict[str, Any],
    comparison_semantics: dict[str, Any],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    """Resolve only exact, unique, non-negated comparator phrases."""
    direct = sorted(set(result.get("comparison_factor_refs", [])))
    status = "unresolved"
    resolved: list[str] = []
    match_spans: list[dict[str, Any]] = []
    candidates: set[str] = set()
    rule = "comparator_source_resolution_exact_phrase_v1"
    if direct:
        status, resolved, rule = "deterministically_resolved", direct, "explicit_result_comparator_ref_v1"
    else:
        for text_index, text in enumerate(source_texts):
            if NEGATED_COMPARISON.search(text):
                continue
            for pattern in COMPARISON_PATTERNS:
                for match in re.finditer(pattern, text, re.I):
                    phrase = match.group("term").strip()
                    matched_here = []
                    for factor in factors:
                        factor_text = _factor_text(factor)
                        if factor_text and re.search(
                            rf"(?<!\w){re.escape(factor_text)}(?!\w)", phrase, re.I
                        ):
                            matched_here.append(factor["identity"])
                    candidates.update(matched_here)
                    match_spans.append({
                        "text_index": text_index, "char_start": match.start(),
                        "char_end": match.end(), "matched_text": match.group(0),
                        "candidate_factor_ids": sorted(matched_here),
                    })
        if len(candidates) == 1 and match_spans and comparison_semantics.get("comparison_required") is True:
            status, resolved = "deterministically_resolved", sorted(candidates)
        elif len(candidates) > 1 or (match_spans and not candidates):
            status = "annotation_required"
        elif not source_not_reported_allowed(scope_audit):
            status = "source_scope_insufficient"
        elif comparison_semantics.get("comparison_required") is True:
            status = "source_not_reported"
        else:
            status = "rejected"
    payload = {
        "result_identity": result["identity"],
        "resolution_status": status,
        "resolved_comparator_factor_refs": resolved,
        "candidate_factor_refs": sorted(candidates),
        "competing_candidate_count": len(candidates),
        "exact_match_spans": match_spans,
        "deterministic_rule_identity": rule,
        "comparison_semantics_identity": comparison_semantics.get("identity"),
        "source_scope_identity": scope_audit["identity"],
        "creates_scientific_link": status == "deterministically_resolved",
        "annotation_candidate_has_authority": False,
        "provider_candidate": False,
        "provider_reextraction_required": False,
        "automatic_execution_authorized": False,
        "provider_call_authorized": False,
        "network_call_authorized": False,
        "budget_authorization_present": False,
        "provenance": provenance,
        "schema_version": "source_grounded_comparator_resolution_v2",
    }
    payload["identity"] = core_identity(
        "source_grounded_comparator_resolution_v2",
        {k: v for k, v in payload.items() if k != "provenance"},
    )
    return payload
