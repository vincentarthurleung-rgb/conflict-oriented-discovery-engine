"""Context prediction to frozen Gold alignment."""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from code_engine.system_b.evaluation.metric_engine import exact_match, jaccard, ranking_metrics, status_result
from code_engine.system_b.persistence.models import GoldRecord, ReviewItem

from .base import AdapterStatus, first_existing, read_jsonl

FACTORS = {
    "species", "cell_type", "tissue", "disease_subtype", "treatment", "dose",
    "duration", "genotype", "localization", "assay_method", "outcome_definition",
    "disease_stage",
}
ALIASES = {
    "time": "duration",
    "cancer_type": "disease_subtype",
    "disease_type": "disease_subtype",
    "method": "assay_method",
}
PREDICTION_FILES = ("triple_contexts.jsonl", "context_predictions.jsonl", "context_matrix.jsonl")


def normalize_factor(value: str) -> tuple[str | None, str]:
    raw = str(value or "").strip()
    mapped = ALIASES.get(raw, raw)
    if mapped in FACTORS:
        reason = "alias" if mapped != raw else "canonical"
        return mapped, reason
    return None, "unknown_factor"


def normalize_factors(values: list) -> tuple[list[str], list[dict]]:
    out = []
    mappings = []
    for value in values or []:
        mapped, reason = normalize_factor(str(value))
        mappings.append({"raw": value, "mapped": mapped, "reason": reason})
        if mapped and mapped not in out:
            out.append(mapped)
    return out, mappings


def build_context_rows(session: Session, *, project_id: str, gold_dataset_version: int, prediction_root: str | Path) -> dict:
    root = Path(prediction_root)
    prediction_path = first_existing(root, PREDICTION_FILES)
    if not prediction_path:
        return AdapterStatus("configuration_mismatch", "context_prediction_artifact_missing", {"searched": list(PREDICTION_FILES)}).to_dict()
    raw = read_jsonl(prediction_path)
    if not raw:
        return AdapterStatus("needs_annotation", "no_context_prediction_rows", {"path": str(prediction_path)}).to_dict()
    gold_rows = session.execute(select(GoldRecord).where(
        GoldRecord.project_id == project_id,
        GoldRecord.status == "frozen",
        GoldRecord.gold_dataset_version == gold_dataset_version,
        GoldRecord.schema_id == "context_attribution_v1",
    )).scalars().all()
    if not gold_rows:
        return AdapterStatus("needs_annotation", "no_frozen_context_gold").to_dict()
    pred_by_unit = {}
    for row in raw:
        unit = row.get("review_item_id") or row.get("evaluation_unit_id") or row.get("triple_id") or row.get("record_id")
        if unit and unit not in pred_by_unit:
            pred_by_unit[str(unit)] = row
    rows = []
    for gold in gold_rows:
        fields = json.loads(gold.structured_gold_json or "{}")
        pred = pred_by_unit.get(gold.review_item_id, {})
        ranked_raw = pred.get("ranked_context_factors") or pred.get("context_factors") or pred.get("factors") or []
        minimal_raw = pred.get("minimal_context_set") or ranked_raw
        ranked, ranked_map = normalize_factors(ranked_raw)
        minimal, minimal_map = normalize_factors(minimal_raw)
        gold_factors, gold_map = normalize_factors(fields.get("gold_context_factors") or [])
        gold_minimal, gold_minimal_map = normalize_factors(fields.get("minimal_context_set") or [])
        item = session.get(ReviewItem, gold.review_item_id)
        rows.append({
            "evaluation_unit_id": gold.review_item_id,
            "case_id": item.case_id if item else "",
            "review_item_id": gold.review_item_id,
            "predicted_ranked_factors": ranked,
            "predicted_minimal_context_set": minimal,
            "gold_context_factors": gold_factors,
            "gold_minimal_context_set": gold_minimal,
            "included": bool(pred) and not fields.get("insufficient_context_information"),
            "exclusion_reason": None if pred else "missing_prediction",
            "normalization": {
                "predicted_ranked": ranked_map,
                "predicted_minimal": minimal_map,
                "gold_context": gold_map,
                "gold_minimal": gold_minimal_map,
            },
        })
    return {"status": "ready", "items": rows, "prediction_artifact": str(prediction_path)}


def context_metrics(rows: list[dict]) -> dict:
    included = [row for row in rows if row.get("included")]
    if not included:
        return {"context_recall_at_3": status_result("needs_annotation", "no_included_context_rows")}
    gold = {row["evaluation_unit_id"]: set(row["gold_context_factors"]) for row in included}
    ranked = {row["evaluation_unit_id"]: row["predicted_ranked_factors"] for row in included}
    pred_sets = {row["evaluation_unit_id"]: set(row["predicted_minimal_context_set"]) for row in included}
    gold_min = {row["evaluation_unit_id"]: ",".join(sorted(row["gold_minimal_context_set"])) for row in included}
    pred_min = {row["evaluation_unit_id"]: ",".join(sorted(row["predicted_minimal_context_set"])) for row in included}
    r1 = ranking_metrics(gold, ranked, k=1)["recall_at_k"]
    r3 = ranking_metrics(gold, ranked, k=3)["recall_at_k"]
    mrr = ranking_metrics(gold, ranked, k=3)["mrr"]
    jac = jaccard(gold, pred_sets)
    exact = exact_match(gold_min, pred_min)
    over_values = []
    under_values = []
    for key, g in gold.items():
        p = pred_sets.get(key, set())
        over_values.append(len(p - g) / len(p) if p else 0.0)
        under_values.append(len(g - p) / len(g) if g else 0.0)
    return {
        "context_recall_at_1": r1,
        "context_recall_at_3": r3,
        "context_mrr": mrr,
        "context_set_jaccard": jac,
        "minimal_context_exact_match": exact,
        "over_explanation_rate": {"status": "ready", "value": sum(over_values) / len(over_values)},
        "under_explanation_rate": {"status": "ready", "value": sum(under_values) / len(under_values)},
    }
