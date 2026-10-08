#!/usr/bin/env python3
"""Alpha3.22A implementation freeze. Synthetic/offline only, no live wiring."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from code_engine import transport_lifecycle_v2 as t
from code_engine import transport_observability_v1 as o
from scripts import run_search_plan_v24_alpha322_master_prereg_offline as master


ROOT = master.ROOT
OUT = ROOT / "runs/20261008_search_plan_v24_dev_alpha3_22a_transport_state_observability_implementation_offline"
ROOT_MARKER = "search_plan_v24_dev_alpha3_22a_sha256"
CLASSIFICATION = "TRANSPORT_STATE_MACHINE_AND_OBSERVABILITY_IMPLEMENTED_OFFLINE"
STAGE = "POST_ALPHA3_21_TRANSPORT_STATE_AND_OBSERVABILITY_IMPLEMENTATION"
NEXT = "IMPLEMENT_ALPHA3_22B_EXCEPTION_MAPPING_INVENTORY_AND_VERSIONED_RETRY_MAPPER_OFFLINE"
BUNDLE_SHA = "2add0bc9ff0e236e2d1e7932317a3ad98365d509476e8654cc0dfa20362951ba"
PLAN_SHA = "4c8ae9a8e63268d5c7447fe19742831c80ede48027e6a5171e927cf57a2027c7"
TEST = ROOT / "tests/test_search_plan_v24_alpha322a_transport_observability_offline.py"
COMPONENTS = [Path(t.__file__), Path(o.__file__)]
SCHEMAS = {"exception_provenance_v1_schema": "exception_provenance_schema",
           "http_response_provenance_v1_schema": "http_response_provenance_schema",
           "body_read_provenance_v1_schema": "body_read_provenance_schema",
           "retry_decision_provenance_v1_schema": "retry_decision_provenance_schema"}
REQUIRED = tuple("""alpha3_22_master_root_verification alpha3_21_closure_binding_verification alpha3_22a_scope_boundary
transport_lifecycle_v2_implementation_manifest transport_lifecycle_v2_state_table transport_lifecycle_v2_transition_audit
response_body_completion_implementation response_body_interruption_implementation transport_failure_taxonomy_implementation
semantic_retry_decision_contract semantic_retry_decision_test_results transport_attempt_observation_schema
exception_provenance_v1_schema http_response_provenance_v1_schema body_read_provenance_v1_schema retry_decision_provenance_v1_schema
observability_secret_redaction_contract observability_secret_redaction_test_results partial_response_quarantine_implementation
partial_response_parser_guard partial_response_parser_guard_test_results deterministic_observability_serialization_audit
synthetic_complete_body_fixture_manifest synthetic_interrupted_body_fixture_manifest content_length_mismatch_fixture_manifest
complete_invalid_payload_fixture_manifest alpha3_21_seen_partial_fixture_usage_audit alpha3_22a_focused_test_manifest
legacy_runtime_preservation_audit new_runtime_component_inventory concrete_exception_mapping_nonimplementation_audit
journal_resume_nonimplementation_audit scientific_policy_firewall_audit contamination_baseline_immutability_audit
historical_preservation_audit scientific_state_safety_audit validation summary""".split())
MARKERS = {"transport_lifecycle_v2_implementation_sha256": "transport_lifecycle_v2_implementation_manifest",
           "transport_observability_v1_bundle_sha256": "transport_observability_v1_bundle",
           "semantic_retry_decision_contract_sha256": "semantic_retry_decision_contract"}
NOW = "2000-01-01T00:00:00Z"
NO_CALLS = {k: 0 for k in ("network_calls", "pubmed_calls", "pmc_calls", "provider_calls", "llm_calls", "builder_calls", "quality_calls")}
NEGATIVE = {k: False for k in ("fresh_primary_attempt_started", "alpha3_21_reopened", "legacy_runtime_modified",
    "concrete_exception_mapping_implemented", "append_only_journal_implemented", "process_resume_implemented",
    "builder_v4_changed", "quality_v2_changed", "search_plan_scientific_architecture_changed",
    "partial_response_authoritative", "partial_response_parser_allowed", "unknown_runtime_failure_automatic_retry")}
canonical, digest, ref, obj, require = o.canonical_bytes, master.digest, master.ref, master.obj, t.require


def verify_authority():
    root = master.prior.root_check(master.OUT, master.ROOT_MARKER, t.MASTER_ROOT_SHA256)
    for name, marker, expected in (("alpha3_22_transport_semantics_bundle", master.BUNDLE_MARKER, BUNDLE_SHA),
                                   ("alpha3_22_master_execution_plan", master.PLAN_MARKER, PLAN_SHA)):
        require(digest(master.OUT / (name + ".json")) == expected == (master.OUT / marker).read_text().strip(), "MASTER_MEMBER_MISMATCH")
        master.d2.d1.d.checked_tree(obj(master.OUT / (name + ".json")))
    closure, _, registry_path, _, counts, bindings = master.verify_baseline()
    inventory = obj(master.OUT / "repository_runtime_authority_inventory.json")
    master.d2.d1.d.checked_tree(inventory)
    legacy = [dict(r) for r in inventory["unchanged_source_code"]]
    legacy.extend(ref(path, "unchanged_frozen_master_or_closure_code") for path in (
        Path(master.__file__), master.TEST, Path(master.closed.__file__), master.closed.TEST))
    return {"master": root, "closure": closure, "phase_roots": master.closed.verify_roots(),
            "registry": ref(registry_path, "sole_unchanged_future_contamination_baseline"), "counts": counts,
            "scientific_bindings": bindings, "legacy": legacy}


def observation_schema():
    string_null = {"type": ["string", "null"]}
    nested = {key: {"type": ["object", "null"]} for key in ("exception_provenance", "http_response_provenance",
        "body_read_provenance", "retry_decision_provenance")}
    fields = {**{k: {"type": "string"} for k in ("logical_request_id", "request_payload_sha256", "runtime_contract_sha256")},
        "attempt_ordinal": {"type": "integer", "minimum": 1, "maximum": 4}, **nested,
        "response_started_at": string_null, "actual_length_bytes": {"type": ["integer", "null"], "minimum": 0},
        "lifecycle_state": {"enum": [s.value for s in t.LifecycleState]}, "lifecycle_events": {"type": "array", "items": {"type": "object"}},
        "journal_persistence_implemented": {"const": False}, "process_resume_implemented": {"const": False}}
    # Exact frozen schemas for the nullable nested members are separately
    # required in validate_observation; none of their definitions is altered.
    return master.schema("TransportAttemptObservationV1", fields)


def validate_observation(record):
    o.validate_schema(record, observation_schema())
    for key, stem in (("exception_provenance", "exception_provenance_schema"), ("http_response_provenance", "http_response_provenance_schema"),
                      ("body_read_provenance", "body_read_provenance_schema"), ("retry_decision_provenance", "retry_decision_provenance_schema")):
        if record[key] is not None:
            o.validate_schema(record[key], obj(master.OUT / (stem + ".json")))


class SyntheticInterruption(Exception):
    """Test-only sentinel, not any library exception mapping."""


class SyntheticStream:
    def __init__(self, prefix: bytes):
        self.prefix = prefix
        self.calls = 0

    def read(self):
        self.calls += 1
        if self.calls == 1:
            return self.prefix
        raise SyntheticInterruption("synthetic stream terminated after controlled prefix")


def expect_denied(callback):
    try:
        callback()
    except t.TransportContractError:
        return True
    raise AssertionError("EXPECTED_FAIL_CLOSED_GUARD")


def synthetic_fixtures(directory: Path):
    """Small 22A unit fixtures, NOT the full alpha3.22D fault matrix."""
    store = t.RawArtifactStoreV1(directory)
    redactor = o.SecretRedactorV1(("synthetic-private-credential",))
    results = {}
    for name in ("complete", "interrupted", "length_mismatch", "invalid_complete"):
        context = t.AttemptContextV1("synthetic:" + name, master.sha(b"immutable synthetic request"), 1)
        lifecycle = t.TransportLifecycleV2(context)
        lifecycle.start_attempt("SYNTHETIC_IN_MEMORY_START_NO_NETWORK", timestamp=NOW)
        lifecycle.receive_headers(200, trustworthy=True, evidence_reference="synthetic_headers", timestamp=NOW)
        lifecycle.start_body("synthetic_read", timestamp=NOW)
        raw = b"<synthetic><id>test-only</id></synthetic>" if name != "invalid_complete" else b"<synthetic>"
        exception_record = None
        if name == "interrupted":
            stream = SyntheticStream(b"<synthetic>quarantined-prefix")
            raw = stream.read()
            try:
                stream.read()
            except SyntheticInterruption as exc:
                captured = o.ExceptionProvenanceV1.capture(exc, context, redactor)
                require(captured.provenance is not None, "SYNTHETIC_EXCEPTION_CAPTURE_FAILED")
                exception_record = captured.provenance
            completion = t.assess_body_completion(raw, read_returned_normally=False,
                interruption_class=t.SemanticFailure.RESPONSE_BODY_TRANSPORT_INTERRUPTION,
                interruption_reason="explicit synthetic sentinel evidence", timestamp=NOW,
                exception_provenance_reference="synthetic_exception_provenance")
        else:
            completion = t.assess_body_completion(raw, read_returned_normally=True,
                expected_content_length=len(raw) + 1 if name == "length_mismatch" else len(raw), expected_length_trustworthy=True,
                expected_length_representation=t.ByteRepresentation.WIRE, timestamp=NOW)
        lifecycle.record_body(completion, "synthetic_body_facts", timestamp=NOW)
        artifact = store.freeze_bytes(name + ".raw", raw)
        response = lifecycle.freeze_response(artifact, timestamp=NOW)
        calls = {key: 0 for key in ("XML", "JSON", "JATS_identity", "license", "BODY_normalizer", "scientific_extraction")}
        if name in {"interrupted", "length_mismatch"}:
            for key in calls:
                def stub(body, key=key):
                    calls[key] += 1
                    return "FORBIDDEN_PARTIAL_ADMISSION"
                expect_denied(lambda: t.guarded_parse(response, stub))
            expect_denied(lambda: lifecycle.record_validation(valid=True, evidence_reference="forbidden_partial_validation"))
            failure = completion.semantic_failure
            require(not response.authoritative and not any(calls.values()), "PARTIAL_QUARANTINE_FAILURE")
        else:
            def xml_stub(body):
                calls["XML"] += 1
                return ET.fromstring(body)
            valid = True
            try:
                t.guarded_parse(response, xml_stub)
            except ET.ParseError:
                valid = False
            failure = lifecycle.record_validation(valid=valid, evidence_reference="synthetic_payload_validation", timestamp=NOW)
            require(valid == (name == "complete"), "SYNTHETIC_VALIDATION_EXPECTATION_MISMATCH")
        decision = t.semantic_retry_decision(failure, request_replay_safe=True, attempt_ordinal=1)
        http = o.HttpResponseProvenanceV1.capture(context, redactor, method="GET", request_url="https://synthetic.invalid/test?api_key=synthetic-private-credential",
            status=200, reason="OK", headers=(("Content-Length", str(completion.expected_content_length if completion.expected_content_length is not None else len(raw))),
                ("Set-Cookie", "synthetic-private-credential")),
            expected_length=completion.expected_content_length, body_byte_representation="wire", trusted=True, headers_received_at=NOW,
            status_origin="SYNTHETIC_TRUSTED_HEADERS")
        body = o.BodyReadProvenanceV1.capture(context, redactor, completion, artifact, started_at=NOW, parser_invoked=bool(calls["XML"]))
        retry = o.RetryDecisionProvenanceV1.capture(context, redactor, decision, replay_safety_authority={"scope": "synthetic-only explicit declaration"})
        observation = o.TransportAttemptObservationV1.capture(lifecycle, redactor, response_started_at=NOW,
            exception=exception_record, http=http, body=body, retry=retry)
        validate_observation(observation.record())
        observation_artifact = observation.freeze(store, name + ".observation.json")
        results[name] = {"fixture_kind": "LOCAL_SYNTHETIC_ONLY", "raw_artifact": artifact.__dict__,
            "observation_artifact": observation_artifact.__dict__, "body_state": completion.body_completion_state.value,
            "semantic_failure": failure.value, "parser_invocation_counts": calls, "retry_authorized": decision.retry_authorized,
            "attempt_ordinal": decision.attempt_ordinal, "next_attempt_ordinal": decision.next_attempt_ordinal,
            "remaining_attempts": decision.remaining_attempts_before_decision, "check_passed": True}
    require(results["invalid_complete"]["semantic_failure"] == t.SemanticFailure.COMPLETE_BODY_RESPONSE_VALIDITY_FAILURE.value
            and results["invalid_complete"]["body_state"] == t.BodyState.COMPLETE.value and not results["invalid_complete"]["retry_authorized"], "COMPLETE_INVALID_MISCLASSIFIED")
    return results


def static_boundaries():
    imports = []
    symbols = []
    for path in COMPONENTS:
        tree = ast.parse(path.read_text())
        imports.extend(n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom))
        imports.extend(alias.name for n in ast.walk(tree) if isinstance(n, ast.Import) for alias in n.names)
        symbols.extend(n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef)))
    banned = {"http.client", "urllib.request", "socket", "requests", "httpx", "openai", "deepseek"}
    require(not banned.intersection(imports), "PREMATURE_NETWORK_OR_CONCRETE_MAPPING_IMPORT")
    require(not any(s in symbols for s in ("resume", "retry_loop", "map_exception", "append_event", "execute_request")), "PREMATURE_MAPPER_JOURNAL_OR_EXECUTOR")
    return {"checked_imports": sorted(set(str(i) for i in imports)), "checked_symbols": sorted(set(symbols)),
            "concrete_exception_mapping_implemented": False, "network_adapter_implemented": False,
            "append_only_journal_implemented": False, "process_resume_implemented": False,
            "in_memory_lifecycle_events_only": True, "raw_byte_storage_is_not_attempt_journal": True}


def crosscutting_checks():
    decisions = {}
    for name, failure, safe, ordinal in (
        ("safe_body_retry", t.SemanticFailure.RESPONSE_BODY_TRANSPORT_INTERRUPTION, True, 1),
        ("unsafe_body_denied", t.SemanticFailure.RESPONSE_BODY_TRANSPORT_INTERRUPTION, False, 1),
        ("budget_exhausted", t.SemanticFailure.RESPONSE_BODY_TRANSPORT_INTERRUPTION, True, 4),
        ("unknown_denied", t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE, True, 1),
        ("complete_invalid_denied", t.SemanticFailure.COMPLETE_BODY_RESPONSE_VALIDITY_FAILURE, True, 1)):
        d = t.semantic_retry_decision(failure, request_replay_safe=safe, attempt_ordinal=ordinal)
        expected = name == "safe_body_retry"
        require(d.retry_authorized is expected and d.remaining_attempts_before_decision == d.remaining_attempts_after_decision == 4 - ordinal, "RETRY_GATE_FAILED")
        decisions[name] = {k: v.value if isinstance(v, t.SemanticFailure) else v for k, v in d.__dict__.items()}
    secret = "synthetic-secret-value"
    redactor = o.SecretRedactorV1((secret,))
    sample = {"headers": [{"name": "Authorization", "value": "Bearer " + secret}, {"name": "Cookie", "value": "private-cookie"}],
        "url": "https://user:private-password@synthetic.invalid/test?api_key=" + secret,
        "message": "password=" + secret, "args": {"token": secret}, "traceback": "authorization: " + secret}
    clean, paths = redactor.tree(sample)
    serialized = canonical(clean)
    require(all(v.encode() not in serialized for v in (secret, "private-cookie", "private-password")) and bool(paths), "SECRET_REDACTION_FAILED")
    require(serialized == canonical(redactor.tree(clean)[0]), "REDACTION_NOT_IDEMPOTENT")
    a = {"timestamp": "clock1", "message": redactor.text("object at 0x123abc"), "data": {"z": 1, "a": 2}}
    b = {"data": {"a": 2, "z": 1}, "message": redactor.text("object at 0x999abc"), "timestamp": "clock2"}
    require(canonical(a) != canonical(b) and canonical(o.semantic_payload(a)) == canonical(o.semantic_payload(b)), "CLOCK_OR_ADDRESS_DETERMINISM_FAILED")
    return {"decisions": decisions, "redaction_paths": list(paths), "redaction_passed": True,
        "serialization_passed": True, "semantic_sha256": master.sha(canonical(o.semantic_payload(a)))}


def build_documents(authority, fixtures, checks, verification):
    inventory = []
    for name, version, path, role, contract in (
        ("TransportLifecycleV2", "V2", COMPONENTS[0], "guarded single-attempt lifecycle", "transport_lifecycle_contract_v2_draft"),
        ("BodyCompletionResultV2", "V2", COMPONENTS[0], "normal return and authoritative framing evidence", "response_body_completion_semantics"),
        ("RawArtifactStoreV1", "V1", COMPONENTS[0], "exclusive complete/partial byte artifacts", "partial_response_quarantine_contract"),
        ("SemanticRetryDecisionV2", "V2", COMPONENTS[0], "pure semantic/replay-safe/budget decision", "transport_retry_semantics_v2_draft"),
        ("TransportAttemptObservationV1", "V1", COMPONENTS[1], "immutable redacted aggregate observation", "transport_observability_contract_v1_draft"),
        ("ExceptionProvenanceV1", "V1", COMPONENTS[1], "actual exception chain/cycle/unavailable capture", "exception_provenance_schema"),
        ("HttpResponseProvenanceV1", "V1", COMPONENTS[1], "trusted and unavailable HTTP provenance", "http_response_provenance_schema"),
        ("BodyReadProvenanceV1", "V1", COMPONENTS[1], "complete versus quarantined byte provenance", "body_read_provenance_schema"),
        ("RetryDecisionProvenanceV1", "V1", COMPONENTS[1], "semantic decision, not retry execution", "retry_decision_provenance_schema"),
        ("SecretRedactorV1", "V1", COMPONENTS[1], "deterministic pre-persistence redaction", "transport_observability_contract_v1_draft"),
        ("guarded_parse", "V2", COMPONENTS[0], "necessary complete-transport guard; unchanged downstream validators still required", "partial_response_quarantine_contract")):
        inventory.append({"component_name": name, "version": version, "semantic_responsibility": role,
            "module_path": str(path.relative_to(ROOT)), "source_sha256": digest(path),
            "master_contract_binding": ref(master.OUT / (contract + ".json"), "unchanged_master_authority")})
    scope = {"development_mode": True, **NEGATIVE, **NO_CALLS,
        "production_wiring": False, "full_fault_matrix_executed": False, "historical_replay_executed": False,
        "runtime_activation_allowed": False, "next_stage_recommendation": NEXT}
    retry_contract = {"schema_version": "SemanticRetryDecisionInterfaceV2", "master_root_sha256": t.MASTER_ROOT_SHA256,
        "source": ref(COMPONENTS[0], "pure_unwired_semantic_function"), "input": ["semantic_failure", "request_replay_safe", "attempt_ordinal", "bound_policy"],
        "output": list(checks["decisions"]["safe_body_retry"]), "maximum_attempts": 4, "timeout_seconds": 60, "backoff_seconds": [2, 4, 8],
        "backend_authority_if_applicable": t.BACKEND_AUTHORITY_SHA256, "exception_mapping": False,
        "decision_consumes_next_attempt": False, "attempt_ordinal_reset_on_retry": False, "complete_validity_failure_generic_retry": False,
        "logical_terminal_state_alias": {"TERMINAL_VALIDITY_FAILURE": "TERMINAL_RESPONSE_VALIDITY_FAILURE"}}
    docs = {"alpha3_22_master_root_verification": {**authority["master"], "bundle_sha256": BUNDLE_SHA, "execution_plan_sha256": PLAN_SHA},
        "alpha3_21_closure_binding_verification": authority["closure"], "alpha3_22a_scope_boundary": scope,
        "transport_lifecycle_v2_implementation_manifest": {"schema_version": "TransportLifecycleV2ImplementationManifest", "members": [r for r in inventory if r["module_path"] == str(COMPONENTS[0].relative_to(ROOT))],
            "runtime_activation_allowed": False, "master_root_sha256": t.MASTER_ROOT_SHA256},
        "transport_lifecycle_v2_state_table": {"states": [s.value for s in t.LifecycleState],
            "allowed_transitions": [{"from": x.value, "to": y.value} for x, y in sorted(t.ALLOWED_TRANSITIONS, key=lambda pair: (pair[0].value, pair[1].value))]},
        "transport_lifecycle_v2_transition_audit": {"master_edges_equal": t.ALLOWED_TRANSITIONS == frozenset((t.LifecycleState(r["from"]), t.LifecycleState(r["to"])) for r in obj(master.OUT / "transport_lifecycle_contract_v2_draft.json")["transitions"]),
            "state_events": "IN_MEMORY_ONLY_NOT_DURABLE_START_AUTHORITY", "fixtures": fixtures},
        "response_body_completion_implementation": {"first_class_state": True, "HTTP_200_is_not_completion": True,
            "scientific_eligibility_implied_by_transport": False,
            "normal_read_required": True, "authoritative_same_representation_length_required": True, "missing_length_not_invented": True,
            "all_available_authoritative_framing_checks_must_pass": True, "unknown_admission": "QUARANTINE_NO_PARSER"},
        "response_body_interruption_implementation": {"first_class_state": True, "semantic_body_phase_required": True,
            "body_interruption_semantically_retryable": True, "length_mismatch_distinct_class": True, "exception_name_mapping": False},
        "transport_failure_taxonomy_implementation": {"states": [s.value for s in t.SemanticFailure], "concrete_mapper_implemented": False},
        "semantic_retry_decision_contract": retry_contract,
        "semantic_retry_decision_test_results": {"check_passed": True, "cases": checks["decisions"]},
        "transport_attempt_observation_schema": observation_schema(),
        "observability_secret_redaction_contract": {"version": "V1", "source": ref(COMPONENTS[1], "redaction_before_record_freeze"),
            "sensitive_keys": sorted(o.SENSITIVE_KEYS), "explicit_known_secret_values_required": True, "reads_environment_secrets": False,
            "URL_userinfo_and_secret_query_values_redacted": True, "header_credentials_and_cookies_redacted": True,
            "exception_message_args_repr_traceback_redacted": True, "redaction_paths_preserved": True},
        "observability_secret_redaction_test_results": {"check_passed": checks["redaction_passed"], "redaction_paths": checks["redaction_paths"]},
        "partial_response_quarantine_implementation": {"partial_response_authoritative": False, "partial_response_parser_allowed": False,
            "exclusive_raw_artifact_storage": True, "partial_hash_and_length_preserved": True, "unknown_completion_quarantined": True,
            "canonical_identity_from_partial_allowed": False},
        "partial_response_parser_guard": {"source": ref(COMPONENTS[0], "guarded_parse"), "blocked_consumers": list(fixtures["interrupted"]["parser_invocation_counts"]),
            "raw_hash_reverified_before_parser": True, "complete_body_required": True, "trusted_accepted_HTTP_required": True},
        "partial_response_parser_guard_test_results": {"check_passed": True, "partial_cases": {k: fixtures[k]["parser_invocation_counts"] for k in ("interrupted", "length_mismatch")}},
        "deterministic_observability_serialization_audit": {"check_passed": checks["serialization_passed"], "sorted_keys": True,
            "memory_addresses_normalized": True, "arbitrary_object_repr_in_args": False, "timestamp_policy": "CONTROLLED_FIXTURE_CLOCK_OR_SEPARATE_SEMANTIC_PAYLOAD", "semantic_sha256": checks["semantic_sha256"]},
        "alpha3_21_seen_partial_fixture_usage_audit": {"fixture_contract": ref(master.OUT / "seen_failure_fixture_usage_contract.json", "already_seen_boundary"),
            "historical_partial_bytes_used": False, "historical_partial_parsed": False, "historical_exception_fields_reconstructed": False,
            "fixture_usage": "NOT_USED_IN_22A_SYNTHETIC_FIXTURES_ONLY"},
        "alpha3_22a_focused_test_manifest": verification,
        "legacy_runtime_preservation_audit": {"legacy_runtime_modified": False, "production_wiring_changed": False, "byte_verified_sources": authority["legacy"]},
        "new_runtime_component_inventory": {"components": inventory, "implementation_runner": ref(Path(__file__), "offline_freeze_only"), "tests": ref(TEST, "offline_focused_tests")},
        "concrete_exception_mapping_nonimplementation_audit": static_boundaries(),
        "journal_resume_nonimplementation_audit": {"append_only_journal_implemented": False, "process_resume_implemented": False,
            "durable_ordinal_reservation": False, "two_phase_barrier_resume": False, "event_objects_only": True,
            "raw_artifact_fsync_is_not_attempt_journal": True},
        "scientific_policy_firewall_audit": {"scientific_policy_changed": False, "unchanged_scientific_bindings": authority["scientific_bindings"], **scope},
        "contamination_baseline_immutability_audit": {"baseline": authority["registry"], **authority["counts"], "competing_registry_created": False, "baseline_modified": False},
        "historical_preservation_audit": {"historical_roots_verified": authority["phase_roots"], "closure": authority["closure"], "master": authority["master"], "historical_artifacts_modified": False},
        "scientific_state_safety_audit": {**scope, "scientific_assets_created": False, "yield_optimization_performed": False},
        "validation": {"status": "passed", "all_22a_release_criteria_passed": True, "later_master_release_gates_completed": False,
            "runtime_activation_allowed": False, "historical_hashes_preserved": True},
        "summary": {"status": "completed", "alpha3_22a_classification": CLASSIFICATION, "stage_identity": STAGE,
            "alpha3_22_master_root_verified": True, "alpha3_21_closure_root_verified": True,
            "transport_lifecycle_v2_implemented": True, "transport_transition_validator_implemented": True,
            "response_body_completion_first_class_state": True, "response_body_interruption_first_class_state": True,
            "content_length_mismatch_distinct_state": True, "complete_body_response_validity_failure_distinct": True,
            "partial_response_quarantine_implemented": True, "semantic_retry_decision_implemented": True,
            "body_interruption_semantically_retryable": True, "body_interruption_retry_requires_replay_safe": True,
            "max_attempts": 4, "timeout_seconds": 60, "attempt_ordinal_reset_on_retry": False,
            **{k: True for k in ("exception_provenance_schema_implemented", "http_provenance_schema_implemented", "body_read_provenance_schema_implemented",
                "retry_decision_provenance_schema_implemented", "secret_redaction_implemented")}, **authority["counts"], **scope}}
    for name, key in (("synthetic_complete_body_fixture_manifest", "complete"), ("synthetic_interrupted_body_fixture_manifest", "interrupted"),
                      ("content_length_mismatch_fixture_manifest", "length_mismatch"), ("complete_invalid_payload_fixture_manifest", "invalid_complete")):
        docs[name] = fixtures[key]
    require(docs["transport_lifecycle_v2_transition_audit"]["master_edges_equal"], "MASTER_LIFECYCLE_AUTHORITY_CONFLICT")
    require(set(REQUIRED) <= set(docs) | set(SCHEMAS), "MISSING_22A_REQUIRED_ARTIFACT")
    return docs


def run(verification):
    require(not OUT.exists(), "ALPHA322A_OUTPUT_EXISTS_NO_OVERWRITE")
    require(verification["checks"] and all(c["check_passed"] is True for c in verification["checks"])
            and verification["implementation_sha256"] == digest(Path(__file__)) and verification["test_implementation_sha256"] == digest(TEST)
            and verification["component_sha256"] == {str(p.relative_to(ROOT)): digest(p) for p in COMPONENTS}, "VERIFICATION_REPORT_MISMATCH")
    with master.prior.offline_guard():
        before = verify_authority()
        boundaries = static_boundaries()
        require(not boundaries["concrete_exception_mapping_implemented"], "PHASE_BOUNDARY_FAILURE")
        # A new isolated output is the only material write target.
        store = t.RawArtifactStoreV1(OUT)
        fixtures = synthetic_fixtures(OUT / "synthetic_fixtures")
        checks = crosscutting_checks()
        after = verify_authority()
        require(before == after, "HISTORICAL_OR_SCIENTIFIC_AUTHORITY_DRIFT")
        docs = build_documents(before, fixtures, checks, verification)
        for name, stem in SCHEMAS.items():
            store.freeze_bytes(name + ".json", (master.OUT / (stem + ".json")).read_bytes())
        schemas = [ref(OUT / (name + ".json"), "byte_identical_master_provenance_schema") for name in SCHEMAS]
        docs["transport_observability_v1_bundle"] = {"schema_version": "TransportObservabilityV1ImplementationBundle",
            "master_root_sha256": t.MASTER_ROOT_SHA256, "source": ref(COMPONENTS[1], "unwired_observability_only"), "schemas": schemas,
            "envelope_schema_sha256": master.sha(canonical(docs["transport_attempt_observation_schema"])), "runtime_activation_allowed": False}
        for marker, stem in MARKERS.items():
            value = master.sha(canonical(docs[stem]))
            docs["summary"][marker] = value
            store.freeze_bytes(marker, (value + "\n").encode())
        for name, value in docs.items():
            store.freeze_bytes(name + ".json", canonical(value))
        for name in REQUIRED:
            require((OUT / (name + ".json")).is_file(), "MISSING_REQUIRED_FILE:" + name)
        for value in docs.values():
            master.d2.d1.d.checked_tree(value)
        require(verify_authority() == before, "POST_FREEZE_HISTORICAL_DRIFT")
        root = master.root_hash(OUT, ROOT_MARKER)
        store.freeze_bytes(ROOT_MARKER, (root + "\n").encode())
        require(master.root_hash(OUT, ROOT_MARKER) == root, "22A_ROOT_VERIFICATION_FAILURE")
        return {**docs["summary"], ROOT_MARKER: root}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--verification", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(obj(args.verification)), sort_keys=True))
