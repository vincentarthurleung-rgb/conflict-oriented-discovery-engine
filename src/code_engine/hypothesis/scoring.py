"""Deterministic pre-validation scoring for run-scoped hypotheses."""

from __future__ import annotations

from typing import Any


def _unit(value: Any, default: float = 0.0) -> float:
    default = 0.0 if default is None else float(default)
    try:
        return round(max(0.0, min(1.0, float(value))), 6)
    except (TypeError, ValueError):
        return default


def score_hypothesis_candidate(candidate: dict) -> dict:
    components = dict(candidate.get("confidence_components") or {})
    source_scope = str(candidate.get("source_scope") or "unknown")
    kind = str(candidate.get("candidate_type") or candidate.get("hypothesis_type") or "")
    evidence_strength = _unit(components.get("evidence_strength"), 0.9 if source_scope == "full_text" else 0.35)
    conflict_strength = _unit(components.get("conflict_strength"), candidate.get("fulltext_entropy") if candidate.get("fulltext_entropy") is not None else candidate.get("abstract_entropy", 0.0))
    context_separability = _unit(components.get("context_separability"), 0.8 if kind == "context_partition_hypothesis" else 0.35)
    mechanism_specificity = _unit(components.get("mechanism_specificity"), candidate.get("mechanism_specificity", 0.0))
    novelty_hint = _unit(components.get("novelty_hint"), 0.45 if kind == "context_partition_hypothesis" else 0.6)
    feasibility = _unit(components.get("feasibility"), 0.7 if candidate.get("linked_evidence_ids") else 0.45)
    validation_readiness = _unit(components.get("validation_readiness"), 0.75 if candidate.get("validation_requirements") else 0.45)
    coverage_penalty = 0.22 if kind == "coverage_gap_hypothesis" else _unit(components.get("coverage_penalty"), 0.0)
    abstract_only_penalty = 0.18 if source_scope == "abstract" else _unit(components.get("abstract_only_penalty"), 0.0)
    manual_review_penalty = 0.08 if candidate.get("requires_manual_review") else _unit(components.get("manual_review_penalty"), 0.0)
    overall = (
        0.22 * evidence_strength + 0.22 * conflict_strength + 0.18 * context_separability
        + 0.16 * mechanism_specificity + 0.08 * novelty_hint + 0.08 * feasibility
        + 0.06 * validation_readiness - coverage_penalty - abstract_only_penalty
        - manual_review_penalty
    )
    scored = {
        "evidence_strength": evidence_strength, "conflict_strength": conflict_strength,
        "context_separability": context_separability, "mechanism_specificity": mechanism_specificity,
        "novelty_hint": novelty_hint, "feasibility": feasibility,
        "validation_readiness": validation_readiness, "coverage_penalty": coverage_penalty,
        "abstract_only_penalty": abstract_only_penalty, "manual_review_penalty": manual_review_penalty,
    }
    return {**candidate, "score_components": scored, "confidence": round((evidence_strength + conflict_strength + mechanism_specificity) / 3, 6), "novelty_score": novelty_hint, "feasibility_score": feasibility, "evidence_strength": evidence_strength, "conflict_strength": conflict_strength, "context_specificity": context_separability, "mechanism_specificity": mechanism_specificity, "overall_score": round(max(0.0, min(1.0, overall)), 6)}


def implementation_status() -> str:
    return "run_scoped_deterministic"


__all__ = ["score_hypothesis_candidate", "implementation_status"]
