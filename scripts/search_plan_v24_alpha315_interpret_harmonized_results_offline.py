#!/usr/bin/env python3
"""Offline, source-bound interpretation of frozen harmonized review outputs."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "runs/20260926_search_plan_v24_dev_alpha3_14e_final_harmonized_review_completion"
REVIEW = ROOT / "runs/20260926_search_plan_v24_dev_alpha3_14e_harmonized_review_continuation"
NEUTRAL = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_13_harmonized_neutral_review_preregistration_offline"
LEXICAL = ROOT / "runs/20260925_search_plan_v24_dev_bounded_lexical_realization_v2_full_retrieval"
ORIGINAL = ROOT / "runs/20260917_search_plan_v23_beta_2_primary_heldout_v2_metrics_unblinding"
V23 = ROOT / "runs/20260916_search_plan_v23_beta_2_primary_heldout_v2_network_retrieval"
EXACT = ROOT / "runs/20260924_search_plan_v24_dev_alpha3_4_development_retrospective_retrieval"
SURFACE = ROOT / "runs/20260925_search_plan_v24_dev_retrieval_surface_v2_technical_continuation"
ALLOCATION = ROOT / "runs/20260925_search_constraint_allocation_v1_development_retrieval"
AUTOPSY = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_8_conjunctive_rigidity_autopsy_offline"
TARGET = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_15_harmonized_results_interpretation_offline"
ROOTS = {
    "alpha3_14e_archive": "d03aa570ddc5ab2ecc3c16383f56be6d7cdec41d3885c7df0bd0229b7b01c671",
    "blinded_adjudication_corpus": "677fb451105feebf091b675149d487b691bbb81ca1eab04fe3bf4e24a2bd23c3",
    "harmonized_results_archive": "2ec85ad42c2bd11952b6f913ea790f15d0314d557bc47ea17d6fd472287af7d2",
    "original_harmonized_results": "5624bbf8c106689a27a883cc43273cb14882f7180f4ceae443eb0183f822413d",
}
HISTORICAL = "ARM_HISTORICAL_V23"
LEXICAL_ARM = "ARM_LEXICAL_V2"
NAMESPACES = {
    "ORIGINAL_V23_REVIEW": "original historical OpenAI adjudication",
    "HARMONIZED_DEEPSEEK_V23_REVIEW": "harmonized DeepSeek historical-retrieval arm",
    "HARMONIZED_DEEPSEEK_LEXICAL_V2_REVIEW": "harmonized DeepSeek Lexical V2 arm",
}


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise RuntimeError(reason)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path: Path) -> list[Any]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write(name: str, value: Any) -> None:
    path = TARGET / name
    body = canonical(value) + b"\n"
    if path.exists():
        require(path.read_bytes() == body, f"refusing different existing artifact: {name}")
        return
    path.write_bytes(body)


def distribution(values: list[Any], taxonomy: list[Any]) -> dict[str, Any]:
    counts = Counter(values)
    require(set(counts) <= set(taxonomy), "value outside frozen taxonomy")
    denominator = len(values)
    return {"denominator": denominator, "categories": [
        {"category": category, "count": counts[category], "denominator": denominator,
         "fraction": counts[category] / denominator if denominator else None}
        for category in taxonomy
    ]}


def cross_tab(items: list[dict[str, Any]], left: str, right: str,
              left_order: list[Any], right_order: list[Any]) -> dict[str, Any]:
    count = Counter((item[left], item[right]) for item in items)
    require(all(a in left_order and b in right_order for a, b in count), "cross-tab state outside taxonomy")
    return {"denominator": len(items), "left_field": left, "right_field": right,
            "left_order": left_order, "right_order": right_order,
            "rows": [{"left_state": a, "denominator": sum(count[(a, b)] for b in right_order),
                      "cells": [{"right_state": b, "count": count[(a, b)]} for b in right_order]}
                     for a in left_order]}


def verify_pair_manifest(root: Path, manifest_name: str, root_name: str, expected: str) -> None:
    manifest = load(root / manifest_name)
    pairs = manifest["aggregate_components"]
    require(all(sha(root / relative) == checksum for relative, checksum in pairs), f"component drift: {manifest_name}")
    require(digest(pairs) == expected == (root / root_name).read_text().strip(), f"root drift: {manifest_name}")


def verify_upstream() -> dict[str, Any]:
    require(not (TARGET / "search_plan_v24_dev_alpha3_15_sha256").exists(),
            "interpretation root exists; never regenerate a frozen run")
    root_pairs = [[path.name, sha(path)] for path in sorted(ARCHIVE.iterdir())
                  if path.is_file() and path.name != "search_plan_v24_dev_alpha3_14e_sha256"]
    require(digest(root_pairs) == ROOTS["alpha3_14e_archive"] ==
            (ARCHIVE / "search_plan_v24_dev_alpha3_14e_sha256").read_text().strip(), "archive root drift")
    verify_pair_manifest(ARCHIVE, "harmonized_deepseek_review_results_manifest.json",
                         "harmonized_deepseek_review_results_sha256", ROOTS["harmonized_results_archive"])
    verify_pair_manifest(REVIEW, "harmonized_deepseek_blinded_adjudication_corpus_manifest.json",
                         "harmonized_deepseek_blinded_adjudication_corpus_sha256", ROOTS["blinded_adjudication_corpus"])
    verify_pair_manifest(REVIEW, "harmonized_deepseek_review_results_manifest.json",
                         "harmonized_deepseek_review_results_sha256", ROOTS["original_harmonized_results"])
    require(load(ARCHIVE / "validation.json")["status"] == "FAILED_PROTOCOL_CHRONOLOGY", "protocol status changed")
    require(load(ARCHIVE / "summary.json")["status"] == "failed", "archive status changed")
    require(load(ARCHIVE / "remaining_five_batch_derivation.json")["strict_post_gate_request_derivation_satisfied"] is False,
            "chronology deviation concealed")
    require(load(REVIEW / "unblinding_barrier_audit.json")["blinded_adjudication_freeze_verified"] is True,
            "blinded freeze barrier invalid")
    for name in ("harmonized_arm_results.jsonl", "complete_blinded_review_unit_results.jsonl",
                 "harmonized_v23_metrics.json", "harmonized_lexical_v2_metrics.json"):
        require(sha(ARCHIVE / name) == sha(REVIEW / name), f"archive/source result mismatch: {name}")
    return {"verified": True, "authoritative_roots": ROOTS,
            "alpha3_14e_protocol_status": "FAILED_PROTOCOL_CHRONOLOGY",
            "archive_scientific_results_byte_identical_to_original_continuation": True}


def candidate_trajectory() -> dict[str, Any]:
    v23 = load(V23 / "summary.json")
    query_log = rows(V23 / "query_execution_log.jsonl")
    by_query = {}
    for record in query_log:
        by_query.setdefault(record["query_id"], record["response_record_count"])
    require(len(by_query) == v23["executed_query_count"] == 32, "v2.3 query denominator drift")
    stages = [
        {"stage": "V23", "queries": 32,
         "nonzero_queries": sum(value > 0 for value in by_query.values()),
         "nonzero_cases": sum(case["raw_query_hits"] > 0 for case in v23["per_case"]),
         "metadata_candidates": v23["metadata_candidate_count"],
         "selected_review_units": v23["selected_fulltext_count"]},
    ]
    for stage, path, query_key, metadata_key, selected_key in (
        ("EXACT_PROPOSITION", EXACT, "executed_query_count", "metadata_candidate_count", "selected_fulltext_count"),
        ("RETRIEVAL_SURFACE_V2", SURFACE, "byte_unique_query_count", "metadata_universe_total", "selected_count"),
        ("SEARCH_CONSTRAINT_ALLOCATION_V1", ALLOCATION, "byte_unique_query_count", "metadata_universe_total", "selected_count"),
        ("ALLOCATION_PLUS_BOUNDED_LEXICAL_V2", LEXICAL, "byte_unique_query_count", "metadata_universe_total", "selected_count"),
    ):
        summary = load(path / "summary.json")
        stages.append({"stage": stage, "queries": summary[query_key],
                       "nonzero_queries": summary.get("nonzero_query_count", 0),
                       "nonzero_cases": summary.get("nonzero_case_count", 0),
                       "metadata_candidates": summary[metadata_key],
                       "selected_review_units": summary.get(selected_key, 0),
                       "acquired_fulltexts": summary["successful_fulltext_acquisition_count"] if "successful_fulltext_acquisition_count" in summary else 0})
    require([(x["queries"], x["nonzero_queries"], x["nonzero_cases"], x["metadata_candidates"], x["selected_review_units"]) for x in stages]
            == [(32, 25, 7, 1214, 60), (29, 0, 0, 0, 0), (25, 0, 0, 0, 0),
                (55, 3, 2, 2, 1), (55, 8, 3, 66, 11)], "candidate-generation trajectory drift")
    return {"stages": stages, "candidate_generation_is_not_scientific_relevance": True,
            "lexical_v2_restored": ["candidate_volume", "case_coverage", "topic_level_retrieval"],
            "relation_bearing_retrieval_scientifically_unverified": True}


def main() -> None:
    upstream = verify_upstream()
    schema = load(NEUTRAL / "neutral_review_output_schema.json")
    relevance = schema["PASS_B"]["properties"]["records"]["items"]["properties"]["relevance_state"]["enum"]
    contaminant = schema["PASS_B"]["properties"]["records"]["items"]["properties"]["contaminant_class"]["enum"]
    acquisition = schema["PASS_A"]["properties"]["records"]["items"]["properties"]["acquisition_decision"]["enum"]
    review = rows(ARCHIVE / "harmonized_arm_results.jsonl")
    map_rows = rows(NEUTRAL / "neutral_review_hidden_arm_map.jsonl")
    by_review_id = {row["review_unit_id"]: row for row in map_rows}
    require(len(review) == len(map_rows) == len(by_review_id) == 71, "review identity collision")
    require(set(row["packet_id"] for row in review) == set(by_review_id), "review/map identity mismatch")
    require(all(row["arm_membership"] == by_review_id[row["packet_id"]]["arm_membership"] and
                row["case_id"] == by_review_id[row["packet_id"]]["case_id"] for row in review), "arm identity mismatch")
    historical = [row for row in review if row["arm_membership"] == HISTORICAL]
    lexical = [row for row in review if row["arm_membership"] == LEXICAL_ARM]
    require(len(historical) == 60 and len(lexical) == 11, "arm denominator drift")
    original = rows(ORIGINAL / "primary_v2_merged_results.jsonl")
    original_by_candidate = {row["candidate_id"]: row for row in original}
    require(len(original) == len(original_by_candidate) == 60, "original reviewer identity collision")
    require(set(by_review_id[row["packet_id"]]["candidate_id"] for row in historical) == set(original_by_candidate),
            "original/harmonized reviewer identities do not align")
    selection = {}
    for case in range(101, 109):
        case_id = f"heldout_v2_{case}"
        for item in load(LEXICAL / "case_selection_manifests" / f"{case_id}.json")["ordered_selections"]:
            require(item["candidate_id"] not in selection, "duplicate selected candidate")
            selection[item["candidate_id"]] = item
    require(len(selection) == 11, "selected candidate count drift")
    require(set(by_review_id[row["packet_id"]]["candidate_id"] for row in lexical) == set(selection),
            "selected/reviewed Lexical V2 identity mismatch")
    source_hashes = {str(path.relative_to(ROOT)): sha(path) for path in (
        ARCHIVE / "harmonized_arm_results.jsonl", NEUTRAL / "neutral_review_hidden_arm_map.jsonl",
        ORIGINAL / "primary_v2_merged_results.jsonl", LEXICAL / "metadata_records.jsonl",
        LEXICAL / "candidate_gate_results.jsonl", LEXICAL / "p0_results.jsonl",
        LEXICAL / "p1_results.jsonl", LEXICAL / "p2_results.jsonl",
        LEXICAL / "policy_a_results.jsonl")}
    TARGET.mkdir(exist_ok=True)
    write("upstream_root_verification.json", {**upstream, "joined_source_file_sha256": source_hashes})

    # The request manifest was frozen before B3; the later calls were gated.
    six_manifest = rows(REVIEW / "six_request_manifest.jsonl")
    requests = rows(REVIEW / "frozen_requests.jsonl")
    attempts = [load(REVIEW / f"attempts/pass_b_batch_{i:02d}.json") for i in range(3, 9)]
    gate = load(REVIEW / "gate/replacement_batch3_validation.json")
    require([a["batch_index"] for a in attempts] == [3, 4, 5, 6, 7, 8], "attempt order drift")
    require(gate["status"] == "VALID" and gate["full_schema_valid"] and gate["identity_binding_valid"], "B3 gate invalid")
    require(all(digest(requests[i]["request"]) == six_manifest[i]["new_request_sha256"] == attempts[i]["request_sha256"]
                for i in range(6)), "request bytes/hash changed")
    require(all(six_manifest[i]["scientific_prompt_sha256"] == six_manifest[0]["scientific_prompt_sha256"]
                for i in range(6)), "scientific prompt hash drift")
    forbidden = ('"arm_membership"', '"case_id"', '"query_text"', '"query_family"',
                 '"selection_rank"', '"historical_label"', '"known_paper_status"', 'heldout_v2_',
                 'ARM_HISTORICAL', 'ARM_LEXICAL', '"pass_a"')
    require(all(not any(token in requests[i]["request"]["messages"][0]["content"] for token in forbidden)
                for i in range(6)), "model-visible request leakage")
    barrier = load(REVIEW / "unblinding_barrier_audit.json")
    chronology = {
        "alpha3_14e_protocol_status": "FAILED_PROTOCOL_CHRONOLOGY",
        "exact_deviation": "Batches 4-8 request payloads were frozen before replacement Batch 3 validated.",
        "A_no_later_provider_call_before_B3_validation": True,
        "A_evidence": "Frozen runner checks the valid B3 gate before each later attempt; all six attempt records are sequential.",
        "B_request_bytes_match_pre_B3_freeze": True,
        "B_limit": "Stored hashes and write-once runner identify no post-B3 modification; they cannot prove that no transient edit was ever made and reverted.",
        "C_evidence_packets_pre_frozen_independently": True,
        "D_batch_membership_pre_frozen": True,
        "E_scientific_prompt_and_rubric_pre_frozen": True,
        "F_B3_scientific_output_could_not_enter_prefrozen_later_requests": True,
        "G_hidden_arm_map_not_accessed_before_blinded_freeze": barrier["arm_map_accessed_before_blinded_freeze"] is False,
        "H_metrics_not_computed_before_complete_blinded_freeze": barrier["metrics_computed_before_blinded_freeze"] is False,
        "classification": "PROTOCOL_DEVIATION_NO_IDENTIFIED_SCIENTIFIC_CONTENT_IMPACT",
        "run_protocol_pass": False,
        "scientific_content_impact_identified": False,
        "rerun_for_chronology_alone_recommended": False,
        "rerun_reason": "Re-inference would add model stochasticity without correcting an identified change in scientific prompts, evidence, or reviewed identities.",
    }
    write("chronology_deviation_scientific_impact_audit.json", chronology)
    write("interpretation_eligibility.json", {
        "eligible": True, "use_class": "DEVELOPMENT_INTERPRETATION_WITH_DISCLOSED_PROTOCOL_DEVIATION",
        "protocol_status_preserved": "FAILED_PROTOCOL_CHRONOLOGY", "model_reviewer_type": "model_retrieval_adjudicator",
        "not_human_gold": True, "cannot_be_used_as_protocol_PASS": True})
    write("three_review_namespace_verification.json", {
        "namespaces": NAMESPACES, "original_count": len(original), "harmonized_historical_count": len(historical),
        "harmonized_lexical_v2_count": len(lexical), "labels_merged_or_overwritten": False,
        "original_label_file_sha256": sha(ORIGINAL / "primary_v2_merged_results.jsonl")})
    trajectory = candidate_trajectory()
    write("candidate_generation_trajectory.json", trajectory)
    lex_dist = distribution([row["relevance_state"] for row in lexical], relevance)
    hist_dist = distribution([row["relevance_state"] for row in historical], relevance)
    require(next(x["count"] for x in lex_dist["categories"] if x["category"] == "DIRECTLY_RELEVANT") == 0,
            "Lexical direct count drift")
    require(next(x["count"] for x in hist_dist["categories"] if x["category"] == "DIRECTLY_RELEVANT") == 1,
            "historical direct count drift")
    write("lexical_v2_relevance_distribution.json", {"namespace": "HARMONIZED_DEEPSEEK_LEXICAL_V2_REVIEW", **lex_dist})
    write("harmonized_v23_relevance_distribution.json", {"namespace": "HARMONIZED_DEEPSEEK_V23_REVIEW", **hist_dist})
    write("harmonized_relevance_comparison.json", {
        "taxonomy_order": relevance, "historical_denominator": 60, "lexical_denominator": 11,
        "categories": [{"category": label,
                        "historical_count": Counter(row["relevance_state"] for row in historical)[label],
                        "lexical_count": Counter(row["relevance_state"] for row in lexical)[label]}
                       for label in relevance],
        "dominant_historical_non_direct": "WRONG_ENTITY",
        "dominant_lexical_non_direct": "WRONG_ENTITY",
        "statistical_significance_claimed": False,
    })
    write("contaminant_distribution_comparison.json", {
        "taxonomy_order": contaminant,
        "historical": distribution([row["contaminant_class"] for row in historical], contaminant),
        "lexical_v2": distribution([row["contaminant_class"] for row in lexical], contaminant),
        "contaminants_inferred_from_relevance_state": False,
    })
    write("pass_a_pass_b_crosstab.json", {
        "historical": cross_tab(historical, "acquisition_decision", "relevance_state", acquisition, relevance),
        "lexical_v2": cross_tab(lexical, "acquisition_decision", "relevance_state", acquisition, relevance),
        "interpretation": "Only one historical unit was BORDERLINE_BUT_JUSTIFIED and it was not directly relevant; all other 70 units were NOT_JUSTIFIED. Acquisition justification and scientific relevance are distinct.",
    })
    tiered = []
    for row in lexical:
        candidate = by_review_id[row["packet_id"]]["candidate_id"]
        tier = selection[candidate]["final_preacquisition_tier"]
        require(tier == row["final_v23_beta_disposition_at_acquisition"] ==
                by_review_id[row["packet_id"]]["frozen_preacquisition_tier"], "tier join drift")
        tiered.append({**row, "tier": tier, "candidate_id": candidate})
    write("tier_review_alignment.json", {
        "tiers": [{"tier": tier, **distribution([row["relevance_state"] for row in tiered if row["tier"] == tier], relevance)}
                  for tier in ("TIER_A", "TIER_B")],
        "tier_a_before_tier_b_selection_policy_unchanged": True,
        "direct_relevance_enrichment_observed": False,
        "failure_category_shift_caveat": "Two reviewed Tier A units are too few to establish general enrichment.",
    })
    stage_sources = {"P0": ("p0_results.jsonl", "state"), "P1": ("p1_results.jsonl", "state"),
                     "P2": ("p2_results.jsonl", "state"), "PolicyA": ("policy_a_results.jsonl", "policy_a_action")}
    stage_tables = {}
    for stage, (filename, state_key) in stage_sources.items():
        stage_rows = rows(LEXICAL / filename)
        by_candidate = {row["candidate_id"]: row for row in stage_rows}
        require(len(by_candidate) == 66 and all(row["candidate_id"] in by_candidate for row in tiered),
                f"{stage} candidate join drift")
        joined = [{"state": by_candidate[row["candidate_id"]][state_key], "relevance_state": row["relevance_state"]}
                  for row in tiered]
        state_order = sorted({row["state"] for row in joined})
        stage_tables[stage] = cross_tab(joined, "state", "relevance_state", state_order, relevance)
    write("validator_review_alignment.json", {
        "stages": stage_tables,
        "reviewed_unit_count": 11,
        "only_frozen_deterministic_outputs_joined": True,
        "rules_modified": False,
        "interpretation": "P0 is predominantly UNRESOLVED among reviewed units despite frequent wrong-biological-unit review contaminants; these stage states are not relevance predictions.",
    })
    case_source = load(LEXICAL / "case_query_hit_summary.json")["cases"]
    require(len(case_source) == 8, "case source count drift")
    case_rows = []
    for source in case_source:
        case_id = source["case_id"]
        reviewed = [row for row in lexical if row["case_id"] == case_id]
        selected = load(LEXICAL / "case_selection_manifests" / f"{case_id}.json")["selection_count"]
        require(source["selected_count"] == selected == len(reviewed), "case selection/review drift")
        case_rows.append({"case_id": case_id,
                          "retrieved_candidate_count": source["observed_unique_pmids_before_tail"],
                          "metadata_count": source["metadata_universe_count"],
                          "selected_count": selected, "reviewed_count": len(reviewed),
                          "review_status": "REVIEWED" if reviewed else "NO_REVIEW_UNITS_FROM_RETRIEVAL",
                          "relevance_distribution": distribution([row["relevance_state"] for row in reviewed], relevance)
                          if reviewed else None})
    require(sum(row["metadata_count"] for row in case_rows) == 66 and
            sum(row["reviewed_count"] for row in case_rows) == 11 and
            sum(row["review_status"] == "NO_REVIEW_UNITS_FROM_RETRIEVAL" for row in case_rows) == 6,
            "case coverage drift")
    write("lexical_v2_case_level_analysis.json", {
        "cases": case_rows,
        "zero_review_cases_are_not_zero_direct_reviewed_cases": True,
        "note": "Six cases have no review units: five have zero metadata and one has metadata but no selected fulltext.",
    })
    lexical_summary = load(LEXICAL / "summary.json")
    metadata = rows(LEXICAL / "metadata_records.jsonl")
    policy_rows = rows(LEXICAL / "policy_a_results.jsonl")
    pmcid_by_candidate = {row["candidate_id"]: bool(row.get("pmcid")) for row in metadata}
    raw_pmcid_count = sum(pmcid_by_candidate.values())
    eligible = sum(pmcid_by_candidate[row["candidate_id"]] and
                   row["final_v23_beta2_disposition"] in ("TIER_A", "TIER_B") for row in policy_rows)
    require(len(metadata) == 66 and raw_pmcid_count == 28 and eligible == 21,
            "metadata/qualified-OA denominator drift")
    write("retrieval_selection_bottleneck_analysis.json", {
        "metadata_candidates": 66, "raw_pmcid_present": raw_pmcid_count,
        "tier_a_or_b_with_pmcid_eligible": eligible, "selected_and_reviewed": 11,
        "unreviewed_metadata_candidates": 55,
        "unselected_pmcid_eligible_candidates": 10,
        "nonzero_retrieval_cases": lexical_summary["nonzero_case_count"],
        "zero_metadata_cases": lexical_summary["zero_hit_case_count"],
        "reviewed_direct_count": 0,
        "can_localize_direct_absence_to_one_stage": False,
        "unreviewed_candidates_assigned_scientific_labels": False,
        "denominator_boundary": "0/11 DIRECT among reviewed units does not establish 0/66 DIRECT among metadata candidates.",
        "interpretation": "Candidate generation improved, but five cases still yielded no metadata, OA/selection reduced 66 metadata to 11 reviewed units, and those 11 were not direct. The scientific status of the other 55 is unknown.",
    })
    availability = {}
    for arm, items in ((HISTORICAL, historical), (LEXICAL_ARM, lexical)):
        availability[arm] = {}
        for state, present in (("WITH_FULLTEXT_EXCERPT", True), ("WITHOUT_FULLTEXT_EXCERPT", False)):
            group = [row for row in items if (by_review_id[row["packet_id"]]["fulltext_excerpt_count"] > 0) == present]
            availability[arm][state] = distribution([row["relevance_state"] for row in group], relevance)
    require(availability[HISTORICAL]["WITHOUT_FULLTEXT_EXCERPT"]["denominator"] == 12 and
            availability[LEXICAL_ARM]["WITHOUT_FULLTEXT_EXCERPT"]["denominator"] == 8,
            "excerpt denominator drift")
    write("evidence_availability_label_analysis.json", {
        "arms": availability, "missing_excerpts_refetched": False,
        "counterfactual_labels_inferred": False,
        "interpretation": "Eight of eleven Lexical V2 units lack fulltext excerpts, but none of the three with excerpts was DIRECT either; availability limits comparison without changing labels.",
    })
    transition_items = []
    for row in historical:
        candidate = by_review_id[row["packet_id"]]["candidate_id"]
        transition_items.append({"original_state": original_by_candidate[candidate]["relevance_state"],
                                 "harmonized_state": row["relevance_state"]})
    matrix = cross_tab(transition_items, "original_state", "harmonized_state", relevance, relevance)
    same = sum(row["original_state"] == row["harmonized_state"] for row in transition_items)
    direct_out = sum(row["original_state"] == "DIRECTLY_RELEVANT" and row["harmonized_state"] != "DIRECTLY_RELEVANT"
                     for row in transition_items)
    direct_in = sum(row["original_state"] != "DIRECTLY_RELEVANT" and row["harmonized_state"] == "DIRECTLY_RELEVANT"
                    for row in transition_items)
    require(same == 24 and direct_out == 1 and direct_in == 0, "reviewer transition drift")
    write("original_vs_harmonized_v23_transition_matrix.json", {
        "matrix": matrix, "same_label_count": same, "different_label_count": 60 - same,
        "DIRECT_to_non_DIRECT": direct_out, "non_DIRECT_to_DIRECT": direct_in,
        "reviewer_system_variation_not_correctness_adjudication": True,
    })
    require(sum(row["relevance_state"] == "DIRECTLY_RELEVANT" for row in original) == 2,
            "original direct count drift")
    autopsy = load(AUTOPSY / "summary.json")
    require(autopsy["search_validation_role_collapse_detected"] and
            autopsy["lexical_surface_undercoverage_detected"] and
            autopsy["causal_limit"], "frozen autopsy evidence drift")
    write("development_hypothesis_assessment.json", {
        "H1_search_validation_role_collapse": {
            "status": "PARTIALLY_SUPPORTED",
            "evidence": "Frozen structural autopsy identified role collapse, and allocation-only queries recovered 2 metadata candidates from zero; no clause-level ablation isolates its causal contribution."},
        "H2_lexical_undercoverage": {
            "status": "SUPPORTED",
            "evidence": "With allocation held as the comparison architecture, bounded lexical realization raised metadata candidates from 2 to 66 and nonzero queries from 3 to 8."},
        "H3_H1_plus_H2_sufficient_for_direct_retrieval": {
            "status": "NOT_SUPPORTED",
            "evidence": "The completed selected/reviewed Lexical V2 set has 0/11 DIRECT; this does not label the other 55 metadata candidates."},
        "no_new_hypotheses_added": True,
    })
    write("current_bottleneck_diagnosis.json", {
        "category": "MULTIPLE_UNRESOLVED_BOTTLENECKS",
        "development_only": True,
        "evidence": [
            "Five of eight cases still have no metadata after Lexical V2.",
            "Only 11 of 66 metadata candidates were selected/reviewed; the other 55 have unknown relevance.",
            "Among 11 reviewed units, 10 were WRONG_ENTITY and 9 carried wrong_biological_unit contaminant labels.",
            "P0 was UNRESOLVED for 10 of 11 reviewed units, and 8 of 11 lack fulltext excerpts."
        ],
        "single_stage_causality_claimed": False,
    })
    write("overfitting_risk_assessment.json", {
        "risk": "HIGH", "cases": [f"heldout_v2_{case}" for case in range(101, 109)],
        "reason": "The same eight development cases have informed repeated architecture and lexical iterations; ten of eleven Lexical review units come from one case.",
        "case_specific_rules_recommended": False,
        "further_synonym_or_morphology_expansion_recommended": False,
    })
    decision = "FREEZE_ARCHITECTURE_AND_TEST_FRESH_HELDOUT"
    write("next_development_decision.json", {
        "recommendation": decision,
        "reason": "The reviewed failures are concentrated in one case, while candidate coverage, selection, biology, and evidence availability all remain unresolved. Fresh targets test generality without further tuning on cases 101-108.",
        "future_targets_selected_without_using_these_review_labels": True,
        "automatic_fresh_heldout_execution_authorized": False,
        "query_or_lexical_tuning_now": False,
    })
    write("scientific_claim_boundary.json", {
        "reviewer_type": "model_retrieval_adjudicator", "human_gold": False,
        "claims_allowed": ["candidate-generation trajectory on eight seen development cases",
                           "descriptive model-review distributions among selected units",
                           "development-stage bottleneck hypotheses with stated uncertainty"],
        "claims_prohibited": ["0/66 DIRECT", "true precision", "true recall", "statistical significance from N=11",
                              "unreviewed-candidate relevance", "protocol-PASS for alpha3.14e",
                              "production activation"],
        "original_historical_labels_preserved": True,
    })
    write("historical_preservation_audit.json", {
        "alpha3_14e_archive_root_sha256": ROOTS["alpha3_14e_archive"],
        "original_v23_labels_sha256": sha(ORIGINAL / "primary_v2_merged_results.jsonl"),
        "source_results_sha256": ROOTS["original_harmonized_results"],
        "review_labels_modified": False, "historical_assets_modified": False,
        "scientific_results_reinferred": 0,
    })
    write("scientific_state_safety_audit.json", {
        "query_modifications": 0, "lexical_changes": 0, "validator_changes": 0,
        "selection_changes": 0, "provider_calls": 0, "llm_calls": 0,
        "network_calls": 0, "retrieval_calls": 0,
        "review_labels_modified": 0, "unreviewed_candidates_assigned_relevance_labels": False,
        "zero_retrieval_cases_treated_as_scientific_negatives": False,
        "arm_metrics_recomputed_from_frozen_labels_only": True,
    })
    write("validation.json", {
        "status": "PASS", "alpha3_14e_protocol_status_preserved": "FAILED_PROTOCOL_CHRONOLOGY",
        "chronology_impact_classified": True,
        "scientific_interpretation_eligible": True,
        "scientific_results_reinferred": 0, "review_labels_modified": 0,
        "reviewer_type": "model_retrieval_adjudicator",
        "zero_retrieval_cases_treated_as_scientific_negatives": False,
        "unreviewed_candidates_assigned_relevance_labels": False,
        "query_modifications": 0, "lexical_changes": 0, "validator_changes": 0,
        "selection_changes": 0, "provider_calls": 0, "llm_calls": 0,
        "network_calls": 0, "retrieval_calls": 0,
    })
    write("summary.json", {
        "status": "completed", "alpha3_14e_protocol_status": "FAILED_PROTOCOL_CHRONOLOGY",
        "chronology_impact_class": chronology["classification"],
        "scientific_interpretation_eligible": True,
        "original_v23_direct_count": 2, "original_v23_review_denominator": 60,
        "harmonized_v23_direct_count": 1, "harmonized_v23_review_denominator": 60,
        "harmonized_lexical_v2_direct_count": 0, "harmonized_lexical_v2_review_denominator": 11,
        "lexical_v2_metadata_universe": 66, "lexical_v2_reviewed_units": 11,
        "lexical_v2_with_fulltext_excerpt": 3, "lexical_v2_without_fulltext_excerpt": 8,
        "reviewer_same_label_count": same, "reviewer_different_label_count": 60 - same,
        "H1": "PARTIALLY_SUPPORTED", "H2": "SUPPORTED", "H3": "NOT_SUPPORTED",
        "current_bottleneck": "MULTIPLE_UNRESOLVED_BOTTLENECKS",
        "development_overfitting_risk": "HIGH", "next_stage_recommendation": decision,
        "historical_assets_modified": False,
    })
    files = [path for path in sorted(TARGET.iterdir()) if path.is_file()]
    pairs = [[path.name, sha(path)] for path in files]
    run_root = digest(pairs)
    (TARGET / "search_plan_v24_dev_alpha3_15_sha256").write_text(run_root + "\n", encoding="utf-8")
    require(all(sha(TARGET / name) == checksum for name, checksum in pairs), "output component drift")
    print(json.dumps({"status": "completed", "root": run_root,
                      "chronology_impact_class": chronology["classification"],
                      "next_stage_recommendation": decision}, sort_keys=True))


if __name__ == "__main__":
    main()
