"""Build deterministic manual-review queues and unvalidated paper metrics."""

from __future__ import annotations

import csv
import hashlib
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

MANIFEST = "case_bundle_manifest.json"
SOURCES = {
    "fulltext_claims": ("l35_fulltext_discovery_l1_claims.jsonl", "fulltext_l1_claim"),
    "fulltext_reviewable": ("l35_fulltext_discovery_observations.jsonl", "fulltext_reviewable_observation"),
    "abstract_reviewable": ("l2_reviewable_graph_observations.jsonl", "abstract_reviewable_observation"),
    "low_priority": ("l2_low_priority_context_observations.jsonl", "low_priority_context_observation"),
    "weak": ("weak_conflict_candidates.jsonl", "weak_candidate"),
    "non_comparable": ("non_comparable_direction_pairs.jsonl", "non_comparable_direction_pair"),
    "hypotheses": ("hypothesis_candidates.jsonl", "formal_hypothesis"),
}
SUMMARY_FILES = (
    MANIFEST, "discovery_filter_summary.json", "l35_fulltext_discovery_escalation_summary.json",
    "l35_fulltext_discovery_reentry_summary.json", "weak_conflict_summary.json",
    "non_comparable_direction_pair_summary.json", "hypothesis_summary.json",
)
METRIC_FIELDS = (
    "case_id", "bundle_path", "pipeline_complete", "ready_for_system_b", "scientific_output_class",
    "raw_l1_claim_count", "l2_retained_observation_count", "abstract_reviewable_count",
    "low_priority_context_count", "selected_fulltext_count", "downloaded_fulltext_count",
    "parsed_section_count", "selected_chunk_count", "fulltext_l1_claim_count",
    "fulltext_claims_reentered_l2", "fulltext_reviewable_count", "weak_conflict_count",
    "non_comparable_direction_pair_count", "formal_hypothesis_count", "review_queue_item_count",
)
ANNOTATION_FIELDS = (
    "final_label", "evidence_supported", "seed_relevance", "subject_correct", "relation_correct",
    "object_correct", "direction_correct", "context_captured", "anchor_correct",
    "mechanistic_usefulness", "comparability_correct", "candidate_type_correct", "correctly_rejected",
    "should_have_been_weak", "worth_followup", "error_type", "notes", "reviewer_id", "reviewed_at",
)
QUEUE_FIELDS = (
    "review_item_id", "case_id", "bundle_path", "item_type", "source_file", "source_line",
    "pmid", "pmcid", "paper_title", "section_title", "source_scope", "subject", "relation", "object",
    "direction", "context", "evidence_sentence", "claim_text", "anchor_strength",
    "seed_neighborhood_score", "review_priority_score", "comparability_label", "candidate_type",
    "observation_a_preview", "observation_b_preview", "rejection_reason",
)


def discover_bundles(roots: Iterable[str | Path]) -> list[Path]:
    found: set[Path] = set()
    for value in roots:
        root = Path(value)
        if root.is_file() and root.name == MANIFEST:
            found.add(root.parent.resolve())
        elif root.is_dir():
            if (root / MANIFEST).is_file():
                found.add(root.resolve())
            found.update(path.parent.resolve() for path in root.rglob(MANIFEST))
    return sorted(found, key=lambda path: str(path))


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _jsonl(path: Path) -> list[tuple[int, dict[str, Any]]]:
    rows = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return rows
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append((line_number, value))
    return rows


def _first(summaries: list[dict[str, Any]], *aliases: str) -> Any:
    def walk(value: Any) -> Any:
        if isinstance(value, dict):
            for alias in aliases:
                if alias in value and value[alias] is not None:
                    return value[alias]
            for child in value.values():
                result = walk(child)
                if result is not None:
                    return result
        return None
    for summary in summaries:
        result = walk(summary)
        if result is not None:
            return result
    return None


def _pick(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return None


def _preview(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return value[:500]
    return json.dumps(value, ensure_ascii=False, sort_keys=True)[:500]


def review_item(case_id: str, bundle: Path, item_type: str, filename: str, line: int, raw: dict[str, Any]) -> dict[str, Any]:
    stable = f"{case_id}::{item_type}::{filename}::{line}"
    return {
        "review_item_id": stable, "case_id": case_id, "bundle_path": str(bundle), "item_type": item_type,
        "source_file": filename, "source_line": line, "pmid": _pick(raw, "pmid", "PMID"),
        "pmcid": _pick(raw, "pmcid", "PMCID"), "paper_title": _pick(raw, "paper_title", "title"),
        "section_title": _pick(raw, "section_title", "section"), "source_scope": raw.get("source_scope"),
        "subject": _pick(raw, "subject", "entity_a"), "relation": _pick(raw, "relation", "predicate"),
        "object": _pick(raw, "object", "entity_b"), "direction": raw.get("direction"), "context": raw.get("context"),
        "evidence_sentence": _pick(raw, "evidence_sentence", "evidence", "sentence"),
        "claim_text": _pick(raw, "claim_text", "claim"), "anchor_strength": raw.get("anchor_strength"),
        "seed_neighborhood_score": raw.get("seed_neighborhood_score"),
        "review_priority_score": _pick(raw, "review_priority_score", "score", "anchor_score"),
        "comparability_label": raw.get("comparability_label"), "candidate_type": raw.get("candidate_type"),
        "observation_a_preview": _preview(_pick(raw, "observation_a", "observation_1")),
        "observation_b_preview": _preview(_pick(raw, "observation_b", "observation_2")),
        "rejection_reason": _pick(raw, "rejection_reason", "reason"),
        "suggested_review_fields": {key: "" for key in (
            "final_label", "evidence_supported", "seed_relevance", "direction_correct", "context_captured",
            "mechanistic_usefulness", "comparability_correct", "candidate_type_correct", "worth_followup", "error_type", "notes")},
    }


def _score(pair: tuple[int, dict[str, Any]]) -> float:
    row = pair[1]
    for key in ("review_priority_score", "seed_neighborhood_score", "score", "anchor_score"):
        try:
            if row.get(key) is not None:
                return float(row[key])
        except (TypeError, ValueError):
            pass
    return float("-inf")


def _metric_record(bundle: Path, summaries: list[dict[str, Any]]) -> dict[str, Any]:
    case_id = _first(summaries, "case_id") or bundle.name
    aliases = {
        "abstract_reviewable_count": ("reviewable_graph_observation_count",),
        "low_priority_context_count": ("low_priority_context_observation_count",),
        "selected_fulltext_count": ("selected_fulltext_count", "discovery_selected_fulltext_count"),
        "downloaded_fulltext_count": ("downloaded_fulltext_count", "discovery_downloaded_fulltext_count"),
        "parsed_section_count": ("parsed_section_count",), "selected_chunk_count": ("selected_chunk_count",),
        "fulltext_l1_claim_count": ("fulltext_l1_claim_count", "fulltext_discovery_l1_claim_count"),
        "fulltext_claims_reentered_l2": ("fulltext_claims_reentered_l2", "fulltext_discovery_reentry_count"),
        "fulltext_reviewable_count": ("fulltext_reviewable_graph_observation_count",),
        "weak_conflict_count": ("weak_conflict_count", "weak_conflict_candidate_count"),
        "non_comparable_direction_pair_count": ("non_comparable_direction_pair_count",),
        "formal_hypothesis_count": ("formal_hypothesis_count",),
    }
    record = {"case_id": case_id, "bundle_path": str(bundle)}
    for key in ("pipeline_complete", "ready_for_system_b", "scientific_output_class", "raw_l1_claim_count", "l2_retained_observation_count"):
        record[key] = _first(summaries, key)
    for key, names in aliases.items():
        record[key] = _first(summaries, *names)
    record["review_queue_item_count"] = 0
    return record


def generate(roots: Iterable[str | Path], output_root: str | Path, *, top_reviewable: int = 20,
             random_fulltext_claims: int = 30, low_priority_context: int = 10,
             include_weak: bool = True, include_non_comparable: bool = True,
             include_hypotheses: bool = True, seed: int = 42, write_csv: bool = True,
             write_jsonl: bool = True, overwrite: bool = False) -> dict[str, Any]:
    output = Path(output_root)
    if output.exists() and any(output.iterdir()) and not overwrite:
        raise FileExistsError(f"output root is not empty: {output}; pass --overwrite")
    output.mkdir(parents=True, exist_ok=True)
    queue, metrics, sampling = [], [], []
    for bundle in discover_bundles(roots):
        summaries = [_json(bundle / name) for name in SUMMARY_FILES if (bundle / name).is_file()]
        metric = _metric_record(bundle, summaries); case_id = str(metric["case_id"])
        loaded: dict[str, list[tuple[int, dict[str, Any]]]] = {}
        missing = []
        for key, (filename, _) in SOURCES.items():
            path = bundle / filename
            if not path.is_file():
                missing.append(filename); loaded[key] = []
            else:
                loaded[key] = _jsonl(path)
        chosen = {
            "fulltext_reviewable": sorted(loaded["fulltext_reviewable"], key=lambda p: (-_score(p), p[0]))[:top_reviewable],
            "abstract_reviewable": sorted(loaded["abstract_reviewable"], key=lambda p: (-_score(p), p[0]))[:top_reviewable],
            "low_priority": sorted(loaded["low_priority"], key=lambda p: (-_score(p), p[0]))[:low_priority_context],
            "weak": loaded["weak"] if include_weak else [],
            "non_comparable": loaded["non_comparable"] if include_non_comparable else [],
            "hypotheses": loaded["hypotheses"] if include_hypotheses else [],
        }
        claims = list(loaded["fulltext_claims"])
        case_seed = seed ^ int(hashlib.sha256(case_id.encode()).hexdigest()[:16], 16)
        chosen["fulltext_claims"] = random.Random(case_seed).sample(claims, min(random_fulltext_claims, len(claims)))
        before = len(queue)
        for key in SOURCES:
            filename, item_type = SOURCES[key]
            queue.extend(review_item(case_id, bundle, item_type, filename, line, row) for line, row in chosen[key])
        metric["review_queue_item_count"] = len(queue) - before; metrics.append(metric)
        sampling.append({"case_id": case_id, "bundle_path": str(bundle),
            "available_fulltext_claims": len(loaded["fulltext_claims"]), "sampled_fulltext_claims": len(chosen["fulltext_claims"]),
            "available_fulltext_reviewable": len(loaded["fulltext_reviewable"]), "sampled_fulltext_reviewable": len(chosen["fulltext_reviewable"]),
            "available_abstract_reviewable": len(loaded["abstract_reviewable"]), "sampled_abstract_reviewable": len(chosen["abstract_reviewable"]),
            "available_low_priority_context": len(loaded["low_priority"]), "sampled_low_priority_context": len(chosen["low_priority"]),
            "available_weak_candidates": len(loaded["weak"]), "sampled_weak_candidates": len(chosen["weak"]),
            "available_non_comparable_pairs": len(loaded["non_comparable"]), "sampled_non_comparable_pairs": len(chosen["non_comparable"]),
            "available_formal_hypotheses": len(loaded["hypotheses"]), "sampled_formal_hypotheses": len(chosen["hypotheses"]), "missing_files": missing})
    _write_outputs(output, queue, metrics, sampling, write_csv, write_jsonl)
    return {"cases_discovered": len(metrics), "queue_items_total": len(queue),
            "items_by_type": dict(sorted(Counter(x["item_type"] for x in queue).items())),
            "items_by_case": dict(sorted(Counter(x["case_id"] for x in queue).items())),
            "missing_files": {x["case_id"]: x["missing_files"] for x in sampling if x["missing_files"]}}


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: Iterable[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore"); writer.writeheader(); writer.writerows(rows)


def _write_outputs(root: Path, queue: list[dict[str, Any]], metrics: list[dict[str, Any]], sampling: list[dict[str, Any]], write_csv: bool, write_jsonl: bool) -> None:
    if write_jsonl:
        (root / "manual_review_queue.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in queue), encoding="utf-8")
    flat_queue = [{key: row.get(key) for key in QUEUE_FIELDS} for row in queue]
    if write_csv:
        _write_csv(root / "manual_review_queue.csv", flat_queue, QUEUE_FIELDS)
        _write_csv(root / "manual_review_annotations_template.csv", [{**row, **{key: "" for key in ANNOTATION_FIELDS}} for row in flat_queue], QUEUE_FIELDS + ANNOTATION_FIELDS)
    (root / "review_sampling_summary.json").write_text(json.dumps({"cases": sampling}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# Review Sampling Summary", ""]
    for row in sampling:
        lines += [f"## {row['case_id']}", "", f"- Queue samples: {sum(v for k, v in row.items() if k.startswith('sampled_'))}", f"- Missing files: {', '.join(row['missing_files']) or 'none'}", ""]
    (root / "review_sampling_summary.md").write_text("\n".join(lines), encoding="utf-8")
    (root / "case_level_metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_csv(root / "case_level_metrics.csv", metrics, METRIC_FIELDS)
    total_fields = [field for field in METRIC_FIELDS if field.endswith("_count")]
    total_fields.append("fulltext_claims_reentered_l2")
    totals = {field: sum(x.get(field) or 0 for x in metrics) for field in total_fields}
    paper = {"validation_status": "AUTOMATED_COUNTS_ONLY", "total_cases": len(metrics),
             "completed_cases": sum(x.get("pipeline_complete") is True for x in metrics),
             "failed_cases": sum(x.get("pipeline_complete") is False for x in metrics), **totals,
             "review_queue_size": len(queue),
             "manual_metrics_notice": "Manual precision, direction accuracy, context capture rate, and reviewable precision@K require completed manual annotations."}
    (root / "paper_metrics_starter.json").write_text(json.dumps(paper, indent=2) + "\n", encoding="utf-8")
    labels = {"raw_l1_claim_count": "Total raw L1 claims", "abstract_reviewable_count": "Total abstract reviewable observations", "selected_fulltext_count": "Total selected fulltexts", "downloaded_fulltext_count": "Total downloaded fulltexts", "parsed_section_count": "Total parsed sections", "selected_chunk_count": "Total selected chunks", "fulltext_l1_claim_count": "Total fulltext L1 claims", "fulltext_claims_reentered_l2": "Total fulltext re-entered observations", "fulltext_reviewable_count": "Total fulltext reviewable observations", "weak_conflict_count": "Total weak candidates", "non_comparable_direction_pair_count": "Total non-comparable direction pairs", "formal_hypothesis_count": "Total formal hypotheses"}
    md = ["# Paper Metrics Starter", "", "> Automated counts only; these are not manually validated scientific results.", "", f"- Total cases: {len(metrics)}", f"- Completed cases: {paper['completed_cases']}", f"- Failed cases if detectable: {paper['failed_cases']}"]
    md += [f"- {label}: {sum(x.get(key) or 0 for x in metrics)}" for key, label in labels.items()]
    md += [f"- Review queue size: {len(queue)}", "", "Manual precision, direction accuracy, context capture rate, and reviewable precision@K require completed manual annotations.", ""]
    (root / "paper_metrics_starter.md").write_text("\n".join(md), encoding="utf-8")
