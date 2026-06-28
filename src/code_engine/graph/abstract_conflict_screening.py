"""Coarse abstract-level conflict candidate discovery using directional entropy."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from code_engine.extraction.evidence_tiers import EvidenceTier, FULLTEXT_ELIGIBLE_STATUSES


BAD_NORMALIZATION_STATUSES = {"ambiguous", "unresolved", "unresolved_fallback", "empty_or_invalid", "low_confidence", "manual_review_required"}


def shannon_entropy(distribution: dict[str, int]) -> float:
    total = sum(distribution.values())
    if total <= 0:
        return 0.0
    return round(-sum((count / total) * math.log2(count / total) for count in distribution.values() if count), 6)


def _usable(observation: dict[str, Any]) -> bool:
    statuses = {
        str(observation.get("normalization_status", "resolved")),
        str(observation.get("subject_normalization_status", "resolved")),
        str(observation.get("object_normalization_status", "resolved")),
    }
    return (
        not statuses.intersection(BAD_NORMALIZATION_STATUSES)
        and bool(observation.get("allow_high_confidence_graph_use", not observation.get("exclude_from_high_confidence_conflict", False)))
        and str(observation.get("normalization_quality", "resolved_or_acceptable")).casefold() not in {"low_confidence", "ambiguous", "unresolved"}
    )


def _observation_index(observations: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed = {}
    for item in observations:
        for key in (item.get("claim_id"), item.get("l1_claim_id"), item.get("observation_id"), item.get("triple_id")):
            if key:
                indexed[str(key)] = item
    return indexed


def build_abstract_conflict_candidates(
    abstract_claims: list[dict],
    normalized_observations: list[dict],
    min_evidence_count: int = 3,
    min_entropy: float = 0.65,
    group_by_relation_family: bool = True,
    paper_level_dedup: bool = True,
    *,
    include_no_effect: bool = True,
    run_dir: Path | None = None,
) -> dict:
    """Build screening candidates; output is not a final L3 conflict graph."""

    observations = _observation_index(normalized_observations)
    grouped: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    excluded = Counter()
    unknown_direction_count = 0
    for claim in abstract_claims:
        if str(claim.get("source_scope", "abstract")) != "abstract":
            excluded["non_abstract_scope"] += 1
            continue
        observation = observations.get(str(claim.get("claim_id") or ""), {})
        merged = {**claim, **observation}
        if observation and not _usable(observation):
            excluded["low_confidence_or_unresolved_l2"] += 1
            continue
        if not observation and not (
            merged.get("subject_canonical_id") and merged.get("object_canonical_id")
            and merged.get("allow_high_confidence_graph_use", False)
        ):
            excluded["missing_high_confidence_l2_observation"] += 1
            continue
        direction = str(claim.get("direction") or merged.get("direction") or "unknown")
        if direction == "unknown":
            unknown_direction_count += 1
            continue
        if direction == "no_effect" and not include_no_effect:
            excluded["no_effect_excluded_by_policy"] += 1
            continue
        subject_id = str(merged.get("subject_canonical_id") or merged.get("subject_id") or "")
        object_id = str(merged.get("object_canonical_id") or merged.get("object_id") or "")
        relation_family = str(claim.get("relation_family") or merged.get("relation_family") or "unknown")
        polarity_type = str(claim.get("polarity_type") or merged.get("polarity_type") or "unknown")
        key = (subject_id, object_id, relation_family if group_by_relation_family else "all", polarity_type)
        grouped[key].append({**merged, "direction": direction, "relation_family": relation_family, "polarity_type": polarity_type})

    candidates = []
    for (subject_id, object_id, relation_family, polarity_type), items in grouped.items():
        paper_votes: dict[str, set[str]] = defaultdict(set)
        for item in items:
            paper_votes[str(item.get("paper_id") or "UNKNOWN")].add(str(item["direction"]))
        if paper_level_dedup:
            directions = [next(iter(values)) if len(values) == 1 else "mixed" for values in paper_votes.values()]
        else:
            directions = [str(item["direction"]) for item in items]
        distribution = dict(sorted(Counter(directions).items()))
        entropy = shannon_entropy(distribution)
        paper_ids = sorted(paper_votes)
        fulltext_available = sum(
            any(str(item.get("paper_id") or "UNKNOWN") == paper_id and str(item.get("full_text_status")) in FULLTEXT_ELIGIBLE_STATUSES for item in items)
            for paper_id in paper_ids
        )
        stable = "|".join((subject_id, object_id, relation_family, polarity_type))
        candidate_id = hashlib.sha256(stable.encode()).hexdigest()[:16]
        recommended = len(paper_ids) >= min_evidence_count and entropy >= min_entropy
        candidates.append({
            "candidate_id": candidate_id,
            "prompt_id": next((item.get("prompt_id") for item in items if item.get("prompt_id")), None),
            "domain_id": next((item.get("domain_id") for item in items if item.get("domain_id")), None),
            "subject_canonical_id": subject_id or None,
            "object_canonical_id": object_id or None,
            "subject_name": str(items[0].get("subject_canonical_name") or items[0].get("normalized_subject") or items[0].get("subject_raw") or "") or None,
            "object_name": str(items[0].get("object_canonical_name") or items[0].get("normalized_object") or items[0].get("object_raw") or "") or None,
            "relation_family": relation_family,
            "polarity_type": polarity_type,
            "direction_distribution": distribution,
            "paper_count": len(paper_ids),
            "claim_count": len(items),
            "abstract_entropy": entropy,
            "evidence_tier": EvidenceTier.ABSTRACT_CONFLICT_SIGNAL.value,
            "paper_ids": paper_ids,
            "claim_ids": sorted(str(item.get("claim_id")) for item in items if item.get("claim_id")),
            "normalized_observation_ids": sorted(str(item.get("observation_id") or item.get("triple_id")) for item in items if item.get("observation_id") or item.get("triple_id")),
            "fulltext_available_paper_count": fulltext_available,
            "fulltext_unavailable_paper_count": len(paper_ids) - fulltext_available,
            "recommended_for_fulltext_escalation": recommended,
            "selection_reason": "entropy_and_evidence_threshold_met" if recommended else "below_abstract_screening_threshold",
            "normalization_quality": 1.0,
            "warnings": ["abstract_level_candidate_not_final_conflict"],
        })
    candidates.sort(key=lambda item: (-item["abstract_entropy"], -item["paper_count"], item["candidate_id"]))
    focus_set = [item for item in candidates if item["recommended_for_fulltext_escalation"]]
    summary = {
        "candidate_count": len(candidates),
        "focus_set_count": len(focus_set),
        "unknown_direction_count": unknown_direction_count,
        "excluded_counts": dict(excluded),
        "min_evidence_count": min_evidence_count,
        "min_entropy": min_entropy,
        "paper_level_dedup": paper_level_dedup,
        "group_by_relation_family": group_by_relation_family,
        "evidence_scope": "abstract_candidate_only",
    }
    artifacts = {}
    if run_dir is not None:
        output = Path(run_dir)
        output.mkdir(parents=True, exist_ok=True)
        candidates_path = output / "abstract_conflict_candidates.jsonl"
        focus_path = output / "conflict_focus_set.jsonl"
        summary_path = output / "abstract_conflict_summary.json"
        candidates_path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in candidates), encoding="utf-8")
        focus_path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in focus_set), encoding="utf-8")
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        artifacts = {"candidates": str(candidates_path), "focus_set": str(focus_path), "summary": str(summary_path)}
    return {"candidates": candidates, "focus_set": focus_set, "summary": summary, "artifacts": artifacts}


__all__ = ["build_abstract_conflict_candidates", "shannon_entropy"]
