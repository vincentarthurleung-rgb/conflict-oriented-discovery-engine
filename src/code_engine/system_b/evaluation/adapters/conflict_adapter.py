"""Conflict prediction to frozen Gold alignment."""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from code_engine.system_b.evaluation.metric_engine import classification_metrics, macro_micro_f1, status_result
from code_engine.system_b.persistence.models import GoldRecord, ReviewItem

from .base import AdapterStatus, first_existing, read_jsonl

GOLD_LABELS = {
    "true_conflict",
    "same_sign_non_conflict",
    "different_context_non_comparable",
    "association_not_causal",
    "expression_state_not_causal",
    "duplicate_evidence",
    "insufficient_information",
}
PREDICTION_FILES = ("conflict_lens_records.jsonl", "weak_conflict_candidates.jsonl", "non_comparable_pairs.jsonl")


def gold_conflict_label(record: GoldRecord) -> str:
    fields = json.loads(record.structured_gold_json or "{}")
    if fields.get("true_conflict") is True or record.final_gold_label == "true_conflict":
        return "true_conflict"
    reason = fields.get("non_conflict_reason") or record.final_gold_label
    return reason if reason in GOLD_LABELS else "insufficient_information"


def prediction_conflict_label(row: dict) -> str:
    if row.get("true_conflict") is True or row.get("predicted_label") == "true_conflict":
        return "true_conflict"
    if row.get("comparability_label") == "non_comparable" or row.get("record_type") == "non_comparable_direction_pair":
        return "different_context_non_comparable"
    if row.get("duplicate_evidence") is True:
        return "duplicate_evidence"
    if row.get("record_type") in {"weak_candidate", "context_split", "formal_hypothesis"}:
        return "true_conflict"
    return "insufficient_information"


def build_conflict_rows(session: Session, *, project_id: str, gold_dataset_version: int, prediction_root: str | Path) -> dict:
    root = Path(prediction_root)
    prediction_path = first_existing(root, PREDICTION_FILES)
    if not prediction_path:
        return AdapterStatus("configuration_mismatch", "prediction_artifact_missing", {"searched": list(PREDICTION_FILES)}).to_dict()
    predictions_raw = read_jsonl(prediction_path)
    if not predictions_raw:
        return AdapterStatus("needs_annotation", "no_prediction_rows", {"path": str(prediction_path)}).to_dict()
    gold_rows = session.execute(select(GoldRecord).where(
        GoldRecord.project_id == project_id,
        GoldRecord.status == "frozen",
        GoldRecord.gold_dataset_version == gold_dataset_version,
        GoldRecord.schema_id == "conflict_pair_v1",
    )).scalars().all()
    if not gold_rows:
        return AdapterStatus("needs_annotation", "no_frozen_conflict_gold").to_dict()
    pred_by_unit = {}
    for row in predictions_raw:
        unit = row.get("review_item_id") or row.get("evaluation_unit_id") or row.get("record_id") or row.get("pair_id")
        if not unit or unit in pred_by_unit:
            continue
        pred_by_unit[str(unit)] = row
    rows = []
    seen_pairs = set()
    for gold in gold_rows:
        item = session.get(ReviewItem, gold.review_item_id)
        source_hash = item.source_hash if item else ""
        pred = pred_by_unit.get(gold.review_item_id)
        gold_label = gold_conflict_label(gold)
        if gold_label == "insufficient_information":
            included = False
            exclusion_reason = "gold_insufficient_information"
        elif not pred:
            included = False
            exclusion_reason = "missing_prediction"
        elif pred.get("source_hash") and source_hash and pred.get("source_hash") != source_hash:
            included = False
            exclusion_reason = "source_hash_mismatch"
        elif gold.review_item_id in seen_pairs:
            included = False
            exclusion_reason = "duplicate_evaluation_unit"
        else:
            included = True
            exclusion_reason = None
        seen_pairs.add(gold.review_item_id)
        rows.append({
            "evaluation_unit_id": gold.review_item_id,
            "case_id": item.case_id if item else "",
            "review_item_id": gold.review_item_id,
            "prediction_run_id": prediction_path.name,
            "predicted_label": prediction_conflict_label(pred or {}),
            "predicted_conflict_type": (pred or {}).get("conflict_type"),
            "predicted_comparable": prediction_conflict_label(pred or {}) != "different_context_non_comparable",
            "gold_label": gold_label,
            "gold_conflict_type": json.loads(gold.structured_gold_json or "{}").get("conflict_type"),
            "included": included,
            "exclusion_reason": exclusion_reason,
            "prediction_provenance": {"path": str(prediction_path), "record_id": (pred or {}).get("record_id")},
            "gold_provenance": {"gold_record_id": gold.gold_record_id, "gold_dataset_version": gold.gold_dataset_version, "candidate_revision": gold.candidate_revision},
        })
    return {"status": "ready", "items": rows, "prediction_artifact": str(prediction_path)}


def conflict_metrics(rows: list[dict]) -> dict:
    included = [row for row in rows if row.get("included")]
    if not included:
        return {"conflict_precision": status_result("needs_annotation", "no_included_conflict_rows")}
    gold = {row["evaluation_unit_id"]: row["gold_label"] for row in included}
    pred = {row["evaluation_unit_id"]: row["predicted_label"] for row in included}
    base = classification_metrics(gold, pred, {"true_conflict"})
    f1s = macro_micro_f1(gold, pred)
    return {
        "conflict_precision": base["precision"],
        "conflict_recall": base["recall"],
        "conflict_f1": base["f1"],
        "conflict_macro_f1": f1s["macro_f1"],
        "conflict_micro_f1": f1s["micro_f1"],
        "false_conflict_rate": base["false_positive_rate"],
        "missed_conflict_rate": base["false_negative_rate"],
        "conflict_auprc": status_result("not_applicable", "no_continuous_conflict_score"),
    }
