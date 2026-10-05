#!/usr/bin/env python3
"""Derive blinded E1R1 states, freeze them, then unblind and select offline."""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from pathlib import Path

from scripts import run_search_plan_v24_alpha320e1r_full_blinded_semantic_replication_prereg_offline as r
from scripts import run_search_plan_v24_alpha320e1r1_full_blinded_semantic_replication_execution as x


ROOT = r.ROOT
OUT = ROOT / "runs/20261004_search_plan_v24_dev_alpha3_20e2_replication_unblind_aggregate_select_offline"
ROOT_MARKER = "search_plan_v24_dev_alpha3_20e2_sha256"
X_ROOT = "8004e7b568adc99953e720499c20d38c2ea3d6c990b51c51fd030af2cf039bad"
JUDGMENT_SHA = "5df8d894055df97ab179bb03d7689799a9b4d380c5f1c9221bac83dbe0e2acd5"
V1, V2 = r.e.d.VARIANT_IDS[:2]
STATES = ("SEMANTIC_FIDELITY_PASS", "SEMANTIC_FIDELITY_FAIL",
          "SEMANTIC_FIDELITY_UNRESOLVED")
COMPARISONS = ("V1_SEMANTICALLY_DOMINATES", "V2_SEMANTICALLY_DOMINATES",
               "SEMANTIC_TIE", "SEMANTIC_INCOMPARABLE")


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RuntimeError(reason)


def put(name: str, value: object) -> str:
    raw = r.canonical(value) + b"\n"
    path = OUT / name
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return r.sha(raw)


def put_rows(name: str, values: list[dict]) -> str:
    raw = b"".join(r.canonical(value) + b"\n" for value in values)
    path = OUT / name
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return r.sha(raw)


def marker(name: str, value: str) -> None:
    with (OUT / name).open("xb") as handle:
        handle.write((value + "\n").encode("ascii"))
        handle.flush()
        os.fsync(handle.fileno())


def state_from_six(criteria: dict) -> str:
    """Controller derivation uses only six categorical states, never rationale."""
    require(set(criteria) == set(r.e.CRITERIA), "CRITERION_KEY_SET_MISMATCH")
    values = []
    for name in r.e.CRITERIA:
        value = criteria[name]
        require(value in r.e.STATES, "CRITERION_STATE_ENUM_MISMATCH")
        values.append(value)
    if "FAIL" in values:
        return "SEMANTIC_FIDELITY_FAIL"
    if "UNRESOLVED" in values:
        return "SEMANTIC_FIDELITY_UNRESOLVED"
    return "SEMANTIC_FIDELITY_PASS"


def comparison(v1: tuple[int, int], v2: tuple[int, int]) -> str:
    if v1 == v2:
        return "SEMANTIC_TIE"
    if all(a <= b for a, b in zip(v1, v2)):
        return "V1_SEMANTICALLY_DOMINATES"
    if all(b <= a for a, b in zip(v1, v2)):
        return "V2_SEMANTICALLY_DOMINATES"
    return "SEMANTIC_INCOMPARABLE"


def preflight() -> dict:
    require(not OUT.exists(), "ALPHA320E2_OUTPUT_ALREADY_EXISTS")
    require((x.OUT / x.ROOT_MARKER).read_text().strip() == X_ROOT
            and r.e.d.c.root_hash(x.OUT, x.ROOT_MARKER) == X_ROOT,
            "E1R1_ROOT_MISMATCH")
    require((r.OUT / r.ROOT_MARKER).read_text().strip() == x.R_ROOT
            and r.e.d.c.root_hash(r.OUT, r.ROOT_MARKER) == x.R_ROOT,
            "E1R_ROOT_MISMATCH")
    validation = r.obj(x.OUT / "validation.json")
    require(validation["alpha3_20e1r1_classification"] ==
                "ALL_28_REPLICATION_SEMANTIC_RESPONSES_VALID_AND_FROZEN"
            and validation["replication_groups_attempted"] == 28
            and validation["replication_semantic_scientific_inference_events"] == 28
            and validation["valid_replication_group_count"] == 28
            and validation["invalid_replication_group_count"] == 0
            and validation["valid_replication_candidate_judgment_set_count"] == 84
            and validation["provider_execution_ambiguous_count"] == 0
            and validation["replication_selection_eligible"] is True
            and validation["unblinding_performed"] is False
            and validation["candidate_overall_state_derived"] is False
            and validation["arm_aggregation_performed"] is False,
            "REPLICATION_SELECTION_ELIGIBILITY_NOT_VERIFIED")
    require(r.digest(r.OUT /
        "replication_semantic_adjudication_request_manifest.jsonl") ==
            validation["authoritative_replication_request_manifest_sha256"] ==
            x.MANIFEST_SHA,
            "REPLICATION_REQUEST_MANIFEST_MISMATCH")
    judgment_path = x.OUT / "replication_raw_judgment_manifest_blinded.jsonl"
    require(r.digest(judgment_path) == JUDGMENT_SHA
            and (x.OUT /
                "replication_raw_judgment_manifest_blinded_sha256").read_text().strip()
                == JUDGMENT_SHA
            and validation["replication_raw_judgment_manifest_blinded_sha256"]
                == JUDGMENT_SHA,
            "REPLICATION_JUDGMENT_MANIFEST_MISMATCH")
    require(r.obj(r.OUT / "replication_dataset_independence_contract.json")[
                "replication_dataset_may_mix_with_e1"] is False,
            "E1_REPLICATION_DATASET_MIXING_PROHIBITION_MISSING")
    require(r.obj(r.OUT / "e1_quarantine_binding.json")[
                "e1_judgments_selection_eligible"] is False,
            "E1_JUDGMENT_QUARANTINE_MISSING")
    derivation_path = r.e.OUT / "semantic_candidate_overall_state_derivation.json"
    derivation_ref = r.obj(r.OUT /
        "semantic_candidate_overall_state_derivation_binding.json")[
            "frozen_authority"]
    require(r.digest(derivation_path) == derivation_ref["sha256"]
            and r.obj(derivation_path)["controller_owned"] is True
            and r.obj(derivation_path)["rationale_overrides_state"] is False,
            "OVERALL_STATE_DERIVATION_AUTHORITY_MISMATCH")
    rubric_ref = r.obj(r.OUT /
        "development_semantic_fidelity_rubric_v1_binding.json")["rubric"]
    require(r.digest(ROOT / rubric_ref["path"]) == rubric_ref["sha256"] ==
            x.r.e1.RUBRIC_SHA,
            "SCIENTIFIC_RUBRIC_BINDING_MISMATCH")
    attempts = r.rows(x.OUT / "replication_request_attempt_log.jsonl")
    judgments = r.rows(judgment_path)
    terminals = r.rows(x.OUT / "replication_group_terminal_states.jsonl")
    token_checks = r.rows(x.OUT / "replication_candidate_token_set_validation.jsonl")
    transports = r.rows(x.OUT / "replication_transport_provenance.jsonl")
    require(len(attempts) == len(terminals) == len(token_checks) ==
            len(transports) == 28 and len(judgments) == 84
            and all(row["terminal_state"] ==
                    "COMPLETED_REPLICATION_SEMANTIC_RESPONSE_VALID"
                    for row in terminals)
            and all(row["exact_token_set_valid"] is True for row in token_checks),
            "FROZEN_REPLICATION_GROUP_OR_TOKEN_COVERAGE_MISMATCH")
    attempts_by_group = {row["blinded_group_token"]: row for row in attempts}
    transport_by_group = {row["blinded_group_token"]: row for row in transports}
    require(len(attempts_by_group) == len(transport_by_group) == 28,
            "BLINDED_GROUP_TOKEN_DUPLICATE")
    seen_tokens = set()
    per_group = Counter()
    for row in judgments:
        group = row["blinded_group_token"]
        token = row["blinded_candidate_token"]
        require(group in attempts_by_group
                and token in attempts_by_group[group]["blinded_candidate_tokens"]
                and token not in seen_tokens
                and row["request_sha256"] == attempts_by_group[group][
                    "request_sha256"]
                and row["raw_response_sha256"] == transport_by_group[group][
                    "raw_response_sha256"]
                and set(row["criteria"]) == set(r.e.CRITERIA)
                and all(row["criteria"][criterion]["state"] in r.e.STATES
                        for criterion in r.e.CRITERIA),
                "FROZEN_BLINDED_JUDGMENT_BINDING_MISMATCH")
        seen_tokens.add(token)
        per_group[group] += 1
    require(len(seen_tokens) == 84
            and all(per_group[group] == 3 for group in attempts_by_group)
            and seen_tokens == {token for row in attempts
                                for token in row["blinded_candidate_tokens"]},
            "BLINDED_CANDIDATE_SET_NOT_EXACT")
    return {"validation": validation, "judgments": judgments,
            "attempts": attempts, "transports": transports,
            "derivation_ref": derivation_ref,
            "rubric_ref": rubric_ref}


def derive_blinded(judgments: list[dict]) -> list[dict]:
    derived = []
    for row in judgments:
        states = {name: row["criteria"][name]["state"] for name in r.e.CRITERIA}
        derived.append({"blinded_group_token": row["blinded_group_token"],
            "blinded_candidate_token": row["blinded_candidate_token"],
            "execution_ordinal": row["execution_ordinal"],
            "criterion_states": states,
            "overall_semantic_state": state_from_six(states),
            "request_sha256": row["request_sha256"],
            "raw_response_sha256": row["raw_response_sha256"]})
    return derived


def freeze_blinded(state: dict) -> tuple[list[dict], str]:
    OUT.mkdir()
    put("alpha3_20e1r1_root_verification.json", {"verified": True,
        "root_sha256": X_ROOT})
    put("alpha3_20e1r_root_verification.json", {"verified": True,
        "root_sha256": x.R_ROOT})
    put("replication_selection_eligibility_verification.json", {
        "verified": True, "valid_groups": 28,
        "invalid_groups": 0, "valid_candidate_judgment_sets": 84,
        "provider_execution_ambiguity": 0,
        "replication_selection_eligible": True,
        "unblinding_performed_in_e1r1": False})
    put("replication_raw_judgment_manifest_verification.json", {
        "sha256": JUDGMENT_SHA, "verified": True,
        "blinded_candidate_count": 84})
    put("semantic_overall_state_derivation_contract_binding.json", {
        "frozen_authority": state["derivation_ref"],
        "rubric": state["rubric_ref"],
        "controller_owned": True, "rationale_prose_used": False})
    first = derive_blinded(state["judgments"])
    second = derive_blinded(state["judgments"])
    first_raw = b"".join(r.canonical(row) + b"\n" for row in first)
    second_raw = b"".join(r.canonical(row) + b"\n" for row in second)
    require(len(first) == len(second) == 84
            and len({row["blinded_candidate_token"] for row in first}) == 84
            and sum(Counter(row["overall_semantic_state"] for row in first).values())
                == 84,
            "BLINDED_OVERALL_STATE_COVERAGE_FAILURE")
    deterministic = first_raw == second_raw
    put("semantic_overall_state_determinism_audit.json", {
        "derivation_runs": 2,
        "byte_identical": deterministic,
        "first_sha256": r.sha(first_raw),
        "second_sha256": r.sha(second_raw),
        "arm_mapping_read": False,
        "lexical_results_read": False})
    if not deterministic:
        raise RuntimeError("BLINDED_OVERALL_STATE_DERIVATION_NONDETERMINISTIC")
    blind_sha = put_rows("semantic_candidate_overall_states_blinded.jsonl", first)
    marker("semantic_candidate_overall_states_blinded_sha256", blind_sha)
    counts = Counter(row["overall_semantic_state"] for row in first)
    require(sum(counts.values()) == 84 and set(counts) <= set(STATES),
            "BLINDED_STATE_COUNT_MISMATCH")
    put("freeze_before_unblind_barrier.json", {
        "passed": True,
        "blinded_candidate_count": 84,
        "blinded_overall_state_count": 84,
        "blinded_manifest_sha256": blind_sha,
        "blinded_derivation_deterministic": True,
        "blinded_pass_count": counts["SEMANTIC_FIDELITY_PASS"],
        "blinded_fail_count": counts["SEMANTIC_FIDELITY_FAIL"],
        "blinded_unresolved_count": counts["SEMANTIC_FIDELITY_UNRESOLVED"],
        "private_mapping_contents_decoded_before_barrier": False,
        "arm_aggregation_before_barrier": False,
        "semantic_comparison_before_barrier": False,
        "lexical_result_content_read_before_barrier": False,
        "unblinding_performed_at_barrier": False})
    return first, blind_sha


def unblind(derived: list[dict], blind_sha: str) -> list[dict]:
    require((OUT / "freeze_before_unblind_barrier.json").is_file()
            and r.obj(OUT / "freeze_before_unblind_barrier.json")["passed"] is True
            and r.digest(OUT / "semantic_candidate_overall_states_blinded.jsonl")
                == blind_sha,
            "FREEZE_BEFORE_UNBLIND_BARRIER_NOT_PASSED")
    blinding = r.obj(r.OUT / "replication_blinding_contract.json")
    group_path = r.OUT / "replication_group_token_mapping_private.jsonl"
    candidate_path = r.OUT / "replication_candidate_token_mapping_private.jsonl"
    require(group_path.is_file() and candidate_path.is_file()
            and not group_path.is_symlink() and not candidate_path.is_symlink()
            and group_path.stat().st_mode & 0o077 == 0
            and candidate_path.stat().st_mode & 0o077 == 0
            and r.digest(group_path) == blinding["private_group_mapping_sha256"]
            and r.digest(candidate_path) == blinding[
                "private_candidate_mapping_sha256"],
            "REPLICATION_PRIVATE_MAPPING_HASH_OR_PERMISSION_FAILURE")
    put("replication_private_mapping_verification.json", {
        "verified": True,
        "group_mapping_sha256": r.digest(group_path),
        "candidate_mapping_sha256": r.digest(candidate_path),
        "permissions_controller_only": True,
        "verification_after_blinded_freeze": True})
    group_rows = r.rows(group_path)
    candidate_rows = r.rows(candidate_path)
    groups = {row["blinded_group_token"]: row for row in group_rows}
    candidates = {row["blinded_candidate_token"]: row for row in candidate_rows}
    require(len(group_rows) == len(groups) == 28
            and len(candidate_rows) == len(candidates) == 84,
            "UNBLIND_MAPPING_IDENTITY_DUPLICATE_OR_MISSING")
    unblinded = []
    for row in derived:
        group_token = row["blinded_group_token"]
        candidate_token = row["blinded_candidate_token"]
        require(group_token in groups and candidate_token in candidates,
                "UNBLIND_MAPPING_TOKEN_MISSING")
        group = groups[group_token]
        candidate = candidates[candidate_token]
        require(candidate["blinded_group_token"] == group_token
                and candidate["private_variant_id"] == group["private_variant_id"]
                and candidate["source_record_token_private"] == group[
                    "source_record_token_private"]
                and group["request_sha256"] == row["request_sha256"]
                and group["private_variant_id"] in (V1, V2),
                "UNBLIND_MAPPING_CROSS_BINDING_FAILURE")
        unblinded.append({**row,
            "source_record_token": group["source_record_token_private"],
            "private_variant_id": group["private_variant_id"],
            "development_candidate_id": candidate["development_candidate_id"],
            "candidate_payload_sha256": candidate["candidate_payload_sha256"]})
    counts = Counter(row["private_variant_id"] for row in unblinded)
    require(counts == {V1: 42, V2: 42}
            and len({row["development_candidate_id"] for row in unblinded}) == 84,
            "UNBLIND_MAPPING_INTEGRITY_FAILURE")
    source_arm = Counter((row["source_record_token"], row["private_variant_id"])
                         for row in unblinded)
    require(len(source_arm) == 28 and set(source_arm.values()) == {3}
            and len({row["source_record_token"] for row in unblinded}) == 14,
            "UNBLIND_SOURCE_ARM_CARDINALITY_FAILURE")
    put("replication_unblind_integrity_audit.json", {
        "passed": True, "unblinding_after_blinded_freeze": True,
        "candidate_count": 84, "v1_candidate_count": 42,
        "v2_candidate_count": 42, "v3_candidate_count": 0,
        "source_count": 14, "source_arm_group_count": 28,
        "candidate_ids_unique": True,
        "e1_mapping_used": False})
    put_rows("semantic_candidate_overall_states_unblinded.jsonl", unblinded)
    return unblinded


def aggregate(unblinded: list[dict]) -> dict:
    result = {}
    criterion_summary = {}
    for variant, label in ((V1, "v1"), (V2, "v2")):
        arm_rows = [row for row in unblinded if row["private_variant_id"] == variant]
        overall = Counter(row["overall_semantic_state"] for row in arm_rows)
        require(len(arm_rows) == 42 and sum(overall.values()) == 42,
                "ARM_CANDIDATE_COUNT_FAILURE")
        candidate_summary = {
            "variant": label.upper(), "candidate_denominator": 42,
            "semantic_pass_count": overall["SEMANTIC_FIDELITY_PASS"],
            "semantic_fail_count": overall["SEMANTIC_FIDELITY_FAIL"],
            "semantic_unresolved_count": overall["SEMANTIC_FIDELITY_UNRESOLVED"]}
        by_source = defaultdict(list)
        for row in arm_rows:
            by_source[row["source_record_token"]].append(row[
                "overall_semantic_state"])
        require(len(by_source) == 14 and all(len(states) == 3
                                              for states in by_source.values()),
                "ARM_SOURCE_GROUP_COUNT_FAILURE")
        source_summary = {
            "variant": label.upper(), "source_denominator": 14,
            "sources_all_three_semantic_pass": sum(all(state ==
                "SEMANTIC_FIDELITY_PASS" for state in states)
                for states in by_source.values()),
            "sources_with_at_least_one_semantic_fail": sum(
                "SEMANTIC_FIDELITY_FAIL" in states for states in by_source.values()),
            "sources_with_at_least_one_semantic_unresolved": sum(
                "SEMANTIC_FIDELITY_UNRESOLVED" in states
                for states in by_source.values()),
            "selection_rule_input": False}
        result[label] = {"candidate": candidate_summary, "source": source_summary}
        criterion_summary[label] = {name: dict(Counter(row["criterion_states"][name]
            for row in arm_rows)) for name in r.e.CRITERIA}
        put(label + "_semantic_candidate_summary.json", candidate_summary)
        put(label + "_semantic_source_summary.json", source_summary)
    put("per_criterion_arm_summary.json", {
        "descriptive_only": True,
        "not_used_for_selection": True,
        "per_arm_criterion_counts": criterion_summary})
    put("semantic_arm_summary_freeze_barrier.json", {
        "passed": True, "v1_candidate_summary_sha256": r.digest(OUT /
            "v1_semantic_candidate_summary.json"),
        "v2_candidate_summary_sha256": r.digest(OUT /
            "v2_semantic_candidate_summary.json"),
        "v1_source_summary_sha256": r.digest(OUT /
            "v1_semantic_source_summary.json"),
        "v2_source_summary_sha256": r.digest(OUT /
            "v2_semantic_source_summary.json"),
        "dominance_not_evaluated_before_barrier": True,
        "lexical_results_not_read_before_barrier": True})
    return result


def select(summary: dict) -> tuple[str, str, str, bool]:
    require(r.obj(OUT / "semantic_arm_summary_freeze_barrier.json")["passed"]
            is True, "SEMANTIC_ARM_SUMMARY_NOT_FROZEN")
    v1 = summary["v1"]["candidate"]
    v2 = summary["v2"]["candidate"]
    v1_vector = (v1["semantic_fail_count"], v1["semantic_unresolved_count"])
    v2_vector = (v2["semantic_fail_count"], v2["semantic_unresolved_count"])
    put("semantic_comparison_vectors.json", {
        "vector_order": ["candidate_semantic_fail_count",
                         "candidate_semantic_unresolved_count"],
        "v1_vector": list(v1_vector), "v2_vector": list(v2_vector),
        "source_level_diagnostics_used": False})
    rule_ref = r.obj(r.OUT / "semantic_dominance_rule_binding.json")[
        "frozen_authority"]
    require(r.digest(ROOT / rule_ref["path"]) == rule_ref["sha256"],
            "SEMANTIC_DOMINANCE_RULE_CHANGED")
    state = comparison(v1_vector, v2_vector)
    require(state in COMPARISONS, "SEMANTIC_COMPARISON_STATE_INVALID")
    put("semantic_dominance_rule_execution.json", {
        "frozen_rule": rule_ref, "state": state,
        "no_weighted_tradeoff": True,
        "lexical_result_used": False})
    put("semantic_comparison_state.json", {
        "semantic_comparison_state": state,
        "frozen_before_lexical_result_content_access": True})
    # The D root is checked only after the scientific comparison is frozen.
    d = r.e.d
    require((d.OUT / "search_plan_v24_dev_alpha3_20d_sha256").read_text().strip()
            == r.e.D_ROOT and d.c.root_hash(d.OUT,
                "search_plan_v24_dev_alpha3_20d_sha256") == r.e.D_ROOT,
            "ALPHA320D_ROOT_MISMATCH")
    put("alpha3_20d_root_verification.json", {
        "root_sha256": r.e.D_ROOT, "verified": True,
        "verified_after_semantic_comparison_freeze": True})
    if state == "SEMANTIC_TIE":
        d_validation = r.obj(d.OUT / "validation.json")
        d_eligibility = r.obj(d.OUT / "variant_nonleakage_eligibility.json")
        require(d_validation["per_variant"]["V1"]["leakage_survivor_count"]
                == 39 and d_validation["per_variant"]["V2"][
                    "leakage_survivor_count"] == 37
                and d_eligibility[V1]["nonleakage_eligible"] is True
                and d_eligibility[V2]["nonleakage_eligible"] is True,
                "FROZEN_LEXICAL_TIE_BREAKER_MISMATCH")
        put("alpha3_20d_lexical_result_binding.json", {
            "bound_for_selection": True,
            "frozen_root_sha256": r.e.D_ROOT,
            "v1_survivors": 39, "v1_denominator": 42,
            "v2_survivors": 37, "v2_denominator": 42,
            "leakage_recomputed": False})
        used = True
        recommendation = "V1"
        classification = "SEMANTIC_SELECTION_COMPLETE_TIE_LEXICAL_BREAKS_TO_V1"
        basis = "frozen lexical abstraction tie breaker"
    else:
        put("alpha3_20d_lexical_result_binding.json", {
            "bound_for_selection": False,
            "frozen_root_sha256": r.e.D_ROOT,
            "lexical_result_content_read": False,
            "leakage_recomputed": False})
        used = False
        if state == "V1_SEMANTICALLY_DOMINATES":
            recommendation = "V1"
            classification = "SEMANTIC_SELECTION_COMPLETE_V1_DOMINATES"
            basis = "scientific semantic fidelity precedence"
        elif state == "V2_SEMANTICALLY_DOMINATES":
            recommendation = "V2"
            classification = "SEMANTIC_SELECTION_COMPLETE_V2_DOMINATES"
            basis = "scientific semantic fidelity precedence"
        else:
            recommendation = "DEFERRED"
            classification = "SEMANTIC_SELECTION_COMPLETE_INCOMPARABLE_DEFERRED"
            basis = "crossed FAIL/UNRESOLVED vectors; no weighted tradeoff"
    put("lexical_result_use_audit.json", {
        "semantic_comparison_state": state,
        "used_for_selection": used,
        "used_only_if_semantic_tie": used == (state == "SEMANTIC_TIE"),
        "recomputed": False})
    selection_ref = r.obj(r.OUT / "semantic_variant_selection_rule_binding.json")[
        "frozen_authority"]
    require(r.digest(ROOT / selection_ref["path"]) == selection_ref["sha256"],
            "VARIANT_SELECTION_RULE_CHANGED")
    put("variant_selection_rule_execution.json", {
        "frozen_rule": selection_ref,
        "semantic_comparison_state": state,
        "deterministic_selection_recommendation": recommendation,
        "basis": basis,
        "source_level_diagnostics_used": False,
        "e1_judgments_used": False,
        "v3_used": False})
    put("development_variant_selection_recommendation.json", {
        "classification": classification,
        "recommendation": recommendation,
        "status": "DEVELOPMENT_SELECTION_RECOMMENDATION",
        "not_final_builder_v4_contract_freeze": True,
        "basis": basis})
    return state, recommendation, classification, used


def finish(state: dict, derived: list[dict], blind_sha: str,
           summary: dict, selected: tuple[str, str, str, bool]) -> dict:
    comparison_state, recommendation, classification, lexical_used = selected
    next_stage = ("DESIGN_ALPHA3_20_SEMANTIC_INCOMPARABLE_RESOLUTION_PROTOCOL"
                  if recommendation == "DEFERRED" else
                  "PREREGISTER_ALPHA3_20F_FINAL_BUILDER_V4_CONTRACT_FREEZE")
    put("e1_nonuse_audit.json", {
        "e1_judgments_used_for_selection": False,
        "e1_judgment_manifest_read": False,
        "replication_dataset_standalone": True,
        "e1_quarantine_state":
            "SEEN_DEVELOPMENT_INCOMPLETE_EXPERIMENT_NOT_SELECTION_ELIGIBLE"})
    put("v3_exclusion_audit.json", {
        "v3_replication_candidate_count": 0,
        "v3_used_for_selection": False,
        "v3_20d_nonleakage_ineligible_preserved": True})
    put("development_interpretation_boundary.json", {
        "classification": "POST_ALPHA3_19_SEEN_DATA_DEVELOPMENT_OFFLINE_SEMANTIC_SELECTION",
        "fresh_heldout": False, "human_gold": False,
        "primary_quality": False,
        "fresh_cohort_superiority_claim": False})
    put("future_alpha3_20f_handoff.json", {
        "recommendation": recommendation,
        "alpha3_20f_may_be_preregistered": recommendation in ("V1", "V2"),
        "builder_v4_contract_mutated_here": False,
        "fresh_primary_attempt_started": False})
    put("historical_inference_accounting.json", {
        "alpha3_18_builder": 56, "alpha3_18_quality": 1,
        "alpha3_19_builder": 14, "alpha3_19_quality": 0,
        "alpha3_20c_builder_v4_development": 42,
        "alpha3_20e1_semantic_adjudication": 28,
        "alpha3_20e1r1_replication_semantic_adjudication": 28,
        "alpha3_20e2_new_inference_events": 0,
        "provider_calls": 0, "deepseek_calls": 0,
        "llm_calls": 0, "network_calls": 0,
        "builder_calls": 0, "quality_calls": 0})
    require(r.e.d.c.root_hash(x.OUT, x.ROOT_MARKER) == X_ROOT
            and r.e.d.c.root_hash(r.OUT, r.ROOT_MARKER) == x.R_ROOT,
            "UPSTREAM_HISTORICAL_ROOT_CHANGED")
    put("historical_preservation_audit.json", {
        "e1r1_root_unchanged": True,
        "e1r_root_unchanged": True,
        "alpha3_20d_root_unchanged": True,
        "historical_assets_modified": False})
    put("scientific_state_safety_audit.json", {
        "provider_calls": 0, "deepseek_calls": 0,
        "llm_calls": 0, "network_calls": 0,
        "builder_calls": 0, "quality_calls": 0,
        "new_adjudication_calls": 0,
        "rationale_prose_interpreted": False,
        "criterion_weighting_used": False,
        "leakage_recomputed": False,
        "builder_v4_contract_mutated": False})
    put("protocol_compliance_audit.json", {
        "blinded_states_frozen_before_arm_mapping_content_read": True,
        "arm_summaries_frozen_before_dominance": True,
        "semantic_comparison_frozen_before_lexical_result_access": True,
        "lexical_used_only_for_tie": lexical_used ==
            (comparison_state == "SEMANTIC_TIE"),
        "e1_judgments_not_used": True,
        "v3_excluded": True,
        "offline_only": True})
    blind_counts = Counter(row["overall_semantic_state"] for row in derived)
    v1 = summary["v1"]
    v2 = summary["v2"]
    validation = {
        "status": "completed",
        "alpha3_20e2_classification": classification,
        "alpha3_20e1r1_root_verified": True,
        "replication_selection_eligible_verified": True,
        "replication_candidate_count": 84,
        "blinded_overall_state_derivation_complete": True,
        "blinded_overall_state_derivation_deterministic": True,
        "blinded_semantic_pass_count": blind_counts["SEMANTIC_FIDELITY_PASS"],
        "blinded_semantic_fail_count": blind_counts["SEMANTIC_FIDELITY_FAIL"],
        "blinded_semantic_unresolved_count": blind_counts[
            "SEMANTIC_FIDELITY_UNRESOLVED"],
        "freeze_before_unblind_passed": True,
        "unblinding_performed": True,
        "unblind_mapping_integrity_passed": True,
        "v1_candidate_count": 42,
        "v1_semantic_pass_count": v1["candidate"]["semantic_pass_count"],
        "v1_semantic_fail_count": v1["candidate"]["semantic_fail_count"],
        "v1_semantic_unresolved_count": v1["candidate"][
            "semantic_unresolved_count"],
        "v1_sources_all_three_semantic_pass": v1["source"][
            "sources_all_three_semantic_pass"],
        "v1_sources_with_semantic_fail": v1["source"][
            "sources_with_at_least_one_semantic_fail"],
        "v1_sources_with_semantic_unresolved": v1["source"][
            "sources_with_at_least_one_semantic_unresolved"],
        "v2_candidate_count": 42,
        "v2_semantic_pass_count": v2["candidate"]["semantic_pass_count"],
        "v2_semantic_fail_count": v2["candidate"]["semantic_fail_count"],
        "v2_semantic_unresolved_count": v2["candidate"][
            "semantic_unresolved_count"],
        "v2_sources_all_three_semantic_pass": v2["source"][
            "sources_all_three_semantic_pass"],
        "v2_sources_with_semantic_fail": v2["source"][
            "sources_with_at_least_one_semantic_fail"],
        "v2_sources_with_semantic_unresolved": v2["source"][
            "sources_with_at_least_one_semantic_unresolved"],
        "semantic_comparison_state": comparison_state,
        "lexical_result_used_for_selection": lexical_used,
        "v1_frozen_lexical_survivors": 39,
        "v1_frozen_lexical_denominator": 42,
        "v2_frozen_lexical_survivors": 37,
        "v2_frozen_lexical_denominator": 42,
        "deterministic_selection_recommendation": recommendation,
        "e1_judgments_used_for_selection": False,
        "v3_used_for_selection": False,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "semantic_candidate_overall_states_blinded_sha256": blind_sha,
        "next_stage_recommendation": next_stage,
        "historical_assets_modified": False}
    put("validation.json", validation)
    put("summary.json", {"status": "completed",
        "classification": classification,
        "semantic_comparison_state": comparison_state,
        "deterministic_selection_recommendation": recommendation,
        "next_stage_recommendation": next_stage})
    root = r.e.d.c.root_hash(OUT, ROOT_MARKER)
    marker(ROOT_MARKER, root)
    return {**validation, "search_plan_v24_dev_alpha3_20e2_sha256": root}


def run() -> dict:
    state = preflight()
    derived, blind_sha = freeze_blinded(state)
    unblinded = unblind(derived, blind_sha)
    summary = aggregate(unblinded)
    selected = select(summary)
    return finish(state, derived, blind_sha, summary, selected)


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
