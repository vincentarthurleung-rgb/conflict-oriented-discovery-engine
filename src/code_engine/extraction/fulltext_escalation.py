"""Conflict-focused full-text escalation planning."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from code_engine.extraction.evidence_tiers import EvidenceTier, FULLTEXT_ELIGIBLE_STATUSES, PaperProcessingRecord


def _priority(candidate: dict[str, Any], prioritize_by: str) -> tuple:
    primary = float(candidate.get(prioritize_by, candidate.get("abstract_entropy", 0.0)) or 0.0)
    paper_count = int(candidate.get("paper_count", 0) or 0)
    available = int(candidate.get("fulltext_available_paper_count", 0) or 0)
    ratio = available / paper_count if paper_count else 0.0
    meaningful = 0 if candidate.get("relation_family") in {None, "", "unknown", "association"} else 1
    quality = float(candidate.get("normalization_quality", candidate.get("normalization_quality_score", 1.0)) or 0.0)
    return (-primary, -paper_count, -meaningful, -quality, -ratio, str(candidate.get("candidate_id", "")))


def plan_fulltext_escalation(
    abstract_conflict_candidates: list[dict],
    paper_records: list[dict],
    max_conflicts: int | None = None,
    max_papers_per_conflict: int = 5,
    require_fulltext_available: bool = True,
    prioritize_by: str = "abstract_entropy",
    *,
    run_dir: Path | None = None,
) -> dict:
    """Select only conflict-linked papers and preserve unavailable coverage gaps."""

    records = {str(item.get("paper_id")): PaperProcessingRecord.model_validate(item) for item in paper_records}
    ordered = sorted(abstract_conflict_candidates, key=lambda item: _priority(item, prioritize_by))
    if max_conflicts is not None:
        ordered = ordered[:max_conflicts]
    selected: list[dict[str, Any]] = []
    coverage_gaps: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for candidate in ordered:
        candidate_id = str(candidate.get("candidate_id") or "UNKNOWN")
        available_for_conflict = 0
        for paper_id in list(dict.fromkeys(str(item) for item in candidate.get("paper_ids", []))):
            record = records.get(paper_id)
            if record is None:
                skipped.append({"candidate_id": candidate_id, "paper_id": paper_id, "reason": "paper_processing_record_missing"})
                continue
            eligible = record.full_text_status in FULLTEXT_ELIGIBLE_STATUSES
            if not eligible:
                record.selected_for_fulltext_escalation = False
                record.selection_reason = "fulltext_unavailable_coverage_gap"
                record.evidence_tier = EvidenceTier.COVERAGE_GAP.value
                if candidate_id not in record.conflict_candidate_ids:
                    record.conflict_candidate_ids.append(candidate_id)
                if "fulltext_coverage_gap" not in record.warnings:
                    record.warnings.append("fulltext_coverage_gap")
                coverage_gaps.append({"candidate_id": candidate_id, "paper_id": paper_id, "full_text_status": record.full_text_status, "reason": record.selection_reason})
                continue
            if available_for_conflict >= max_papers_per_conflict:
                skipped.append({"candidate_id": candidate_id, "paper_id": paper_id, "reason": "max_papers_per_conflict_reached"})
                continue
            available_for_conflict += 1
            record.selected_for_fulltext_escalation = True
            record.selection_reason = f"conflict_focus:{candidate_id}"
            if candidate_id not in record.conflict_candidate_ids:
                record.conflict_candidate_ids.append(candidate_id)
            selected.append({
                "candidate_id": candidate_id,
                "paper_id": paper_id,
                "abstract_entropy": float(candidate.get("abstract_entropy", 0.0)),
                "relation_family": candidate.get("relation_family"),
                "polarity_type": candidate.get("polarity_type"),
                "full_text_status": record.full_text_status,
                "selection_reason": record.selection_reason,
            })
    summary = {
        "conflict_candidate_count": len(ordered),
        "selected_paper_count": len({item["paper_id"] for item in selected}),
        "selection_count": len(selected),
        "coverage_gap_count": len(coverage_gaps),
        "skipped_count": len(skipped),
        "require_fulltext_available": require_fulltext_available,
        "max_papers_per_conflict": max_papers_per_conflict,
        "prioritize_by": prioritize_by,
        "dry_run": True,
    }
    artifacts = {}
    if run_dir is not None:
        output = Path(run_dir)
        output.mkdir(parents=True, exist_ok=True)
        plan_path = output / "fulltext_escalation_plan.json"
        papers_path = output / "fulltext_escalation_papers.jsonl"
        plan_path.write_text(json.dumps({"summary": summary, "selected": selected, "coverage_gaps": coverage_gaps, "skipped": skipped}, ensure_ascii=False, indent=2), encoding="utf-8")
        papers_path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in selected), encoding="utf-8")
        artifacts = {"plan": str(plan_path), "papers": str(papers_path)}
    return {
        "summary": summary,
        "selected_papers": selected,
        "coverage_gaps": coverage_gaps,
        "skipped": skipped,
        "paper_records": [item.model_dump(mode="json") for item in records.values()],
        "artifacts": artifacts,
    }


__all__ = ["plan_fulltext_escalation"]
