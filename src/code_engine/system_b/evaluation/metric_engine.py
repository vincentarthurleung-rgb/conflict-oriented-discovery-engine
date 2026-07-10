"""Deterministic metric registry and first-pass paper evaluation metrics."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, asdict
import math
import random


@dataclass(frozen=True)
class MetricSpec:
    metric_id: str
    formula_version: str
    required_inputs: tuple[str, ...]
    aggregation: str
    sample_unit: str
    missing_policy: str
    bootstrap_policy: str
    higher_is_better: bool = True


METRIC_REGISTRY: dict[str, MetricSpec] = {
    "precision": MetricSpec("precision", "v1", ("gold", "predictions"), "micro", "item", "status", "case_cluster"),
    "recall": MetricSpec("recall", "v1", ("gold", "predictions"), "micro", "item", "status", "case_cluster"),
    "f1": MetricSpec("f1", "v1", ("gold", "predictions"), "micro", "item", "status", "case_cluster"),
    "accuracy": MetricSpec("accuracy", "v1", ("gold", "predictions"), "micro", "item", "status", "case_cluster"),
    "specificity": MetricSpec("specificity", "v1", ("gold", "predictions"), "micro", "item", "status", "case_cluster"),
    "false_positive_rate": MetricSpec("false_positive_rate", "v1", ("gold", "predictions"), "micro", "item", "status", "case_cluster", False),
    "false_negative_rate": MetricSpec("false_negative_rate", "v1", ("gold", "predictions"), "micro", "item", "status", "case_cluster", False),
    "macro_f1": MetricSpec("macro_f1", "v1", ("gold", "predictions"), "macro", "item", "status", "case_cluster"),
    "micro_f1": MetricSpec("micro_f1", "v1", ("gold", "predictions"), "micro", "item", "status", "case_cluster"),
    "weighted_f1": MetricSpec("weighted_f1", "v1", ("gold", "predictions"), "weighted", "item", "status", "case_cluster"),
    "exact_match": MetricSpec("exact_match", "v1", ("gold", "predictions"), "mean", "item", "status", "case_cluster"),
    "jaccard": MetricSpec("jaccard", "v1", ("gold_sets", "prediction_sets"), "mean", "item", "status", "case_cluster"),
    "precision_at_k": MetricSpec("precision_at_k", "v1", ("gold_sets", "ranked_predictions"), "mean", "case", "status", "case_cluster"),
    "recall_at_k": MetricSpec("recall_at_k", "v1", ("gold_sets", "ranked_predictions"), "mean", "case", "status", "case_cluster"),
    "mrr": MetricSpec("mrr", "v1", ("gold_sets", "ranked_predictions"), "mean", "case", "status", "case_cluster"),
    "cohen_kappa": MetricSpec("cohen_kappa", "v1", ("labels_a", "labels_b"), "global", "item", "insufficient_sample", "case_cluster"),
    "fleiss_kappa": MetricSpec("fleiss_kappa", "v1", ("ratings"), "global", "item", "insufficient_sample", "case_cluster"),
    "krippendorff_alpha": MetricSpec("krippendorff_alpha", "v1", ("ratings"), "global", "item", "insufficient_sample", "case_cluster"),
    "weighted_kappa": MetricSpec("weighted_kappa", "v1", ("labels_a", "labels_b"), "global", "item", "insufficient_sample", "case_cluster"),
    "icc": MetricSpec("icc", "v1", ("numeric_ratings"), "global", "item", "insufficient_sample", "case_cluster"),
    "exact_agreement": MetricSpec("exact_agreement", "v1", ("labels_a", "labels_b"), "mean", "item", "insufficient_sample", "case_cluster"),
    "field_agreement": MetricSpec("field_agreement", "v1", ("fields_a", "fields_b"), "mean", "item", "insufficient_sample", "case_cluster"),
    "adjudication_rate": MetricSpec("adjudication_rate", "v1", ("agreement_statuses",), "mean", "item", "status", "case_cluster", False),
}


def registry_payload() -> list[dict]:
    return [asdict(METRIC_REGISTRY[key]) for key in sorted(METRIC_REGISTRY)]


def _status_missing(gold, predictions):
    if not gold:
        return {"status": "needs_adjudication", "missing_reason": "no_frozen_gold_records", "value": None}
    if not predictions:
        return {"status": "needs_annotation", "missing_reason": "no_predictions", "value": None}
    return None


def status_result(status: str, reason: str) -> dict:
    return {"status": status, "missing_reason": reason, "value": None}


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


def exact_match(gold: dict[str, str], predictions: dict[str, str]) -> dict:
    missing = _status_missing(gold, predictions)
    if missing:
        return missing
    common = [key for key in gold if key in predictions]
    if not common:
        return status_result("needs_annotation", "no_overlapping_predictions")
    hits = sum(1 for key in common if gold[key] == predictions[key])
    return {"status": "ready", "value": hits / len(common), "numerator": hits, "denominator": len(common)}


def jaccard(gold_sets: dict[str, set], prediction_sets: dict[str, set]) -> dict:
    if not gold_sets:
        return status_result("needs_annotation", "no_gold_sets")
    values = []
    for key, gold in gold_sets.items():
        pred = prediction_sets.get(key, set())
        union = set(gold) | set(pred)
        values.append((len(set(gold) & set(pred)) / len(union)) if union else 1.0)
    return {"status": "ready", "value": sum(values) / len(values), "sample_size_items": len(values)}


def ranking_metrics(gold_sets: dict[str, set], ranked_predictions: dict[str, list], *, k: int = 5) -> dict:
    if not gold_sets:
        missing = status_result("needs_annotation", "no_gold_sets")
        return {"precision_at_k": missing, "recall_at_k": missing, "mrr": missing}
    p_values = []
    r_values = []
    rr_values = []
    for key, gold in gold_sets.items():
        gold = set(gold)
        ranked = list(ranked_predictions.get(key, []))[:k]
        hits = [idx for idx, value in enumerate(ranked, start=1) if value in gold]
        p_values.append(len(hits) / k if k else None)
        r_values.append(len(set(ranked) & gold) / len(gold) if gold else None)
        rr_values.append(1 / hits[0] if hits else 0.0)
    return {
        "precision_at_k": {"status": "ready", "value": sum(p_values) / len(p_values), "k": k},
        "recall_at_k": {"status": "ready", "value": sum(r_values) / len(r_values), "k": k},
        "mrr": {"status": "ready", "value": sum(rr_values) / len(rr_values), "k": k},
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


def exact_agreement(labels_a: dict[str, str], labels_b: dict[str, str]) -> dict:
    common = sorted(set(labels_a) & set(labels_b))
    if not common:
        return status_result("insufficient_sample", "no_common_items")
    hits = sum(1 for key in common if labels_a[key] == labels_b[key])
    return {"status": "ready", "value": hits / len(common), "numerator": hits, "denominator": len(common)}


def weighted_kappa(labels_a: dict[str, str], labels_b: dict[str, str], weights: dict[tuple[str, str], float] | None = None) -> dict:
    common = sorted(set(labels_a) & set(labels_b))
    if len(common) < 2:
        return status_result("insufficient_sample", "need_at_least_two_items")
    labels = sorted(set(labels_a.values()) | set(labels_b.values()))
    weights = weights or {(a, b): (0.0 if a == b else 1.0) for a in labels for b in labels}
    observed = sum(weights[(labels_a[k], labels_b[k])] for k in common) / len(common)
    ca = Counter(labels_a[k] for k in common)
    cb = Counter(labels_b[k] for k in common)
    expected = sum(weights[(a, b)] * ca[a] * cb[b] for a in labels for b in labels) / (len(common) ** 2)
    value = 1 - observed / expected if expected else None
    return {"status": "ready", "value": value, "observed_weighted_disagreement": observed, "expected_weighted_disagreement": expected}


def fleiss_kappa(ratings: dict[str, list[str]]) -> dict:
    if not ratings:
        return status_result("insufficient_sample", "no_ratings")
    n = len(next(iter(ratings.values())))
    if n < 2 or any(len(v) != n for v in ratings.values()):
        return status_result("configuration_mismatch", "unequal_rater_counts")
    labels = sorted({label for values in ratings.values() for label in values})
    if not labels:
        return status_result("insufficient_sample", "no_labels")
    p_i = []
    label_totals = Counter()
    for values in ratings.values():
        counts = Counter(values)
        label_totals.update(counts)
        p_i.append((sum(c * c for c in counts.values()) - n) / (n * (n - 1)))
    p_bar = sum(p_i) / len(p_i)
    total = len(ratings) * n
    p_e = sum((label_totals[label] / total) ** 2 for label in labels)
    value = (p_bar - p_e) / (1 - p_e) if p_e != 1 else None
    return {"status": "ready", "value": value, "observed_agreement": p_bar, "expected_agreement": p_e}


def krippendorff_alpha(ratings: dict[str, list[str]]) -> dict:
    # Nominal alpha; equivalent disagreement formulation with missing labels removed.
    cleaned = {k: [x for x in v if x is not None] for k, v in ratings.items()}
    cleaned = {k: v for k, v in cleaned.items() if len(v) >= 2}
    if not cleaned:
        return status_result("insufficient_sample", "need_two_ratings_per_item")
    labels = sorted({x for values in cleaned.values() for x in values})
    total_pairs = 0
    observed_disagreement = 0
    marginals = Counter()
    for values in cleaned.values():
        marginals.update(values)
        for i, a in enumerate(values):
            for b in values[i + 1:]:
                total_pairs += 1
                observed_disagreement += 0 if a == b else 1
    do = observed_disagreement / total_pairs if total_pairs else None
    n = sum(marginals.values())
    de_num = sum(marginals[a] * marginals[b] for a in labels for b in labels if a != b)
    de = de_num / (n * (n - 1)) if n > 1 else None
    value = 1 - do / de if do is not None and de else None
    return {"status": "ready", "value": value, "observed_disagreement": do, "expected_disagreement": de}


def icc_oneway(numeric_ratings: dict[str, list[float]]) -> dict:
    rows = [values for values in numeric_ratings.values() if len(values) >= 2]
    if len(rows) < 2:
        return status_result("insufficient_sample", "need_at_least_two_items")
    k = len(rows[0])
    if any(len(row) != k for row in rows):
        return status_result("configuration_mismatch", "unequal_rater_counts")
    grand = sum(sum(row) for row in rows) / (len(rows) * k)
    row_means = [sum(row) / k for row in rows]
    ms_between = k * sum((m - grand) ** 2 for m in row_means) / (len(rows) - 1)
    ms_within = sum(sum((x - m) ** 2 for x in row) for row, m in zip(rows, row_means)) / (len(rows) * (k - 1))
    value = (ms_between - ms_within) / (ms_between + (k - 1) * ms_within) if (ms_between + (k - 1) * ms_within) else None
    return {"status": "ready", "value": value, "sample_size_items": len(rows), "raters": k}


def field_agreement(fields_a: dict[str, dict], fields_b: dict[str, dict]) -> dict:
    common = sorted(set(fields_a) & set(fields_b))
    if not common:
        return status_result("insufficient_sample", "no_common_items")
    values = []
    for key in common:
        keys = set(fields_a[key]) | set(fields_b[key])
        values.append(sum(1 for f in keys if fields_a[key].get(f) == fields_b[key].get(f)) / len(keys) if keys else 1.0)
    return {"status": "ready", "value": sum(values) / len(values), "sample_size_items": len(values)}


def adjudication_rate(statuses: list[str]) -> dict:
    if not statuses:
        return status_result("needs_annotation", "no_agreement_statuses")
    count = sum(1 for status in statuses if status == "needs_adjudication")
    return {"status": "ready", "value": count / len(statuses), "numerator": count, "denominator": len(statuses)}


def case_cluster_bootstrap(case_items: dict[str, list[str]], item_scores: dict[str, float], *, repetitions: int = 1000, seed: int = 13) -> dict:
    case_ids = sorted(case_items)
    if len(case_ids) < 2:
        return {"status": "insufficient_sample", "missing_reason": "need_at_least_two_cases", "value": None, "included_case_ids": case_ids}
    rng = random.Random(seed)
    values = []
    for _ in range(repetitions):
        sampled_cases = [rng.choice(case_ids) for _ in case_ids]
        sampled_items = [item for case_id in sampled_cases for item in case_items.get(case_id, []) if item in item_scores]
        if sampled_items:
            values.append(sum(item_scores[item] for item in sampled_items) / len(sampled_items))
    if not values:
        return {"status": "needs_annotation", "missing_reason": "no_scored_items", "value": None, "included_case_ids": case_ids}
    values.sort()
    low = values[max(0, math.floor(0.025 * (len(values) - 1)))]
    high = values[min(len(values) - 1, math.ceil(0.975 * (len(values) - 1)))]
    return {"status": "ready", "value": sum(values) / len(values), "ci_low": low, "ci_high": high, "bootstrap_seed": seed, "bootstrap_repetitions": repetitions, "included_case_ids": case_ids}


def paired_case_cluster_bootstrap(case_items: dict[str, list[str]], scores_a: dict[str, float], scores_b: dict[str, float], *, repetitions: int = 1000, seed: int = 13) -> dict:
    if set(scores_a) != set(scores_b):
        return {"status": "configuration_mismatch", "missing_reason": "score_item_sets_differ", "value": None}
    deltas = {key: scores_a[key] - scores_b[key] for key in scores_a}
    result = case_cluster_bootstrap(case_items, deltas, repetitions=repetitions, seed=seed)
    if result["status"] == "ready":
        result["absolute_delta"] = result["value"]
    return result
