#!/usr/bin/env python3
"""Read-only D2 failure-authority audit; never implement or execute recovery.

Only the new audit directory is written. Binary responses are hashed, not
parsed. Continuation coordinates are non-executable diagnostics, not a new
request manifest or authorization. Missing exception provenance stays missing.
"""

from __future__ import annotations

import http.client
import inspect
import json
import os
import socket
import urllib.error
import urllib.request
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from scripts import run_search_plan_v24_alpha321d2_pmc_execution as d2


ROOT = d2.ROOT
OUT = ROOT / "runs/20261007_search_plan_v24_primary_alpha3_21d21_runtime_failure_authority_audit_offline"
ROOT_MARKER = "search_plan_v24_primary_alpha3_21d21_sha256"
STAGE = "FRESH_PRIMARY_ALPHA3_21_D2_RUNTIME_FAILURE_AUTHORITY_AUDIT"
CLASS_C = "INCOMPLETE_READ_RETRY_AUTHORITY_UNRESOLVED"
CLASS_INTEGRITY = "D2_RUNTIME_FAILURE_AUDIT_BLOCKED_BY_ARTIFACT_INTEGRITY_FAILURE"
NEXT_C = "AUDIT_ALPHA3_21_D2_RETRY_POLICY_AUTHORITY_OFFLINE"
NEXT_INTEGRITY = "AUDIT_ALPHA3_21D2_ARTIFACT_INTEGRITY_OFFLINE"
D2_SHA = "6e79e6f4b48c0d670a1de7f1c6bc7627095d90ac037ce3400f19c65efa56bdc8"
RETRY_SHA = "8035ef2073e450b79f89404dd760a8fe8bebbe69f0d0e47bdf3b188f3eb72faa"
NO_CALLS = {k: 0 for k in ("network_calls", "pubmed_calls", "pmc_calls", "provider_calls",
                         "llm_calls", "builder_calls", "quality_calls")}
REQUIRED = (
    "alpha3_21d2_root_verification", "alpha3_21d1_root_verification", "alpha3_21d_root_verification",
    "d2_failure_snapshot_integrity_audit", "failed_jats_logical_request_reconstruction",
    "failed_attempt_exception_chain", "incomplete_read_partial_response_audit",
    "frozen_retry_contract_authority_binding", "retry_semantic_scope_audit",
    "runtime_exception_mapping_audit", "incomplete_read_retry_authority_classification",
    "per_request_attempt_budget_audit", "jats_execution_state_reconstruction",
    "blocked_jats_semantics_audit", "partial_construction_handoff_semantics_audit",
    "oa_phase_immutability_audit", "jats_activation_manifest_immutability_audit",
    "successful_jats_immutability_audit", "continuation_resume_point_contract",
    "continuation_order_contract", "continuation_transport_budget", "fulltext_exposure_state_audit",
    "current_attempt_no_self_contamination_audit", "known_preexisting_test_environment_issue",
    "scientific_policy_nonadaptation_audit", "historical_preservation_audit",
    "scientific_state_safety_audit", "validation", "summary",
)
A_ONLY = (
    "pmc_jats_transport_exception_mapping_overlay_v1.json",
    "pmc_jats_transport_exception_mapping_overlay_v1_sha256",
    "d2r_runtime_overlay_test_results.json", "d2r_continuation_eligibility.json",
)
canonical, sha, digest, obj, rows, ref, root_hash, require = (
    d2.canonical, d2.sha, d2.digest, d2.obj, d2.rows, d2.ref, d2.root_hash, d2.require)


def root_check(directory, marker, expected):
    actual = root_hash(directory, marker)
    marker_value = (directory / marker).read_text().strip()
    require(actual == marker_value == expected, "ARTIFACT_ROOT_MISMATCH:" + str(directory))
    return {"verified": True, "expected_sha256": expected, "computed_sha256": actual,
            "marker": ref(directory / marker, "immutable_upstream_root")}


def checked_records(path):
    values = rows(path)
    for value in values:
        d2.d1.d.checked_tree(value)
    return values


def code_binding(value):
    return d2.d1.d.implementation(value, "read_only_frozen_runtime_evidence")


def persisted_exception_facts(attempt):
    """The spelling is observed; the concrete class/module/chain is not."""
    require(attempt.get("unhandled_frozen_client_exception") is True,
            "EXPECTED_UNHANDLED_EXCEPTION_RECORD_MISSING")
    name, separator, message = attempt["transport_error"].partition(":")
    require(separator and name == "IncompleteRead", "OBSERVED_FAILURE_SHAPE_CHANGED")
    candidate = http.client.IncompleteRead(b"x" * attempt["raw_bytes"])
    return {
        "observed_exception_name": name, "observed_exception_message": message,
        "observed_exception_module": None, "observed_qualified_exception_class": None,
        "traceback": None, "cause_chain": None, "context_chain": None,
        "expected_remaining_bytes": None, "actual_HTTP_response_status": None,
        "logged_HTTP_status": attempt["http_status"],
        "logged_HTTP_status_origin": "getattr(exc, 'code', None), not preserved response.status",
        "timestamp_utc": attempt["timestamp_utc"], "timestamp_kind": attempt["timestamp_kind"],
        "provenance_state": "CONCRETE_CLASS_AND_CHAIN_NOT_PRESERVED_IN_FROZEN_ARTIFACTS",
        "missing_data_not_reconstructed_by_assumption": True,
        "local_candidate_demonstration": {
            "class": "http.client.IncompleteRead", "origin": "LOCAL_SYNTHETIC_NOT_OBSERVED_EXCEPTION",
            "message_matches": str(candidate) == message,
            "mro": [cls.__module__ + "." + cls.__name__ for cls in type(candidate).__mro__],
            "matches_frozen_generic_exception_tuple": isinstance(candidate, (urllib.error.URLError, TimeoutError, OSError)),
            "consistent_candidate_not_unique_provenance_proof": True,
            "used_as_retry_authority": False,
            "local_class_source_sha256": sha(inspect.getsource(http.client.IncompleteRead).encode()),
        },
    }


def reconstruct(activated, requests, attempts, structural, maximum):
    """Reconstruct from original identities only; create no request payloads."""
    frozen = {r["logical_request_id"]: r for r in requests}
    require(len(frozen) == len(requests), "DUPLICATE_FROZEN_REQUEST_ID")
    active = [r for r in activated if r["activation_state"] == "REQUIRED_BY_OA_ELIGIBILITY"]
    original = [r for r in requests if r["request_class"] == "PMC_JATS"]
    require([r["logical_request_id"] for r in activated] == [r["logical_request_id"] for r in original],
            "ACTIVATION_ORDER_DIFFERS_FROM_FROZEN_REQUEST_ORDER")
    for entry in activated:
        request = frozen[entry["logical_request_id"]]
        require(entry["frozen_request_record_sha256"] == sha(canonical(request))
                and entry["request_payload_sha256"] == request["request_payload_sha256"],
                "ACTIVATION_REQUEST_BINDING_MISMATCH")
    seen_order = list(dict.fromkeys(a["logical_request_id"] for a in attempts))
    require(seen_order == [r["logical_request_id"] for r in active[:len(seen_order)]],
            "STARTED_REQUESTS_NOT_FROZEN_ORDER_PREFIX")
    successful = [r["logical_request_id"] for r in structural]
    require(successful == seen_order[:-1] and len(set(successful)) == len(successful),
            "SUCCESSFUL_PREFIX_RECONSTRUCTION_MISMATCH")
    failed_id = seen_order[-1]
    failed = frozen[failed_id]
    failed_attempts = [a for a in attempts if a["logical_request_id"] == failed_id]
    for key in seen_order:
        history = [a for a in attempts if a["logical_request_id"] == key]
        require([a["attempt"] for a in history] == list(range(1, len(history) + 1))
                and len(history) <= maximum, "NONCONTIGUOUS_OR_EXCEEDED_ATTEMPT_BUDGET")
        for attempt in history:
            request = frozen[key]
            require(attempt["frozen_request_record_sha256"] == sha(canonical(request))
                    and attempt["request_payload_sha256"] == request["request_payload_sha256"]
                    and attempt["endpoint"] == request["request_payload"]["endpoint"]
                    and attempt["parameters"] == request["request_payload"]["parameters"]
                    and attempt["pmid"] == request["pmid"], "ATTEMPT_FROZEN_REQUEST_BINDING_MISMATCH")
    untouched = active[len(seen_order):]
    remaining = maximum - len(failed_attempts)
    return {"failed": failed, "failed_attempts": failed_attempts, "successful_ids": successful,
            "untouched": untouched, "active": active, "remaining_attempts": remaining,
            "hypothetical_next_attempt": len(failed_attempts) + 1,
            "hypothetical_original_order_ids": [failed_id] + [r["logical_request_id"] for r in untouched],
            "conditional_additional_ceiling": remaining + len(untouched) * maximum}


def retry_scope(policy, historical_failure, historical_jats, exception_facts):
    """Explicitly scoped evidence assessment, not a new runtime retry predicate."""
    require(policy["maximum_attempts_per_request"] == historical_failure["attempts_max"]
            == historical_jats["technical_max_attempts"] == 4, "RETRY_BUDGET_AUTHORITY_MISMATCH")
    require(policy["retryable_http_status"] == historical_failure["retryable_status"]
            == [408, 429, 500, 502, 503, 504]
            and policy["missing_HTTP_status_retryable"] is True
            and policy["HTTP_200_without_transport_error_ends_retry"] is True
            and policy["parse_license_identity_BODY_failure_retry_allowed"] is False,
            "FROZEN_RETRY_CONTRACT_CHANGED")
    # No exception-set closure or broad body-read domain occurs in these exact
    # bound contracts. The incidental catch tuple cannot establish closure.
    require("exception_classes" not in policy and "body_read_interruption" not in policy,
            "RETRY_AUTHORITY_REQUIRES_NEW_OFFLINE_AUDIT")
    return {
        "classification": CLASS_C, "primary_classification_count": 1,
        "frozen_retry_semantics_resolved": False,
        "incomplete_read_covered_by_frozen_retry_semantics": False,
        "coverage_state": "NOT_ESTABLISHED_NEITHER_COVERED_NOR_PROVEN_EXCLUDED",
        "false_coverage_boolean_means": "coverage not established, not affirmative exclusion (B)",
        "runtime_exception_mapping_defect": False,
        "defect_state": "SEMANTIC_IMPLEMENTATION_DEFECT_NOT_ESTABLISHED",
        "runtime_exception_mapping_omission_observed": True,
        "retry_policy_semantics_changed": False,
        "runtime_recovery_within_same_primary_attempt_allowed": False,
        "next_stage_recommendation": NEXT_C,
        "broad_body_read_transport_class_explicitly_defined": False,
        "closed_explicit_exception_set_semantically_declared": False,
        "status_domain_defined": policy["retryable_http_status"],
        "missing_HTTP_status_retryable": True,
        "HTTP_200_with_incomplete_transfer_semantics_explicitly_defined": False,
        "actual_HTTP_status_available": exception_facts["actual_HTTP_response_status"] is not None,
        "concrete_exception_provenance_available": exception_facts["observed_qualified_exception_class"] is not None,
        "reason": "Frozen contracts define status/budget mechanics, not a complete body-read exception domain. "
                  "The outer adapter's null status is not proof of a missing HTTP response status. "
                  "Observed unhandled exception name lacks module/chain provenance. "
                  "Neither broad coverage (A) nor a semantically closed excluding exception set (B) is established.",
        "no_exclusion_inferred_from_missing_catch": True,
        "no_retry_inferred_from_network_appearance_or_null_adapter_status": True,
        "scientific_yield_used_in_classification": False,
    }


def collect_audit():
    artifacts = {}
    protected = ((d2.OUT, d2.ROOT_MARKER, D2_SHA), (d2.D1, d2.d1.ROOT_MARKER, d2.D1_SHA),
                 (d2.D, d2.d1.d.ROOT_MARKER, d2.d1.D_SHA))
    for stem, values in zip(("alpha3_21d2", "alpha3_21d1", "alpha3_21d"), protected):
        artifacts[stem + "_root_verification"] = root_check(*values)
    state = d2.preflight()  # Read-only inherited roots/contracts/request-byte checks.
    for path in sorted(d2.OUT.glob("*.json")):
        d2.d1.d.checked_tree(obj(path))
    frozen_refs = []
    for path in sorted(d2.OUT.rglob("*")):
        if path.is_file():
            frozen_refs.append(ref(path, "D2_snapshot_read_only"))
    streams = {Path(name).stem: checked_records(d2.OUT / name) for name in d2.STREAMS}
    summary = obj(d2.OUT / "summary.json")
    require(summary["status"] == "failed" and summary["alpha3_21d2_classification"] == d2.CLASS_FAIL,
            "D2_FROZEN_FAILURE_STATE_MISMATCH")
    bindings = obj(d2.OUT / "alpha321_pmc_jats_execution_authority_v2_binding.json")
    for key, value in (("historical_transport", d2.legacy.PMCTransport.fetch),
                       ("persistence_adapter", d2.FrozenTransportAdapter)):
        current = code_binding(value)
        require(all(current[k] == bindings[key][k] for k in ("sha256", "entrypoint_source_sha256")),
                "FROZEN_RUNTIME_CODE_BINDING_MISMATCH:" + key)
    current = code_binding(d2.run)
    frozen_execution = obj(d2.OUT / "execution_implementation_binding.json")
    require(all(current[k] == frozen_execution[k] for k in ("sha256", "entrypoint_source_sha256")),
            "D2_ORCHESTRATION_CHANGED")
    policy_path = d2.D / "alpha3_21d_technical_retry_policy.json"
    require(digest(policy_path) == RETRY_SHA, "RETRY_POLICY_HASH_MISMATCH")
    policy, historical_failure, historical_jats = obj(policy_path), obj(state["failure_path"]), obj(state["jats_path"])
    activation_path = d2.OUT / "alpha3_21d2_jats_activation_manifest.json"
    activation = obj(activation_path)
    require(digest(activation_path) == (d2.OUT / "alpha3_21d2_jats_activation_manifest_sha256").read_text().strip(),
            "ACTIVATION_MARKER_MISMATCH")
    structural = streams["jats_structural_states"]
    rec = reconstruct(activation["requests"], state["requests"], streams["jats_request_attempt_log"],
                      structural, policy["maximum_attempts_per_request"])
    failed, failed_attempts = rec["failed"], rec["failed_attempts"]
    require(len(failed_attempts) == 1 and failed["pmid"] == "42731998", "FAILED_REQUEST_SNAPSHOT_MISMATCH")
    attempt = failed_attempts[0]
    raw_path = d2.OUT / attempt["raw_path"]
    require(attempt["raw_bytes"] == raw_path.stat().st_size == 188590
            and digest(raw_path) == attempt["raw_sha256"], "PARTIAL_RESPONSE_HASH_OR_LENGTH_MISMATCH")
    for log, manifest in (("oa_request_attempt_log", "oa_raw_response_manifest"),
                          ("jats_request_attempt_log", "jats_raw_response_manifest")):
        require(streams[log] == streams[manifest], "ATTEMPT_RAW_MANIFEST_MISMATCH")
        for a in streams[log]:
            p = d2.OUT / a["raw_path"]
            require(digest(p) == a["raw_sha256"] and p.stat().st_size == a["raw_bytes"], "RAW_ATTEMPT_MISMATCH")
    exception = persisted_exception_facts(attempt)
    assessment = retry_scope(policy, historical_failure, historical_jats, exception)
    artifacts["incomplete_read_retry_authority_classification"] = assessment
    artifacts["failed_attempt_exception_chain"] = {"attempt_log": ref(d2.OUT / "jats_request_attempt_log.jsonl", "observed_failure"), **exception}
    artifacts["failed_jats_logical_request_reconstruction"] = {
        "network_request_manifest": ref(d2.d1.REQUESTS, "original_not_regenerated"),
        "activation_manifest": ref(activation_path, "original_required_JATS_order"),
        "frozen_request_record": failed, "frozen_request_record_sha256": sha(canonical(failed)),
        "logical_request_id": failed["logical_request_id"], "request_payload_sha256": failed["request_payload_sha256"],
        "pmid": failed["pmid"], "pmcid": failed["pmcid"], "expected_doi": failed["source_provenance"]["doi"],
        "frozen_source_input_ordinal": failed["source_input_ordinal"], "runtime_ordinal": attempt["ordinal"],
        "attempt_ordinal": attempt["attempt"], "preserved_attempt": attempt,
        "no_request_regeneration": True, "no_source_replacement": True,
    }
    reached = ["jats_structural_states", "jats_direct_identifier_extraction", "jats_primary_identity_states_v2",
               "jats_license_states", "canonical_body_states", "canonical_body_manifest"]
    require(all(not any(r.get("pmid") == failed["pmid"] for r in streams[n]) for n in reached),
            "PARTIAL_RESPONSE_REACHED_TRUSTED_PROCESSING")
    require(not any(r.get("pmid") == failed["pmid"] and r["resolution_reached"]
                    for r in streams["updateof_structural_resolution_states"]), "PARTIAL_UPDATEOF_PROCESSING")
    handoff_path = d2.OUT / "alpha3_21e_construction_source_handoff.json"
    handoff = obj(handoff_path)
    require(not any(r["pmid"] == failed["pmid"] for r in handoff["sources"]), "PARTIAL_RESPONSE_HANDED_OFF")
    artifacts["incomplete_read_partial_response_audit"] = {
        "raw_artifact": ref(raw_path, "NON_AUTHORITATIVE_PARTIAL_TRANSPORT_OBSERVATION"),
        "preserved_bytes": raw_path.stat().st_size, "preserved_sha256": digest(raw_path),
        "trusted_jats_parsed": False, "identity_authoritative": False, "body_authoritative": False,
        "license_eligibility_used": False, "UpdateOf_resolution_used": False,
        "authoritative_handoff_used": False, "new_raw_XML_inspection_or_parsing": False,
        "proof": "Frozen downstream record absence plus frozen execute_jats transport-before-parser ordering",
        "downstream_record_stream_bindings": [ref(d2.OUT / (n + ".jsonl"), "processing_not_reached_for_failed_source") for n in reached],
        "exception_preservation_is_not_JATS_validity": True,
    }
    historical_log_path = d2.legacy.OUT / "pmc_request_attempts.jsonl"
    historical_attempts = checked_records(historical_log_path)
    historical_read_failures = []
    for a in historical_attempts:
        if a["stage"] == "PMC_JATS" and a["transport_error"]:
            history = [r for r in historical_attempts if (r["stage"], r["pmid"]) == (a["stage"], a["pmid"])]
            historical_read_failures.append({"preserved_attempt": a, "attempt_count_for_same_logical_request": len(history),
                                            "not_generic_IncompleteRead_coverage_proof": True})
    test_paths = [ROOT / "tests/test_run_search_plan_v24_alpha319d_pmc_oa_jats_construction_eligibility.py",
                  ROOT / "tests/test_search_plan_v24_alpha321d2_pmc_execution.py"]
    source_policy_path = state["failure_path"].parent / "source_execution_policy.json"
    acquisition_path = state["failure_path"].parent / "construction_fulltext_acquisition_policy.json"
    artifacts["frozen_retry_contract_authority_binding"] = {
        "D1_execution_authority": ref(d2.D1 / "alpha321_pmc_jats_execution_authority_v2.json", "D2_composite_authority"),
        "D_retry_policy": ref(policy_path, "primary_retry_authority"), "D_retry_policy_verbatim": policy,
        "historical_fulltext_failure_policy": ref(state["failure_path"], "bound_PMC_JATS_retry_semantics"),
        "historical_fulltext_failure_policy_verbatim": historical_failure,
        "historical_JATS_acquisition_contract": ref(state["jats_path"], "original_route_and_budget_contract"),
        "historical_acquisition_policy": ref(acquisition_path, "NCBI_only_no_body_exception_domain_definition"),
        "frozen_runtime_bindings": bindings,
        "inspected_historical_tests": [ref(p, "read_only_test_evidence_no_incomplete_body_retry_case") for p in test_paths],
        "historical_execution_log": ref(historical_log_path, "behavior_evidence_not_semantic_expansion"),
        "historical_request_attempt_count": len(historical_attempts),
        "historical_JATS_transport_error_observations": historical_read_failures,
        "out_of_scope_source_ESearch_policy": ref(source_policy_path, "PubMed_ESearch_only_not_PMC_JATS_authority"),
        "other_stage_retry_amendments_imported": False, "web_or_generic_advice_used": False,
    }
    artifacts["retry_semantic_scope_audit"] = {
        **assessment, "authority_domain": "Frozen PMC/JATS contracts only",
        "authority_precedence": "contract semantics before incidental implementation catch omission",
        "historical_200_with_TimeoutError_behavior": historical_read_failures,
        "historical_behavior_interpretation": "A recorded HTTP 200 plus TimeoutError did not retry. "
            "This contradicts an assumed universal read-error retry rule but does not declare a closed exception taxonomy.",
        "missing_actual_HTTP_status_does_not_authorize_status_reclassification": True,
    }
    fetch_lines, fetch_start = inspect.getsourcelines(d2.legacy.PMCTransport.fetch)
    adapter_lines, adapter_start = inspect.getsourcelines(d2.FrozenTransportAdapter.fetch)
    artifacts["runtime_exception_mapping_audit"] = {
        "historical_fetch_binding": code_binding(d2.legacy.PMCTransport.fetch),
        "adapter_fetch_binding": code_binding(d2.FrozenTransportAdapter.fetch),
        "historical_fetch_lines": [fetch_start, fetch_start + len(fetch_lines) - 1],
        "adapter_fetch_lines": [adapter_start, adapter_start + len(adapter_lines) - 1],
        "normal_read_inside_try": True,
        "HTTPError_handler_read_not_protected_by_sibling_except": True,
        "caught_exception_mapping": ["urllib.error.HTTPError", "urllib.error.URLError", "TimeoutError", "OSError"],
        "success_predicate": "status == 200 and error is None",
        "retry_predicate": "status is None or status in {408,429,500,502,503,504}",
        "status_200_plus_read_error_retry_predicate": False,
        "observed_failure": "Exception escaped frozen fetch and was quarantined by outer adapter, then re-raised",
        "concrete_exception_escape_cause": "UNRESOLVED_WITHOUT_MODULE_CHAIN_AND_TRACEBACK",
        "candidate_reproduction": "Synthetic http.client.IncompleteRead is absent from caught generic tuple and escapes normal read",
        "candidate_not_substituted_for_actual_exception_provenance": True,
        "outer_adapter_catch_Exception_is_quarantine_not_retry": True,
        "adding_catch_alone_does_not_establish_retry_authority_or_predicate": True,
        "semantic_mapping_defect_confirmed": False, "runtime_overlay_created": False,
    }
    maximum = policy["maximum_attempts_per_request"]
    artifacts["per_request_attempt_budget_audit"] = {
        "logical_request_id": failed["logical_request_id"], "maximum_attempts": maximum,
        "attempts_consumed": len(failed_attempts), "remaining_attempts": rec["remaining_attempts"],
        "original_failed_attempt_ordinal": attempt["attempt"],
        "hypothetical_next_attempt_ordinal": rec["hypothetical_next_attempt"],
        "attempt_numbering_reset_allowed": False, "retry_execution_authorized": False,
        "timeout_seconds_unchanged": policy["timeout_seconds"], "backoff_seconds_unchanged": policy["backoff_seconds"],
        "hypothetical_remaining_backoffs_before_attempts_2_3_4": policy["backoff_seconds"],
    }
    require(len(structural) == len(rec["successful_ids"]) == 9
            and all(r["state"] == "JATS_XML_ARTICLE_STRUCTURE_VALID" and r["transport_succeeded"] for r in structural),
            "SUCCESSFUL_JATS_STATE_MISMATCH")
    require(len(streams["jats_primary_identity_states_v2"]) == 9
            and all(r["result"]["identity_state"] == d2.identity.SUCCESS for r in streams["jats_primary_identity_states_v2"]),
            "SUCCESSFUL_JATS_IDENTITY_SNAPSHOT_MISMATCH")
    execution_records = [{"logical_request_id": r["logical_request_id"], "pmid": r["pmid"],
                          "frozen_source_input_ordinal": r["source_input_ordinal"],
                          "runtime_ordinal": i, "execution_state": "COMPLETED_VALID_JATS" if i <= 9 else
                          "INCOMPLETE_TRANSPORT_PENDING_TERMINAL_RESOLUTION" if r["logical_request_id"] == failed["logical_request_id"]
                          else "NOT_EXECUTED_AFTER_ABORT"}
                         for i, r in enumerate(rec["active"], 1)]
    counts = Counter(r["execution_state"] for r in execution_records)
    require(len(rec["active"]) == 47 and len(rec["untouched"]) == 37, "ACTIVATED_STATE_PARTITION_MISMATCH")
    artifacts["jats_execution_state_reconstruction"] = {
        "activation_manifest": ref(activation_path, "unchanged_single_authoritative_universe"),
        "execution_records": execution_records, "execution_state_counts": dict(counts),
        "started_logical_requests": len(rec["successful_ids"]) + 1, "activated_request_count": len(rec["active"]),
        "request_universe_rebuilt": False, "classification_changes_scientific_source_state": False,
    }
    dimensions_path = d2.OUT / "d2_per_source_dimension_states.jsonl"
    dimensions = checked_records(dimensions_path)
    pending_ids = {r["pmid"] for r in execution_records if r["execution_state"] != "COMPLETED_VALID_JATS"}
    reporting_rows = [r for r in dimensions if r["pmid"] in pending_ids]
    require(len(reporting_rows) == 38 and all(r["oa_state"] == "OA_SUBSET_ELIGIBLE" for r in reporting_rows),
            "PENDING_SOURCE_REPORTING_SNAPSHOT_MISMATCH")
    artifacts["blocked_jats_semantics_audit"] = {
        "frozen_report": ref(dimensions_path, "unchanged_generic_stage_abort_fallback"),
        "interpretive_clarification_only": True, "historical_rows_rewritten": False,
        "pending_source_count": len(reporting_rows),
        "observed_fallback_count": sum(r["jats_validity_state"] == "NOT_REQUESTED_OA_NOT_ELIGIBLE" for r in reporting_rows),
        "reported_BLOCKED_JATS_is_not_scientific_exclusion": True,
        "NOT_REQUESTED_OA_NOT_ELIGIBLE_is_not_new_OA_verdict": True,
        "actual_execution_states": [r for r in execution_records if r["pmid"] in pending_ids],
        "pending_failed_source_terminal_scientific_exclusion": False,
        "not_executed_sources_OA_JATS_identity_license_BODY_failure_inferred": False,
        "dangling_failed_source_terminal_link": attempt["source_terminal_link"],
        "failed_source_structural_terminal_row_exists": False,
        "dangling_link_interpretation": "Aborted before structural-row append; unresolved execution linkage, not physical hash corruption",
    }
    require(handoff["complete_D2_execution"] is False and handoff["21E_execution_authorized"] is False
            and handoff["source_count"] == len(handoff["sources"]) == 6, "PARTIAL_HANDOFF_STATE_MISMATCH")
    artifacts["partial_construction_handoff_semantics_audit"] = {
        "historical_handoff": ref(handoff_path, "preserved_partial_handoff_not_completion"),
        "partial_construction_source_count": len(handoff["sources"]), "final_construction_source_count": "NOT_DERIVED",
        "final_construction_source_count_derived": False, "construction_source_handoff_complete": False,
        "alpha3_21e_handoff_eligible": False, "valid_partial_sources_removed_or_modified": False,
    }
    oa_rows = streams["oa_source_states"]
    oa_attempts = streams["oa_request_attempt_log"]
    oa_ids = [r["logical_request_id"] for r in state["requests"] if r["request_class"] == "PMC_OA_SUBSET"]
    require([r["logical_request_id"] for r in oa_rows] == oa_ids
            and len(oa_rows) == 49 and len(oa_attempts) == 55, "OA_COMPLETION_SNAPSHOT_MISMATCH")
    require(all(r["transport_succeeded"] for r in oa_rows)
            and sum(r["state"] == "OA_SUBSET_ELIGIBLE" for r in oa_rows) == 47,
            "OA_COMPLETION_STATE_MISMATCH")
    barrier_path = d2.OUT / "oa_phase_completion_barrier.json"
    require(obj(barrier_path)["all_49_terminal_states_frozen"] is True, "OA_BARRIER_NOT_FROZEN")
    artifacts["oa_phase_immutability_audit"] = {
        "oa_completed_source_count": len(oa_rows), "oa_eligible_count": 47, "oa_ineligible_count": 2,
        "historical_OA_transport_attempts": len(oa_attempts), "oa_phase_reexecution_allowed": False,
        "OA_states": ref(d2.OUT / "oa_source_states.jsonl", "immutable_completed_phase"),
        "OA_barrier": ref(barrier_path, "immutable_pre_JATS_barrier"), "new_OA_requests": 0,
    }
    artifacts["jats_activation_manifest_immutability_audit"] = {
        "activation_manifest": ref(activation_path, "not_regenerated_from_later_snapshot"),
        "required_count": 47, "not_required_count": 2, "total_conditional_count": len(activation["requests"]),
        "regeneration_allowed": False, "request_universe_unchanged": True,
    }
    artifacts["successful_jats_immutability_audit"] = {
        "successful_jats_refresh_allowed": False, "completed_valid_jats_count": len(structural),
        "successful_logical_request_ids": rec["successful_ids"],
        "raw_and_normalized_JATS_and_identity_states_unchanged": True,
        "successful_records": [{"pmid": r["pmid"], "logical_request_id": r["logical_request_id"],
                                "raw_artifact": r["raw_artifact"], "normalized_JATS": r["normalized_JATS"]} for r in structural],
    }
    artifacts["continuation_resume_point_contract"] = {
        "executable": False, "continuation_authorized": False, "network_authorized": False,
        "state": "BLOCKED_RETRY_AUTHORITY_UNRESOLVED", "only_if_future_authority_establishes_A": True,
        "hypothetical_same_logical_request_id": failed["logical_request_id"],
        "hypothetical_next_attempt_ordinal": rec["hypothetical_next_attempt"],
        "failed_request_must_reach_authorized_terminal_state_before_any_later_request": True,
        "existing_failure_must_remain_append_only_history": True, "attempt_budget_reset_allowed": False,
    }
    artifacts["continuation_order_contract"] = {
        "executable": False, "continuation_authorized": False,
        "diagnostic_original_order_ids_if_future_A": rec["hypothetical_original_order_ids"],
        "remaining_not_executed_order_ids": [r["logical_request_id"] for r in rec["untouched"]],
        "OA_request_count": 0, "successful_JATS_request_count": 0,
        "request_payloads_regenerated": False, "source_replacement": False,
        "original_manifest": ref(d2.d1.REQUESTS, "reference_only_never_recompiled"),
    }
    transport_total = len(oa_attempts) + len(streams["jats_request_attempt_log"])
    require(transport_total == summary["total_transport_attempts"] == 66, "HISTORICAL_ATTEMPT_TOTAL_MISMATCH")
    artifacts["continuation_transport_budget"] = {
        "existing_transport_attempts": transport_total, "failed_request_remaining_attempts": rec["remaining_attempts"],
        "untouched_request_count": len(rec["untouched"]), "per_untouched_request_maximum": maximum,
        "conditional_arithmetic_additional_ceiling_if_future_A": rec["conditional_additional_ceiling"],
        "conditional_arithmetic_cumulative_ceiling_if_future_A": transport_total + rec["conditional_additional_ceiling"],
        "maximum_additional_transport_attempts": None, "maximum_final_cumulative_transport_attempts": None,
        "arithmetic_is_not_retry_authorization": True, "executable": False,
    }
    exposure_path = d2.OUT / "alpha3_21_current_attempt_fulltext_exposure_registry.json"
    exposure = obj(exposure_path)
    require(exposure["authoritative_exposure_count"] == len(exposure["source_identities"]) == 9
            and exposure["untrusted_observation_count"] == len(exposure["untrusted_observations"]) == 1
            and exposure["untrusted_observations"][0]["logical_request_id"] == failed["logical_request_id"]
            and exposure["future_history_only"] is True and exposure["current_exclusion_authority"] is False
            and exposure["current_attempt_fulltext_self_excludes"] is False, "EXPOSURE_SNAPSHOT_MISMATCH")
    artifacts["fulltext_exposure_state_audit"] = {
        "registry": ref(exposure_path, "unchanged_current_attempt_future_history"),
        "current_authoritative_fulltext_exposure_count": 9, "current_partial_non_authoritative_observation_count": 1,
        "partial_identity_promoted": False, "future_success_must_append_without_removing_partial_observation": True,
        "partial_observation_remains_current_attempt_history": True,
    }
    artifacts["current_attempt_no_self_contamination_audit"] = {
        "current_exclusion_authority": False, "current_attempt_fulltext_self_excludes": False,
        "partial_observation_excludes_current_source": False, "registry_mutated": False,
        "historical_seen_source_registries_mutated": False,
        "contract": ref(d2.D / "alpha3_21d_no_self_contamination_contract.json", "unchanged_no_self_exclusion"),
    }
    issue_path = d2.OUT / "known_preexisting_test_environment_issue.json"
    artifacts["known_preexisting_test_environment_issue"] = {
        "preserved_issue": obj(issue_path), "historical_issue_artifact": ref(issue_path, "not_related_to_IncompleteRead"),
        "historical_directory_deleted": False, "historical_test_weakened": False, "issue_claimed_fixed": False,
        "related_to_retry_authority_classification": False,
    }
    artifacts["scientific_policy_nonadaptation_audit"] = {
        **d2.UNCHANGED, "retry_policy_semantics_changed": False, "runtime_helper_changed": False,
        "result_driven_recovery_policy_added": False, "runtime_overlay_created": False,
        "partial_scientific_content_inspected": False, "yield_used_as_recovery_authority": False,
    }
    artifacts["scientific_state_safety_audit"] = {
        **NO_CALLS, "fresh_JATS_observed": False, "trusted_JATS_parsing_performed": False,
        "ConstructionEvidenceDocument_generated": False, "span_anchors_generated": 0,
        "Builder_requests_constructed": 0, "Quality_requests_constructed": 0,
        "21E_started": False, "scientific_relevance_adjudication_started": False,
        "request_regeneration_performed": False, "source_replacement_used": False,
    }
    # Compare complete byte-level snapshots after all read-only processing.
    for values in protected:
        root_check(*values)
    d2.preflight()
    for frozen_ref in frozen_refs:
        require(digest(ROOT / frozen_ref["artifact_path"]) == frozen_ref["sha256"], "HISTORICAL_D2_BYTES_CHANGED")
    artifacts["historical_preservation_audit"] = {
        "D2_D1_D_C2_master_and_inherited_roots_reverified": True, "D2_frozen_file_manifest": frozen_refs,
        "D2_failed_status_and_classification_preserved": True, "historical_assets_modified": False,
        "original_logs_raw_manifests_exposures_partial_handoff_validation_summary_unchanged": True,
        "old_runtime_and_test_files_unchanged": True,
    }
    artifacts["d2_failure_snapshot_integrity_audit"] = {
        "verified": True, "physical_artifact_integrity_verified": True,
        "D2_failed_status": summary["status"], "D2_original_classification": summary["alpha3_21d2_classification"],
        "raw_attempt_artifacts_verified": transport_total, "required_roots_and_refs_verified": True,
        "failed_source_terminal_link_unmaterialized_due_to_abort": True,
        "exception_provenance_missing_is_not_file_hash_integrity_failure": True,
    }
    result = {
        "status": "completed", "stage_identity": STAGE, "alpha3_21d21_classification": CLASS_C,
        "primary_classification_count": 1, "alpha3_21d2_root_verified": True,
        "alpha3_21d1_root_verified": True, "alpha3_21d_root_verified": True,
        "failed_jats_pmid": failed["pmid"], "failed_jats_attempts_consumed": len(failed_attempts),
        "failed_jats_partial_bytes": raw_path.stat().st_size,
        "partial_response_trusted_jats_parsed": False, "partial_response_identity_authoritative": False,
        "partial_response_body_authoritative": False, "frozen_retry_semantics_resolved": False,
        "incomplete_read_covered_by_frozen_retry_semantics": False, "runtime_exception_mapping_defect": False,
        "coverage_state": assessment["coverage_state"], "runtime_exception_mapping_omission_observed": True,
        "retry_policy_semantics_changed": False, "scientific_policy_changed": False,
        "failed_request_max_attempts": maximum, "failed_request_remaining_attempts": rec["remaining_attempts"],
        "oa_phase_reexecution_allowed": False, "successful_jats_refresh_allowed": False,
        "oa_completed_source_count": len(oa_rows), "activated_jats_request_count": len(rec["active"]),
        "completed_valid_jats_count": len(structural), "pending_failed_jats_count": len(failed_attempts),
        "not_executed_after_abort_count": len(rec["untouched"]),
        "partial_construction_source_count": len(handoff["sources"]), "final_construction_source_count": "NOT_DERIVED",
        "final_construction_source_count_derived": False, "alpha3_21e_handoff_eligible": False,
        "current_authoritative_fulltext_exposure_count": 9, "current_partial_non_authoritative_observation_count": 1,
        "runtime_recovery_within_same_primary_attempt_allowed": False,
        "maximum_additional_transport_attempts": None, "maximum_final_cumulative_transport_attempts": None,
        **NO_CALLS, "next_stage_recommendation": NEXT_C, "historical_assets_modified": False,
        "audit_completed_does_not_mean_D2_completed_or_retry_authority_resolved": True,
    }
    artifacts["summary"] = result
    artifacts["validation"] = {**result, "audit_integrity_checks_passed": True,
                               "no_A_only_artifacts_allowed": True, "no_executable_recovery_plan": True}
    require(set(artifacts) == set(REQUIRED), "AUDIT_ARTIFACT_MEMBERSHIP_MISMATCH")
    return artifacts


@contextmanager
def offline_guard():
    def prohibited(*args, **kwargs):
        raise AssertionError("D21_OFFLINE_NETWORK_FORBIDDEN")
    with patch.object(socket.socket, "connect", prohibited), patch.object(socket.socket, "connect_ex", prohibited), \
            patch.object(socket, "create_connection", prohibited), patch.object(urllib.request, "urlopen", prohibited), \
            patch.object(urllib.request.OpenerDirector, "open", prohibited):
        yield


def put_bytes(name, raw):
    path = OUT / name
    require(path.parent == OUT and not path.is_symlink(), "OUTPUT_PATH_ESCAPE_OR_SYMLINK")
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def run(verification=None):
    require(not OUT.exists(), "D21_OUTPUT_ALREADY_EXISTS_NO_OVERWRITE")
    if verification is not None:
        require(verification["implementation_sha256"] == digest(Path(__file__))
                and verification["test_implementation_sha256"] == digest(
                    ROOT / "tests/test_search_plan_v24_alpha321d21_runtime_failure_audit_offline.py")
                and verification["checks"] and all(check["check_passed"] is True for check in verification["checks"]),
                "LOCAL_VERIFICATION_REPORT_MISMATCH")
    with offline_guard():
        try:
            artifacts = collect_audit()
        except Exception as exc:
            result = {"status": "failed", "stage_identity": STAGE,
                      "alpha3_21d21_classification": CLASS_INTEGRITY, "primary_classification_count": 1,
                      "failure": type(exc).__name__ + ":" + str(exc), **NO_CALLS,
                      "runtime_recovery_within_same_primary_attempt_allowed": False,
                      "historical_assets_modified": False, "next_stage_recommendation": NEXT_INTEGRITY}
            artifacts = {name: {"audit_state": "NOT_DERIVED_AFTER_INTEGRITY_BARRIER_FAILURE", **result} for name in REQUIRED}
            artifacts["summary"] = artifacts["validation"] = result
        OUT.mkdir()
        for name, value in artifacts.items():
            put_bytes(name + ".json", canonical(value) + b"\n")
        put_bytes("audit_implementation_binding.json", canonical(code_binding(run)) + b"\n")
        put_bytes("focused_test_implementation_binding.json", canonical(ref(
            ROOT / "tests/test_search_plan_v24_alpha321d21_runtime_failure_audit_offline.py", "synthetic_offline_tests")) + b"\n")
        if verification is not None:
            put_bytes("offline_verification_results.json", canonical(verification) + b"\n")
        require(not any((OUT / name).exists() for name in A_ONLY), "A_ONLY_ARTIFACT_WITHOUT_A_AUTHORITY")
        value = root_hash(OUT, ROOT_MARKER)
        put_bytes(ROOT_MARKER, (value + "\n").encode("ascii"))
        require(root_hash(OUT, ROOT_MARKER) == value, "D21_OUTPUT_ROOT_MISMATCH")
        return {**artifacts["summary"], ROOT_MARKER: value}


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, sort_keys=True), flush=True)
    raise SystemExit(0 if result["status"] == "completed" else 1)
