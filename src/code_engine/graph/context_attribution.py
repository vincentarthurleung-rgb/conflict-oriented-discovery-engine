"""Deterministic context attribution for conflict edges."""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Tuple


def calculate_shannon_entropy(prob_list: List[float]) -> float:
    entropy = 0.0
    for p in prob_list:
        if p > 0:
            entropy -= p * math.log2(p)
    return round(entropy, 4)


def run_variational_em_attribution(observations: List[Dict[str, Any]], latent_universe: List[str]) -> Tuple[str, float, float]:
    """Compatibility implementation of the prior weakly supervised EM scorer."""

    if not observations:
        return "None", 0.0, 0.0
    if not latent_universe:
        latent_universe = ["HYPOXIA", "NORMOXIA", "ACUTE_PHASE", "CHRONIC_PHASE"]

    q_latent = {v: 1.0 / len(latent_universe) for v in latent_universe}
    evidence_text_corpus = " ".join(obs.get("evidence_sentence", "").upper() for obs in observations)

    for _ in range(12):
        weights = {}
        total_weight = 0.0
        for v in latent_universe:
            co_occur_hits = len(re.findall(r"\b" + re.escape(v) + r"\b", evidence_text_corpus))
            prior = q_latent[v]
            biochemical_bonus = 1.8 if v in ["HYPOXIA", "ACUTE_PHASE"] else 1.0
            likelihood = (1.0 + co_occur_hits) * biochemical_bonus
            weights[v] = prior * likelihood
            total_weight += weights[v]
        if total_weight == 0.0:
            break
        q_latent = {v: w / total_weight for v, w in weights.items()}

    best_latent = max(q_latent, key=q_latent.get)
    significance = round(q_latent[best_latent], 4)
    collapsed_entropy = round(max(0.0, 0.92 - (significance * 0.88)), 4)
    return best_latent, significance, collapsed_entropy


def context_entropy_reduction(observations: List[Dict[str, Any]], base_entropy: float) -> List[Dict[str, Any]]:
    """Rank observed context values by deterministic entropy reduction."""

    grouped: Dict[Tuple[str, str], List[int]] = defaultdict(list)
    for obs in observations:
        for axis, value in obs.get("context", {}).items():
            clean_value = str(value).upper().strip()
            if clean_value and clean_value != "UNSPECIFIED":
                grouped[(axis, clean_value)].append(obs.get("relation_sign", 0))

    ranked = []
    for (axis, value), signs in grouped.items():
        counts = Counter(signs)
        total = len(signs)
        ent = calculate_shannon_entropy([counts.get(1, 0) / total, counts.get(-1, 0) / total])
        reduction = round(max(0.0, base_entropy - ent), 4)
        ranked.append(
            {
                "axis": axis,
                "value": value,
                "support_count": total,
                "positive_count": counts.get(1, 0),
                "negative_count": counts.get(-1, 0),
                "entropy": ent,
                "entropy_reduction": reduction,
                "attribution_score": reduction,
            }
        )
    ranked.sort(key=lambda item: (item["attribution_score"], item["support_count"]), reverse=True)
    return ranked


def build_context_attributions(
    grouped_observations: Dict[Tuple[str, str], List[Dict[str, Any]]],
    edge_entropy: Dict[Tuple[str, str], float],
    latent_pool: List[str],
) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """Return attribution payloads keyed by normalized edge pair."""

    attributions: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for pair, observations in grouped_observations.items():
        best_delta_c, score, collapsed_entropy = run_variational_em_attribution(observations, latent_pool)
        ranked_contexts = context_entropy_reduction(observations, edge_entropy.get(pair, 0.0))
        attributions[pair] = {
            "conflict_edge_id": f"{pair[0]}->{pair[1]}",
            "ranked_contexts": ranked_contexts,
            "method": "entropy_reduction_plus_legacy_em",
            "score_components": {
                "legacy_em_best_delta_c": best_delta_c,
                "legacy_em_score": score,
                "legacy_collapsed_entropy": collapsed_entropy,
            },
        }
    return attributions
