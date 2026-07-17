"""Deterministic, conditional claim-evaluation sampling primitives.

The frame is restricted to text units already selected for System A L1.  It is
therefore suitable for conditional extraction evaluation, not end-to-end
discovery recall.
"""
from __future__ import annotations

import hashlib
import json
import random
from collections import Counter
from typing import Any


FRAME_SCOPE = "selected_for_l1_extraction"


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
