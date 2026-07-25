"""Deterministic projection of explicit historical factors."""
from __future__ import annotations

from typing import Any


def explicit_factor_candidates(source: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(source.get("experimental_factors") or []):
        if isinstance(item, dict):
            rows.append({**item, "_source": "experimental_factors", "_order": index})
    for index, item in enumerate(source.get("interventions") or []):
        if isinstance(item, dict):
            rows.append({**item, "_source": "interventions", "_order": index})
    experiment = source.get("experiment") if isinstance(source.get("experiment"), dict) else {}
    for key, role in (
        ("control_arm_raw", "control"), ("comparison_arm_raw", "comparator"),
        ("cohort_raw", "cohort"),
    ):
        value = experiment.get(key)
        if value:
            rows.append({
                "local_factor_id": f"{role}_{len(rows)}",
                "role": role, "raw_text": str(value), "extracted_value": value,
                "evidence_span_ids": [], "_source": f"experiment.{key}", "_order": len(rows),
            })
    return rows


def role_for(item: dict[str, Any]) -> str:
    role = item.get("role")
    if role in {
        "intervention", "treatment", "exposure", "genetic_manipulation",
        "environmental_condition", "disease_condition", "cohort",
        "experimental_group", "control", "comparator", "baseline",
        "sample_condition", "unresolved",
    }:
        return str(role)
    kind = str(item.get("intervention_type") or item.get("intervention_type_raw") or "").lower()
    return {
        "treatment": "treatment", "drug": "treatment", "exposure": "exposure",
        "knockout": "genetic_manipulation", "knockdown": "genetic_manipulation",
        "overexpression": "genetic_manipulation",
    }.get(kind, "intervention" if item.get("_source") == "interventions" else "unresolved")
