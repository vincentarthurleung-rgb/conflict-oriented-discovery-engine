#!/usr/bin/env python3
"""Freeze interpretation and closure of the incomplete alpha3.18 attempt."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts import search_plan_v24_alpha318c_preregister_quality_offline as prior
from scripts import run_search_plan_v24_alpha318c_quality as failed_run
from scripts import search_plan_v24_alpha318c1_audit_quality_response_offline as audit


ROOT = prior.ROOT
B2 = prior.B2
PREREG = prior.OUT
FAILED = failed_run.OUT
C1 = audit.OUT
A6 = prior.A6
OUT = ROOT / "runs/20261001_search_plan_v24_dev_alpha3_18c2_quality_failure_interpretation_and_attempt_closure_offline"
ROOT_MARKER = "search_plan_v24_dev_alpha3_18c2_sha256"
B2_SHA = prior.B2_SHA
PREREG_SHA = failed_run.PREREG_SHA
FAILED_SHA = audit.FAILED_SHA
C1_SHA = "53ce1197f945bf97369ccc97969a7dd7c0f03cf774c3afd4002bca4a7f3ea006"
A6_SHA = "204bcc949b3f8b86fd03cc1dfd4cbab371ceceab7e44824df9c71e58e3f26b40"
NEXT = "DESIGN_NEW_PROSPECTIVE_FRESH_HELDOUT_ATTEMPT_WITH_HARDENED_QUALITY_RESPONSE_CONTRACT"
REPORTING = (
    "Fresh-pool construction reached five deterministically prechecked candidate "
    "propositions across three source groups. Quality adjudication did not complete: "
    "the first of three preregistered Quality calls returned a schema-invalid response, "
    "triggering the preregistered fail-closed stop rule. No candidate-level Quality "
    "outcomes or final heldout pool were derived."
)


def require(ok: bool, code: str) -> None:
    if not ok:
        raise RuntimeError(code)


def load(path: Path) -> Any:
    return json.loads(path.read_bytes())


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_bytes().splitlines() if line]


def ref(path: Path) -> dict[str, str]:
    return {"path": str(path.relative_to(ROOT)), "sha256": prior.digest(path)}


def write(name: str, value: Any) -> None:
    with (OUT / name).open("xb") as handle:
        handle.write(prior.canonical(value) + b"\n")


def a6_recursive_root() -> str:
    return prior.sha(prior.canonical([[str(path.relative_to(A6)), prior.digest(path)]
        for path in sorted(A6.rglob("*"))
        if path.is_file() and path.name != "search_plan_v24_dev_alpha3_18a6_sha256"]))


def preflight() -> dict[str, Any]:
    require(not OUT.exists(), "ALPHA3_18C2_ALREADY_EXISTS")
    frozen = (
        (B2, "search_plan_v24_dev_alpha3_18b2_sha256", B2_SHA),
        (PREREG, prior.ROOT_MARKER, PREREG_SHA),
        (FAILED, failed_run.ROOT_MARKER, FAILED_SHA),
        (C1, audit.ROOT_MARKER, C1_SHA),
    )
    for directory, marker, expected in frozen:
        require(prior.root(directory, marker) == expected and
            (directory / marker).read_text().strip() == expected,
            "FROZEN_HISTORY_ROOT_MISMATCH:" + directory.name)
    require(a6_recursive_root() == A6_SHA and
        (A6 / "search_plan_v24_dev_alpha3_18a6_sha256").read_text().strip() == A6_SHA,
        "FROZEN_HISTORY_ROOT_MISMATCH:" + A6.name)
    b2 = load(B2 / "summary.json")
    a6 = load(A6 / "summary.json")
    c = load(FAILED / "summary.json")
    c_accounting = load(FAILED / "quality_execution_accounting.json")
    c1 = load(C1 / "summary.json")
    transport = rows(FAILED / "quality_transport_provenance.jsonl")
    terminals = rows(FAILED / "quality_source_terminal_states.jsonl")
    requests = rows(B2 / "proposition_quality_v2_request_manifest_v3.jsonl")
    require(len(requests) == 3 and len(transport) == len(terminals) == 1 and
        transport[0]["source_group_id"] == terminals[0]["source_group_id"] ==
        requests[0]["source_group_id"] and
        transport[0]["http_status"] == 200 and
        transport[0]["model"] == prior.MODEL and
        transport[0]["scientific_inference_event"] == 1 and
        terminals[0]["terminal_state"] == "QUALITY_RESPONSE_INVALID" and
        len(list((FAILED / "attempts").glob("*.json"))) == 1,
        "QUALITY_EXECUTION_HISTORY_MISMATCH")
    require(b2["status"] == "completed" and
        b2["builder_v3_scientific_inference_events"] == 28 and
        b2["historical_builder_v2_scientific_inference_events"] == 28 and
        b2["cumulative_builder_scientific_inference_events"] == 56 and
        b2["builder_v3_raw_candidate_count"] == 40 and
        b2["builder_v3_leakage_evaluated_denominator"] == 14 and
        b2["quality_input_candidate_count_v3"] == 5 and
        b2["quality_source_group_count_v3"] == 3 and
        b2["actual_quality_adjudication_call_count"] == 3 and
        b2["builder_v3_requests_attempted"] == 28,
        "UPSTREAM_BUILDER_FACT_MISMATCH")
    require(a6["construction_source_count_v4"] == 28 and
        a6["construction_document_valid"] == 28 and
        len(rows(A6 / "construction_source_manifest_v4.jsonl")) == 28,
        "UPSTREAM_CONSTRUCTION_FACT_MISMATCH")
    require(c["status"] == "failed" and c["failure_code"] == "QUALITY_RESPONSE_INVALID" and
        c["quality_requests_attempted"] == 1 and
        c["quality_scientific_inference_events"] == 1 and
        c["quality_valid_responses"] == 0 and
        c["quality_invalid_responses"] == 1 and
        c["all_quality_outputs_frozen"] is False and
        c_accounting["requests_attempted"] == 1 and
        c_accounting["scientific_inference_events"] == 1,
        "QUALITY_COMPLETION_STATE_MISMATCH")
    require(c1["status"] == "completed" and
        c1["defect_classification"] == "NO_INTERFACE_DEFECT_MODEL_OMISSION" and
        c1["group1_missing_schema_version_count"] == 1 and
        c1["group1_other_structural_error_count"] == 0 and
        c1["next_stage_recommendation"] ==
        "INTERPRET_ALPHA3_18C_FAILURE_UNDER_VALID_QUALITY_CONTRACT",
        "QUALITY_CONTRACT_AUDIT_MISMATCH")
    require(load(FAILED / "all_quality_outputs_freeze_barrier.json")["crossed"] is False and
        not (FAILED / "quality_candidate_final_states.jsonl").read_bytes() and
        not any((FAILED / name).exists() for name in (
            "quality_pass_candidate_manifest.jsonl", "quality_fail_candidate_manifest.jsonl",
            "quality_unresolved_candidate_manifest.jsonl")),
        "QUALITY_OUTCOME_NONDERIVATION_MISMATCH")
    require(prior.digest(FAILED / "raw_provider_responses/01.json") == audit.RAW_SHA,
        "GROUP1_RAW_RESPONSE_HASH_MISMATCH")
    return {"a6": a6, "b2": b2, "c": c, "c1": c1,
        "transport": transport[0], "terminal": terminals[0], "requests": requests}


def main() -> None:
    state = preflight()
    request_rows = state["requests"]
    group_states = [{"order_index": index, "source_group_id": row["source_group_id"],
        "terminal_state": "QUALITY_RESPONSE_INVALID" if index == 1 else
            "UNATTEMPTED_DUE_TO_PREREGISTERED_STAGE_STOP",
        "scientific_inference_events": 1 if index == 1 else 0,
        "candidate_quality_state": "UNDEFINED"}
        for index, row in enumerate(request_rows, 1)]
    OUT.mkdir()
    write("alpha3_18c_history_verification.json", {"roots": {
        "alpha3_18a6": A6_SHA, "alpha3_18b2": B2_SHA,
        "alpha3_18c_prereg": PREREG_SHA, "alpha3_18c_failed": FAILED_SHA,
        "alpha3_18c1_audit": C1_SHA}, "all_roots_verified": True,
        "group1_raw_response": ref(FAILED / "raw_provider_responses/01.json"),
        "group1_raw_hash_verified": True})
    write("quality_execution_completion_state.json", {
        "classification": "QUALITY_EXECUTION_INCOMPLETE_UNDER_VALID_RESPONSE_CONTRACT",
        "planned_quality_calls": 3, "attempted_quality_calls": 1,
        "completed_quality_scientific_inference_events": 1,
        "valid_quality_responses": 0, "invalid_quality_responses": 1,
        "unattempted_quality_source_groups": 2,
        "quality_execution_complete": False,
        "reason": "first completed inference omitted an explicitly required exact model-visible schema_version",
        "not_provider_rejection": True, "not_transport_failure": True,
        "not_scientific_candidate_rejection": True})
    write("quality_candidate_outcome_claim_boundary.json", {
        "quality_input_candidate_count": 5,
        "quality_pass_candidate_count": None,
        "quality_fail_candidate_count": None,
        "quality_unresolved_candidate_count": None,
        "count_state": "UNDEFINED",
        "candidate_quality_outcomes_derived": False,
        "zero_pass_claim_allowed": False,
        "invalid_response_criterion_values_used": False})
    write("quality_rate_claim_boundary.json", {"rates_computed": False,
        "forbidden_rate_claims": ["Quality PASS rate", "Quality FAIL rate",
            "Quality unresolved rate", "candidate acceptance rate",
            "source-level Quality success rate"],
        "reason": "valid response and denominator completion requirements not met"})
    write("quality_group_terminal_state_summary.json", {"groups": group_states,
        "groups_2_3_missing_at_random_claim": False,
        "groups_2_3_scientifically_failed_claim": False})
    write("eligible_pool_state.json", {"eligible_proposition_pool_state": "NOT_DERIVED",
        "final_pool_size": None,
        "final_pool_size_null_reason": "QUALITY_ADJUDICATION_INCOMPLETE",
        "empty_pool_or_zero_eligible_claim_allowed": False,
        "alpha3_18d_pool_finalization_allowed": False})
    write("fresh_heldout_state.json", {"fresh_heldout_v3_selected": False,
        "reason": "Quality adjudication incomplete; no eligible proposition pool frozen",
        "heldout_case_count": None})
    write("search_plan_evaluation_nonclaim.json", {"fresh_heldout_v3_search_plan_evaluation": False,
        "claims_not_supported": ["heldout retrieval accuracy", "recall", "precision",
            "candidate relevance", "Search Plan generalization"],
        "quality_failure_not_search_plan_result": True})
    write("upstream_validity_preservation.json", {"construction_sources": 28,
        "construction_evidence_documents_valid": 28,
        "builder_v3_scientific_inferences": 28,
        "builder_v3_raw_candidates": 40,
        "body_grounding_survivors": 14,
        "deterministic_precheck_survivors": 5,
        "quality_source_groups": 3,
        "upstream_source_and_builder_results_preserved": True,
        "five_candidates_scientifically_invalid_claim": False,
        "source_acquisition_OA_license_source_type_or_grounding_reversed": False})
    write("primary_failure_location.json", {"stage":
        "QUALITY_MODEL_RESPONSE_CONFORMANCE_STAGE",
        "not_stages": ["SOURCE_ACQUISITION", "BUILDER_GENERATION",
            "GROUNDING_PRECHECK", "LEAKAGE_PRECHECK",
            "QUALITY_SCIENTIFIC_ADJUDICATION_RESULT"],
        "provider_http_200": True, "model_identifier_accepted": True,
        "schema_invalid_completed_response": True})
    write("alpha3_18_attempt_terminal_state.json", {
        "ALPHA3_18_FRESH_HELDOUT_CONSTRUCTION_ATTEMPT":
            "TERMINATED_INCOMPLETE_AT_QUALITY_EXECUTION",
        "execution_protocol_outcome_not_scientific_zero_result": True,
        "post_hoc_completion_allowed": False})
    write("publication_reporting_language.json", {"preferred_concise_form": REPORTING,
        "forbidden_example": "0/5 passed Quality.",
        "must_not_imply_zero_eligible_candidates": True})
    write("reviewer_failure_disclosure.json", {"failure_class":
        "OPERATIONAL_SCHEMA_CONFORMANCE",
        "response_contract_frozen_prospectively": True,
        "missing_field_explicit_and_exact_in_model_visible_request": True,
        "retry_allowed": False,
        "preregistered_fail_closed_stop_obeyed": True,
        "incomplete_attempt_converted_to_scientific_result": False})
    write("cumulative_inference_accounting.json", {
        "historical_builder_v2_inference_events": 28,
        "builder_v3_inference_events": 28,
        "cumulative_builder_inference_events": 56,
        "quality_scientific_inference_events": 1,
        "schema_invalid_quality_inference_counted": True,
        "remaining_calls_authorized_under_completed_alpha3_18c": 0,
        "original_planned_quality_calls": 3})
    write("provider_provenance.json", {"quality_provider": "DeepSeek",
        "quality_model": prior.MODEL,
        "model_identifier_accepted": True,
        "http_status": 200,
        "historical_model_fallback_used": False,
        "prospective_active_default_reversion": False})
    write("future_protocol_boundary.json", {
        "future_controller_owned_schema_metadata_possible": True,
        "requires_new_prospective_execution_protocol": True,
        "alpha3_18c_retrospectively_defective": False,
        "alpha3_18c_groups_2_3_append_as_original_completion": False,
        "historical_group1_replay_or_schema_injection": False,
        "current_attempt_quality_execution_complete": False})
    write("primary_vs_secondary_future_use_policy.json", {
        "same_five_candidates_under_changed_contract_default_classification":
            "POST_FAILURE_SECONDARY_QUALITY_EXECUTION",
        "exception_requires_new_methodological_preregistration": True,
        "clean_primary_recommendation":
            "START_NEW_PROSPECTIVE_FRESH_HELDOUT_ATTEMPT_WITH_HARDENED_QUALITY_RESPONSE_CONTRACT",
        "new_attempt_auto_executed": False})
    write("future_quality_response_hardening_recommendation.json", {
        "status": "PROSPECTIVE_RECOMMENDATION_NOT_ACTIVATED",
        "basis": "response robustness, not scientific Quality outcomes",
        "recommended_boundaries": [
            "controller-owned deterministic schema/version metadata",
            "model ownership limited to scientifically adjudicated fields",
            "exact candidate-ID binding", "strict enum validation",
            "provider-native structured schema where supported and tested, or equivalent deterministic envelope"],
        "future_provider": "DeepSeek", "future_model": prior.MODEL,
        "historical_response_contract_changed": False})
    write("scientific_state_safety_audit.json", {"provider_calls": 0,
        "llm_calls": 0, "network_calls": 0,
        "quality_retry_calls": 0, "groups_2_3_calls": 0,
        "candidate_quality_outcomes_derived": False,
        "quality_rates_computed": False, "pool_finalized": False,
        "fresh_heldout_cases_selected": False,
        "scientific_judgment_content_used": False})
    write("historical_preservation_audit.json", {"alpha3_18a6_root_preserved":
        a6_recursive_root() == A6_SHA,
        "alpha3_18b2_root_preserved": prior.root(B2, "search_plan_v24_dev_alpha3_18b2_sha256") == B2_SHA,
        "alpha3_18c_prereg_root_preserved": prior.root(PREREG, prior.ROOT_MARKER) == PREREG_SHA,
        "alpha3_18c_failed_root_preserved": prior.root(FAILED, failed_run.ROOT_MARKER) == FAILED_SHA,
        "alpha3_18c1_root_preserved": prior.root(C1, audit.ROOT_MARKER) == C1_SHA,
        "group1_raw_response_preserved": prior.digest(FAILED / "raw_provider_responses/01.json") == audit.RAW_SHA,
        "historical_assets_modified": False})
    write("validation.json", {"status": "PASS", "alpha3_18c_history_verified": True,
        "quality_execution_complete": False,
        "quality_valid_response_count": 0,
        "quality_invalid_response_count": 1,
        "quality_unattempted_group_count": 2,
        "candidate_quality_outcomes_derived": False,
        "quality_pass_count_is_zero_claim_allowed": False,
        "quality_rates_computed": False,
        "eligible_proposition_pool_derived": False,
        "final_pool_size": None,
        "fresh_heldout_v3_selected": False,
        "alpha3_18d_allowed": False,
        "source_construction_results_preserved": True,
        "builder_results_preserved": True,
        "quality_failure_not_interpreted_as_scientific_zero": True,
        "historical_quality_inference_events": 1,
        "deepseek_flash_provider_accepted": True,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0})
    write("summary.json", {"status": "completed",
        "attempt_terminal_state": "TERMINATED_INCOMPLETE_AT_QUALITY_EXECUTION",
        "failure_classification": "QUALITY_EXECUTION_INCOMPLETE_UNDER_VALID_RESPONSE_CONTRACT",
        "quality_execution_complete": False,
        "quality_input_candidates": 5,
        "quality_source_groups": 3,
        "quality_valid_responses": 0,
        "quality_invalid_responses": 1,
        "quality_unattempted_source_groups": 2,
        "candidate_quality_outcomes_derived": False,
        "eligible_proposition_pool_state": "NOT_DERIVED",
        "final_pool_size": None,
        "fresh_heldout_v3_selected": False,
        "next_stage_recommendation": NEXT})
    require(prior.root(B2, "search_plan_v24_dev_alpha3_18b2_sha256") == B2_SHA and
        prior.root(FAILED, failed_run.ROOT_MARKER) == FAILED_SHA and
        prior.root(C1, audit.ROOT_MARKER) == C1_SHA and
        prior.digest(FAILED / "raw_provider_responses/01.json") == audit.RAW_SHA,
        "HISTORICAL_ASSET_MUTATION_DETECTED")
    root_sha = prior.root(OUT, ROOT_MARKER)
    with (OUT / ROOT_MARKER).open("x", encoding="ascii") as handle:
        handle.write(root_sha + "\n")
    print(json.dumps({"status": "completed", "root_sha256": root_sha,
        "attempt_terminal_state": "TERMINATED_INCOMPLETE_AT_QUALITY_EXECUTION",
        "next_stage_recommendation": NEXT}, sort_keys=True))


if __name__ == "__main__":
    main()
