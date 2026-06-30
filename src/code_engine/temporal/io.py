"""Artifact-only timeline runner. This module has no remote or model dependencies."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .evidence_timeline import build_conflict_evidence_timelines, conflict_key
from .windows import TimelineConfig

INPUT_ARTIFACTS = (
    "abstract_conflict_candidates.jsonl", "conflict_focus_set.jsonl",
    "fulltext_conflict_confirmation.jsonl", "fulltext_evidence_records.jsonl",
    "l2_abstract_observations.json", "l2_fulltext_observations.json",
    "mechanism_graph.json", "hypothesis_hyperedges.jsonl",
    "hypothesis_candidates.jsonl", "run_paper_manifest.jsonl",
)


def _read(path: Path) -> Any:
    if not path.exists():
        return []
    try:
        if path.suffix == ".jsonl":
            return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    if isinstance(value, dict):
        for name in ("observations", "records", "items", "evidence", "confirmations", "candidates"):
            if isinstance(value.get(name), list):
                return [x for x in value[name] if isinstance(x, dict)]
    return []


def _first(item: dict[str, Any], *names: str) -> Any:
    for name in names:
        value: Any = item
        for part in name.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        if value not in (None, "", []):
            return value
    return None


def _normalize(item: dict[str, Any], manifest: dict[str, dict[str, Any]], mechanisms: dict[str, list[str]]) -> dict[str, Any]:
    paper_id = _first(item, "canonical_paper_id", "paper_id", "source_paper_id", "provenance.paper_id")
    paper = manifest.get(str(paper_id), {})
    evidence_id = _first(item, "evidence_id", "observation_id", "claim_id", "triple_id")
    direction = _first(item, "direction", "relation_direction", "effect_direction")
    if direction is None:
        sign = _first(item, "relation_sign", "sign")
        direction = "increase" if sign in (1, "+1", "positive") else "decrease" if sign in (-1, "-1", "negative") else "unknown"
    normalized = dict(item)
    normalized.update({
        "evidence_id": evidence_id,
        "paper_id": _first(item, "paper_id", "source_paper_id") or paper.get("paper_id") or paper_id,
        "canonical_paper_id": _first(item, "canonical_paper_id") or paper.get("canonical_paper_id") or paper_id,
        "doi": _first(item, "doi", "provenance.doi") or paper.get("doi"),
        "title": _first(item, "title", "article_title", "paper_title", "provenance.title") or paper.get("title"),
        "journal": _first(item, "journal", "journal_name", "provenance.journal") or paper.get("journal"),
        "publication_year": _first(item, "publication_year", "year", "provenance.publication_year") or paper.get("publication_year") or paper.get("year"),
        "publication_date": _first(item, "publication_date", "date") or paper.get("publication_date"),
        "direction": str(direction).casefold(),
        "subject_canonical_id": _first(item, "subject_canonical_id", "subject_id", "normalized_subject_id"),
        "object_canonical_id": _first(item, "object_canonical_id", "object_id", "normalized_object_id"),
        "relation_family": _first(item, "relation_family", "relation_type", "predicate") or "unknown",
        "polarity_type": _first(item, "polarity_type", "polarity") or "unknown",
        "evidence_span": _first(item, "evidence_span", "span", "evidence_sentence", "sentence"),
        "evidence_text": _first(item, "evidence_text", "evidence_sentence", "text", "sentence"),
        "context_variables": _first(item, "context_variables", "context_slots", "context", "conditions") or {},
        "source_scope": _first(item, "source_scope", "scope"),
        "evidence_tier": _first(item, "evidence_tier", "tier"),
        "confidence": _first(item, "confidence", "belief_weight", "score"),
    })
    if evidence_id and str(evidence_id) in mechanisms:
        normalized["linked_mechanism_edge_ids"] = sorted(set((normalized.get("linked_mechanism_edge_ids") or []) + mechanisms[str(evidence_id)]))
    return normalized


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, payload: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in payload), encoding="utf-8")


def run_conflict_timeline(run_dir: str | Path, *, cutoff_year: int | None = None, window_size: int = 5,
                          min_conflict_papers: int = 3, min_later_papers: int = 1,
                          enabled: bool = True) -> dict[str, Any]:
    artifact_dir = Path(run_dir) / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    config = TimelineConfig(window_size=window_size, min_conflict_source_papers=min_conflict_papers,
                            min_later_evidence_papers=min_later_papers, cutoff_year=cutoff_year)
    manifest_records = _records(_read(artifact_dir / "run_paper_manifest.jsonl"))
    manifest: dict[str, dict[str, Any]] = {}
    for item in manifest_records:
        for name in ("paper_id", "canonical_paper_id", "original_paper_id"):
            if item.get(name):
                manifest[str(item[name])] = item
    graph = _read(artifact_dir / "mechanism_graph.json")
    mechanisms: dict[str, list[str]] = {}
    if isinstance(graph, dict):
        for edge in graph.get("edges", []):
            edge_id = str(edge.get("edge_id") or edge.get("mechanism_edge_id") or "")
            for evidence_id in edge.get("linked_evidence_ids", []) or edge.get("evidence_ids", []):
                mechanisms.setdefault(str(evidence_id), []).append(edge_id)
    raw_evidence = []
    for name in ("fulltext_evidence_records.jsonl", "l2_abstract_observations.json", "l2_fulltext_observations.json"):
        raw_evidence.extend(_records(_read(artifact_dir / name)))
    normalized = [_normalize(x, manifest, mechanisms) for x in raw_evidence]
    seen, evidence = set(), []
    for index, item in enumerate(normalized):
        identity = str(item.get("evidence_id") or f"anon:{index}:{item.get('canonical_paper_id')}:{item.get('direction')}")
        if identity not in seen:
            seen.add(identity); evidence.append(item)
    def parsed_year(item: dict[str, Any]) -> int | None:
        try:
            return int(item.get("publication_year") or str(item.get("publication_date") or "")[:4])
        except (TypeError, ValueError):
            return None
    excluded = [x for x in evidence if cutoff_year is not None and parsed_year(x) is not None and parsed_year(x) > cutoff_year]
    gated = [x for x in evidence if x not in excluded]
    candidates = _records(_read(artifact_dir / "abstract_conflict_candidates.jsonl"))
    if not candidates:
        candidates = _records(_read(artifact_dir / "conflict_focus_set.jsonl"))
    graph_candidates = [item for item in _records(_read(artifact_dir / "graph_conflict_candidates.jsonl")) if item.get("status") == "graph_conflict_candidate"]
    # Graph-derived conflicts are primary; legacy candidates remain as fallback/supplement.
    by_key = {conflict_key(item): item for item in candidates}
    for item in graph_candidates:
        by_key[conflict_key(item)] = item
    candidates = list(by_key.values())
    confirmations = _records(_read(artifact_dir / "fulltext_conflict_confirmation.jsonl"))
    by_candidate = {str(x.get("candidate_id")): x for x in candidates}
    for confirmation in confirmations:
        parent = by_candidate.get(str(confirmation.get("abstract_conflict_candidate_id")))
        if parent:
            confirmation.update({k: v for k, v in parent.items() if k not in confirmation})
    if not candidates:
        grouped: dict[str, dict[str, Any]] = {}
        for item in gated:
            grouped.setdefault(conflict_key(item), item)
        candidates = [{**item, "candidate_id": f"derived_{index}"} for index, item in enumerate(grouped.values())]
    hypotheses = _records(_read(artifact_dir / "hypothesis_hyperedges.jsonl")) or _records(_read(artifact_dir / "hypothesis_candidates.jsonl"))
    timelines = build_conflict_evidence_timelines(candidates, gated, hypotheses, confirmations, config)
    rows = [x.to_dict() for x in timelines]
    windows = [{k: row.get(k) for k in ("conflict_id", "conflict_key", "conflict_source_window", "later_evidence_window", "paper_count_by_year", "evidence_count_by_year", "entropy_by_year", "direction_distribution_by_year", "warnings")} for row in rows]
    comparisons = [{"timeline_id": row["timeline_id"], "conflict_id": row["conflict_id"], **item} for row in rows for item in row["hypothesis_vs_later_evidence"]]
    status_counts = Counter(row["status"] for row in rows)
    comparison_counts = Counter(x["comparison_to_later_evidence"] for x in comparisons)
    warnings = sorted({warning for row in rows for warning in row["warnings"]})
    if not raw_evidence:
        warnings.append("no_timeline_evidence_input")
    summary = {
        "status": "completed" if rows and raw_evidence else "no_input", "mode": "time_gated",
        "not_used_for_hypothesis_generation": True, "timeline_count": len(rows),
        **{f"{status}_count": status_counts[status] for status in (
            "persistent_conflict", "emerging_conflict", "conflict_with_later_explanation_evidence",
            "recent_consensus_signal", "context_partition_supported", "stale_unresolved_conflict",
            "abandoned_or_understudied_conflict", "insufficient_later_evidence", "uncertain_temporal_evidence_status")},
        "human_review_required_count": len(rows), "hypothesis_compared_count": len(comparisons),
        "hypothesis_covered_by_later_evidence_count": comparison_counts["covered_by_later_evidence"],
        "hypothesis_extends_later_evidence_count": comparison_counts["extends_later_evidence"],
        "hypothesis_diverges_from_later_evidence_count": comparison_counts["diverges_from_later_evidence"],
        "excluded_future_evidence_count": len(excluded),
        "excluded_future_paper_ids": sorted({str(x.get("canonical_paper_id") or x.get("paper_id")) for x in excluded}),
        "warnings": sorted(set(warnings)), "system_judgment": "non_decisive",
        "graph_conflict_candidates_used": len(graph_candidates),
        "timelines_from_graph_conflicts": sum(row.get("conflict_id") in {str(item.get("graph_conflict_id")) for item in graph_candidates} for row in rows),
    }
    if not enabled:
        rows, windows, comparisons = [], [], []
        summary.update(status="disabled", timeline_count=0, warnings=["conflict_timeline_disabled"])
    _write_jsonl(artifact_dir / "conflict_evidence_timelines.jsonl", rows)
    _write_jsonl(artifact_dir / "conflict_temporal_windows.jsonl", windows)
    _write_jsonl(artifact_dir / "hypothesis_later_evidence_comparisons.jsonl", comparisons)
    _write_json(artifact_dir / "conflict_evidence_timeline_summary.json", summary)
    return summary
