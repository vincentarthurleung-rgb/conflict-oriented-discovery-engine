"""Deterministic provenance linking for mechanism edges."""

from __future__ import annotations

import hashlib

from code_engine.mechanism.models import MechanismEdge


PLANNING_SOURCES = {"llm_semantic_intake", "deterministic_degraded_fallback", "user_intent_llm_parser", "user_intent", "semantic_intake_repair"}


def _eligible(item: dict) -> bool:
    source = str(item.get("source", "")).casefold()
    return not (item.get("is_evidence") is False or source in PLANNING_SOURCES or "user_intent" in source or "seed" in source or "search" in str(item.get("purpose", "")).casefold())


def _sentence_hash(value: str) -> str:
    normalized = " ".join(str(value or "").casefold().split())
    return hashlib.sha256(normalized.encode()).hexdigest() if normalized else ""


def link_evidence_to_mechanism_edges(mechanism_edges: list[MechanismEdge], evidence_records: list[dict], l1_claims: list[dict] | None = None) -> list[MechanismEdge]:
    evidence = [item for item in evidence_records if _eligible(item)]
    claims = [item for item in (l1_claims or []) if _eligible(item)]
    by_evidence = {str(item.get("evidence_id")): item for item in evidence if item.get("evidence_id")}
    by_claim = {str(item.get("claim_id")): item for item in claims if item.get("claim_id")}
    evidence_by_sentence = {_sentence_hash(str(item.get("sentence") or item.get("quote") or item.get("evidence_sentence") or "")): item for item in evidence if _sentence_hash(str(item.get("sentence") or item.get("quote") or item.get("evidence_sentence") or ""))}
    for edge in mechanism_edges:
        exact_ids = {item for item in edge.evidence_ids if item in by_evidence}
        for claim_id in edge.claim_ids:
            claim = by_claim.get(claim_id)
            if claim and claim.get("evidence_id") in by_evidence:
                exact_ids.add(str(claim["evidence_id"]))
        for item in evidence:
            linked_observations = {str(value) for value in item.get("observation_ids", [])}
            linked_claims = {str(value) for value in item.get("claim_ids", [])}
            if linked_observations.intersection(edge.observation_ids) or linked_claims.intersection(edge.claim_ids):
                exact_ids.add(str(item.get("evidence_id")))
        for source in edge.context_slots.get("evidence_sentence", []):
            matched = evidence_by_sentence.get(_sentence_hash(str(source.get("value") or "")))
            if matched and matched.get("evidence_id"):
                exact_ids.add(str(matched["evidence_id"]))
        if exact_ids:
            edge.evidence_ids = sorted(set(edge.evidence_ids).union(exact_ids))
            continue
        paper_matches = [item for item in evidence if str(item.get("paper_id") or item.get("source_asset") or "") in edge.paper_ids]
        if paper_matches:
            edge.evidence_ids = sorted(set(edge.evidence_ids).union(str(item.get("evidence_id")) for item in paper_matches if item.get("evidence_id")))
            if "evidence_linked_by_paper_level_fallback" not in edge.warnings:
                edge.warnings.append("evidence_linked_by_paper_level_fallback")
    return mechanism_edges
