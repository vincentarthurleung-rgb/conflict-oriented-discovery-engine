"""Deterministic representative and complete-coverage planning."""
from __future__ import annotations

import re
from typing import Any

SELECTION_POLICY_VERSION = "context_smoke_stratified_greedy_v1"
REQUESTED_CATEGORIES = (
    "abstract_abstract", "fulltext_fulltext", "abstract_fulltext",
    "same_conditions_different_wording", "explicit_context_difference",
    "missing_information", "multi_intervention", "complex_fulltext_logic_chain",
)
_WEIGHTS = {
    "abstract_abstract": 100, "fulltext_fulltext": 100, "abstract_fulltext": 100,
    "multi_intervention": 70, "explicit_context_difference": 60,
    "missing_information": 50, "same_conditions_different_wording": 40,
    "complex_fulltext_logic_chain": 30,
}

def observation_id(row: dict[str, Any]) -> str:
    return str(row.get("observation_id") or row.get("claim_id") or "")

def observation_input_mode(row: dict[str, Any]) -> str:
    schema = str(row.get("schema_version") or row.get("adapter_source_schema") or "")
    if schema.startswith("fulltext_l1_experimental_observation_schema_v") or row.get("adapter_mode") == "formal_v3_native":
        return "fulltext"
    return "abstract"

def pair_input_mode(pair: dict[str, Any]) -> str:
    modes = (observation_input_mode(pair["claim_a"]), observation_input_mode(pair["claim_b"]))
    if modes == ("abstract", "abstract"): return "abstract_abstract"
    if modes == ("fulltext", "fulltext"): return "fulltext_fulltext"
    return "abstract_fulltext"

def _context_signature(row: dict[str, Any]) -> tuple[str, ...]:
    experiment = row.get("experiment") or {}
    values = [
        experiment.get("species_raw"), experiment.get("model_system_raw"),
        experiment.get("experimental_unit_raw"), experiment.get("tissue_raw"),
        experiment.get("disease_model_raw"), experiment.get("genotype_raw"),
        row.get("species_canonical_id"),
    ]
    return tuple(str(x).strip().casefold() for x in values if str(x or "").strip())

def _complexity(row: dict[str, Any]) -> int:
    anchors = (row.get("provenance") or {}).get("evidence_spans") or row.get("authoritative_evidence_spans") or []
    interventions = row.get("interventions") or []
    chain_nodes = sum(bool(x) for x in (
        row.get("experiment"), interventions, row.get("measurement"), row.get("observation"),
        row.get("interpretation_raw"),
    ))
    return len(anchors) + len(interventions) * 2 + chain_nodes

def classify_pair(pair: dict[str, Any]) -> dict[str, Any]:
    left, right = pair["claim_a"], pair["claim_b"]
    record = pair.get("candidate_record") or {}
    mode = pair_input_mode(pair)
    categories = {mode}
    left_sig, right_sig = _context_signature(left), _context_signature(right)
    evidence_a = str(left.get("evidence_sentence") or "")
    evidence_b = str(right.get("evidence_sentence") or "")
    context_left = list(record.get("context_terms_left") or [])
    context_right = list(record.get("context_terms_right") or [])
    compartments_left = list(record.get("object_compartments_left") or [])
    compartments_right = list(record.get("object_compartments_right") or [])
    explicit_difference = (
        record.get("context_match") == "context_split"
        or bool(record.get("context_split_axes"))
        or bool(compartments_left and compartments_right and compartments_left != compartments_right)
        or bool(left_sig and right_sig and left_sig != right_sig)
    )
    if explicit_difference:
        categories.add("explicit_context_difference")
    if left_sig and left_sig == right_sig and evidence_a and evidence_b and _norm(evidence_a) != _norm(evidence_b):
        categories.add("same_conditions_different_wording")
    if not context_left or not context_right or not left_sig or not right_sig:
        categories.add("missing_information")
    if len(left.get("interventions") or []) > 1 or len(right.get("interventions") or []) > 1:
        categories.add("multi_intervention")
    max_complexity = max(_complexity(left), _complexity(right))
    if mode != "abstract_abstract" and max_complexity >= 6:
        categories.add("complex_fulltext_logic_chain")
    family_a = str((left.get("experiment") or {}).get("evidence_family_id") or left.get("evidence_family_id") or "")
    family_b = str((right.get("experiment") or {}).get("evidence_family_id") or right.get("evidence_family_id") or "")
    if family_a and family_b and family_a != family_b:
        categories.add("different_evidence_family")
    base_score = sum(_WEIGHTS.get(x, 10) for x in categories) + min(max_complexity, 20)
    return {
        "pair_id": pair["pair_id"], "claim_a_id": observation_id(left),
        "claim_b_id": observation_id(right), "pair_input_mode": mode,
        "selection_categories": sorted(categories), "selection_score_or_priority": base_score,
        "selection_reason": "deterministic category coverage, new endpoint coverage, evidence-chain complexity, then stable pair_id",
        "evidence_chain_complexity": max_complexity,
    }

def _norm(value: str) -> str:
    return re.sub(r"\W+", " ", value.casefold()).strip()

def representative_smoke_selection(pairs: list[dict[str, Any]], target_count: int) -> dict[str, Any]:
    annotated = [(pair, classify_pair(pair)) for pair in pairs]
    selected: list[tuple[dict[str, Any], dict[str, Any]]] = []
    remaining = list(annotated)
    covered: set[str] = set()
    covered_observations: set[str] = set()
    while remaining and len(selected) < min(max(0, target_count), len(annotated)):
        def rank(item: tuple[dict[str, Any], dict[str, Any]]) -> tuple[int, int, int, int, str]:
            info = item[1]
            new = set(info["selection_categories"]) - covered
            gain = sum(_WEIGHTS.get(x, 10) for x in new)
            new_observations = len({info["claim_a_id"], info["claim_b_id"]} - covered_observations)
            return (-gain, -new_observations, -int(info["selection_score_or_priority"]),
                    -int(info["evidence_chain_complexity"]), info["pair_id"])
        chosen = sorted(remaining, key=rank)[0]
        selected.append(chosen)
        covered.update(chosen[1]["selection_categories"])
        covered_observations.update((chosen[1]["claim_a_id"], chosen[1]["claim_b_id"]))
        remaining.remove(chosen)
    selected_ids = {x[1]["pair_id"] for x in selected}
    available = {category: any(category in x[1]["selection_categories"] for x in annotated)
                 for category in REQUESTED_CATEGORIES}
    category_coverage = {
        category: {
            "requested_category": category, "available": available[category],
            "selected": any(category in x[1]["selection_categories"] for x in selected),
            "selected_pair_ids": [x[1]["pair_id"] for x in selected if category in x[1]["selection_categories"]],
            "reason": None if available[category] else "category_not_present_in_current_candidate_pairs",
        } for category in REQUESTED_CATEGORIES
    }
    observation_ids = sorted({oid for _, info in selected for oid in (info["claim_a_id"], info["claim_b_id"])})
    return {
        "selection_policy_version": SELECTION_POLICY_VERSION,
        "deterministic_tiebreak": "stable pair_id ascending",
        "available_categories": available,
        "selected_pairs": [info for _, info in selected],
        "selected_pair_ids": [info["pair_id"] for _, info in selected],
        "selected_observations": observation_ids,
        "unselected_pairs": [{"pair_id": info["pair_id"], "reason": "smoke_not_selected"}
                             for _, info in annotated if info["pair_id"] not in selected_ids],
        "category_coverage": category_coverage,
    }

def complete_selection(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    infos = [classify_pair(x) for x in sorted(pairs, key=lambda x: x["pair_id"])]
    observations = sorted({oid for info in infos for oid in (info["claim_a_id"], info["claim_b_id"])})
    available = {category: any(category in x["selection_categories"] for x in infos)
                 for category in REQUESTED_CATEGORIES}
    return {
        "selection_policy_version": "context_complete_coverage_v1",
        "deterministic_tiebreak": "stable pair_id ascending",
        "available_categories": available, "selected_pairs": infos,
        "selected_pair_ids": [x["pair_id"] for x in infos],
        "selected_observations": observations, "unselected_pairs": [],
        "category_coverage": {
            category: {"requested_category": category, "available": available[category],
                       "selected": available[category],
                       "selected_pair_ids": [x["pair_id"] for x in infos if category in x["selection_categories"]],
                       "reason": None if available[category] else "category_not_present_in_current_candidate_pairs"}
            for category in REQUESTED_CATEGORIES
        },
    }

def validate_plan(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    selected_pairs = plan["selected_pairs"]
    selected_ids = {x["pair_id"] for x in selected_pairs}
    endpoints = {oid for x in selected_pairs for oid in (x["claim_a_id"], x["claim_b_id"])}
    covered_observations = set(plan["cached_extraction_observation_ids"]) | set(plan["planned_extraction_observation_ids"])
    covered_pairs = set(plan["cached_comparison_pair_ids"]) | set(plan["planned_comparison_pair_ids"])
    if endpoints != set(plan["selected_observation_ids"]): errors.append("selected_observation_closure_mismatch")
    if plan.get("plan_status") != "blocked_by_call_bound" and not endpoints <= covered_observations:
        errors.append("selected_pair_endpoint_not_cached_or_planned")
    if not covered_pairs <= selected_ids: errors.append("comparison_outside_selected_pairs")
    if int(plan["provider_calls_hard_bound"]) != int(plan["extraction_calls_planned"]) + int(plan["comparison_calls_planned"]):
        errors.append("provider_hard_bound_mismatch")
    if plan["purpose"] == "smoke":
        if plan["coverage_complete"]: errors.append("smoke_must_be_partial")
        if len(selected_pairs) != min(plan["smoke_pair_count"], plan["candidate_pair_count"]):
            errors.append("smoke_pair_count_mismatch")
    else:
        if plan["coverage_complete"] and (
            set(plan["all_candidate_observation_ids"]) != covered_observations
            or set(plan["all_candidate_pair_ids"]) != covered_pairs
        ): errors.append("complete_coverage_claim_is_false")
    return errors

__all__ = [
    "SELECTION_POLICY_VERSION", "classify_pair", "complete_selection",
    "observation_id", "observation_input_mode", "pair_input_mode",
    "representative_smoke_selection", "validate_plan",
]
