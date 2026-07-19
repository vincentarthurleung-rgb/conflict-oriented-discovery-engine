"""Confirm or resolve abstract conflict signals with full-text evidence."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from code_engine.graph.abstract_conflict_screening import shannon_entropy


def _context_key(record: dict[str, Any]) -> str:
    context = dict(record.get("context_slots") or record.get("context") or {})
    selected = {key: context.get(key) for key in sorted(context) if context.get(key) not in (None, "", [], {})}
    if not selected:
        selected = {
            key: record.get(key)
            for key in ("species", "cell_type", "tissue_or_region", "dose", "timepoint", "assay")
            if record.get(key) not in (None, "")
        }
    return json.dumps(selected, sort_keys=True, ensure_ascii=False) if selected else "context_unknown"


def _conditioned_entropy(records: list[dict[str, Any]]) -> tuple[float | None, dict[str, Any]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for item in records:
        direction = str(item.get("direction") or "unknown")
        if direction != "unknown":
            groups[_context_key(item)].append(direction)
    total = sum(len(values) for values in groups.values())
    if not total:
        return None, {"context_group_count": 0, "groups": {}}
    group_summary = {}
    weighted = 0.0
    for key, directions in groups.items():
        entropy = shannon_entropy(dict(Counter(directions)))
        weighted += len(directions) / total * entropy
        group_summary[key] = {"evidence_count": len(directions), "entropy": entropy, "direction_distribution": dict(Counter(directions))}
    return round(weighted, 6), {"context_group_count": len(groups), "groups": group_summary}


def confirm_conflicts_with_fulltext_evidence(
    abstract_conflict_candidates: list[dict],
    fulltext_evidence_records: list[dict],
    normalized_fulltext_observations: list[dict],
    min_fulltext_evidence_count: int = 2,
    *,
    conflict_entropy_threshold: float = 0.65,
    context_resolution_drop: float = 0.3,
    run_dir: Path | None = None,
) -> dict:
    """Compute full-text and context-conditioned entropy without changing L3."""

    normalization_supplied = bool(normalized_fulltext_observations)
    usable_ids = {
        str(item.get("evidence_id"))
        for item in normalized_fulltext_observations
        if item.get("evidence_id") and item.get("allow_high_confidence_graph_use", not item.get("exclude_from_high_confidence_conflict", False))
        and str(item.get("normalization_status", "resolved")) not in {"ambiguous", "ambiguous_external_candidate", "rejected_external_candidate", "unresolved", "unresolved_fallback", "low_confidence"}
    }
    confirmations = []
    for candidate in abstract_conflict_candidates:
        candidate_id = str(candidate.get("candidate_id") or "UNKNOWN")
        linked = [
            item for item in fulltext_evidence_records
            if candidate_id in [str(value) for value in item.get("linked_conflict_candidate_ids", [])]
            and str(item.get("source_scope")) == "full_text"
            and (not normalization_supplied or str(item.get("evidence_id")) in usable_ids)
        ]
        directions = [str(item.get("direction")) for item in linked if str(item.get("direction")) != "unknown"]
        distribution = dict(Counter(directions))
        fulltext_entropy = shannon_entropy(distribution) if directions else None
        conditioned_entropy, context_summary = _conditioned_entropy(linked)
        paper_ids = sorted({str(item.get("paper_id")) for item in linked})
        available = int(candidate.get("fulltext_available_paper_count", len(paper_ids)) or 0)
        unavailable = int(candidate.get("fulltext_unavailable_paper_count", 0) or 0)
        error_suspected = False
        manual = False
        if len(linked) < min_fulltext_evidence_count:
            status = "insufficient_fulltext_coverage"
        elif fulltext_entropy is not None and fulltext_entropy >= conflict_entropy_threshold:
            if conditioned_entropy is not None and fulltext_entropy - conditioned_entropy >= context_resolution_drop:
                status = "context_resolved_conflict"
            else:
                status = "confirmed_conflict"
        elif len(distribution) <= 1 and float(candidate.get("abstract_entropy", 0.0)) >= conflict_entropy_threshold:
            status = "false_conflict_due_to_abstract_loss"
            error_suspected = True
        else:
            status = "manual_review_required"
            manual = True
        warnings = []
        if unavailable:
            warnings.append("partial_fulltext_coverage")
        if not linked:
            warnings.append("no_fulltext_evidence_not_a_contradiction")
        confirmations.append({
            "candidate_id": f"confirmation_{candidate_id}",
            "abstract_conflict_candidate_id": candidate_id,
            "abstract_entropy": float(candidate.get("abstract_entropy", 0.0)),
            "fulltext_entropy": fulltext_entropy,
            "context_conditioned_entropy": conditioned_entropy,
            "fulltext_evidence_count": len(linked),
            "fulltext_paper_count": len(paper_ids),
            "fulltext_available_paper_count": available,
            "fulltext_unavailable_paper_count": unavailable,
            "confirmation_status": status,
            "context_resolution_summary": context_summary,
            "error_suspected": error_suspected,
            "manual_review_required": manual,
            "linked_evidence_ids": [str(item.get("evidence_id")) for item in linked if item.get("evidence_id")],
            "linked_paper_ids": paper_ids,
            "warnings": warnings,
        })
    counts = Counter(item["confirmation_status"] for item in confirmations)
    summary = {
        "confirmation_count": len(confirmations),
        "confirmed_conflict_count": counts["confirmed_conflict"],
        "context_resolved_conflict_count": counts["context_resolved_conflict"],
        "false_conflict_due_to_abstract_loss_count": counts["false_conflict_due_to_abstract_loss"],
        "insufficient_fulltext_coverage_count": counts["insufficient_fulltext_coverage"],
        "manual_review_required_count": counts["manual_review_required"],
    }
    artifacts = {}
    if run_dir is not None:
        output = Path(run_dir)
        output.mkdir(parents=True, exist_ok=True)
        confirmation_path = output / "fulltext_conflict_confirmation.jsonl"
        summary_path = output / "fulltext_conflict_summary.json"
        confirmation_path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in confirmations), encoding="utf-8")
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        artifacts = {"confirmations": str(confirmation_path), "summary": str(summary_path)}
    return {"confirmations": confirmations, "summary": summary, "artifacts": artifacts}


__all__ = ["confirm_conflicts_with_fulltext_evidence"]
