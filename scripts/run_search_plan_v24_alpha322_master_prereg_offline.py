#!/usr/bin/env python3
"""Freeze a declarative engineering master, not a new transport implementation.

No classifier, mapper, retry engine, journal executor, fault injection, parser,
or science is run here. All proposed runtime gates remain NOT_IMPLEMENTED.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from scripts import run_search_plan_v24_alpha321_terminal_closure_offline as closed


ROOT, d2, prior = closed.ROOT, closed.d2, closed.prior
OUT = ROOT / "runs/20261008_search_plan_v24_dev_alpha3_22_runtime_hardening_master_preregistration_offline"
ROOT_MARKER = "search_plan_v24_dev_alpha3_22_master_prereg_sha256"
BUNDLE_MARKER = "alpha3_22_transport_semantics_bundle_sha256"
PLAN_MARKER = "alpha3_22_master_execution_plan_sha256"
CLOSURE_SHA = "3e066b012a0b422c1b1c97f68364bd9bd8373ee78c53665322f665c61d84a788"
REGISTRY_SHA = "80e51107b6e357b210a6860888d6c27bf634eb540dee1a9ba94c3b94465f10ca"
STAGE = "POST_ALPHA3_21_SEEN_RUNTIME_HARDENING_DEVELOPMENT"
CLASSIFICATION = "POST_ALPHA3_21_RUNTIME_HARDENING_PROTOCOL_PREREGISTERED"
NEXT = "IMPLEMENT_ALPHA3_22A_TRANSPORT_STATE_MACHINE_AND_OBSERVABILITY_OFFLINE"
TEST = ROOT / "tests/test_search_plan_v24_alpha322_master_prereg_offline.py"
canonical, sha, digest, obj, rows, ref, require, root_hash = (
    closed.canonical, closed.sha, closed.digest, closed.obj, closed.rows,
    closed.ref, closed.require, closed.root_hash)
NO_CALLS = dict(closed.NO_CALLS)
COUNTS = {"future_seen_unique_pmid_count": 3560, "future_seen_unique_pmcid_count": 218,
          "future_seen_unique_doi_count": 252, "future_seen_candidate_identity_count": 271}
NO_FRESH = {key: False for key in ("fresh_primary_attempt_started", "fresh_source_acquisition_started",
    "fresh_builder_execution_started", "fresh_quality_execution_started", "fresh_retrieval_evaluation_started")}
STATES = ["REQUEST_NOT_STARTED", "REQUEST_ATTEMPT_STARTED", "RESPONSE_HEADERS_RECEIVED", "RESPONSE_BODY_READING",
          "RESPONSE_BODY_COMPLETE", "RESPONSE_BODY_INTERRUPTED", "RAW_RESPONSE_FROZEN", "RESPONSE_VALIDATION_COMPLETE",
          "TERMINAL_TECHNICAL_FAILURE"]
TAXONOMY = ["PRE_RESPONSE_TRANSPORT_INTERRUPTION", "RESPONSE_BODY_TRANSPORT_INTERRUPTION",
            "RESPONSE_BODY_LENGTH_MISMATCH", "RETRYABLE_HTTP_STATUS", "RETRYABLE_PROVIDER_BACKEND_FAILURE",
            "COMPLETE_BODY_RESPONSE_VALIDITY_FAILURE", "NONRETRYABLE_HTTP_STATUS", "UNKNOWN_RUNTIME_FAILURE"]
PHASES = [
    ("alpha3.22A", "TRANSPORT STATE MACHINE + OBSERVABILITY CONTRACT IMPLEMENTATION"),
    ("alpha3.22B", "EXCEPTION-MAPPING INVENTORY + VERSIONED RETRY MAPPER"),
    ("alpha3.22C", "APPEND-ONLY ATTEMPT JOURNAL + PROCESS-RESUME IMPLEMENTATION"),
    ("alpha3.22D", "OFFLINE FAULT-INJECTION MATRIX"),
    ("alpha3.22E", "HISTORICAL REGRESSION + SEEN-DATA REPLAY"),
    ("alpha3.22F", "FINAL RUNTIME CONTRACT / REPRODUCIBILITY BUNDLE FREEZE"),
]
REQUIRED = (
    "alpha3_21_closure_root_verification", "alpha3_21_terminal_state_binding",
    "alpha3_21_future_contamination_registry_binding", "alpha3_22_development_identity",
    "alpha3_22_scientific_policy_firewall", "transport_lifecycle_contract_v2_draft",
    "response_body_completion_semantics", "response_body_interruption_semantics",
    "transport_retry_semantics_v2_draft", "transport_failure_taxonomy", "transport_retryability_matrix",
    "transport_exception_mapping_design_contract", "transport_observability_contract_v1_draft",
    "exception_provenance_schema", "http_response_provenance_schema", "body_read_provenance_schema",
    "partial_response_quarantine_contract", "attempt_consumption_contract",
    "append_only_attempt_journal_contract_v1_draft", "logical_request_state_contract",
    "process_restart_semantics", "continuation_order_contract", "two_phase_barrier_resume_contract",
    "fault_injection_matrix_contract", "historical_regression_contract", "seen_failure_fixture_usage_contract",
    "runtime_hardening_non_yield_optimization_contract", "builder_v4_nonchange_binding",
    "quality_v2_nonchange_binding", "search_plan_nonchange_binding", "future_fresh_contamination_baseline",
    "alpha3_22_phase_plan", "alpha3_22_release_gate", "fresh_primary_start_prohibition",
    "scientific_state_safety_audit", "historical_preservation_audit", "validation", "summary",
)
EXTRAS = ("repository_runtime_authority_inventory", "replay_safe_request_design_contract", "retry_decision_provenance_schema")
SEMANTIC_STEMS = tuple(name for name in REQUIRED if name.startswith(("transport_", "response_body_", "exception_", "http_response_", "body_read_", "partial_response_", "attempt_", "append_only_", "logical_request_", "process_restart_", "continuation_", "two_phase_", "fault_injection_"))) + (
    "repository_runtime_authority_inventory", "replay_safe_request_design_contract", "retry_decision_provenance_schema")
RELEASE_REQUIREMENTS = ["transport_lifecycle_frozen", "body_completion_semantics_frozen", "body_interruption_retry_semantics_frozen",
    "concrete_exception_mapping_frozen", "observability_schema_frozen", "partial_quarantine_validated",
    "attempt_journal_validated", "restart_resume_semantics_validated", "fault_matrix_passed",
    "historical_regression_passed", "no_scientific_policy_changes", "runtime_reproducibility_bundle_frozen"]


def draft(version, **values):
    return {"schema_version": version, "contract_state": "PROSPECTIVE_DEVELOPMENT_DESIGN_FROZEN",
            "implementation_state": "NOT_IMPLEMENTED", "runtime_activation_allowed": False,
            "scope": "FUTURE_VERSIONED_RUNTIME_ONLY_NOT_ALPHA3_21", **values}


def schema(name, fields):
    """Declarative JSON Schema, not a production response/provenance parser."""
    properties = {"schema_version": {"const": name}, **fields,
                  "unavailable_fields": {"type": "object", "additionalProperties": {"type": "string"}}}
    return {"$schema": "http://json-schema.org/draft-07/schema#", "$id": "urn:alpha3_22:" + name,
            "type": "object", "additionalProperties": False, "properties": properties,
            "required": list(properties)}


def verify_baseline():
    check = prior.root_check(closed.OUT, closed.ROOT_MARKER, CLOSURE_SHA)
    closed.verify_roots()
    prior.root_check(d2.OUT, d2.ROOT_MARKER, prior.D2_SHA)
    prior.root_check(closed.terminal.OUT, closed.terminal.ROOT_MARKER, closed.D22_SHA)
    summary = obj(closed.OUT / "summary.json")
    require(summary["status"] == "completed" and summary["alpha3_21_terminal_classification"] == closed.CLASSIFICATION
            and summary["fresh_primary_attempt_terminated"] is True and summary["fresh_primary_attempt_completed"] is False,
            "ALPHA321_NOT_PERMANENTLY_CLOSED")
    for key in ("same_attempt_network_continuation_allowed", "same_attempt_retry_policy_development_allowed", "alpha3_21e_allowed"):
        require(summary[key] is False, "ALPHA321_CONTINUATION_AUTHORITY_NOT_CLOSED")
    path = closed.OUT / "alpha3_21_future_contamination_registry.json"
    require(digest(path) == REGISTRY_SHA == (closed.OUT / closed.REGISTRY_MARKER).read_text().strip(), "CONTAMINATION_BASELINE_MISMATCH")
    registry = obj(path)
    counts = {}
    for kind in ("pmid", "pmcid", "doi"):
        ids = registry["source_identifier_sets"][kind + "s"]
        require(len(ids) == len(set(ids)) == len(closed.exact_ids(registry["source_identities"], kind, optional=True)),
                "CONTAMINATION_REGISTRY_SET_MISMATCH")
        require(set(ids) == closed.exact_ids(registry["source_identities"], kind, optional=True), "CONTAMINATION_IDENTITY_UNION_MISMATCH")
        counts["future_seen_unique_" + kind + "_count"] = len(ids)
    counts["future_seen_candidate_identity_count"] = len(closed.unique_ids(registry["candidate_identities"], "candidate_id"))
    require(counts == COUNTS, "CONTAMINATION_BASELINE_COUNT_MISMATCH")
    historical_bindings = {}
    for name in ("alpha3_21_builder_v4_binding", "alpha3_21_builder_runtime_binding", "builder_v4_final_contract_binding",
                 "alpha3_21_quality_v2_binding", "alpha3_21_quality_runtime_binding", "alpha3_21_quality_response_envelope_v3_binding",
                 "alpha3_21_search_plan_architecture_binding", "alpha3_21_future_retrieval_leakage_firewall",
                 "alpha3_21_metadata_policy_binding", "alpha3_21_pmc_oa_policy_binding", "alpha3_21_construction_document_binding"):
        p = d2.MASTER / (name + ".json")
        d2.d1.d.checked_tree(obj(p))
        historical_bindings[name] = ref(p, "unchanged_historical_scientific_authority")
    return check, summary, path, registry, counts, historical_bindings


def runtime_inventory():
    """Read-only authority inspection; no transport object is constructed."""
    paths = {"PubMed_ESearch": closed.b.A / "alpha3_21_technical_retry_policy.json",
             "PubMed_metadata": closed.c.OUT / "metadata_technical_retry_policy.json",
             "PMC_OA_and_JATS": d2.D / "alpha3_21d_technical_retry_policy.json"}
    budgets = []
    for component, path in paths.items():
        policy = obj(path)
        d2.d1.d.checked_tree(policy)
        maximum = policy.get("max_attempts_per_logical_page", policy.get("maximum_attempts_per_request"))
        require((maximum, policy["timeout_seconds"], policy["backoff_seconds"]) == (4, 60, [2, 4, 8]), "INHERITED_COMPONENT_BUDGET_MISMATCH")
        statuses = policy.get("retryable_http_status", policy.get("http_status_retryable"))
        require(statuses == [408, 429, 500, 502, 503, 504], "INHERITED_HTTP_STATUS_SET_MISMATCH")
        budgets.append({"component": component, "maximum_attempts_per_logical_request": maximum,
                        "timeout_seconds": policy["timeout_seconds"], "backoff_seconds": policy["backoff_seconds"],
                        "retryable_http_status": statuses, "frozen_policy": ref(path, "numeric_policy_not_changed")})
    manifests = [closed.b.A / "alpha3_21_potential_page_request_manifest.jsonl",
                 closed.c.OUT / "metadata_request_manifest.jsonl", closed.d1.REQUESTS]
    observed = []
    for path in manifests:
        records = rows(path)
        methods = set()
        routes = set()
        for r in records:
            if path == manifests[0]:
                # This historical ESearch manifest stores only parameters;
                # the frozen transport log proves the actual method.
                payload = r["request_payload"]
                endpoint, db, method = r["endpoint"], payload["db"], "GET"
            else:
                payload = r["request_payload"]
                endpoint, db, method = payload["endpoint"], payload["parameters"]["db"], payload["method"]
            require(method == "GET" and db in {"pubmed", "pmc"} and endpoint in {
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"}, "REPOSITORY_READ_ONLY_ROUTE_NOT_CONFIRMED")
            methods.add(method)
            routes.add((endpoint, db))
        observed.append({"frozen_request_manifest": ref(path, "read_only_route_scope_evidence_not_new_request_universe"),
                         "request_count": len(records), "methods": sorted(methods),
                         "routes": [{"endpoint": endpoint, "db": db} for endpoint, db in sorted(routes)]})
    a1log = closed.b.A1 / "all_pubmed_request_attempt_log.jsonl"
    require(all(r["method"] == "GET" for r in rows(a1log)), "ESEARCH_OBSERVED_METHOD_MISMATCH")
    code_paths = [ROOT / "scripts/run_search_plan_v24_alpha321a1_source_acquisition.py",
                  ROOT / "scripts/run_search_plan_v24_alpha319c_pubmed_metadata_eligibility.py",
                  ROOT / "scripts/run_search_plan_v24_alpha319d_pmc_oa_jats_construction_eligibility.py",
                  ROOT / "scripts/run_search_plan_v24_alpha321c2_metadata_execution.py", Path(d2.__file__)]
    require(all("urllib.request" in p.read_text() for p in code_paths[:3]), "BOUND_CLIENT_STACK_MISMATCH")
    return {"client_family": "Python standard-library urllib.request / http.client",
            "read_operation_observed_in_bound_clients": "response.read()",
            "concrete_exception_mapping_frozen_here": False, "components": budgets,
            "request_route_evidence": observed, "ESearch_method_log": ref(a1log, "frozen_GET_method_proof"),
            "unchanged_source_code": [ref(p, "read_only_actual_bound_stack_inspection") for p in code_paths],
            "provider_backend_authority": obj(paths["PubMed_ESearch"])["backend_retry_eligibility"],
            "historical_generic_exception_retry_predicates_not_carried_forward_as_new_authority": True}


def build_protocol():
    before, terminal_summary, registry_path, registry, counts, bindings = verify_baseline()
    inventory = runtime_inventory()
    str_null = {"type": ["string", "null"]}
    int_null = {"type": ["integer", "null"], "minimum": 0}
    bool_null = {"type": ["boolean", "null"]}
    ids = {"logical_request_id": {"type": "string"}, "request_payload_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
           "attempt_ordinal": {"type": "integer", "minimum": 1}, "runtime_contract_sha256": {"type": "string"}}
    provenance_node = {"type": "object", "additionalProperties": False, "properties": {
        "node_id": {"type": "string"}, "module": str_null, "class_name": str_null, "qualified_class_name": str_null,
        "message": str_null, "repr": str_null, "args": {"type": ["array", "null"], "items": {"type": "object"}},
        "traceback": str_null, "cause_node_id": str_null, "context_node_id": str_null,
        "suppress_context": bool_null, "chain_cycle_detected": {"type": "boolean"},
        "unavailable_fields": {"type": "object", "additionalProperties": {"type": "string"}}}}
    provenance_node["required"] = list(provenance_node["properties"])
    exception_schema = schema("TransportExceptionProvenanceV1", {**ids,
        "root_exception_node_id": str_null, "exception_nodes": {"type": "array", "items": provenance_node},
        "runtime_identity": {"type": "object", "properties": {"python_version": {"type": "string"},
            "client_module": {"type": "string"}, "client_version": str_null, "client_code_sha256": {"type": "string"}},
            "required": ["python_version", "client_module", "client_version", "client_code_sha256"], "additionalProperties": False},
        "redaction_applied": {"type": "boolean"}, "redaction_paths": {"type": "array", "items": {"type": "string"}}})
    http_schema = schema("HTTPResponseProvenanceV1", {**ids, "request_method": {"type": "string"},
        "request_url_without_secrets": str_null, "request_identity_sha256": {"type": "string"}, "status": int_null,
        "reason": str_null, "response_headers": {"type": ["array", "null"], "items": {"type": "object",
            "properties": {"name": {"type": "string"}, "value": {"type": "string"}}, "required": ["name", "value"], "additionalProperties": False}},
        "content_length_raw": str_null, "expected_content_length_bytes": int_null, "transfer_encoding": str_null,
        "content_encoding": str_null, "body_byte_representation": str_null, "connection_state": str_null,
        "headers_received_at": str_null, "HTTP_provenance_trusted": {"type": "boolean"}, "status_origin": str_null})
    body_schema = schema("BodyReadProvenanceV1", {**ids, "body_read_started_at": str_null,
        "body_read_ended_at": str_null, "body_read_failed_at": str_null, "bytes_read": int_null,
        "partial_body_artifact_path": str_null, "partial_body_sha256": {"type": ["string", "null"], "pattern": "^[0-9a-f]{64}$"},
        "complete_body_artifact_path": str_null, "complete_body_sha256": {"type": ["string", "null"], "pattern": "^[0-9a-f]{64}$"},
        "expected_content_length_bytes": int_null, "read_returned_normally": bool_null,
        "framing_integrity_checks": {"type": "array", "items": {"type": "object"}},
        "completion_state": {"enum": ["NOT_STARTED", "BODY_READING", "BODY_COMPLETE", "BODY_INTERRUPTED", "BODY_COMPLETION_UNKNOWN"]},
        "semantic_failure_state": {"enum": [None, *TAXONOMY, "ABANDONED_ATTEMPT_UNKNOWN_TERMINATION"]},
        "parser_invoked": {"type": "boolean"}})
    decision_schema = schema("TransportRetryDecisionProvenanceV2", {**ids,
        "semantic_transport_classification": {"enum": ["NO_TECHNICAL_FAILURE", *TAXONOMY, "ABANDONED_ATTEMPT_UNKNOWN_TERMINATION"]},
        "retryable": {"type": "boolean"}, "retry_decision_authority": {"type": "object"},
        "request_replay_safe": {"type": "boolean"}, "replay_safety_authority": {"type": ["object", "null"]},
        "remaining_attempts_before_decision": {"type": "integer", "minimum": 0},
        "remaining_attempts_after_decision": {"type": "integer", "minimum": 0},
        "backoff_selected_seconds": {"enum": [0, 2, 4, 8]},
        "decision": {"enum": ["VALID_SUCCESS", "VALID_NONELIGIBLE_RESPONSE", "CONTINUE_WITH_NEXT_ORDINAL", "TERMINAL_TECHNICAL_FAILURE", "TERMINAL_VALIDITY_FAILURE"]}})
    transitions = [
        ("REQUEST_NOT_STARTED", "REQUEST_ATTEMPT_STARTED", "frozen request verified; budget available; durable ATTEMPT_STARTED committed before network"),
        ("REQUEST_ATTEMPT_STARTED", "RESPONSE_HEADERS_RECEIVED", "trusted response headers obtained"),
        ("RESPONSE_HEADERS_RECEIVED", "RESPONSE_BODY_READING", "configured body read operation begins"),
        ("RESPONSE_BODY_READING", "RESPONSE_BODY_COMPLETE", "normal read return AND all available authoritative framing/integrity checks pass"),
        ("RESPONSE_BODY_READING", "RESPONSE_BODY_INTERRUPTED", "versioned adapter proves interruption or authoritative length mismatch"),
        ("RESPONSE_BODY_COMPLETE", "RAW_RESPONSE_FROZEN", "complete bytes durably preserved and SHA-256 verified"),
        ("RESPONSE_BODY_INTERRUPTED", "RAW_RESPONSE_FROZEN", "partial bytes quarantined durably; parser admission remains false"),
        ("RAW_RESPONSE_FROZEN", "RESPONSE_VALIDATION_COMPLETE", "BODY_COMPLETE plus accepted HTTP/response policy; unchanged validator returns a recorded outcome"),
    ]
    # A terminal technical transition can occur at any started lifecycle phase;
    # it never retroactively promotes partial bytes or implies retry authority.
    transitions += [(s, "TERMINAL_TECHNICAL_FAILURE", "nonretryable/unknown failure OR exhausted budget; preserve provenance")
                    for s in STATES if s not in {"REQUEST_NOT_STARTED", "TERMINAL_TECHNICAL_FAILURE"}]
    matrix = []
    for state in TAXONOMY:
        allowed = state in TAXONOMY[:5]
        matrix.append({"semantic_state": state, "retryable_technical_class": allowed,
                       "automatic_retry_permitted": "ONLY_IF_REPLAY_SAFE_AND_BUDGET_REMAINS_AND_BOUND_AUTHORITY" if allowed else False,
                       "additional_authority_requirement": "unchanged component-specific backend response contract" if state == "RETRYABLE_PROVIDER_BACKEND_FAILURE" else
                           "explicit separately frozen response policy; never generic transport retry" if state == "COMPLETE_BODY_RESPONSE_VALIDITY_FAILURE" else None})
    fault_rows = [
        ("connection_failure_before_headers", "PRE_RESPONSE_TRANSPORT_INTERRUPTION", "RETRY_NEXT_IF_SAFE_WITH_BUDGET"),
        ("timeout_before_headers", "PRE_RESPONSE_TRANSPORT_INTERRUPTION", "RETRY_NEXT_IF_SAFE_WITH_BUDGET"),
        ("HTTP_retryable_status", "RETRYABLE_HTTP_STATUS", "RETRY_NEXT_IF_SAFE_WITH_BUDGET"),
        ("HTTP_nonretryable_status", "NONRETRYABLE_HTTP_STATUS", "NO_AUTOMATIC_RETRY"),
        ("connection_reset_during_body_read", "RESPONSE_BODY_TRANSPORT_INTERRUPTION", "RETRY_NEXT_IF_SAFE_WITH_BUDGET"),
        ("timeout_during_body_read", "RESPONSE_BODY_TRANSPORT_INTERRUPTION", "RETRY_NEXT_IF_SAFE_WITH_BUDGET"),
        ("incomplete_body_transfer", "RESPONSE_BODY_TRANSPORT_INTERRUPTION", "RETRY_NEXT_IF_SAFE_WITH_BUDGET"),
        ("declared_Content_Length_mismatch", "RESPONSE_BODY_LENGTH_MISMATCH", "RETRY_NEXT_IF_SAFE_WITH_BUDGET"),
        ("complete_valid_body", "NO_TECHNICAL_FAILURE", "VALID_SUCCESS_NO_REFRESH"),
        ("complete_malformed_XML_body", "COMPLETE_BODY_RESPONSE_VALIDITY_FAILURE", "NO_AUTOMATIC_TRANSPORT_RETRY"),
        ("complete_JATS_identity_mismatch", "COMPLETE_BODY_RESPONSE_VALIDITY_FAILURE", "NO_AUTOMATIC_TRANSPORT_RETRY_UNCHANGED_IDENTITY_FAILURE"),
        ("unknown_exception_during_body_read", "UNKNOWN_RUNTIME_FAILURE", "FAIL_CLOSED_NO_AUTOMATIC_RETRY"),
        ("process_termination_with_open_attempt", "ABANDONED_ATTEMPT_UNKNOWN_TERMINATION", "NEXT_UNUSED_ORDINAL_IF_SAFE_WITH_BUDGET"),
        ("frozen_provider_backend_failure", "RETRYABLE_PROVIDER_BACKEND_FAILURE", "UNCHANGED_COMPONENT_SPECIFIC_CONTRACT_ONLY"),
    ]
    future_phases = [{"phase": name, "objective": title, "depends_on": "MASTER_PREREGISTRATION" if i == 0 else PHASES[i - 1][0],
                      "execution_state": "NOT_STARTED", "separate_phase_instruction_required": True,
                      "allowed_data": "LOCAL_SYNTHETIC_OR_ALREADY_SEEN_ONLY", "network_calls_allowed": False}
                     for i, (name, title) in enumerate(PHASES)]
    fixture = obj(closed.OUT / "alpha3_21_runtime_terminal_reason.json")["frozen_failed_attempt"]
    require(fixture["pmid"] == "42731998" and fixture["raw_bytes"] == 188590, "SEEN_FIXTURE_IDENTITY_MISMATCH")
    d2.d1.d.checked_tree(fixture)
    terminal_state = {"alpha3_21_terminal_classification": closed.CLASSIFICATION,
        "alpha3_21_reopen_allowed": False, "alpha3_21_network_continuation_allowed": False,
        "alpha3_21_builder_execution_allowed": False, "alpha3_21_quality_execution_allowed": False,
        "alpha3_21_reopened": False, "alpha3_21_continuation_created": False, "alpha3_21_artifacts_modified": False,
        "closure_summary": ref(closed.OUT / "summary.json", "authoritative_terminal_state_not_reinterpreted")}
    baseline = {"authoritative_registry": ref(registry_path, "sole_minimum_future_fresh_exclusion_baseline"),
        "alpha3_21_future_contamination_registry_sha256": REGISTRY_SHA, **counts,
        "competing_registry_created": False, "baseline_reduction_allowed": False,
        "seen_assets_may_return_to_fresh": False, "registry_content_copied_or_modified": False}
    firewall = {"builder_v4_change_allowed": False, "quality_v2_change_allowed": False,
        "search_plan_scientific_architecture_change_allowed": False, "scientific_policy_change_allowed": False,
        "source_scientific_query_design_change_allowed": False, "selected_V1_relation_sentence_prompt_change_allowed": False,
        "BuilderOutputSchemaV4_change_allowed": False, "EvidenceReferenceContractV4_change_allowed": False,
        "GroundingContractV4_change_allowed": False, "PropositionAbstractionContractV1_change_allowed": False,
        "leakage_policy_change_allowed": False, "QualityResponseEnvelopeV3_change_allowed": False,
        "OA_license_identity_BODY_eligibility_change_allowed": False, "yield_informed_runtime_policy_allowed": False,
        "frozen_scientific_authority_bindings": bindings,
        "frozen_source_query_set": ref(d2.MASTER / "alpha3_21_source_query_set.jsonl", "source_scientific_queries_unchanged")}
    docs = {
        "alpha3_21_closure_root_verification": before,
        "alpha3_21_terminal_state_binding": terminal_state,
        "alpha3_21_future_contamination_registry_binding": baseline,
        "alpha3_22_development_identity": {"identity": STAGE, "development_mode": True, "seen_data_engineering_only": True,
            "master_preregistration_only": True, "runtime_implementation_performed": False,
            "scientific_method_development": False, **NO_FRESH, **terminal_state},
        "alpha3_22_scientific_policy_firewall": firewall,
        "repository_runtime_authority_inventory": inventory,
        "replay_safe_request_design_contract": draft("ReplaySafeAcquisitionRequestContractV1",
            repository_read_only_acquisition_routes_confirmed=True,
            scope="FUTURE_EXPLICITLY_DECLARED_NCBI_READ_ONLY_GET_ACQUISITION_ONLY",
            authority_evidence=inventory["request_route_evidence"],
            explicit_frozen_request_replay_safe_declaration_required=True,
            method_GET_alone_sufficient=False, arbitrary_future_request_replay_safety_assumed=False,
            request_payload_and_logical_identity_immutable=True, replay_safety_missing_behavior="FAIL_CLOSED_NO_RETRY",
            alpha3_21_requests_reclassified_or_reauthorized=False),
        "transport_lifecycle_contract_v2_draft": draft("TransportLifecycleContractV2", states=STATES,
            transitions=[{"from": f, "to": t, "guard": g} for f, t, g in transitions],
            lifecycle_scope="ONE_STARTED_TRANSPORT_ATTEMPT", retries_use_new_attempt_lifecycle=True,
            terminal_record_separate_from_lifecycle_progress=True,
            forbidden_transition="partial RAW_RESPONSE_FROZEN -> RESPONSE_VALIDATION_COMPLETE",
            state_validation_failure_behavior="FAIL_CLOSED_WITH_PROVENANCE"),
        "response_body_completion_semantics": draft("ResponseBodyCompletionSemanticsV2",
            response_body_completion_first_class_state=True, HTTP_status_or_headers_sufficient=False,
            BODY_COMPLETE_requires=["configured body read returns normally", "all available authoritative framing/integrity checks pass"],
            TRANSPORT_SUCCESS_requires=["BODY_COMPLETE", "raw complete bytes frozen and hash verified", "accepted transport HTTP status"],
            scientific_validity_not_implied=True,
            content_length_rule="actual acquired bytes equal authoritative expected length in the SAME BYTE REPRESENTATION",
            encoded_wire_length_must_not_be_compared_to_decoded_length=True,
            alternate_representation_requires_explicit_frozen_client_semantics=True,
            length_absent_rule="normal configured read completion plus all available framing checks; never invent Content-Length",
            conflicting_or_invalid_framing_rule="adapter-proven framing interruption; otherwise UNKNOWN_RUNTIME_FAILURE",
            body_unknown_admission="FAIL_CLOSED_NO_PARSER", body_completeness_reconstructed_from_parser_success=False),
        "response_body_interruption_semantics": draft("ResponseBodyInterruptionSemanticsV2",
            response_body_interruption_first_class_state=True,
            definition="body read does not reach normal completion because a versioned adapter proves transport/read interruption",
            examples=["body-read timeout", "remote connection termination", "incomplete response transfer", "premature framing termination"],
            authoritative_length_mismatch_state="RESPONSE_BODY_LENGTH_MISMATCH",
            semantic_phase_required="trusted body-read lifecycle context", exception_name_only_sufficient=False,
            unknown_exception_not_automatically_interruption=True, partial_bytes_not_canonical_identity=True),
        "transport_retry_semantics_v2_draft": draft("TransportRetrySemanticsV2",
            future_body_interruption_retryable=True, future_body_interruption_retry_requires_replay_safe_request=True,
            development_decision_is_new_not_preexisting_alpha321_authority=True, retroactive_alpha321_authorization=False,
            retry_requires=["frozen semantic class mapped by versioned adapter", "frozen replay-safe request declaration", "attempt budget remains"],
            component_numeric_policies=inventory["components"], HTTP_retryable_status=[408, 429, 500, 502, 503, 504],
            component_provider_backend_semantics_preserved=True, provider_backend_authority=inventory["provider_backend_authority"],
            complete_validity_failure_automatic_transport_retry=False, unknown_runtime_failure_automatic_retry=False,
            broad_exception_capture_implies_retry=False, catch_Exception_OSError_IOError_retry_authorized=False,
            decision_precedence=["unmapped exception or contradictory trusted evidence -> UNKNOWN fail-closed",
                "mapped interruption/authoritative length mismatch -> semantic transport failure, retaining HTTP provenance",
                "otherwise trusted HTTP status -> frozen status class",
                "otherwise BODY_COMPLETE -> unchanged component response validation",
                "component backend exception to validity nonretry requires its separately frozen explicit contract"],
            terminal_scope="preserve component-specific source/stage fail-closed controller policy; no recovery policy inferred here"),
        "transport_failure_taxonomy": draft("TransportFailureTaxonomyV2", states=TAXONOMY,
            phase_specific_mapping_required=True, provider_backend_HTTP_transport_parser_classes_distinct=True,
            process_recovery_class="ABANDONED_ATTEMPT_UNKNOWN_TERMINATION",
            historical_unknown_qualified_exception_not_reconstructed=True),
        "transport_retryability_matrix": draft("TransportRetryabilityMatrixV2", entries=matrix,
            matrix_is_not_executable_classifier=True, replay_safe_and_budget_required_for_every_retry=True,
            unlisted_failure_state="UNKNOWN_RUNTIME_FAILURE", all_unmapped_failures_default_no_retry=True),
        "transport_exception_mapping_design_contract": draft("TransportExceptionMappingV2Design",
            semantic_taxonomy_authoritative=True, mapper_versioned_separately=True, mapping_entries=[],
            concrete_mapping_inventory_frozen=False, inventory_phase="alpha3.22B",
            inspected_stack_evidence=inventory["unchanged_source_code"],
            freeze_requires=["actual imported concrete class or deterministic wrapper binding", "client/library/code identity",
                "lifecycle phase predicate", "trusted transfer/framing evidence", "semantic output class", "mapping source SHA-256", "offline regression fixtures"],
            exception_name_string_only_mapping_allowed=False, broad_base_class_retry_allowed=False,
            mapping_ambiguous_or_missing_behavior="UNKNOWN_RUNTIME_FAILURE_NO_AUTOMATIC_RETRY"),
        "transport_observability_contract_v1_draft": draft("TransportObservabilityContractV1",
            broad_exception_capture_for_observability_allowed=True, broad_exception_capture_implies_retry=False,
            capture_before_reraise_or_fail_close=True, capture_schema_artifacts=["exception_provenance_schema.json", "http_response_provenance_schema.json",
                "body_read_provenance_schema.json", "retry_decision_provenance_schema.json"],
            unavailable_value_policy="null PLUS explicit availability reason; never guessed",
            secrets_policy="deterministic redaction of credentials, authorization/cookie headers, secret URL fields, messages/args/tracebacks; preserve redaction paths",
            exception_args_serialization="type-tagged deterministic JSON-safe values; bytes as length/SHA-256/artifact refs, not scientific content",
            exception_chain_serialization="stable traversal node IDs; preserve cause/context/suppress flags; explicit cycle references, never silently truncate",
            logging_failure_behavior="FAIL_CLOSED_NO_NEW_ATTEMPT", observability_capture_creates_retry_authority=False),
        "exception_provenance_schema": exception_schema, "http_response_provenance_schema": http_schema,
        "body_read_provenance_schema": body_schema, "retry_decision_provenance_schema": decision_schema,
        "partial_response_quarantine_contract": draft("PartialResponseQuarantineContractV2",
            partial_response_authoritative=False, partial_response_parser_allowed=False,
            preserve_partial_bytes_if_any=True, preserve_path_length_SHA256=True,
            blocked_consumers=["XML parser", "complete-body JSON parser", "JATS identity validator", "license parser", "BODY normalization", "scientific extraction"],
            partial_identifier_state="UNTRUSTED_PARTIAL_TRANSPORT_OBSERVATIONS", canonical_source_identity_allowed=False,
            unknown_completion_also_quarantined=True, partial_artifact_never_overwritten_by_success=True),
        "attempt_consumption_contract": draft("TransportAttemptConsumptionV2",
            maximum_attempts_per_logical_request=4, timeout_seconds=60, backoff_seconds=[2, 4, 8],
            every_started_attempt_consumes_ordinal=True, partial_failure_erases_attempt=False,
            attempt_ordinal_reset_on_retry=False, next_ordinal="max(all durably started ordinals, including abandoned)+1",
            remaining_attempts="max(0, frozen maximum minus count of distinct durably started ordinals)",
            retries_backoff_by_consumed_ordinal={"1_to_2": 2, "2_to_3": 4, "3_to_4": 8},
            backoff_persists_across_process_restart=True, exhaustion_behavior="TERMINAL_TECHNICAL_FAILURE_NO_FIFTH_ATTEMPT",
            retry_decision_does_not_reserve_or_consume_next_attempt=True,
            remaining_before_and_after_decision_equal_without_new_start=True),
        "append_only_attempt_journal_contract_v1_draft": draft("AppendOnlyAttemptJournalContractV1",
            append_only_attempt_journal_required=True, overwrite_or_delete_prior_events_allowed=False,
            event_identity_fields=["run_epoch", "journal_segment_id", "event_sequence", "logical_request_id", "request_payload_sha256", "attempt_ordinal", "runtime_contract_sha256"],
            event_kinds=["ATTEMPT_STARTED", "LIFECYCLE_PROGRESS", "ATTEMPT_TERMINAL", "ABANDONED_ATTEMPT_CLASSIFIED", "CONTINUATION_SEGMENT_OPENED"],
            integrity="canonical event bytes, chained previous-event SHA-256, monotonic sequence, durable flush/fsync before state promotion",
            write_ahead_start_before_network_required=True, one_active_writer_or_locked_atomic_reservation_required=True,
            attempt_terminal_commit_requires="artifact bytes/hash durably committed first, then terminal event fsync",
            progress_events_not_terminal_authority=True, duplicate_or_conflicting_terminal_records="FAIL_CLOSED",
            torn_tail_policy="preserve damaged segment byte-identical; verify committed prefix; freeze corruption/recovery sidecar; append only in a new chained segment; never truncate or relabel original events",
            ambiguous_prefix_or_identity_or_counter_recovery="FAIL_CLOSED_NO_NETWORK",
            historical_runtime_journals_rewritten=False),
        "logical_request_state_contract": draft("LogicalRequestStateContractV2",
            states=["NOT_STARTED", "IN_PROGRESS", "RETRYABLE_FAILURE_WITH_BUDGET", "VALID_SUCCESS", "TERMINAL_TECHNICAL_FAILURE",
                "VALID_NONELIGIBLE_RESPONSE", "NOT_REQUIRED", "TERMINAL_RESPONSE_VALIDITY_FAILURE"],
            state_derived_only_from_verified_append_only_journal_and_frozen_barriers=True,
            VALID_SUCCESS_requires=["trusted terminal commit", "BODY_COMPLETE", "complete raw artifact hash verified", "unchanged response validation accepted"],
            VALID_NONELIGIBLE_RESPONSE_definition="complete validated response; unchanged eligibility says not eligible; not transport failure",
            NOT_REQUIRED_definition="only frozen activation barrier; not a failed or refreshed request",
            successful_request_refresh_allowed=False, terminal_request_automatic_reexecution_allowed=False,
            unresolved_state_not_scientific_failure=True),
        "process_restart_semantics": draft("ProcessRestartSemanticsV1",
            process_resume_semantics_required=True, open_attempt_rule="ACCEPTED_PROSPECTIVELY_FOR_FUTURE_VERSIONED_RUNTIME",
            started_without_trusted_terminal_state="ABANDONED_ATTEMPT_UNKNOWN_TERMINATION",
            abandoned_attempt_consumes_ordinal=True, abandoned_attempt_retry_requires=["frozen replay-safe declaration", "remaining budget", "verified journal and immutable request identity"],
            no_reuse_of_abandoned_ordinal=True, example="attempt 2 committed STARTED then crash -> append abandoned classification -> next start attempt 3",
            crash_after_body_freeze_before_terminal="orphan body quarantined; no trusted completion inferred; consume abandoned ordinal",
            crash_before_durable_STARTED="network must not have been invoked; verify write-ahead invariant, otherwise fail closed",
            reservation_before_network_crash="conservatively abandoned and consumed even if actual network initiation cannot be established",
            trusted_success_after_crash="verify recorded artifact hash and terminal commit; skip request, do not refetch",
            restart_integrity_failure="FAIL_CLOSED_NO_NETWORK", retry_budget_reset=False),
        "continuation_order_contract": draft("ContinuationOrderContractV2",
            immutable_frozen_request_identity_and_scientific_payload_required=True,
            same_runtime_contract_and_mapping_version_required=True, technical_connection_metadata_may_differ=True,
            resume_rule="first unresolved logical request in original frozen order; skip trusted completed success/noneligible/not-required; no reordering",
            successful_request_refresh_allowed=False, future_unresolved_order_unchanged=True,
            terminal_fail_closed_request_requires="stop; only separately prospectively frozen continuation authority can reopen a future technical request",
            alpha3_21_continuation_allowed=False),
        "two_phase_barrier_resume_contract": draft("TwoPhaseBarrierResumeContractV2",
            completed_OA_phase_refresh_allowed=False, frozen_activation_barrier_must_be_consumed=True,
            barrier_SHA256_and_OA_artifact_hashes_verified_before_resume=True,
            live_OA_recomputation_allowed=False, JATS_requests_only_from_frozen_activated_order=True,
            missing_or_corrupt_barrier_behavior="FAIL_CLOSED_NO_JATS", alpha3_21_barrier_consumed_for_new_execution=False),
        "fault_injection_matrix_contract": draft("OfflineTransportFaultInjectionMatrixV1",
            execution_phase="alpha3.22D", matrix_executed_in_master=False,
            allowed_fixtures=["synthetic streams", "mock responses", "local fixtures", "already-seen historical artifacts"],
            fresh_network_or_scientific_data_allowed=False,
            cases=[{"case_id": name, "expected_semantic_class": state, "expected_decision": decision, "execution_state": "NOT_EXECUTED"}
                   for name, state, decision in fault_rows],
            body_interruption_required_assertions=["partial bytes preserved/hash bound", "body incomplete", "parser not invoked", "deterministic retry decision", "attempt consumed", "next ordinal correct"],
            unknown_failure_required_assertions=["complete provenance", "no partial parser admission", "no automatic retry", "terminal fail-closed"],
            additional_crosscutting_cases=["budget exhaustion", "unsafe request no retry", "successful request no refresh", "consumed abandoned ordinal not reused",
                "OA barrier reused without refresh", "same payload/hash on retry", "torn journal segment retained", "duplicate writers/ordinal collision fails closed",
                "complete invalid body not transport interruption", "encoded-vs-wire length mismatch avoided", "provider backend contract isolated"],
            engineering_only=True, scientific_yield_metric=None),
        "historical_regression_contract": draft("HistoricalTransportRegressionV1",
            execution_phase="alpha3.22E", regressions_run_in_master=False,
            frozen_historical_parsers_modified=False, reference_outputs_byte_or_semantically_reproducible=True,
            allowed_data="synthetic or historical already-seen bytes; zero live network",
            cases=["historical successful ESearch valid-page behavior", "historical successful PubMed metadata", "historical successful OA/JATS",
                "unchanged identity/license/BODY outcomes for complete validated responses", "component-specific backend classification and numeric retry budgets"],
            frozen_reference_record_manifests=[ref(p, "already_seen_complete_response_reference_states_no_reexecution") for p in (
                closed.b.A1 / "per_page_terminal_states.jsonl", d2.C2 / "metadata_final_source_states.jsonl",
                d2.OUT / "oa_source_states.jsonl", d2.OUT / "jats_structural_states.jsonl",
                d2.OUT / "jats_primary_identity_states_v2.jsonl", d2.OUT / "jats_license_states.jsonl",
                d2.OUT / "canonical_body_manifest.jsonl")],
            reference_fulltext_admission="only the 9 frozen completed structural/identity-bound responses; interrupted and unexecuted responses never complete fixtures",
            comparison_boundary="run new versioned components offline; never rewrite historical outputs/contracts",
            known_environment_issue=ref(closed.OUT / "known_preexisting_test_environment_issue.json", "separate_unfixed_directory_conflict_not_runtime_failure")),
        "seen_failure_fixture_usage_contract": draft("SeenFailureFixtureUsageV1",
            alpha321_closed_and_seen=True, partial_artifact=fixture["raw_artifact"], expected_bytes=188590,
            partial_qualified_exception_class="UNKNOWN", historical_exception_class_not_inferred=True,
            offline_synthetic_stream_wrapper_allowed=True, controlled_interruption_offset_required=True,
            successful_full_JATS_claim_allowed=False, content_reclassified_as_fresh=False,
            fixture_read_for_scientific_content_in_master=False, fixture_parsed_in_master=False),
        "runtime_hardening_non_yield_optimization_contract": {"runtime_semantics_justified_by_transport_reliability_and_provenance": True,
            "construction_source_count_optimization_allowed": False, "Builder_candidate_count_optimization_allowed": False,
            "Quality_pass_count_optimization_allowed": False, "result_driven_scientific_tuning_allowed": False},
        "builder_v4_nonchange_binding": {"builder_v4_change_allowed": False, "authority": bindings["alpha3_21_builder_v4_binding"],
            "runtime_binding": bindings["alpha3_21_builder_runtime_binding"], "final_contract": bindings["builder_v4_final_contract_binding"]},
        "quality_v2_nonchange_binding": {"quality_v2_change_allowed": False, "authority": bindings["alpha3_21_quality_v2_binding"],
            "envelope": bindings["alpha3_21_quality_response_envelope_v3_binding"], "runtime_binding": bindings["alpha3_21_quality_runtime_binding"]},
        "search_plan_nonchange_binding": {"search_plan_scientific_architecture_change_allowed": False,
            "authority": bindings["alpha3_21_search_plan_architecture_binding"], "source_query_binding": firewall["frozen_source_query_set"]},
        "future_fresh_contamination_baseline": baseline,
        "alpha3_22_phase_plan": {"master_scope": "DECLARATIVE_PREREGISTRATION_ONLY", "phases": future_phases,
            "next_fresh_attempt_only_after": "alpha3.22F", "next_fresh_attempt_preregistered_here": False,
            "phase_instructions_and_offline_only_boundaries_required": True},
        "alpha3_22_release_gate": {"require_all": RELEASE_REQUIREMENTS,
            "current_evidence": {k: "NOT_EVALUATED_PENDING_ALPHA3_22_IMPLEMENTATION_AND_FINAL_FREEZE" for k in RELEASE_REQUIREMENTS},
            "implementation_release_gate_satisfied": False, "fresh_primary_start_allowed": False,
            "final_F_bundle_and_new_fresh_preregistration_required": True},
        "fresh_primary_start_prohibition": {**NO_FRESH, "fresh_cohort_before_alpha322F_allowed": False,
            "network_authorization_granted": False, "phase_A_implemented_here": False},
        "scientific_state_safety_audit": {**NO_CALLS, **NO_FRESH, **terminal_state,
            "new_runtime_behavior_implemented": False, "fault_matrix_executed": False, "historical_scientific_replay_executed": False,
            "Builder_requests_constructed": 0, "Quality_requests_constructed": 0, "new_source_selected": False,
            "partial_XML_parsed": False, "scientific_policy_changed": False},
        "historical_preservation_audit": {"alpha3_21_artifacts_modified": False, "historical_runtime_modified": False,
            "alpha321_closure_before": before, "alpha321_contamination_registry_hash": REGISTRY_SHA,
            "scientific_bound_files_unchanged": True, "sole_baseline_preserved": True},
        "validation": {"status": "completed", "preregistration_validation_only": True,
            "future_fault_matrix_passed": False, "future_historical_regression_passed": False,
            "release_gate_satisfied": False, "runtime_not_implemented": True, **NO_CALLS},
        "summary": {"status": "completed", "stage_identity": STAGE, "alpha3_22_master_classification": CLASSIFICATION,
            "alpha3_21_closure_root_verified": True, "alpha3_21_terminal_classification_verified": True,
            "development_mode": True, **NO_FRESH, **terminal_state,
            "response_body_completion_first_class_state": True, "response_body_interruption_first_class_state": True,
            "future_body_interruption_retryable": True, "future_body_interruption_retry_requires_replay_safe_request": True,
            "partial_response_authoritative": False, "partial_response_parser_allowed": False,
            "unknown_runtime_failure_automatic_retry": False, "broad_exception_capture_for_observability_allowed": True,
            "broad_exception_capture_implies_retry": False, "attempt_ordinal_reset_on_retry": False,
            "successful_request_refresh_allowed": False, "append_only_attempt_journal_required": True,
            "process_resume_semantics_required": True, "builder_v4_change_allowed": False,
            "quality_v2_change_allowed": False, "search_plan_scientific_architecture_change_allowed": False,
            **counts, "alpha3_21_future_contamination_registry_sha256": REGISTRY_SHA, **NO_CALLS,
            "production_runtime_modified": False, "implementation_release_gate_satisfied": False,
            "next_stage_recommendation": NEXT},
    }
    validate_design(docs)
    after = verify_baseline()[0]
    require(before == after, "HISTORICAL_CLOSURE_MUTATED_DURING_MASTER")
    docs["historical_preservation_audit"]["alpha321_closure_after"] = after
    docs["historical_preservation_audit"]["historical_code_hashes_before_after_equal"] = all(
        digest(ROOT / r["artifact_path"]) == r["sha256"] for r in inventory["unchanged_source_code"])
    require(docs["historical_preservation_audit"]["historical_code_hashes_before_after_equal"], "HISTORICAL_RUNTIME_CODE_MUTATED")
    return docs


def validate_design(docs):
    """Static document consistency only. Never run the prospective runtime."""
    require(set(docs) == set(REQUIRED) | set(EXTRAS), "MASTER_ARTIFACT_MEMBERSHIP_MISMATCH")
    for row in docs["transport_lifecycle_contract_v2_draft"]["transitions"]:
        require(row["from"] in STATES and row["to"] in STATES and row["guard"], "INVALID_LIFECYCLE_DRAFT_TRANSITION")
    matrix = docs["transport_retryability_matrix"]["entries"]
    require([r["semantic_state"] for r in matrix] == TAXONOMY, "TAXONOMY_MATRIX_MISMATCH")
    require(all(r["retryable_technical_class"] is (r["semantic_state"] in TAXONOMY[:5]) for r in matrix), "RETRY_MATRIX_DESIGN_DRIFT")
    require(docs["transport_exception_mapping_design_contract"]["mapping_entries"] == [], "PREMATURE_CONCRETE_EXCEPTION_MAPPER")
    semantic_checks = {
        "response_body_completion_semantics": {"response_body_completion_first_class_state": True, "HTTP_status_or_headers_sufficient": False},
        "response_body_interruption_semantics": {"response_body_interruption_first_class_state": True, "exception_name_only_sufficient": False},
        "transport_retry_semantics_v2_draft": {"future_body_interruption_retryable": True,
            "future_body_interruption_retry_requires_replay_safe_request": True, "retroactive_alpha321_authorization": False,
            "unknown_runtime_failure_automatic_retry": False, "broad_exception_capture_implies_retry": False,
            "catch_Exception_OSError_IOError_retry_authorized": False},
        "partial_response_quarantine_contract": {"partial_response_authoritative": False, "partial_response_parser_allowed": False,
            "canonical_source_identity_allowed": False},
        "transport_observability_contract_v1_draft": {"broad_exception_capture_for_observability_allowed": True,
            "broad_exception_capture_implies_retry": False},
        "attempt_consumption_contract": {"attempt_ordinal_reset_on_retry": False, "every_started_attempt_consumes_ordinal": True,
            "partial_failure_erases_attempt": False},
        "logical_request_state_contract": {"successful_request_refresh_allowed": False},
        "two_phase_barrier_resume_contract": {"completed_OA_phase_refresh_allowed": False,
            "frozen_activation_barrier_must_be_consumed": True, "live_OA_recomputation_allowed": False},
    }
    for name, fields in semantic_checks.items():
        for field, expected in fields.items():
            require(docs[name][field] is expected, "SEMANTIC_DESIGN_SAFETY_DRIFT:" + name + ":" + field)
    consumption = docs["attempt_consumption_contract"]
    require((consumption["maximum_attempts_per_logical_request"], consumption["timeout_seconds"], consumption["backoff_seconds"])
            == (4, 60, [2, 4, 8]), "NUMERIC_BUDGET_DESIGN_DRIFT")
    for name in ("exception_provenance_schema", "http_response_provenance_schema", "body_read_provenance_schema", "retry_decision_provenance_schema"):
        s = docs[name]
        require(s["type"] == "object" and s["additionalProperties"] is False
                and set(s["required"]) == set(s["properties"]), "PROVENANCE_SCHEMA_STATIC_INCONSISTENCY")
    phases = docs["alpha3_22_phase_plan"]["phases"]
    require([p["phase"] for p in phases] == [p[0] for p in PHASES]
            and all(p["execution_state"] == "NOT_STARTED" and p["network_calls_allowed"] is False for p in phases), "PHASE_BOUNDARY_VIOLATION")
    gate = docs["alpha3_22_release_gate"]
    require(gate["require_all"] == RELEASE_REQUIREMENTS and gate["implementation_release_gate_satisfied"] is False
            and gate["fresh_primary_start_allowed"] is False, "PREMATURE_RUNTIME_RELEASE")
    require(len(docs["fault_injection_matrix_contract"]["cases"]) >= 13
            and all(c["execution_state"] == "NOT_EXECUTED" for c in docs["fault_injection_matrix_contract"]["cases"]), "FAULT_MATRIX_EXECUTED_IN_MASTER")
    require(docs["process_restart_semantics"]["open_attempt_rule"] == "ACCEPTED_PROSPECTIVELY_FOR_FUTURE_VERSIONED_RUNTIME", "OPEN_ATTEMPT_RULE_LEFT_AMBIGUOUS")
    for name in SEMANTIC_STEMS:
        value = docs[name]
        if "implementation_state" in value:
            require(value["implementation_state"] == "NOT_IMPLEMENTED" and value["runtime_activation_allowed"] is False, "RUNTIME_IMPLEMENTATION_IN_MASTER")
    firewall = docs["alpha3_22_scientific_policy_firewall"]
    require(all(v is False for k, v in firewall.items() if k.endswith("_allowed")), "SCIENTIFIC_FIREWALL_BREACH")
    require(docs["summary"]["alpha3_21_reopened"] is False
            and docs["summary"]["alpha3_21_continuation_created"] is False
            and docs["summary"]["fresh_primary_attempt_started"] is False, "CLOSED_OR_FRESH_BOUNDARY_BREACH")


def bundle_documents(docs):
    """Hash manifests bind exact prospective documents, with no activation."""
    def binding(name):
        return {"artifact_path": str((OUT / (name + ".json")).relative_to(ROOT)),
                "sha256": sha(canonical(docs[name]) + b"\n"), "immutable_frozen": True,
                "artifact_role": "frozen_prospective_design_not_runtime_activation"}
    bundle = {"schema_version": "Alpha322TransportSemanticsBundleV1", "members": [binding(n) for n in SEMANTIC_STEMS],
              "implementation_state": "NOT_IMPLEMENTED", "runtime_activation_allowed": False,
              "applies_to_alpha321": False, "exception_mapping_entries_frozen": False}
    bundle_sha = sha(canonical(bundle) + b"\n")
    plan = {"schema_version": "Alpha322MasterDevelopmentExecutionPlanV1", "master_only": True,
            "transport_semantics_bundle_sha256": bundle_sha,
            "phase_plan": binding("alpha3_22_phase_plan"), "release_gate": binding("alpha3_22_release_gate"),
            "scientific_firewall": binding("alpha3_22_scientific_policy_firewall"),
            "contamination_baseline": binding("future_fresh_contamination_baseline"),
            "seen_fixture_boundary": binding("seen_failure_fixture_usage_contract"),
            "historical_regression": binding("historical_regression_contract"),
            "fresh_start_prohibition": binding("fresh_primary_start_prohibition"),
            "execute_implementation_now": False, "network_authorized": False, "next_stage_recommendation": NEXT}
    return bundle, bundle_sha, plan, sha(canonical(plan) + b"\n")


def run(verification=None):
    require(not OUT.exists(), "ALPHA322_MASTER_OUTPUT_EXISTS_NO_OVERWRITE")
    if verification is not None:
        require(verification["implementation_sha256"] == digest(Path(__file__))
                and verification["test_implementation_sha256"] == digest(TEST)
                and verification["checks"] and all(c["check_passed"] is True for c in verification["checks"]), "LOCAL_VERIFICATION_REPORT_MISMATCH")
    with prior.offline_guard():
        try:
            docs = build_protocol()
            bundle, bundle_sha, plan, plan_sha = bundle_documents(docs)
            docs["summary"].update({BUNDLE_MARKER: bundle_sha, PLAN_MARKER: plan_sha})
        except Exception as exc:
            result = {"status": "failed", "alpha3_22_master_classification": "MASTER_PREREGISTRATION_BLOCKED_BY_INTEGRITY_OR_DESIGN_FAILURE",
                      "failure": type(exc).__name__ + ":" + str(exc), "runtime_activation_allowed": False,
                      "fresh_primary_attempt_started": False, "alpha3_21_reopened": False, **NO_CALLS}
            docs = {name: dict(result) for name in (*REQUIRED, *EXTRAS)}
            bundle = plan = None
        OUT.mkdir()

        def write(name, raw):
            p = OUT / name
            require(p.parent == OUT and not p.is_symlink(), "OUTPUT_PATH_ESCAPE_OR_SYMLINK")
            with p.open("xb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())

        for name, value in docs.items():
            write(name + ".json", canonical(value) + b"\n")
        if bundle is not None:
            write("alpha3_22_transport_semantics_bundle.json", canonical(bundle) + b"\n")
            write(BUNDLE_MARKER, (bundle_sha + "\n").encode())
            write("alpha3_22_master_execution_plan.json", canonical(plan) + b"\n")
            write(PLAN_MARKER, (plan_sha + "\n").encode())
            require(digest(OUT / "alpha3_22_transport_semantics_bundle.json") == bundle_sha
                    and digest(OUT / "alpha3_22_master_execution_plan.json") == plan_sha, "WRITTEN_BUNDLE_OR_PLAN_HASH_MISMATCH")
            d2.d1.d.checked_tree(bundle)
            d2.d1.d.checked_tree(plan)
        write("master_prereg_implementation_binding.json", canonical(ref(Path(__file__), "declarative_master_writer_not_transport_runtime")) + b"\n")
        write("focused_test_implementation_binding.json", canonical(ref(TEST, "offline_master_design_validation_not_fault_execution")) + b"\n")
        if verification is not None:
            write("offline_verification_results.json", canonical(verification) + b"\n")
        prior.root_check(closed.OUT, closed.ROOT_MARKER, CLOSURE_SHA)
        closed.verify_roots()
        if docs["summary"]["status"] == "completed":
            verify_baseline()
            for value in docs.values():
                d2.d1.d.checked_tree(value)
        sealed = root_hash(OUT, ROOT_MARKER)
        write(ROOT_MARKER, (sealed + "\n").encode())
        require(root_hash(OUT, ROOT_MARKER) == sealed, "ALPHA322_MASTER_ROOT_MISMATCH")
        return {**docs["summary"], ROOT_MARKER: sealed}


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, sort_keys=True), flush=True)
    raise SystemExit(0 if result["status"] == "completed" else 1)
