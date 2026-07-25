"""Deterministic comparator candidate graph and immutable link recovery."""
from __future__ import annotations

import re
from typing import Any

from .identities import core_identity


def _norm(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().casefold())


def recover_comparator(
    result: dict[str, Any], factors: list[dict[str, Any]],
    semantics: dict[str, Any], evidence_texts: list[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Authorize exact evidence only when phrase, factor and syntax are unique."""
    edges: list[dict[str, Any]] = []
    texts = [_norm(text) for text in evidence_texts if text]
    for factor in factors:
        phrase = _norm(factor.get("raw_text") or factor.get("extracted_value"))
        exact = bool(phrase) and any(
            re.search(rf"\b(?:versus|vs\.?|compared (?:to|with)|relative to|than)\s+(?:the\s+)?{re.escape(phrase)}\b", text)
            for text in texts
        )
        edge = {
            "result_identity": result["identity"],
            "candidate_factor_identity": factor["identity"],
            "direct_ref_evidence": [],
            "nested_structure_evidence": [],
            "exact_text_evidence": [phrase] if exact else [],
            "evidence_anchor_refs": list(result.get("evidence_anchor_ids", [])),
            "negative_evidence": [],
            "competing_candidate_count": 0,
            "deterministic_uniqueness": False,
            "candidate_authority": "candidate_non_authoritative" if exact else "rejected",
            "diagnostic_score": 1 if exact else 0,
            "schema_version": "comparative_link_candidate_edge_v1",
        }
        edge["edge_identity"] = core_identity("comparative_link_candidate_edge_v1", edge)
        edges.append(edge)
    matches = [edge for edge in edges if edge["exact_text_evidence"]]
    for edge in edges:
        edge["competing_candidate_count"] = len(matches)
        edge["deterministic_uniqueness"] = len(matches) == 1 and bool(edge["exact_text_evidence"])
        if edge["deterministic_uniqueness"]:
            edge["candidate_authority"] = "deterministic_exact_evidence_reference"
    existing = list(result.get("comparison_factor_refs", []))
    baseline = result.get("baseline_ref")
    if existing or baseline:
        authority, recovered_ref, status = "direct_structured_reference", (existing or [baseline])[0], "already_complete"
    elif semantics["comparison_required"] is False:
        authority, recovered_ref, status = "unresolved", None, "not_required_by_semantics"
    elif len(matches) == 1:
        authority = "deterministic_exact_evidence_reference"
        recovered_ref, status = matches[0]["candidate_factor_identity"], "recovered"
    else:
        authority, recovered_ref, status = "unresolved", None, "unresolved"
    recovery = {
        "result_identity": result["identity"],
        "comparison_semantics_identity": semantics["identity"],
        "pre_recovery_missing": not bool(existing or baseline),
        "recovered_comparator_factor_ref": recovered_ref,
        "comparator_link_authority": authority,
        "recovery_status": status,
        "candidate_edge_refs": [edge["edge_identity"] for edge in edges],
        "creates_new_link_revision": status == "recovered",
        "historical_content_unchanged": True,
        "provenance": result["provenance"],
        "schema_version": "comparative_result_link_recovery_v1",
    }
    recovery["identity"] = core_identity("comparative_result_link_recovery_v1", recovery)
    return sorted(edges, key=lambda row: row["edge_identity"]), recovery
