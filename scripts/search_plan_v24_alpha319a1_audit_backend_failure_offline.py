#!/usr/bin/env python3
"""Offline audit of the closed alpha3.19A ESearch backend failure."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts import run_search_plan_v24_alpha319a_ncbi_source_acquisition as failed
from scripts import search_plan_v24_alpha319a_preregister_source_acquisition_offline as prereg
from scripts import search_plan_v24_alpha319_master_preregister_offline as master
from scripts import search_plan_v24_alpha318a4_esearch_response_validity as v2
from scripts import search_plan_v24_alpha319a1_esearch_response_validity_v2_1 as v21


ROOT = master.ROOT
FAILED = failed.OUT
OUT = ROOT / "runs/20261002_search_plan_v24_dev_alpha3_19a1_ncbi_esearch_backend_failure_audit_offline"
ROOT_MARKER = "search_plan_v24_dev_alpha3_19a1_sha256"
FAILED_SHA = "0fb0fb6dba2685a3441c3148e2148d1f65f3c2a95960a6aedb15d7e2b3db03b0"
NEXT = "AUTHORIZE_ALPHA3_19A2_FULL_NCBI_ACQUISITION_RESTART"
ENVELOPE = "NCBI_BACKEND_ERROR_ENVELOPE_IDENTIFIABLE"
DEFECT = "MULTIPLE_ESEARCH_RUNTIME_CONTRACT_GAPS"
REUSE = "PARTIAL_FRAME_REUSE_NOT_RECOMMENDED"


def require(ok: bool, code: str):
    if not ok:
        raise RuntimeError(code)


def load(path: Path):
    return json.loads(path.read_bytes())


def rows(path: Path):
    return [json.loads(x) for x in path.read_bytes().splitlines() if x]


def ref(path: Path):
    return master.ref(path)


def write(name: str, value):
    (OUT / name).write_bytes(master.canonical(value) + b"\n")


def marker(name: str, value: str):
    (OUT / name).write_text(value + "\n")


def root_hash():
    return master.sha(master.canonical([[p.name, master.digest(p)] for p in sorted(OUT.iterdir())
        if p.is_file() and p.name != ROOT_MARKER]))


def preflight():
    require(not OUT.exists(), "ALPHA3_19A1_OUTPUT_EXISTS")
    require(failed.root_hash() == FAILED_SHA and
            (FAILED / failed.ROOT_MARKER).read_text().strip() == FAILED_SHA,
            "FAILED_19A_ROOT_MISMATCH")
    require(prereg.frozen_root(prereg.OUT, "search_plan_v24_dev_alpha3_19a_prereg_sha256") ==
            failed.EXPECTED_PREREG and
            master.digest(prereg.OUT / "alpha3_19a_source_acquisition_execution_manifest.json") ==
            failed.EXPECTED_MANIFEST and
            master.digest(prereg.OUT / "alpha3_19_source_query_set.jsonl") ==
            failed.EXPECTED_QUERY_SET,
            "PREREGISTRATION_BINDING_MISMATCH")
    summary = load(FAILED / "summary.json")
    attempts = rows(FAILED / "ncbi_transport_attempts.jsonl")
    page_results = rows(FAILED / "source_query_execution_results.jsonl")
    request_rows = rows(FAILED / "source_query_request_manifest.jsonl")
    require(summary["status"] == "failed" and
            summary["failure_code"] ==
            "PhaseFailure:ALPHA3_19A_SOURCE_FRAME_FAILED_CLOSED:RESPONSE_SCHEMA_INVALID" and
            summary["source_frames_completed"] == 4 and summary["raw_source_records"] == 800 and
            summary["deduplicated_source_records"] is None and
            summary["sampled_source_count"] is None and
            summary["sampled_metadata_records"] == 0 and
            summary["pmc_jats_requested"] == 0 and
            len(attempts) == 22 and len(page_results) == 20 and
            len({a["request_key"] for a in attempts}) == 20 and
            len(list((FAILED / "six_source_frame_manifests").glob("*.json"))) == 4 and
            not any((FAILED / name).exists() for name in (
                "alpha3_19_sampling_universe.jsonl", "deterministic_source_sampling_results.jsonl",
                "historical_source_contamination_results.jsonl", "sampled_source_metadata_manifest.jsonl",
                "oa_subset_request_manifest.jsonl", "pmc_jats_request_manifest.jsonl",
                "alpha3_19a_jats_handoff_manifest.jsonl")),
            "FAILED_RUN_STATE_MISMATCH")
    request = next((r for r in request_rows if r["request_ordinal"] == 20), None)
    page = page_results[-1]
    pair = [a for a in attempts if a["request_key"] == "05_150"]
    require(request is not None and request["stratum_id"] == "cancer_biology" and
            request["page_retstart"] == 150 and page["request_ordinal"] == 20 and
            page["stratum_id"] == "cancer_biology" and page["retstart"] == 150 and
            page["validity"]["state"] == "RESPONSE_SCHEMA_INVALID" and
            page["validity"]["reason"] == "COUNT_OR_PAGINATION_FIELD_INVALID" and
            len(pair) == 2 and pair[0]["attempt"] == 1 and pair[1]["attempt"] == 2 and
            pair[0]["status"] is None and "Connection reset by peer" in pair[0]["error"] and
            pair[0]["raw_bytes"] == 0 and pair[1]["status"] == 200 and
            pair[1]["raw_bytes"] == 154 and
            pair[1]["raw_sha256"] == page["raw_response_sha256"],
            "FAILING_PAGE_PROVENANCE_MISMATCH")
    raw1 = FAILED / pair[0]["raw_path"]
    raw2 = FAILED / pair[1]["raw_path"]
    require(raw1.read_bytes() == b"" and
            master.digest(raw1) == pair[0]["raw_sha256"] and
            master.digest(raw2) == pair[1]["raw_sha256"] and
            pair[1]["raw_sha256"] ==
            "aef9ad596fe089f1907c40ea6126abd35414ec1746a310a04e5453bb24bf5b67",
            "RAW_ATTEMPT_INTEGRITY_MISMATCH")
    payload = json.loads(raw2.read_bytes())
    require(set(payload) == {"header", "esearchresult"} and
            set(payload["esearchresult"]) == {"ERROR"} and
            isinstance(payload["esearchresult"]["ERROR"], str) and
            payload["esearchresult"]["ERROR"].startswith(v21.BACKEND_PREFIX),
            "OBSERVED_ERROR_ENVELOPE_MISMATCH")
    old = v2.validate_response(200, raw2.read_bytes(), 150, 50)
    new = v21.validate_response(200, raw2.read_bytes(), 150, 50)
    require(old == page["validity"] and
            new["state"] == "NCBI_ESearch_BACKEND_ERROR" and
            new["technical_retryable"] and not new["valid_page"],
            "VALIDATOR_REPLAY_MISMATCH")
    frozen_transport = load(master.A4 / "alpha3_18a4_source_acquisition_execution_manifest_v2.json")[
        "active_source_frame_policy_v2"]
    require(frozen_transport["maximum_attempts_per_request"] == 4 and
            frozen_transport["backoff_seconds"] == [2, 4, 8] and
            frozen_transport["timeout_seconds"] == 60,
            "HISTORICAL_RETRY_POLICY_MISMATCH")
    return {"summary": summary, "attempts": attempts, "request": request,
            "page": page, "pair": pair, "payload": payload, "old": old,
            "new": new, "raw1": raw1, "raw2": raw2,
            "frozen_transport": frozen_transport}


def main():
    state = preflight()
    request = state["request"]
    pair = state["pair"]
    payload = state["payload"]
    manifest_path = prereg.OUT / "alpha3_19a_source_acquisition_execution_manifest.json"
    manifest = load(manifest_path)
    seed_path = master.OUT / "alpha3_19_sampling_seed_contract.json"
    seed = load(seed_path)
    require(seed["seed"] == master.sha(seed["seed_input"].encode()),
            "SAMPLING_SEED_MISMATCH")
    OUT.mkdir()
    write("failed_19a_root_verification.json", {
        "failed_run_root_sha256": FAILED_SHA,
        "root_verified": True, "historical_state": "FAILED_CLOSED",
        "completed_frames": 4, "raw_completed_frame_records": 800,
        "logical_page_requests": 20, "ncbi_attempts": 22,
        "deduplication_occurred": False, "sampling_occurred": False,
        "metadata_oa_jats_builder_occurred": False,
        "historical_run_modified": False})
    write("failing_logical_request_identity.json", {
        "request_ordinal": 20, "frame_index": 5, "stratum_id": request["stratum_id"],
        "retstart": 150, "query_sha256": request["query_sha256"],
        "request_record_sha256": master.sha(master.canonical(request)),
        "request_parameters_sha256": master.sha(master.canonical(request["parameters"])),
        "request_record": request,
        "historical_request_manifest": ref(FAILED / "source_query_request_manifest.jsonl"),
        "transport_attempt_count": 2,
        "headers_preserved": False,
        "headers_not_preserved_claim_boundary": "HTTP response headers were not serialized by the frozen Transport log"})
    write("attempt1_connection_reset_audit.json", {
        "attempt": 1, "transport_record": pair[0],
        "raw_response": ref(state["raw1"]),
        "transport_state": "CONNECTION_RESET_BY_PEER",
        "application_body_received": False,
        "scientific_or_source_data_returned": False,
        "frozen_retry_allowed": True,
        "attempt_budget_consumed": 1})
    write("attempt2_http200_error_payload_audit.json", {
        "attempt": 2, "transport_record": pair[1],
        "raw_response": ref(state["raw2"]),
        "http_status": 200, "body_bytes": pair[1]["raw_bytes"],
        "body_utf8": state["raw2"].read_text(),
        "top_level_keys": sorted(payload),
        "esearchresult_keys": sorted(payload["esearchresult"]),
        "exact_error_only_esearchresult": True,
        "raw_error_text": payload["esearchresult"]["ERROR"],
        "errorlist_present": False,
        "ordinary_success_fields_present": False,
        "http_headers_preserved": False})
    write("esearch_v2_validator_trace.json", {
        "contract": ref(master.A4 / "pubmed_esearch_response_validity_v2.json"),
        "implementation": ref(ROOT / "scripts/search_plan_v24_alpha318a4_esearch_response_validity.py"),
        "trace": ["HTTP 200 -> transport success", "JSON parse success",
                  "esearchresult object valid", "lowercase errorlist absent",
                  "uppercase ERROR not handled by V2",
                  "count/retstart/retmax missing -> COUNT_OR_PAGINATION_FIELD_INVALID"],
        "historical_v2_result": state["old"],
        "historical_failure_classification": "RESPONSE_SCHEMA_INVALID",
        "retrospective_reclassification_allowed": False})
    write("esearch_error_vs_errorlist_audit.json", {
        "observed_key": "esearchresult.ERROR", "v2_key": "esearchresult.errorlist",
        "same_field": False, "v2_uppercase_error_recognition": False,
        "semantic_ErrorList_rule_preserved": True,
        "phrase_or_field_not_found_semantics_not_backend_retry": True,
        "HTTP_like_number_in_ErrorList_does_not_override_semantic_state": True})
    write("esearch_backend_error_envelope_assessment.json", {
        "classification": ENVELOPE,
        "observed_exact_structure": {"top_level_keys": sorted(payload),
                                     "esearchresult_keys": ["ERROR"]},
        "recognition": "error-only esearchresult.ERROR nonempty string with Search Backend failed: prefix",
        "HTTP_502_substring_required": False,
        "raw_text_retained": True,
        "not_a_valid_zero_or_success_page": True,
        "non_backend_ERROR_text": "ERROR_ENVELOPE_AUTHORITY_UNRESOLVED_FAIL_CLOSED",
        "ERROR_plus_success_fields": "CONFLICTING_ERROR_ENVELOPE_FAIL_CLOSED"})
    write("esearch_runtime_defect_classification.json", {
        "classification": DEFECT,
        "validator_gap": "V2 omitted the distinct uppercase ERROR envelope; returned generic schema-invalid",
        "retry_contract_gap": "frozen policy had no category-specific HTTP-200 backend ERROR retry disposition",
        "historical_fail_closed_behavior_valid": True,
        "historical_state_rewrite_allowed": False,
        "scientific_query_defect": False})
    write("historical_failure_classification_preservation.json", {
        "historical_state": "RESPONSE_SCHEMA_INVALID",
        "historical_reason": "COUNT_OR_PAGINATION_FIELD_INVALID",
        "historical_run_root": FAILED_SHA,
        "v2_1_replay_is_prospective_design_evidence_only": True,
        "failed_execution_overwritten_or_resumed": False})
    write("technical_retry_policy_audit.json", {
        "frozen_policy": ref(master.A4 / "alpha3_18a4_source_acquisition_execution_manifest_v2.json"),
        "maximum_attempts_per_logical_request": 4,
        "timeout_seconds": 60, "backoff_seconds": [2, 4, 8],
        "attempt1_connection_reset_consumed": 1,
        "attempt2_http200_backend_error_consumed": 1,
        "historical_remaining_attempts_not_authorized_for_retroactive_use": True,
        "historical_HTTP200_backend_ERROR_disposition": "UNSPECIFIED_THEN_V2_SCHEMA_INVALID_TERMINAL",
        "new_budget_increase": False})
    write("historical_retry_accounting.json", {
        "logical_page_requests": 20, "actual_ncbi_attempts": 22,
        "failing_logical_request_attempts": 2,
        "connection_reset_attempt_retained": True,
        "third_historical_attempt_allowed_now": False,
        "attempt_records": [ref(FAILED / "ncbi_transport_attempts.jsonl"),
                            ref(state["raw1"]), ref(state["raw2"])]})
    write("partial_frame_reuse_audit.json", {
        "classification": REUSE,
        "completed_frames": 4,
        "fifth_frame_partial_valid_pages": [0, 50, 100],
        "reason": "relevance-sorted live PubMed pages lack a frozen shared server-side snapshot identity; mixing executions could change membership/order",
        "direct_import_of_failed_pages": False,
        "future_page_union_or_best_of_two": False,
        "future_full_restart_from_frame1_retstart0": True})
    request_rows = rows(FAILED / "source_query_request_manifest.jsonl")
    require(not any(any(key.casefold() in {k.casefold() for k in row["parameters"]}
                        for key in ("usehistory", "WebEnv", "query_key"))
                    for row in request_rows),
            "UNEXPECTED_SERVER_SNAPSHOT_IDENTITY")
    write("search_snapshot_mechanism_audit.json", {
        "stable_snapshot_bound": False,
        "request_parameter_audit": ref(FAILED / "source_query_request_manifest.jsonl"),
        "usehistory_WebEnv_query_key_present": False,
        "sort": "relevance", "pagination": "live retstart offsets",
        "all_pages_same_server_snapshot_guaranteed": False})
    eligible = all([
        not (FAILED / "alpha3_19_sampling_universe.jsonl").exists(),
        not (FAILED / "deterministic_source_sampling_results.jsonl").exists(),
        not (FAILED / "historical_source_contamination_results.jsonl").exists(),
        not (FAILED / "sampled_source_metadata_manifest.jsonl").exists(),
        load(FAILED / "summary.json")["source_query_changes"] == 0,
        manifest["query_set"]["sha256"] == failed.EXPECTED_QUERY_SET,
        manifest["sampling_seed"]["sha256"] == master.digest(seed_path),
    ])
    require(eligible, "FULL_RESTART_ELIGIBILITY_FAILED")
    write("full_restart_eligibility.json", {
        "full_six_frame_restart_eligible": True,
        "identity": "PROSPECTIVE_TECHNICAL_ACQUISITION_RESTART_AFTER_PRE_SAMPLING_NCBI_FAILURE",
        "remains_alpha3_19_fresh_heldout_attempt_2": True,
        "historical_deduplication_occurred": False,
        "historical_sampling_occurred": False,
        "historical_contamination_screening_occurred": False,
        "historical_metadata_or_scientific_selection_occurred": False,
        "query_or_seed_changed": False,
        "failed_run_yield_used_for_policy_tuning": False,
        "not_best_of_two_sampled_pools": True,
        "separate_future_network_authorization_required": True})
    write("failed_technical_source_record_disposition.json", {
        "complete_frame_raw_record_count": 800,
        "state": "FAILED_TECHNICAL_ACQUISITION_PROVENANCE",
        "direct_import_to_restart_frame": False,
        "partial_fifth_frame_pages_direct_import": False,
        "naturally_reappearing_pmids_blacklisted": False,
        "old_new_page_union_or_rank_selection": False})
    write("sampling_seed_preservation_audit.json", {
        "master_seed_contract": ref(seed_path),
        "seed": seed["seed"], "seed_changed": False,
        "new_seed_because_of_failure": False,
        "used_only_after_complete_new_frame_freeze": True})

    scientific_keys = ["query_set", "query_hashes", "query_count", "frame_policy",
        "dedup", "sampling_seed", "sampling_algorithm", "historical_contamination_registry",
        "historical_contamination_gate", "metadata_parser_and_fields", "date_rule",
        "publication_type_rule", "correction_rule", "oa_subset_route", "jats_route",
        "required_future_output_paths"]
    write("scientific_configuration_nonadaptation_audit.json", {
        "same_source_cohort": ["2024-01-01", "2025-12-31"],
        "same_six_queries_sha256": failed.EXPECTED_QUERY_SET,
        "same_sort_page_size_frame_cap": ["relevance", 50, 200],
        "same_sampling_seed": seed["seed"],
        "same_sample_cap_per_stratum": 12,
        "same_seen_source_registry": manifest["historical_contamination_registry"],
        "downstream_metadata_oa_jats_policies_unchanged": True,
        "query_or_scientific_policy_changed": False,
        "only_transport_response_classification_and_retry_ownership_amended": True,
        "scientific_manifest_keys_preserved": scientific_keys})

    v21_contract = {
        "schema_version": "PubMedESearchResponseValidityV2_1",
        "prospective_only": True,
        "historical_V2_reclassification": False,
        "implementation": ref(ROOT / "scripts/search_plan_v24_alpha319a1_esearch_response_validity_v2_1.py"),
        "old_v2_contract": ref(master.A4 / "pubmed_esearch_response_validity_v2.json"),
        "classification_order": ["transport", "JSON parse / XML ErrorList guard",
            "esearchresult object", "uppercase ERROR envelope / conflict",
            "lowercase errorlist semantic failure", "ordinary success schema",
            "WarningList policy", "valid zero or nonzero"],
        "states": ["TRANSPORT_FAILURE", "JSON_PARSE_FAILURE", "NCBI_ESearch_BACKEND_ERROR",
            "ERROR_ENVELOPE_AUTHORITY_UNRESOLVED", "CONFLICTING_ERROR_ENVELOPE",
            "QUERY_SEMANTIC_ERROR", "WARNING_POLICY_FAILURE", "SUCCESS_SCHEMA_INVALID",
            "VALID_ZERO", "VALID_NONZERO"],
        "backend_recognition": "exact error-only esearchresult.ERROR nonempty string beginning Search Backend failed:",
        "HTTP_502_text_required": False,
        "raw_ERROR_text_retained": True,
        "ERROR_plus_success_fields": "CONFLICTING_ERROR_ENVELOPE_FAIL_CLOSED_NO_RETRY",
        "non_backend_ERROR": "ERROR_ENVELOPE_AUTHORITY_UNRESOLVED_FAIL_CLOSED_NO_RETRY",
        "ErrorList_semantic_rule_unchanged": True,
        "WarningList_allowlist_unchanged": True,
        "backend_ERROR_valid_zero_allowed": False}
    write("pubmed_esearch_response_validity_v2_1.json", v21_contract)
    marker("pubmed_esearch_response_validity_v2_1_sha256",
           master.digest(OUT / "pubmed_esearch_response_validity_v2_1.json"))
    retry = {
        "schema_version": "Alpha319A2ESearchTechnicalRetryPolicyV1",
        "prospective_full_restart_only": True,
        "attempts_max_per_logical_page": 4,
        "timeout_seconds": 60, "backoff_seconds": [2, 4, 8],
        "http_retryable_status": [408, 429, 500, 502, 503, 504],
        "connection_reset_or_timeout": "RETRY_WITHIN_SAME_FOUR_ATTEMPTS",
        "HTTP_5xx": "RETRY_WITHIN_SAME_FOUR_ATTEMPTS",
        "HTTP200_NCBI_ESearch_BACKEND_ERROR": "RETRY_WITHIN_SAME_FOUR_ATTEMPTS",
        "HTTP200_response_handling": "freeze raw attempt, run V2.1 classifier before transport returns success; backend-error state consumes this attempt and may retry",
        "historical_HTTP200_immediate_return_implementation_reusable_unchanged": False,
        "HTTP200_QUERY_SEMANTIC_ERROR": "FAIL_CLOSED_NO_RETRY",
        "HTTP200_WARNING_POLICY_FAILURE": "FAIL_CLOSED_NO_RETRY",
        "HTTP200_SUCCESS_SCHEMA_INVALID": "FAIL_CLOSED_NO_RETRY",
        "HTTP200_JSON_PARSE_FAILURE": "FAIL_CLOSED_NO_RETRY",
        "ERROR_ENVELOPE_AUTHORITY_UNRESOLVED": "FAIL_CLOSED_NO_RETRY",
        "CONFLICTING_ERROR_ENVELOPE": "FAIL_CLOSED_NO_RETRY",
        "non_retryable_HTTP_status": "FAIL_CLOSED_NO_RETRY",
        "technical_attempts_consumed_by_backend_ERROR": True,
        "technical_budget_increased": False,
        "technical_attempts_exhausted": "STOP_STAGE_FAIL_CLOSED",
        "unknown_or_unclassified_state": "STOP_STAGE_FAIL_CLOSED",
        "query_rewrite_or_fallback": False,
        "historical_third_attempt": False}
    write("alpha3_19a2_retry_policy.json", retry)
    future = copy.deepcopy(manifest)
    future["schema_version"] = "Alpha319A2FullAcquisitionRestartExecutionManifestV1"
    future["status"] = "PROSPECTIVE_FULL_RESTART_PREREGISTERED_NO_NETWORK_AUTHORIZED_HERE"
    future["phase"] = "19A2"
    future["restart_mode"] = "FULL_SIX_FRAME_FROM_FRAME_1_RETSTART_0"
    future["source_run_disposition"] = "FAILED_19A_PROVENANCE_ONLY_NO_DIRECT_IMPORT"
    future["parent_execution_manifest"] = ref(manifest_path)
    future["failed_19a_run_root_sha256"] = FAILED_SHA
    future["esearch_validator"] = ref(OUT / "pubmed_esearch_response_validity_v2_1.json")
    future["esearch_validator_implementation"] = ref(ROOT / "scripts/search_plan_v24_alpha319a1_esearch_response_validity_v2_1.py")
    future["esearch_retry_policy"] = ref(OUT / "alpha3_19a2_retry_policy.json")
    future["response_aware_retry_adapter_required"] = True
    future["historical_HTTP200_immediate_return_transport_not_reusable_unchanged"] = True
    future["esearch_error_warning_schema"]["historical_semantic_authority_unchanged"] = True
    future["future_network_execution_requires_separate_authorization"] = True
    future["material_runtime_policy_unresolved_count"] = 0
    require(all(future[key] == manifest[key] for key in scientific_keys) and
            future["query_count"] == 6 and
            future["material_runtime_policy_unresolved_count"] == 0,
            "SCIENTIFIC_CONFIGURATION_DRIFT")
    def verify_refs(node):
        if isinstance(node, dict):
            if "path" in node and "sha256" in node:
                prereg.check_ref(node)
            for value in node.values():
                verify_refs(value)
        elif isinstance(node, list):
            for value in node:
                verify_refs(value)
    verify_refs(future)
    write("alpha3_19a2_source_acquisition_execution_manifest.json", future)
    marker("alpha3_19a2_source_acquisition_execution_manifest_sha256",
           master.digest(OUT / "alpha3_19a2_source_acquisition_execution_manifest.json"))
    write("historical_preservation_audit.json", {
        "historical_assets_modified": False,
        "verified_failed_root_sha256": FAILED_SHA,
        "read_only_sources": [ref(FAILED / "summary.json"),
            ref(FAILED / "source_query_execution_results.jsonl"),
            ref(FAILED / "ncbi_transport_attempts.jsonl"), ref(state["raw1"]), ref(state["raw2"])],
        "historical_v2_classification_preserved": True})
    write("scientific_state_safety_audit.json", {
        "queries_changed": False, "sampling_seed_changed": False,
        "source_or_candidate_selected": False,
        "failed_19a_artifacts_reused_as_new_frames": False,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0})
    required = ["failed_19a_root_verification.json", "failing_logical_request_identity.json",
        "attempt1_connection_reset_audit.json", "attempt2_http200_error_payload_audit.json",
        "esearch_v2_validator_trace.json", "esearch_error_vs_errorlist_audit.json",
        "esearch_backend_error_envelope_assessment.json", "esearch_runtime_defect_classification.json",
        "historical_failure_classification_preservation.json", "technical_retry_policy_audit.json",
        "historical_retry_accounting.json", "partial_frame_reuse_audit.json",
        "search_snapshot_mechanism_audit.json", "full_restart_eligibility.json",
        "failed_technical_source_record_disposition.json", "sampling_seed_preservation_audit.json",
        "scientific_configuration_nonadaptation_audit.json",
        "pubmed_esearch_response_validity_v2_1.json",
        "pubmed_esearch_response_validity_v2_1_sha256", "alpha3_19a2_retry_policy.json",
        "alpha3_19a2_source_acquisition_execution_manifest.json",
        "alpha3_19a2_source_acquisition_execution_manifest_sha256",
        "historical_preservation_audit.json", "scientific_state_safety_audit.json"]
    require(all((OUT / name).is_file() for name in required), "AUDIT_REQUIRED_ARTIFACT_MISSING")
    write("validation.json", {"status": "completed", "required_artifacts_present": True,
        "failed_root_verified": True, "raw_attempt_hashes_verified": True,
        "v2_replay_matches_historical": True,
        "v2_1_replay_backend_classification": True,
        "manifest_scientific_keys_unchanged": True,
        "synthetic_validator_tests_required": True,
        "material_runtime_policy_unresolved_count": 0})
    write("summary.json", {"status": "completed",
        "historical_alpha3_19a_preserved": True,
        "failed_frame_index": 5, "failed_retstart": 150,
        "attempt1_transport_state": "CONNECTION_RESET_BY_PEER",
        "attempt2_http_status": 200,
        "attempt2_esearchresult_error_present": True,
        "esearch_backend_error_envelope": ENVELOPE,
        "historical_failure_classification": "RESPONSE_SCHEMA_INVALID",
        "runtime_contract_defect_classification": DEFECT,
        "stable_snapshot_bound": False,
        "partial_frame_reuse_recommended": False,
        "historical_deduplication_occurred": False,
        "historical_sampling_occurred": False,
        "historical_scientific_selection_occurred": False,
        "full_six_frame_restart_eligible": True,
        "sampling_seed_changed": False, "source_queries_changed": False,
        "scientific_policy_changed": False,
        "pubmed_esearch_response_validity_v2_1_created": True,
        "material_runtime_policy_unresolved_count": 0,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "next_stage_recommendation": NEXT,
        "historical_assets_modified": False})
    marker(ROOT_MARKER, root_hash())
    print(master.canonical({"status": "completed", "out": str(OUT),
        "v2_1_sha256": master.digest(OUT / "pubmed_esearch_response_validity_v2_1.json"),
        "a2_manifest_sha256": master.digest(OUT / "alpha3_19a2_source_acquisition_execution_manifest.json"),
        "root_sha256": root_hash()}).decode())


if __name__ == "__main__":
    main()
