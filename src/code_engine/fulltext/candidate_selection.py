from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from code_engine.fulltext.candidate_bridge import canonical_fulltext_candidates


@dataclass(frozen=True)
class FulltextSelectionPolicy:
    fulltext_min_relevance_score: float = 0.65
    fulltext_min_anchor_strength: str = "medium"
    allow_context_only_fulltext: bool = False
    allow_low_relevance_oa_backfill: bool = False
    max_scientific_candidate_pool: int = 50
    max_fulltext_papers: int = 20


def load_fulltext_selection_policy(path: str | Path | None = None) -> FulltextSelectionPolicy:
    default_path = Path(__file__).resolve().parents[3] / "configs/fulltext/relevance_oa_policy.json"
    target = Path(path) if path else default_path
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    allowed = FulltextSelectionPolicy.__dataclass_fields__
    return FulltextSelectionPolicy(**{key: value for key, value in payload.items() if key in allowed})


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _read_jsonl(path: Path) -> list[dict]:
    try:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError):
        return []


def assess_scientific_relevance(paper: dict, policy: FulltextSelectionPolicy) -> dict:
    score = float(paper.get("relevance_score", paper.get("selection_score", 0.0)) or 0.0)
    strength = str(paper.get("anchor_strength") or "none").lower()
    rank = {"none": 0, "weak": 1, "medium": 2, "strong": 3}
    reasons = list(paper.get("selection_reasons") or [])
    source = str(paper.get("selection_source") or "")
    linked_weak = bool(paper.get("linked_weak_candidate_ids"))
    linked_reviewable = bool(paper.get("linked_observation_ids")) and source in {"anchored_reviewable", "reviewable_graph"}
    seed_anchor = bool(paper.get("seed_anchor") or paper.get("pathway_anchor") or paper.get("contains_seed_anchor") or paper.get("contains_pathway_anchor"))
    context_only = bool(paper.get("context_only_match"))
    anchor_ok = rank.get(strength, 0) >= rank.get(policy.fulltext_min_anchor_strength, 2)
    qualifying_link = anchor_ok and (linked_weak or linked_reviewable)
    qualifying_reason = qualifying_link or seed_anchor or score >= policy.fulltext_min_relevance_score
    blocked: list[str] = []
    if context_only and not seed_anchor and not policy.allow_context_only_fulltext:
        blocked.append("context_only_without_seed_or_pathway_anchor")
    if not anchor_ok:
        blocked.append("anchor_strength_below_minimum")
    if score < policy.fulltext_min_relevance_score and not (qualifying_link or seed_anchor):
        blocked.append("relevance_score_below_threshold")
    if not qualifying_reason:
        blocked.append("no_scientific_relevance_qualifier")
    relevance_passed = qualifying_reason and not blocked
    if qualifying_link:
        reasons.append("medium_or_strong_anchored_discovery_link")
    if seed_anchor:
        reasons.append("seed_or_pathway_anchor")
    if score >= policy.fulltext_min_relevance_score:
        reasons.append("relevance_score_threshold")
    return {
        **paper,
        "selection_score": float(paper.get("selection_score", score) or 0.0),
        "relevance_score": score,
        "anchor_strength": strength,
        "relevance_passed": bool(relevance_passed),
        "oa_available": False,
        "candidate_tier": "high_relevance_non_oa" if relevance_passed else "low_relevance_non_oa",
        "selected_for_fulltext_l1": False,
        "selection_reasons": list(dict.fromkeys(reasons)),
        "blocked_reasons": list(dict.fromkeys(blocked)),
    }


def classify_oa_candidate(paper: dict, *, oa_available: bool, selected: bool = False) -> dict:
    relevance = bool(paper.get("relevance_passed"))
    tier = ("high_relevance_" if relevance else "low_relevance_") + ("oa" if oa_available else "non_oa")
    blocked = list(paper.get("blocked_reasons") or [])
    if oa_available and not relevance:
        blocked.append("low_relevance_oa_backfill_blocked")
    if relevance and not oa_available:
        blocked.append("oa_fulltext_unavailable")
    return {**paper, "oa_available": oa_available, "candidate_tier": tier,
            "selected_for_fulltext_l1": bool(selected and relevance and oa_available),
            "blocked_reasons": list(dict.fromkeys(blocked))}


def select_conflict_related_papers(artifacts_dir: str | Path, *, include_near_conflicts: bool = False,
                                   max_papers: int | None = None, policy: FulltextSelectionPolicy | None = None) -> dict:
    policy = policy or load_fulltext_selection_policy()
    root = Path(artifacts_dir)
    selected: dict[str, dict] = {}
    sources: list[str] = []
    discovery, _conflicts = canonical_fulltext_candidates(root)
    if discovery:
        for paper in discovery:
            for source_file in paper.get("source_files") or ["fulltext_candidate_bridge"]:
                if source_file not in sources:
                    sources.append(source_file)
    for paper in discovery:
        key = str(paper.get("paper_id") or paper.get("pmid") or paper.get("canonical_paper_id") or "")
        if key:
            selected[key] = {**paper, "paper_id": paper.get("paper_id") or key,
                "selection_reason": paper.get("selection_source") or "discovery_escalation",
                "conflict_candidate_ids": list(paper.get("linked_weak_candidate_ids") or []),
                "abstract_observation_ids": list(paper.get("linked_observation_ids") or [])}
    candidates: list[dict] = []
    for name in ("graph_conflict_candidates.jsonl", "conflict_graph_candidates.jsonl"):
        rows = _read_jsonl(root / name)
        if rows:
            candidates.extend(rows); sources.append(name)
    graph = _read_json(root / "graph_conflict_summary.json")
    if graph:
        candidates.extend(graph.get("candidates", graph.get("graph_conflict_candidates", []))); sources.append("graph_conflict_summary.json")
    for candidate in candidates:
        is_true = bool(candidate.get("is_true_graph_conflict", candidate.get("true_graph_conflict", candidate.get("status") in {"true_graph_conflict", "confirmed"})))
        if not (is_true or include_near_conflicts):
            continue
        reason = "true_graph_conflict" if is_true else "near_conflict_optional"
        for raw in candidate.get("papers") or [{"paper_id": value} for value in candidate.get("paper_ids", [])]:
            paper = raw if isinstance(raw, dict) else {"paper_id": raw}
            key = str(paper.get("paper_id") or paper.get("pmid") or paper.get("pmcid") or "")
            if not key:
                continue
            item = selected.setdefault(key, {**paper, "paper_id": paper.get("paper_id", key), "selection_reason": reason,
                "selection_source": reason, "selection_score": 1.0 if is_true else 0.65,
                "anchor_strength": "strong" if is_true else "medium", "conflict_candidate_ids": [], "abstract_observation_ids": []})
            item["conflict_candidate_ids"].append(candidate.get("candidate_id")); item["abstract_observation_ids"] += candidate.get("observation_ids", [])
    pool_limit = max(0, policy.max_scientific_candidate_pool)
    papers = sorted(selected.values(), key=lambda item: float(item.get("selection_score", 0) or 0), reverse=True)[:pool_limit]
    assessed = [assess_scientific_relevance(paper, policy) for paper in papers]
    return {"selection_policy": "relevance_first_oa_aware", "include_near_conflicts": include_near_conflicts,
        "source_artifacts": sources, "scientific_candidate_count": len(assessed), "candidate_paper_count": len(assessed),
        "relevance_passed_candidate_count": sum(x["relevance_passed"] for x in assessed), "candidate_papers": assessed,
        "max_fulltext_papers": max_papers if max_papers is not None else policy.max_fulltext_papers,
        "status": "completed" if assessed else "completed_no_candidates",
        "message": None if assessed else "No conflict-related papers selected for full-text retrieval."}


__all__ = ["FulltextSelectionPolicy", "assess_scientific_relevance", "classify_oa_candidate",
           "load_fulltext_selection_policy", "select_conflict_related_papers"]
