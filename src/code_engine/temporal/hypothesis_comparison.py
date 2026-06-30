"""Rule-based comparison of retained hypotheses with later evidence."""

from __future__ import annotations

from typing import Any

QUESTION = "该系统假设是否只是复述了后续证据趋势，还是提出了新的可实验验证机制？"


def _values(item: dict[str, Any], *names: str) -> set[str]:
    result: set[str] = set()
    for name in names:
        value = item.get(name)
        if isinstance(value, list):
            result.update(str(x) for x in value if x not in (None, ""))
        elif value not in (None, ""):
            result.add(str(value))
    return result


def hypothesis_matches_conflict(hypothesis: dict[str, Any], conflict: dict[str, Any]) -> bool:
    conflict_ids = {str(conflict.get("conflict_id")), str(conflict.get("candidate_id")), str(conflict.get("abstract_conflict_candidate_id"))} - {"None", ""}
    if conflict_ids & _values(hypothesis, "linked_conflict_ids", "linked_fulltext_confirmation_ids"):
        return True
    hs = str(hypothesis.get("subject_canonical_id") or hypothesis.get("subject_id") or "")
    ho = str(hypothesis.get("object_canonical_id") or hypothesis.get("object_id") or "")
    return bool(hs and ho and hs == str(conflict.get("subject_canonical_id") or "") and ho == str(conflict.get("object_canonical_id") or ""))


def compare_hypothesis_to_later_evidence(hypothesis: dict[str, Any], later: list[dict[str, Any]],
                                         dominant_direction: str | None) -> dict[str, Any]:
    h_direction = str(hypothesis.get("direction") or hypothesis.get("predicted_direction") or "unknown").casefold()
    h_context = _values(hypothesis, "context_variables", "context", "conditions")
    h_edges = _values(hypothesis, "linked_mechanism_edge_ids")
    h_paths = _values(hypothesis, "linked_mechanism_path_ids")
    later_context = set().union(*(_values(item, "context_variables", "context_slots", "context") for item in later)) if later else set()
    later_edges = set().union(*(_values(item, "linked_mechanism_edge_ids", "mechanism_edges") for item in later)) if later else set()
    later_paths = set().union(*(_values(item, "linked_mechanism_path_ids") for item in later)) if later else set()
    overlaps = []
    differences = []
    if not later:
        comparison = "no_later_evidence_to_compare"
    elif dominant_direction and h_direction not in {"", "unknown", "none"} and h_direction != dominant_direction:
        comparison = "diverges_from_later_evidence"
        differences.append(f"hypothesis_direction={h_direction};later_dominant_direction={dominant_direction}")
    else:
        if dominant_direction and h_direction == dominant_direction:
            overlaps.append("direction")
        if h_context & later_context:
            overlaps.append("context")
        if (h_edges & later_edges) or (h_paths & later_paths):
            overlaps.append("mechanism")
        unexplained_mechanism = bool((h_edges - later_edges) or (h_paths - later_paths))
        if unexplained_mechanism and overlaps:
            comparison = "extends_later_evidence"
            differences.append("hypothesis_contains_additional_mechanism")
        elif len(overlaps) >= 2:
            comparison = "covered_by_later_evidence"
        elif overlaps:
            comparison = "partially_covered_by_later_evidence"
        elif h_edges or h_paths:
            comparison = "extends_later_evidence"
            differences.append("later_evidence_does_not_cover_hypothesized_mechanism")
        else:
            comparison = "uncertain_comparison"
    return {
        "hypothesis_id": hypothesis.get("hypothesis_id") or hypothesis.get("candidate_id"),
        "hypothesis_type": hypothesis.get("hypothesis_type") or hypothesis.get("type"),
        "hypothesis_text": hypothesis.get("hypothesis_text") or hypothesis.get("text") or hypothesis.get("description"),
        "overall_score": hypothesis.get("overall_score") or hypothesis.get("score"),
        "linked_dois": list(hypothesis.get("linked_dois") or []),
        "linked_titles": list(hypothesis.get("linked_titles") or []),
        "linked_journals": list(hypothesis.get("linked_journals") or []),
        "linked_evidence_ids": list(hypothesis.get("linked_evidence_ids") or []),
        "linked_mechanism_edge_ids": sorted(h_edges), "linked_mechanism_path_ids": sorted(h_paths),
        "comparison_to_later_evidence": comparison,
        "overlap_with_later_evidence": overlaps,
        "difference_from_later_evidence": differences,
        "still_requires_validation": True, "human_review_question": QUESTION,
    }


def compare_hypotheses(conflict: dict[str, Any], hypotheses: list[dict[str, Any]], later: list[dict[str, Any]], dominant: str | None) -> list[dict[str, Any]]:
    return [compare_hypothesis_to_later_evidence(h, later, dominant) for h in hypotheses if hypothesis_matches_conflict(h, conflict)]
