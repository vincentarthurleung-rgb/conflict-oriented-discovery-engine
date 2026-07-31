"""Deterministic, conditional claim-evaluation sampling primitives.

The frame is restricted to text units already selected for System A L1.  It is
therefore suitable for conditional extraction evaluation, not end-to-end
discovery recall.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter
from typing import Any


FRAME_SCOPE = "selected_for_l1_extraction"
SAMPLING_PURPOSES = {"predicted_claim_precision", "source_unit_exhaustive_gold"}


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sampling_frame_hash(rows: list[dict[str, Any]]) -> str:
    material = [{key: row.get(key) for key in sorted(row) if key not in {"stratum", "inclusion_probability", "sampling_weight"}} for row in rows]
    return hashlib.sha256(_canonical(sorted(material, key=lambda row: str(row.get("source_unit_id"))))).hexdigest()


def evaluation_readiness(source_units: list[dict[str, Any]], gold_records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    gold_records = gold_records or []
    exhaustive = {row.get("source_unit_id") for row in gold_records if row.get("annotation_completeness") == "exhaustive"}
    unit_ids = {row.get("source_unit_id") for row in source_units if row.get("source_unit_id")}
    exhaustive_ready = bool(unit_ids) and unit_ids.issubset(exhaustive)
    return {
        "schema_version": "claim_evaluation_readiness_v1", "frame_scope": FRAME_SCOPE,
        "source_unit_count": len(unit_ids),
        "paper_count": len({row.get("paper_id") for row in source_units if row.get("paper_id")}),
        "case_count": len({row.get("case_id") for row in source_units if row.get("case_id")}),
        "domain_count": len({(row.get("domain_snapshot") or {}).get("domain_id") for row in source_units if (row.get("domain_snapshot") or {}).get("domain_id")}),
        "source_scope_distribution": dict(Counter(row.get("source_scope") or "unknown" for row in source_units)),
        "exhaustive_gold_unit_count": len(exhaustive & unit_ids),
        "claim_precision": {"status": "needs_annotation"},
        "claim_recall": {"status": "available" if exhaustive_ready else "needs_exhaustive_gold", "value": None},
        "claim_f1": {"status": "available" if exhaustive_ready else "needs_exhaustive_gold", "value": None},
        "conditional_only": True,
        "notice": "当前只能评估给定已选文本片段的 Claim 抽取，不能代表整篇论文端到端发现 Recall。",
    }


def sampling_frame_stats(rows: list[dict[str, Any]], *, projection: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return an operations-safe description of the live source-unit frame."""
    projection = projection or {}
    scopes = Counter(row.get("source_scope") or "unknown" for row in rows)
    sections = Counter(row.get("section_type") or "unknown" for row in rows)
    domains = Counter((row.get("domain_snapshot") or {}).get("domain_id") or "unclassified" for row in rows)
    projection_status = str(projection.get("validation_status") or projection.get("status") or "").casefold()
    frame_version = projection.get("schema_version") or "source_text_unit_frame_v1"
    if not rows:
        status = "missing"
    elif projection_status in {"invalid", "failed", "schema_unsupported", "unsupported"}:
        status = "invalid"
    elif "legacy" in str(frame_version).casefold() or projection_status == "legacy":
        status = "legacy"
    else:
        status = "current"
    return {
        "frame_scope": FRAME_SCOPE,
        "frame_hash": sampling_frame_hash(rows) if rows else "",
        "frame_version": frame_version,
        "projection_id": projection.get("projection_id") or "",
        "generated_from": projection.get("generated_from") or "current_projection",
        "adapter_version": projection.get("adapter_version") or "",
        "artifact_hash": projection.get("artifact_hash") or projection.get("projection_manifest_sha256") or "",
        "status": status,
        "supported": bool(rows) and status == "current",
        "source_unit_count": len({row.get("source_unit_id") for row in rows if row.get("source_unit_id")}),
        "predicted_claim_count": sum(int(row.get("predicted_claim_count") or 0) for row in rows),
        "paper_count": len({row.get("paper_id") for row in rows if row.get("paper_id")}),
        "case_count": len({row.get("case_id") for row in rows if row.get("case_id")}),
        "domain_count": len(domains),
        "source_scope_distribution": dict(scopes),
        "section_type_distribution": dict(sections),
        "domain_distribution": dict(domains),
        "conditional_only": True,
        "notice": "抽样框仅包含 selected_for_l1_extraction，不代表完整论文端到端 Claim Discovery Recall。",
    }


def _eligible_rows(
    rows: list[dict[str, Any]],
    *,
    domain_ids: list[str] | None,
    source_scopes: list[str] | None,
    section_types: list[str] | None,
    relation_types: list[str] | None = None,
    confidence_bands: list[str] | None = None,
    exclusions: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    domain_set, scope_set, section_set = set(domain_ids or []), set(source_scopes or []), set(section_types or [])
    relation_set, confidence_set = set(relation_types or []), set(confidence_bands or [])
    exclusions = exclusions or {}
    excluded: Counter[str] = Counter()
    unique_ids: set[str] = set()
    unique_hashes: set[str] = set()
    eligible: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda value: str(value.get("source_unit_id") or "")):
        if domain_set and (row.get("domain_snapshot") or {}).get("domain_id") not in domain_set:
            excluded["outside_domain_filter"] += 1
            continue
        if scope_set and row.get("source_scope") not in scope_set:
            excluded["outside_scope_filter"] += 1
            continue
        if section_set and row.get("section_type") not in section_set:
            excluded["outside_section_filter"] += 1
            continue
        if relation_set and row.get("relation_type") not in relation_set:
            excluded["outside_relation_filter"] += 1
            continue
        if confidence_set and row.get("confidence_band") not in confidence_set:
            excluded["outside_confidence_filter"] += 1
            continue
        unit_id = str(row.get("source_unit_id") or "")
        text_hash = str(row.get("text_hash") or "")
        if not unit_id:
            excluded["missing_source_unit_id"] += 1
            continue
        if exclusions.get("exclude_annotated", True) and row.get("annotation_status") in {"submitted", "completed", "gold"}:
            excluded["already_annotated"] += 1
            continue
        if exclusions.get("exclude_no_text", False) and not str(row.get("text") or row.get("text_excerpt") or row.get("evidence_sentence") or "").strip():
            excluded["missing_text"] += 1
            continue
        if exclusions.get("exclude_unsupported_schema", True) and row.get("schema_supported") is False:
            excluded["unsupported_schema"] += 1
            continue
        if exclusions.get("exclude_inactive_case", True) and row.get("case_active") is False:
            excluded["inactive_case"] += 1
            continue
        if exclusions.get("exclude_legacy_invalid", True) and row.get("legacy_invalid") is True:
            excluded["legacy_invalid"] += 1
            continue
        if exclusions.get("exclude_duplicate_source_unit", True) and unit_id in unique_ids:
            excluded["duplicate_source_unit_id"] += 1
            continue
        if exclusions.get("exclude_duplicate_text_hash", True) and text_hash and text_hash in unique_hashes:
            excluded["duplicate_text_hash"] += 1
            continue
        unique_ids.add(unit_id)
        if text_hash:
            unique_hashes.add(text_hash)
        eligible.append(row)
    return eligible, dict(excluded)


def _distribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "domains": dict(Counter((row.get("domain_snapshot") or {}).get("domain_id") or "unclassified" for row in rows)),
        "cases": dict(Counter(row.get("case_id") or "unknown" for row in rows)),
        "papers": dict(Counter(row.get("paper_id") or "unknown" for row in rows)),
        "source_scopes": dict(Counter(row.get("source_scope") or "unknown" for row in rows)),
        "section_types": dict(Counter(row.get("section_type") or "unknown" for row in rows)),
        "relation_types": dict(Counter(row.get("relation_type") or "unknown" for row in rows)),
        "confidence_bands": dict(Counter(row.get("confidence_band") or "unknown" for row in rows)),
    }


def preview_sample(rows: list[dict[str, Any]], *, configuration: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic, read-only sample preview with explainable coverage."""
    purpose = configuration.get("purpose") or "source_unit_exhaustive_gold"
    if purpose not in SAMPLING_PURPOSES:
        raise ValueError("unsupported_sampling_purpose")
    sample_size = int(configuration.get("sample_size") or 0)
    seed = int(configuration.get("random_seed") or 0)
    if sample_size < 1:
        raise ValueError("sample_size_must_be_positive")
    purpose_rows = rows
    if purpose == "predicted_claim_precision":
        purpose_rows = [row for row in rows if int(row.get("predicted_claim_count") or 0) > 0]
    eligible, excluded = _eligible_rows(
        purpose_rows,
        domain_ids=configuration.get("domain_ids"),
        source_scopes=configuration.get("source_scopes"),
        section_types=configuration.get("section_types"),
        relation_types=configuration.get("relation_types"),
        confidence_bands=configuration.get("confidence_bands"),
        exclusions=configuration.get("exclusions"),
    )
    rng = random.Random(seed)
    shuffled = list(eligible)
    rng.shuffle(shuffled)
    paper_cap = max(0, int(configuration.get("max_per_paper") or 0))
    case_cap = max(0, int(configuration.get("max_per_case") or 0))
    case_minimum = max(0, int(configuration.get("min_per_case") or 0))
    domain_minimum = max(0, int(configuration.get("min_per_domain") or 0))
    abstract_min_ratio = min(1.0, max(0.0, float(configuration.get("min_abstract_ratio") or 0)))
    fulltext_min_ratio = min(1.0, max(0.0, float(configuration.get("min_fulltext_ratio") or 0)))
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    paper_counts: Counter[str] = Counter()
    case_counts: Counter[str] = Counter()

    def take(row: dict[str, Any]) -> bool:
        unit_id = str(row.get("source_unit_id"))
        paper = str(row.get("paper_id") or "unknown")
        case = str(row.get("case_id") or "unknown")
        if unit_id in selected_ids or (paper_cap and paper_counts[paper] >= paper_cap) or (case_cap and case_counts[case] >= case_cap) or len(selected) >= sample_size:
            return False
        selected.append(row)
        selected_ids.add(unit_id)
        paper_counts[paper] += 1
        case_counts[case] += 1
        return True

    def satisfy(key, minimum):
        if not minimum:
            return
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in shuffled:
            value = key(row)
            groups.setdefault(value, []).append(row)
        for value in sorted(groups):
            current = sum(key(row) == value for row in selected)
            for row in groups[value]:
                if current >= minimum or len(selected) >= sample_size:
                    break
                if take(row):
                    current += 1

    satisfy(lambda row: str((row.get("domain_snapshot") or {}).get("domain_id") or "unclassified"), domain_minimum)
    satisfy(lambda row: str(row.get("case_id") or "unknown"), case_minimum)
    def satisfy_scope(scope: str, target: int):
        current = sum(row.get("source_scope") == scope for row in selected)
        for row in shuffled:
            if current >= target or len(selected) >= sample_size:
                break
            if row.get("source_scope") == scope and take(row):
                current += 1
    satisfy_scope("abstract", int(math.ceil(sample_size * abstract_min_ratio)))
    satisfy_scope("fulltext", int(math.ceil(sample_size * fulltext_min_ratio)))
    for row in shuffled:
        take(row)
    selected = sorted(selected, key=lambda row: str(row.get("source_unit_id")))
    population_distribution = _distribution(eligible)
    sample_distribution = _distribution(selected)
    frame_hash = sampling_frame_hash(rows)
    canonical_config = {
        "purpose": purpose,
        "sample_size": sample_size,
        "random_seed": seed,
        "domain_ids": sorted(configuration.get("domain_ids") or []),
        "source_scopes": sorted(configuration.get("source_scopes") or []),
        "section_types": sorted(configuration.get("section_types") or []),
        "relation_types": sorted(configuration.get("relation_types") or []),
        "confidence_bands": sorted(configuration.get("confidence_bands") or []),
        "min_per_domain": domain_minimum,
        "min_per_case": case_minimum,
        "max_per_case": case_cap,
        "max_per_paper": paper_cap,
        "min_abstract_ratio": abstract_min_ratio,
        "min_fulltext_ratio": fulltext_min_ratio,
        "exclusions": configuration.get("exclusions") or {},
    }
    config_hash = hashlib.sha256(_canonical(canonical_config)).hexdigest()
    blockers = []
    if not rows:
        blockers.append({"code": "sampling_frame_missing", "message": "当前没有可用的 Sampling Frame。"})
    if purpose == "predicted_claim_precision" and not purpose_rows:
        blockers.append({"code": "predicted_claim_frame_empty", "message": "当前 Frame 没有可用于精度审核的预测 Claim。"})
    if not eligible:
        blockers.append({"code": "no_eligible_source_units", "message": "排除规则后没有可抽样的源文本单元。"})
    if len(selected) < sample_size:
        blockers.append({"code": "sample_constraints_unsatisfied", "message": f"配置要求 {sample_size} 条，但当前只能选择 {len(selected)} 条。"})
    for label, distribution, minimum in (
        ("Domain", sample_distribution["domains"], domain_minimum),
        ("Case", sample_distribution["cases"], case_minimum),
    ):
        if minimum and any(distribution.get(key, 0) < minimum for key in population_distribution[label.lower() + "s"]):
            blockers.append({"code": f"min_per_{label.lower()}_unsatisfied", "message": f"无法满足每个 {label} 至少 {minimum} 条。"})
    for scope, ratio in (("abstract", abstract_min_ratio), ("fulltext", fulltext_min_ratio)):
        required = int(math.ceil(sample_size * ratio))
        if sample_distribution["source_scopes"].get(scope, 0) < required:
            blockers.append({"code": f"min_{scope}_ratio_unsatisfied", "message": f"无法满足 {scope} 最低比例 {round(ratio * 100)}%。"})
    uncovered_cases = sorted(set(population_distribution["cases"]) - set(sample_distribution["cases"]))
    warnings = []
    if uncovered_cases:
        warnings.append({"code": "cases_not_covered", "message": f"{len(uncovered_cases)} 个 Case 未覆盖。"})
    inclusion_probability = len(selected) / len(eligible) if eligible else None
    units = [{
        "source_unit_id": row.get("source_unit_id"),
        "review_item_id": row.get("review_item_id") or row.get("source_unit_id"),
        "case_id": row.get("case_id"),
        "domain_id": (row.get("domain_snapshot") or {}).get("domain_id") or "unclassified",
        "paper_id": row.get("paper_id"),
        "source_scope": row.get("source_scope"),
        "section_type": row.get("section_type"),
        "relation_type": row.get("relation_type"),
        "confidence_band": row.get("confidence_band"),
        "stratum": "|".join([
            str((row.get("domain_snapshot") or {}).get("domain_id") or "unclassified"),
            str(row.get("case_id") or "unknown"),
            str(row.get("source_scope") or "unknown"),
        ]),
        "inclusion_probability": inclusion_probability,
        "domain_snapshot": row.get("domain_snapshot") or {},
        "source_artifact_hash": row.get("source_artifact_hash") or row.get("source_hash") or "",
        "text_excerpt": str(row.get("text_excerpt") or row.get("text") or row.get("evidence_sentence") or "")[:180],
    } for row in selected]
    return {
        "schema_version": "predicted_claim_precision_cluster_sample_v1" if purpose == "predicted_claim_precision" else "source_unit_exhaustive_gold_sample_v1",
        "sampling_unit": "source_unit_cluster_with_predicted_claims" if purpose == "predicted_claim_precision" else "source_unit",
        "purpose": purpose,
        "frame_scope": FRAME_SCOPE,
        "frame_hash": frame_hash,
        "configuration_hash": config_hash,
        "random_seed": seed,
        "requested_sample_size": sample_size,
        "population_size": len(eligible),
        "sample_size": len(selected),
        "population_distribution": population_distribution,
        "sample_distribution": sample_distribution,
        "excluded_breakdown": excluded,
        "coverage": {
            "papers": len(sample_distribution["papers"]),
            "cases": len(sample_distribution["cases"]),
            "domains": len(sample_distribution["domains"]),
            "abstract": sample_distribution["source_scopes"].get("abstract", 0),
            "fulltext": sample_distribution["source_scopes"].get("fulltext", 0),
            "uncovered_cases": uncovered_cases,
            "max_paper_share": round(max(sample_distribution["papers"].values(), default=0) / len(selected), 6) if selected else None,
            "max_case_share": round(max(sample_distribution["cases"].values(), default=0) / len(selected), 6) if selected else None,
            "duplicate_source_unit_ids": 0,
            "duplicate_text_hashes": 0,
        },
        "units": units,
        "blockers": blockers,
        "warnings": warnings,
        "blocked": bool(blockers),
        "metric_readiness": {
            "claim_precision": {"status": "needs_annotation", "value": None},
            "claim_recall": {"status": "not_supported_by_precision_sample" if purpose == "predicted_claim_precision" else "needs_exhaustive_gold", "value": None},
            "claim_f1": {"status": "not_supported_by_precision_sample" if purpose == "predicted_claim_precision" else "needs_exhaustive_gold", "value": None},
        },
        "configuration": canonical_config,
        "preview_writes_database": False,
    }


def create_pilot_sample(
    rows: list[dict[str, Any]], *, sample_size: int, random_seed: int,
    domain_ids: list[str] | None = None, source_scopes: list[str] | None = None,
    section_types: list[str] | None = None,
) -> dict[str, Any]:
    if sample_size < 1:
        raise ValueError("sample_size must be positive")
    domain_set = set(domain_ids or [])
    scope_set = set(source_scopes or [])
    section_set = set(section_types or [])
    filtered = [row for row in rows if (
        (not domain_set or (row.get("domain_snapshot") or {}).get("domain_id") in domain_set)
        and (not scope_set or row.get("source_scope") in scope_set)
        and (not section_set or row.get("section_type") in section_set)
    )]
    unique: dict[str, dict[str, Any]] = {}
    duplicates = []
    for row in filtered:
        key = str(row.get("source_unit_id") or "")
        if not key:
            continue
        if key in unique:
            duplicates.append(key)
        else:
            unique[key] = row
    population = sorted(unique.values(), key=lambda row: str(row.get("source_unit_id")))
    n = min(sample_size, len(population))
    rng = random.Random(random_seed)
    selected = rng.sample(population, n) if n else []
    probability = n / len(population) if population else None
    weight = 1 / probability if probability else None
    units = [{**row, "inclusion_probability": probability, "sampling_weight": weight} for row in sorted(selected, key=lambda row: str(row.get("source_unit_id")))]
    text_hash_counts = Counter(row.get("text_hash") for row in units if row.get("text_hash"))
    overlapping_text_hashes = sorted(key for key, count in text_hash_counts.items() if count > 1)
    return {
        "schema_version": "claim_evaluation_pilot_sample_v1", "random_seed": random_seed,
        "frame_hash": sampling_frame_hash(rows), "frame_scope": FRAME_SCOPE,
        "requested_sample_size": sample_size, "population_size": len(population), "sample_size": n,
        "filters": {"domain_ids": sorted(domain_set), "source_scopes": sorted(scope_set), "section_types": sorted(section_set)},
        "units": units,
        "preview": {
            "unique_source_units": len({row.get("source_unit_id") for row in units}),
            "unique_papers": len({row.get("paper_id") for row in units if row.get("paper_id")}),
            "unique_cases": len({row.get("case_id") for row in units if row.get("case_id")}),
            "domain_distribution": dict(Counter((row.get("domain_snapshot") or {}).get("domain_id") or "unclassified" for row in units)),
            "expected_sampling_weight": weight,
            "duplicate_source_unit_ids": sorted(set(duplicates)),
            "overlapping_text_hashes": overlapping_text_hashes,
            "overlap_warning": bool(duplicates or overlapping_text_hashes),
        },
    }
