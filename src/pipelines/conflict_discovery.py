"""Deterministic conflict discovery and Type I/II/III classification."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List, Tuple

from src.pipelines.context_attribution import build_context_attributions, calculate_shannon_entropy


DEFAULT_THRESHOLDS = {
    "marginal_entropy_conflict_gate": 0.10,
    "type_i_attribution_gate": 0.45,
}


def group_observations(observations: List[Dict[str, Any]]) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
    grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for obs in observations:
        grouped[(obs["subject"], obs["object"])].append(obs)
    return grouped


def build_conflict_graph(
    observations: List[Dict[str, Any]],
    *,
    latent_pool: List[str],
    thresholds: Dict[str, float] | None = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """Build legacy-compatible L3 graph plus normalized conflict/audit records."""

    active_thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    conflict_gate = active_thresholds["marginal_entropy_conflict_gate"]
    type_i_gate = active_thresholds["type_i_attribution_gate"]

    grouped = group_observations(observations)
    edge_entropy = {}
    for pair, items in grouped.items():
        counts = Counter(item["relation_sign"] for item in items)
        total = len(items)
        edge_entropy[pair] = calculate_shannon_entropy([counts.get(1, 0) / total, counts.get(-1, 0) / total])

    attributions = build_context_attributions(grouped, edge_entropy, latent_pool)
    legacy_graph: List[Dict[str, Any]] = []
    conflict_edges: List[Dict[str, Any]] = []
    attribution_records: List[Dict[str, Any]] = []
    type_counters = {"Uncontested": 0, "Type I": 0, "Type II": 0, "Type III": 0}

    for (sub, obj), raw_obs in grouped.items():
        seen_ids = set()
        observations_dedup = []
        for obs in raw_obs:
            if obs["evidence_id"] not in seen_ids:
                seen_ids.add(obs["evidence_id"])
                observations_dedup.append(obs)

        total_obs = len(observations_dedup)
        sign_counts = Counter(obs["relation_sign"] for obs in observations_dedup)
        unique_labs = {obs["source_asset"] for obs in observations_dedup}
        h_r = calculate_shannon_entropy(
            [sign_counts.get(1, 0) / total_obs, sign_counts.get(-1, 0) / total_obs]
        )
        mean_edge_confidence = round(sum(obs["belief_weight"] for obs in observations_dedup) / total_obs, 4)
        attr = attributions[(sub, obj)]
        attribution_score = float(attr["score_components"]["legacy_em_score"])
        collapsed_entropy = float(attr["score_components"]["legacy_collapsed_entropy"])
        best_delta_c = attr["score_components"]["legacy_em_best_delta_c"]

        is_conflicting = h_r >= conflict_gate
        conflict_type = "Uncontested"
        primary_driver = "None"
        if is_conflicting:
            if total_obs <= 2 or len(unique_labs) == 1:
                conflict_type = "Type III"
                primary_driver = "System_Noise_or_Single_Lab_Bias"
            elif attribution_score >= type_i_gate:
                conflict_type = "Type I"
                primary_driver = "Latent_Condition_Omission"
            else:
                conflict_type = "Type II"
                primary_driver = "Spatiotemporal_Context_Variation"

        type_counters[conflict_type] += 1
        traceability = [
            {
                "evidence_id": obs["evidence_id"],
                "triple_id": obs["triple_id"],
                "source_asset": obs["source_asset"],
                "doi": obs["doi"],
                "article_title": obs["article_title"],
                "evidence_sentence": obs["evidence_sentence"],
                "relation_sign": obs["relation_sign"],
                "context_snapshot": obs["context"],
            }
            for obs in observations_dedup
        ]

        legacy_graph.append(
            {
                "subject": sub,
                "object": obj,
                "marginal_entropy_H_R": h_r,
                "conditional_entropy_collapse_H_R_C": collapsed_entropy if is_conflicting else h_r,
                "conflict_attribution_type": conflict_type,
                "primary_driver": primary_driver,
                "weak_supervised_delta_c": best_delta_c,
                "attribution_significance_score": attribution_score,
                "evidence_count": total_obs,
                "independent_labs_count": len(unique_labs),
                "mean_edge_confidence": mean_edge_confidence,
                "whitebox_traceability": traceability,
            }
        )

        edge_id = f"{sub}->{obj}"
        conflict_edges.append(
            {
                "edge_id": edge_id,
                "source": sub,
                "target": obj,
                "positive_count": sign_counts.get(1, 0),
                "negative_count": sign_counts.get(-1, 0),
                "neutral_count": sign_counts.get(0, 0),
                "entropy": h_r,
                "conflict_status": "conflicting" if is_conflicting else "uncontested",
                "conflict_type": conflict_type,
                "supporting_triples": [obs["triple_id"] for obs in observations_dedup if obs["relation_sign"] == 1],
                "contradicting_triples": [obs["triple_id"] for obs in observations_dedup if obs["relation_sign"] == -1],
                "independent_labs_count": len(unique_labs),
            }
        )
        attr["conflict_edge_id"] = edge_id
        attribution_records.append(attr)

    report = {
        "total_pairs_evaluated": len(legacy_graph),
        "conflict_attribution_summary": type_counters,
        "thresholds": active_thresholds,
    }
    return legacy_graph, conflict_edges, attribution_records, report
