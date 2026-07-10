"""Small deterministic metric engine for frozen-Gold evaluation."""
from __future__ import annotations

from collections import Counter


def _status_missing(gold, predictions):
    if not gold:
        return {"status": "needs_adjudication", "missing_reason": "no_frozen_gold_records", "value": None}
    if not predictions:
        return {"status": "needs_annotation", "missing_reason": "no_predictions", "value": None}
    return None


def classification_metrics(gold: dict[str, str], predictions: dict[str, str], positive_labels: set[str] | None = None) -> dict:
    missing = _status_missing(gold, predictions)
    if missing:
        return {"precision": missing, "recall": missing, "f1": missing}
    labels = sorted(set(gold.values()) | set(predictions.values()))
    positive = positive_labels or set(labels)
    tp = sum(1 for k, g in gold.items() if predictions.get(k) == g and g in positive)
    fp = sum(1 for k, p in predictions.items() if k in gold and p != gold[k] and p in positive)
    fn = sum(1 for k, g in gold.items() if predictions.get(k) != g and g in positive)
    tn = sum(1 for k, g in gold.items() if predictions.get(k) == g and g not in positive)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else None
    accuracy = sum(1 for k, g in gold.items() if predictions.get(k) == g) / len(gold)
    specificity = tn / (tn + fp) if tn + fp else None
    return {
        "precision": {"status": "ready", "value": precision, "numerator": tp, "denominator": tp + fp},
        "recall": {"status": "ready", "value": recall, "numerator": tp, "denominator": tp + fn},
        "f1": {"status": "ready", "value": f1},
        "accuracy": {"status": "ready", "value": accuracy},
        "specificity": {"status": "ready", "value": specificity},
        "false_positive_rate": {"status": "ready", "value": 1 - specificity if specificity is not None else None},
        "false_negative_rate": {"status": "ready", "value": 1 - recall if recall is not None else None},
    }


def macro_micro_f1(gold: dict[str, str], predictions: dict[str, str]) -> dict:
    missing = _status_missing(gold, predictions)
    if missing:
        return {"macro_f1": missing, "micro_f1": missing, "weighted_f1": missing}
    labels = sorted(set(gold.values()) | set(predictions.values()))
    per_label = {}
    total_weight = 0
    weighted_sum = 0.0
    for label in labels:
        metrics = classification_metrics(gold, predictions, {label})
        f1 = metrics["f1"]["value"]
        support = sum(1 for v in gold.values() if v == label)
        per_label[label] = f1
        if f1 is not None:
            weighted_sum += f1 * support
            total_weight += support
    macro_values = [x for x in per_label.values() if x is not None]
    micro = classification_metrics(gold, predictions, set(labels))["f1"]["value"]
    return {
        "macro_f1": {"status": "ready", "value": sum(macro_values) / len(macro_values) if macro_values else None},
        "micro_f1": {"status": "ready", "value": micro},
        "weighted_f1": {"status": "ready", "value": weighted_sum / total_weight if total_weight else None},
        "per_label_f1": per_label,
    }


def cohen_kappa(labels_a: dict[str, str], labels_b: dict[str, str]) -> dict:
    common = sorted(set(labels_a) & set(labels_b))
    if not common:
        return {"status": "insufficient_sample", "missing_reason": "no_common_items", "value": None}
    observed = sum(1 for key in common if labels_a[key] == labels_b[key]) / len(common)
    ca = Counter(labels_a[key] for key in common)
    cb = Counter(labels_b[key] for key in common)
    expected = sum((ca[label] / len(common)) * (cb[label] / len(common)) for label in set(ca) | set(cb))
    value = (observed - expected) / (1 - expected) if expected != 1 else None
    return {"status": "ready", "value": value, "observed_agreement": observed, "expected_agreement": expected, "sample_size_items": len(common)}
