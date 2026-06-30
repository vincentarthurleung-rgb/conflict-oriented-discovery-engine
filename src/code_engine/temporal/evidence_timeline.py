"""Build traceable evidence timelines from normalized local artifact records."""

from __future__ import annotations

import hashlib
from typing import Any

from .hypothesis_comparison import compare_hypotheses, hypothesis_matches_conflict
from .models import ConflictEvidenceTimeline
from .status_classifier import classify_temporal_status
from .windows import TimelineConfig, detect_temporal_windows, direction_stats, paper_identity


def conflict_key(item: dict[str, Any]) -> str:
    return "|".join(str(item.get(name) or "unknown") for name in ("subject_canonical_id", "object_canonical_id", "relation_family", "polarity_type"))


def _year(item: dict[str, Any]) -> int | None:
    try:
        return int(item.get("publication_year") or str(item.get("publication_date") or "")[:4])
    except (TypeError, ValueError):
        return None


def _same_conflict(record: dict[str, Any], conflict: dict[str, Any]) -> bool:
    linked = {str(x) for name in ("linked_conflict_ids", "linked_conflict_candidate_ids") for x in (record.get(name) or [])}
    ids = {str(conflict.get(x)) for x in ("conflict_id", "candidate_id", "abstract_conflict_candidate_id") if conflict.get(x)}
    if linked & ids:
        return True
    required = ("subject_canonical_id", "object_canonical_id")
    if not all(conflict.get(x) and record.get(x) for x in required):
        return False
    if any(str(conflict[x]) != str(record[x]) for x in required):
        return False
    for name in ("relation_family", "polarity_type"):
        left, right = str(conflict.get(name) or "unknown"), str(record.get(name) or "unknown")
        if left != "unknown" and right != "unknown" and left != right:
            return False
    return True


def _paper(item: dict[str, Any]) -> dict[str, Any]:
    return {name: item.get(name) for name in ("paper_id", "canonical_paper_id", "doi", "title", "journal", "publication_year")}


def _item(record: dict[str, Any], primary: str, secondary: list[str]) -> dict[str, Any]:
    return {
        "year": _year(record), "primary_role": primary, "role": primary,
        "secondary_roles": sorted(set(secondary)),
        **{name: record.get(name) for name in (
            "paper_id", "canonical_paper_id", "doi", "title", "journal", "direction",
            "relation_family", "polarity_type", "context_variables", "evidence_span",
            "evidence_text", "source_scope", "evidence_tier", "confidence")},
        "mechanism_edges": record.get("linked_mechanism_edge_ids") or record.get("mechanism_edges") or [],
        "evidence_id": record.get("evidence_id") or record.get("observation_id") or record.get("claim_id"),
    }


def build_conflict_evidence_timelines(conflicts: list[dict[str, Any]], evidence: list[dict[str, Any]],
                                      hypotheses: list[dict[str, Any]] | None = None,
                                      confirmations: list[dict[str, Any]] | None = None,
                                      config: TimelineConfig | None = None) -> list[ConflictEvidenceTimeline]:
    config, hypotheses, confirmations = config or TimelineConfig(), hypotheses or [], confirmations or []
    output = []
    for conflict in conflicts:
        records = [x for x in evidence if _same_conflict(x, conflict)]
        metadata = detect_temporal_windows(records, config)
        source, later_window = metadata["conflict_source_window"], metadata["later_evidence_window"]
        early = [x for x in records if source and _year(x) is not None and source["start_year"] <= _year(x) <= source["end_year"]]
        later = [x for x in records if later_window and _year(x) is not None and later_window["start_year"] <= _year(x) <= later_window["end_year"]]
        overall_dist, overall_entropy, warnings = direction_stats(records)
        early_dist, early_entropy, ew = direction_stats(early)
        later_dist, later_entropy, lw = direction_stats(later)
        warnings += ew + lw + metadata["warnings"]
        if any(not (x.get("paper_id") or x.get("canonical_paper_id") or x.get("doi") or x.get("title")) for x in records):
            warnings.append("missing_paper_provenance")
        if any(not (x.get("evidence_span") or x.get("evidence_text") or x.get("evidence_sentence")) for x in records):
            warnings.append("missing_evidence_span")
        dominant, share = None, 0.0
        if later_dist:
            dominant, count = max(later_dist.items(), key=lambda pair: (pair[1], pair[0]))
            share = round(count / sum(later_dist.values()), 6)
        confirmation = next((x for x in confirmations if str(x.get("abstract_conflict_candidate_id")) in {str(conflict.get("candidate_id")), str(conflict.get("conflict_id"))}), {})
        has_context_partition = confirmation.get("confirmation_status") == "context_resolved_conflict" or (
            confirmation.get("context_conditioned_entropy") is not None and
            float(confirmation.get("fulltext_entropy") or 0) - float(confirmation["context_conditioned_entropy"]) >= 0.25
        )
        has_context_evidence = any(x.get("context_variables") or x.get("context_slots") or x.get("context") for x in later)
        has_mechanism = any(x.get("linked_mechanism_edge_ids") or x.get("linked_mechanism_path_ids") or x.get("mechanism_edges") for x in later)
        critical = not source or "missing_publication_year" in warnings or not records
        status, confidence = classify_temporal_status(
            early_entropy=early_entropy, later_entropy=later_entropy,
            early_paper_count=len({paper_identity(x) for x in early}), later_paper_count=len({paper_identity(x) for x in later}),
            later_dominant_direction_share=share, min_later_evidence_papers=config.min_later_evidence_papers,
            has_context_partition=bool(has_context_partition), has_mechanism_evidence=has_mechanism,
            has_explanation_evidence=has_context_evidence, critical_fields_missing=critical,
        )
        timeline_items = []
        for record in records:
            year = _year(record)
            secondary = []
            if source and year is not None and source["start_year"] <= year <= source["end_year"]:
                primary = "conflict_source"
            elif later_window and year is not None and later_window["start_year"] <= year <= later_window["end_year"]:
                primary = "later_explanation_evidence"
                if dominant and str(record.get("direction") or "unknown").casefold() == dominant:
                    secondary.append("recent_consensus_evidence")
                if record.get("context_variables") or record.get("context_slots") or record.get("context"):
                    secondary.append("context_partition_evidence")
                if record.get("linked_mechanism_edge_ids") or record.get("linked_mechanism_path_ids") or record.get("mechanism_edges"):
                    secondary.append("mechanism_explanation_evidence")
            else:
                primary = "stale_evidence"
            timeline_items.append(_item(record, primary, secondary))
        timeline_items.sort(key=lambda x: (x["year"] is None, x["year"] or 0, str(x.get("canonical_paper_id") or x.get("paper_id") or "")))
        cid = str(conflict.get("graph_conflict_id") or conflict.get("conflict_id") or conflict.get("candidate_id") or conflict.get("edge_id") or hashlib.sha256(conflict_key(conflict).encode()).hexdigest()[:16])
        matched_hypotheses = [h for h in hypotheses if hypothesis_matches_conflict(h, {**conflict, "conflict_id": cid})]
        comparisons = compare_hypotheses({**conflict, "conflict_id": cid}, hypotheses, later, dominant)
        output.append(ConflictEvidenceTimeline(
            timeline_id=f"timeline_{cid}", conflict_id=cid, conflict_key=conflict_key(conflict),
            subject_canonical_id=conflict.get("subject_canonical_id"), object_canonical_id=conflict.get("object_canonical_id"),
            relation_family=str(conflict.get("relation_family") or "unknown"), polarity_type=str(conflict.get("polarity_type") or "unknown"),
            conflict_source_window=source, later_evidence_window=later_window, evidence_timeline=timeline_items,
            early_conflicting_papers=[_paper(x) for x in early], later_explanation_evidence_papers=[_paper(x) for x in later],
            recent_consensus_papers=[_paper(x) for x in later if dominant and str(x.get("direction") or "").casefold() == dominant],
            stale_or_missing_recent_evidence_papers=[_paper(x) for x in early] if not later else [],
            overall_direction_distribution=overall_dist, early_direction_distribution=early_dist, later_direction_distribution=later_dist,
            direction_distribution_by_year=metadata["direction_distribution_by_year"], paper_count_by_year=metadata["paper_count_by_year"],
            evidence_count_by_year=metadata["evidence_count_by_year"], entropy_by_year=metadata["entropy_by_year"],
            overall_entropy=overall_entropy, early_entropy=early_entropy, later_entropy=later_entropy,
            later_dominant_direction=dominant, later_dominant_direction_share=share,
            status=status, status_confidence=confidence, latest_evidence_pattern={"dominant_direction": dominant, "dominant_direction_share": share, "direction_distribution": later_dist},
            system_hypotheses=matched_hypotheses, hypothesis_vs_later_evidence=comparisons,
            possible_explanation_evidence=bool(later and (has_context_evidence or has_mechanism or share >= .75)),
            recent_consensus_signal=status == "recent_consensus_signal", active_like_signal=status in {"persistent_conflict", "emerging_conflict"},
            warnings=sorted(set(warnings)),
        ))
    return output
