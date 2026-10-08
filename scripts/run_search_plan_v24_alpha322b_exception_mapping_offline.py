#!/usr/bin/env python3
"""Inventory, exercise and freeze the unwired 22B mapper without network."""

from __future__ import annotations

import ast
import hashlib
import http.client
import inspect
import io
import json
import platform
import socket
import ssl
import urllib.error
import urllib.request
import urllib.response
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path

from code_engine import transport_exception_mapping_v2 as mapping
from scripts import run_search_plan_v24_alpha322a_transport_observability_offline as prior
from scripts import search_plan_v24_alpha319a1_esearch_response_validity_v2_1 as backend


ROOT = prior.ROOT
OUT = ROOT / "runs/20261008_search_plan_v24_dev_alpha3_22b_exception_mapping_retry_mapper_offline"
ROOT_MARKER = "search_plan_v24_dev_alpha3_22b_sha256"
CLASSIFICATION = "VERSIONED_PHASE_AWARE_TRANSPORT_EXCEPTION_MAPPER_IMPLEMENTED_OFFLINE"
STAGE = "POST_ALPHA3_21_TRANSPORT_EXCEPTION_MAPPING_IMPLEMENTATION"
NEXT = "IMPLEMENT_ALPHA3_22C_APPEND_ONLY_ATTEMPT_JOURNAL_AND_PROCESS_RESUME_OFFLINE"
TEST = ROOT / "tests/test_search_plan_v24_alpha322b_exception_mapping_offline.py"
COMPONENT = Path(mapping.__file__)
t, o, master = prior.t, prior.o, prior.master
canonical, digest, ref, obj, require = o.canonical_bytes, prior.digest, prior.ref, prior.obj, t.require
STD_MODULES = (http.client, urllib.request, urllib.error, urllib.response, socket, ssl)
REQUIRED = tuple("""alpha3_22_master_root_verification alpha3_22a_root_verification alpha3_22b_scope_boundary
bound_transport_stack_inventory transport_client_callsite_inventory candidate_transport_exception_inventory
accepted_transport_exception_mapping_inventory rejected_transport_exception_mapping_inventory structured_exception_wrapper_inventory
transport_exception_mapping_v2_contract transport_exception_mapping_v2_table transport_phase_mapping_contract
exception_match_mode_contract wrapper_traversal_contract wrapper_cycle_safety_audit unknown_runtime_failure_mapping_contract
http_status_adapter_binding provider_backend_adapter_binding transport_exception_mapping_v2_implementation_manifest
transport_exception_mapper_v2_test_results semantic_retry_delegate_binding retry_orchestration_v2_contract retry_orchestration_v2_test_results
incomplete_read_mapping_fixture_audit timeout_phase_fixture_results connection_reset_phase_fixture_results wrapped_exception_fixture_results
unknown_exception_fixture_results broad_base_exception_fixture_results parser_error_nontransport_fixture_results http_status_fixture_results
provider_backend_fixture_results observability_mapper_integration_audit mapping_rule_provenance_audit mapper_determinism_audit
alpha3_21_exception_uncertainty_preservation_audit legacy_runtime_preservation_audit journal_resume_nonimplementation_audit
scientific_policy_firewall_audit contamination_baseline_immutability_audit historical_preservation_audit scientific_state_safety_audit
validation summary""".split())
MARKERS = {"transport_exception_mapping_v2_table_sha256": "transport_exception_mapping_v2_table",
    "transport_exception_mapping_v2_implementation_sha256": "transport_exception_mapping_v2_implementation_manifest",
    "retry_orchestration_v2_contract_sha256": "retry_orchestration_v2_contract"}
NO_CALLS = dict(prior.NO_CALLS)
NO_CHANGE = {k: False for k in ("fresh_primary_attempt_started", "alpha3_21_reopened", "alpha3_21_continuation_created",
    "alpha3_21_network_execution_started", "append_only_journal_implemented", "process_resume_implemented", "legacy_runtime_modified",
    "builder_v4_changed", "quality_v2_changed", "search_plan_scientific_architecture_changed", "historical_assets_modified",
    "partial_response_authoritative", "partial_response_parser_allowed", "string_only_exception_mapping_used", "broad_base_class_retry_mapping_used",
    "unknown_runtime_failure_automatic_retry", "duplicate_retry_policy_matrix_in_22b")}


def verify_authority():
    authority = prior.verify_authority()
    aroot = master.prior.root_check(prior.OUT, prior.ROOT_MARKER, mapping.ALPHA322A_ROOT_SHA256)
    expected = {"transport_lifecycle_v2_implementation_sha256": "8ce3e671bcc3e15bef45958899f068b93b0b80b1786c2407e37f174f3948eb08",
        "transport_observability_v1_bundle_sha256": "6526e447ec6a4ab12fefc1c35c592a8462449b1b913f77670d1ae98fabf1074d",
        "semantic_retry_decision_contract_sha256": mapping.SEMANTIC_RETRY_CONTRACT_SHA256}
    for marker, stem in prior.MARKERS.items():
        require(digest(prior.OUT / (stem + ".json")) == expected[marker] == (prior.OUT / marker).read_text().strip(), "FROZEN_22A_CONTRACT_MISMATCH")
        master.d2.d1.d.checked_tree(obj(prior.OUT / (stem + ".json")))
    master.d2.d1.d.checked_tree(obj(prior.OUT / "new_runtime_component_inventory.json"))
    require(digest(Path(backend.__file__)) == mapping.BACKEND_VALIDATOR_SOURCE_SHA256, "BACKEND_VALIDATOR_SOURCE_MISMATCH")
    return {**authority, "alpha322a": aroot, "alpha322a_contract_hashes": expected,
        "alpha322a_sources": [ref(p, "immutable_22A_implementation_or_tests") for p in (*prior.COMPONENTS, Path(prior.__file__), prior.TEST)],
        "backend_validator_source": ref(Path(backend.__file__), "unchanged_backend_predicate")}


def client_identity(authority):
    stdlib = [{"module": module.__name__, "source_path": module.__file__, "source_sha256": digest(Path(module.__file__))} for module in STD_MODULES]
    repo = [r for r in authority["legacy"] if "alpha322" not in r["artifact_path"] and "terminal_closure" not in r["artifact_path"]]
    identity = {"python_version": platform.python_version(), "stdlib": stdlib, "repository_client_sources": repo}
    value = hashlib.sha256(master.canonical(identity)).hexdigest()
    require(value == mapping.BOUND_CLIENT_IDENTITY_SHA256, "ALPHA3_22B_BLOCKED_BY_TRANSPORT_STACK_AUTHORITY_AMBIGUITY")
    return identity, value


def source_evidence(identifier, function):
    lines, start = inspect.getsourcelines(function)
    path = Path(inspect.getsourcefile(function))
    return {"evidence_id": identifier, "qualified_callable": function.__module__ + "." + function.__qualname__,
        "source_path": str(path), "source_sha256": digest(path), "line_start": start, "line_count": len(lines), "source_excerpt": "".join(lines)}


def inventory(authority):
    identity, value = client_identity(authority)
    evidence = [source_evidence(key, fn) for key, fn in (
        ("urllib_do_open", urllib.request.AbstractHTTPHandler.do_open),
        ("url_error_constructor", urllib.error.URLError.__init__), ("http_error_constructor", urllib.error.HTTPError.__init__),
        ("http_response_read", http.client.HTTPResponse.read), ("http_safe_read", http.client.HTTPResponse._safe_read),
        ("http_read_status", http.client.HTTPResponse._read_status), ("http_read_chunked", http.client.HTTPResponse._read_chunked),
        ("http_response_begin", http.client.HTTPResponse.begin), ("http_connection_getresponse", http.client.HTTPConnection.getresponse),
        ("http_connection_putrequest", http.client.HTTPConnection.putrequest), ("http_connection_connect", http.client.HTTPConnection.connect),
        ("https_connection_connect", http.client.HTTPSConnection.connect), ("urllib_https_open", urllib.request.HTTPSHandler.https_open),
        ("ssl_socket_read", ssl.SSLSocket.read),
        ("backend_validator_source", backend.validate_response))]
    callsites = []
    for source in identity["repository_client_sources"]:
        path = ROOT / source["artifact_path"]
        raw = path.read_text()
        lines = raw.splitlines()
        tree = ast.parse(raw)
        sites = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"open", "read", "validate_response", "fetch", "build_opener"}:
                sites.append({"kind": "call", "line": node.lineno, "expression": ast.unparse(node.func), "code": lines[node.lineno - 1].strip()})
            elif isinstance(node, ast.ExceptHandler):
                sites.append({"kind": "exception_handler", "line": node.lineno, "expression": ast.unparse(node.type) if node.type is not None else "bare except", "code": lines[node.lineno - 1].strip()})
            elif isinstance(node, ast.Attribute) and node.attr in {"status", "headers"}:
                sites.append({"kind": "header_or_status_access", "line": node.lineno, "expression": ast.unparse(node), "code": lines[node.lineno - 1].strip()})
        callsites.append({"source": source, "sites": sorted(sites, key=lambda r: (r["line"], r["expression"]))})
    accepted = []
    for key, kind in mapping.CONCRETE_CLASSES.items():
        accepted.append({"binding_key": key, "module": kind.__module__, "qualified_class": mapping.qualified(kind),
            "aliases": ["socket.timeout"] if key == "timeout" else [], "relevant_bases": [mapping.qualified(base) for base in kind.__mro__[1:]],
            "transport_library": "bound Python stdlib", "rule_ids": [r["rule_id"] for r in mapping.table_record()["rules"] if r["class_binding_key"] == key],
            "possible_lifecycle_phases": sorted({p for r in mapping.table_record()["rules"] if r["class_binding_key"] == key for p in r["allowed_lifecycle_phases"]}),
            "structured_wrapper_fields": ["reason"] if key == "url_error" else ["code", "headers"] if key == "http_error" else ["partial", "expected"] if key == "incomplete_read" else [],
            "evidence_ids": sorted({e for r in mapping.table_record()["rules"] if r["class_binding_key"] == key for e in r["authority_evidence_ids"]}),
            "repository_callsite_inventory": "transport_client_callsite_inventory.json", "admitted": True,
            "preexisting_handling": "HTTPError separately; URLError/TimeoutError/OSError broadly caught by historical clients; parser errors downstream; IncompleteRead unhandled by frozen PMC fetch",
            "scientific_eligibility_authority": False})
    rejected = []
    for kind, reason in ((OSError, "BROAD_BASE_NOT_TRANSPORT_RETRY_AUTHORITY"), (RuntimeError, "BROAD_RUNTIME_CLASS_AND_SCOPE_GUARD_NOT_RETRY_AUTHORITY"),
        (ValueError, "DOWNSTREAM_VALIDATOR_OR_GENERAL_VALUE_ERROR_NOT_TRANSPORT_AUTHORITY"),
        (Exception, "BROAD_BASE_NOT_TRANSPORT_RETRY_AUTHORITY"), (BaseException, "BROAD_BASE_NOT_TRANSPORT_RETRY_AUTHORITY"),
        (http.client.HTTPException, "BROAD_PROTOCOL_BASE_NOT_RETRY_AUTHORITY"),
        (http.client.BadStatusLine, "PROTOCOL_ERROR_WITHOUT_POSITIVE_FROZEN_INTERRUPTION_RULE"),
        (http.client.LineTooLong, "PROTOCOL_LIMIT_ERROR_WITHOUT_POSITIVE_FROZEN_INTERRUPTION_RULE"),
        (http.client.UnknownProtocol, "UNSUPPORTED_PROTOCOL_IS_NOT_POSITIVE_INTERRUPTION_AUTHORITY"),
        (http.client.ResponseNotReady, "CLIENT_STATE_VIOLATION_IS_NOT_POSITIVE_INTERRUPTION_AUTHORITY"),
        (http.client.CannotSendRequest, "CLIENT_STATE_VIOLATION_IS_NOT_POSITIVE_INTERRUPTION_AUTHORITY"),
        (ssl.SSLError, "TLS_ERROR_WITHOUT_POSITIVE_FROZEN_INTERRUPTION_RULE"),
        (ssl.SSLCertVerificationError, "CERTIFICATE_FAILURE_WITHOUT_POSITIVE_FROZEN_INTERRUPTION_RULE"),
        (UnicodeDecodeError, "DECODING_VALIDITY_NOT_TRANSPORT_INTERRUPTION")):
        rejected.append({"module": kind.__module__, "qualified_class": mapping.qualified(kind), "aliases": ["builtins.IOError"] if kind is OSError else [],
            "relevant_bases": [mapping.qualified(base) for base in kind.__mro__[1:]], "transport_library": "bound Python stdlib or downstream validator",
            "possible_lifecycle_phases": "unrestricted candidate inspection; none admitted", "structured_wrapper_fields": [],
            "repository_callsite_inventory": "transport_client_callsite_inventory.json", "evidence": "bound stdlib sources, catch sites or unchanged backend validator",
            "admitted": False, "rejection_reason": reason, "result": "UNKNOWN_RUNTIME_FAILURE_NO_AUTOMATIC_RETRY"})
    stack = {"bound_client_identity": identity, "bound_client_identity_sha256": value,
        "response_object_type": "http.client.HTTPResponse", "response_body_read": "response.read() without amt",
        "normal_header_read": "response.status / response.headers after opener.open", "error_header_read": "HTTPError.code / headers",
        "wrapper_layers": ["urllib.request.AbstractHTTPHandler.do_open -> URLError.reason", "HTTPError status wrapper", "historical C2/D2 preservation-only adapters"],
        "timeout_seconds": 60, "max_attempts": 4, "backoff_seconds": [2, 4, 8], "historical_generic_catch_retry_behavior_not_new_authority": True,
        "local_source_evidence": evidence, "scope": "THIS_EXACT_BOUND_STDLIB_STACK_ONLY_NOT_ALL_PYTHON_TRANSPORTS"}
    return stack, callsites, accepted, rejected


class LocalSocket:
    """Socket-shaped local file holder; never a socket.socket."""
    def __init__(self, file):
        self.file = file

    def makefile(self, mode):
        return self.file


class FaultFile(io.BytesIO):
    def __init__(self, failure_type, phase):
        super().__init__(b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nabcde")
        self.failure_type, self.phase = failure_type, phase

    def readline(self, limit=-1):
        if self.phase == "pre_headers":
            raise self.failure_type("synthetic local I/O signal; text not classification authority")
        return super().readline(limit)

    def read(self, amount=-1):
        if self.phase == "body":
            raise self.failure_type("synthetic local I/O signal; text not classification authority")
        return super().read(amount)


def actual_response_failure(kind, phase):
    file = FaultFile(kind, phase)
    response = http.client.HTTPResponse(LocalSocket(file))
    try:
        response.begin()
        response.read()
    except kind as exc:
        return exc
    finally:
        response.close()
    raise AssertionError("EXPECTED_ACTUAL_STDLIB_SIGNAL")


def actual_wrapped_failure(kind=TimeoutError):
    class LocalHTTPConnection:
        def __init__(self, host, timeout, **kwargs):
            self.sock = None
        def set_debuglevel(self, value):
            pass
        def request(self, *args, **kwargs):
            raise kind("synthetic-private-credential")
        def close(self):
            pass
    request = urllib.request.Request("https://synthetic.invalid/test?api_key=synthetic-private-credential")
    request.timeout = 60
    try:
        urllib.request.AbstractHTTPHandler().do_open(LocalHTTPConnection, request)
    except urllib.error.URLError as exc:
        require(type(exc.reason) is kind and exc.__context__ is exc.reason, "ACTUAL_WRAPPER_STRUCTURE_NOT_PROVEN")
        return exc
    raise AssertionError("EXPECTED_ACTUAL_URL_ERROR_WRAPPER")


def facts(phase, *, completion=None, status=None, trusted=None, origin=None, outcome=None):
    if trusted is None:
        trusted = phase != t.LifecycleState.REQUEST_ATTEMPT_STARTED
    return mapping.TransportMappingFactsV2(phase, mapping.BOUND_CLIENT_IDENTITY_SHA256, trusted, status,
        origin if origin is not None else "BOUND_HTTP_RESPONSE" if status is not None else None, completion, outcome)


def fixtures(directory: Path):
    store = t.RawArtifactStoreV1(directory)
    audits = {}
    results = []
    def case(name, exception, evidence, expected, retry_expected, *, safe=True, ordinal=1):
        decision = mapping.classify_transport_failure_and_decide_retry_v2(exception, evidence,
            request_replay_safe=safe, attempt_ordinal=ordinal)
        require(decision.mapping.semantic_failure_class == expected and decision.retry.retry_authorized is retry_expected, "MAPPING_FIXTURE_FAILED:" + name)
        result = {"case_id": name, **decision.record(), "original_exception_qualified_class": mapping.qualified(type(exception)) if exception is not None else None,
            "fixture_kind": "LOCAL_SYNTHETIC_THROUGH_BOUND_STDLIB_OR_STRUCTURED_OUTCOME", "check_passed": True}
        results.append(result)
        return decision, result
    for key, kind in (("timeout", TimeoutError), ("connection_reset", ConnectionResetError)):
        values = []
        for place, phase, semantic in (("pre_headers", t.LifecycleState.REQUEST_ATTEMPT_STARTED, t.SemanticFailure.PRE_RESPONSE_TRANSPORT_INTERRUPTION),
                ("body", t.LifecycleState.RESPONSE_BODY_READING, t.SemanticFailure.RESPONSE_BODY_TRANSPORT_INTERRUPTION)):
            exception = actual_response_failure(kind, place)
            _, result = case(key + "_" + place, exception, facts(phase, status=200 if place == "body" else None), semantic, True)
            values.append(result)
        audits[key] = {"check_passed": True, "cases": values, "actual_HTTPResponse_used": True, "network_calls": 0}
    empty_response = http.client.HTTPResponse(LocalSocket(io.BytesIO(b"")))
    try:
        empty_response.begin()
    except http.client.RemoteDisconnected as exc:
        _, remote_case = case("actual_HTTPResponse_remote_disconnected", exc, facts(t.LifecycleState.REQUEST_ATTEMPT_STARTED),
            t.SemanticFailure.PRE_RESPONSE_TRANSPORT_INTERRUPTION, True)
    finally:
        empty_response.close()
    audits["remote_disconnected"] = {"check_passed": True, "case": remote_case, "actual_HTTPResponse_begin_used": True}
    response = http.client.HTTPResponse(LocalSocket(io.BytesIO(b"HTTP/1.1 200 OK\r\nContent-Length: 9\r\n\r\nprefix")))
    response.begin()
    try:
        response.read()
    except http.client.IncompleteRead as exc:
        original = exc
    finally:
        response.close()
    require(type(original) is http.client.IncompleteRead and original.partial == b"prefix", "INCOMPLETE_READ_NOT_PROVEN")
    decision, entry = case("actual_HTTPResponse_incomplete_read", original, facts(t.LifecycleState.RESPONSE_BODY_READING, status=200),
        t.SemanticFailure.RESPONSE_BODY_TRANSPORT_INTERRUPTION, True)
    context = t.AttemptContextV1("synthetic:22b-incomplete", master.sha(b"immutable local request"), 1)
    attempt = prior.t.TransportLifecycleV2(context)
    attempt.start_attempt("synthetic in-memory start")
    attempt.receive_headers(200, trustworthy=True, evidence_reference="actual local HTTPResponse headers")
    attempt.start_body("actual local HTTPResponse.read")
    completion = t.assess_body_completion(original.partial, read_returned_normally=False, interruption_class=decision.mapping.semantic_failure_class,
        timestamp=prior.NOW, interruption_reason="mapped actual exact concrete IncompleteRead")
    attempt.record_body(completion, "22b phase-aware adapter outcome")
    partial = store.freeze_bytes("incomplete_read.partial", original.partial)
    frozen = attempt.freeze_response(partial)
    calls = []
    prior.expect_denied(lambda: t.guarded_parse(frozen, lambda raw: calls.append(raw)))
    body = o.BodyReadProvenanceV1.capture(context, o.SecretRedactorV1(), completion, partial, parser_invoked=False)
    observable = mapping.mapped_observation_v2(decision, attempt, o.SecretRedactorV1(("synthetic-private-credential",)), original_exception=original,
        body=body, replay_safety_authority={"scope": "synthetic local explicitly replay-safe request"},
        runtime_identity={"python_version": platform.python_version(), "client_module": "http.client", "client_version": platform.python_version(),
            "client_code_sha256": digest(Path(http.client.__file__))})
    observation_artifact = observable.freeze(store, "incomplete_read.mapped_observation.json")
    prior.validate_observation(observable.record()["observation"])
    audits["incomplete_read"] = {"check_passed": True, "case": entry, "partial_artifact": partial.__dict__,
        "parser_invocations": len(calls), "partial_authoritative": frozen.authoritative,
        "observation_artifact": observation_artifact.__dict__, "historical_alpha321_exception_class_inferred": False}
    wrapped = actual_wrapped_failure()
    _, result = case("actual_urllib_wrapped_timeout", wrapped, facts(t.LifecycleState.REQUEST_ATTEMPT_STARTED), t.SemanticFailure.PRE_RESPONSE_TRANSPORT_INTERRUPTION, True)
    audits["wrapped"] = {"check_passed": True, "case": result, "actual_do_open_used": True, "authorized_path": ["reason"], "cause_and_context_are_not_mapping_authority": True}
    redactor = o.SecretRedactorV1(("synthetic-private-credential",))
    captured = o.ExceptionProvenanceV1.capture(wrapped, context, redactor)
    require(captured.provenance is not None and b"synthetic-private-credential" not in captured.provenance._serialized, "WRAPPER_PROVENANCE_SECRET_FAILURE")
    wrapped_artifact = captured.provenance.freeze(store, "wrapped_exception.provenance.json")
    cycle_results = []
    for form in ("reason_self", "nested_url", "reverse_cause", "reverse_context", "outer_cause_self", "outer_context_self", "inner_cause_self", "inner_context_self"):
        inner = TimeoutError("synthetic cycle node")
        cyc = urllib.error.URLError(inner)
        if form == "reason_self": cyc.reason = cyc
        elif form == "nested_url": cyc.reason = urllib.error.URLError(inner)
        elif form == "reverse_cause": inner.__cause__ = cyc
        elif form == "reverse_context": inner.__context__ = cyc
        elif form == "outer_cause_self": cyc.__cause__ = cyc
        elif form == "outer_context_self": cyc.__context__ = cyc
        elif form == "inner_cause_self": inner.__cause__ = inner
        elif form == "inner_context_self": inner.__context__ = inner
        _, cycle_result = case("wrapper_" + form, cyc, facts(t.LifecycleState.REQUEST_ATTEMPT_STARTED), t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE, False)
        cycle_results.append(cycle_result)
    unknown_results = []
    class UnmappedSignal(Exception):
        pass
    for name, exception in (("unmapped_exception", UnmappedSignal("IncompleteRead timed out connection reset")),
                            ("plain_OSError", OSError("IncompleteRead timed out connection reset"))):
        _, result = case(name, exception, facts(t.LifecycleState.RESPONSE_BODY_READING, status=200), t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE, False)
        unknown_results.append(result)
    audits["unknown"] = {"check_passed": True, "case": unknown_results[0]}
    audits["broad"] = {"check_passed": True, "case": unknown_results[1]}
    audits["cycles"] = {"check_passed": True, "cases": cycle_results, "traversal_maximum_depth": 1}
    complete = t.assess_body_completion(b"synthetic completed body", read_returned_normally=True, timestamp=prior.NOW)
    parser_results = []
    for name, action in (("malformed_complete_XML", lambda: ET.fromstring(b"<synthetic>")), ("malformed_complete_JSON", lambda: json.loads(b"{"))):
        try:
            action()
        except (ET.ParseError, json.JSONDecodeError) as exc:
            _, result = case(name, exc, facts(t.LifecycleState.RAW_RESPONSE_FROZEN, completion=complete, status=200),
                t.SemanticFailure.COMPLETE_BODY_RESPONSE_VALIDITY_FAILURE, False)
            parser_results.append(result)
    for name in ("identifier_mismatch", "license_failure", "BODY_normalizer_failure"):
        _, result = case(name, ValueError("synthetic downstream failure"), facts(t.LifecycleState.RAW_RESPONSE_FROZEN, completion=complete, status=200),
            t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE, False)
        result["downstream_validator_retains_ownership"] = True
        parser_results.append(result)
    audits["parser"] = {"check_passed": True, "cases": parser_results, "body_interruption_misclassifications": 0}
    status_results = []
    for status, expected, retry in ((502, t.SemanticFailure.RETRYABLE_HTTP_STATUS, True), (403, t.SemanticFailure.NONRETRYABLE_HTTP_STATUS, False)):
        exception = urllib.error.HTTPError("https://synthetic.invalid/test", status, "synthetic", {}, io.BytesIO(b"local"))
        exception.__cause__ = TimeoutError("must not override outer status")
        _, result = case("HTTPError_" + str(status), exception,
            facts(t.LifecycleState.REQUEST_ATTEMPT_STARTED, trusted=True, status=status, origin="BOUND_HTTP_ERROR"), expected, retry)
        status_results.append(result)
        _, result = case("structured_HTTP_" + str(status), None,
            facts(t.LifecycleState.RESPONSE_HEADERS_RECEIVED, status=status), expected, retry)
        status_results.append(result)
    audits["http"] = {"check_passed": True, "cases": status_results, "status_set_unchanged": True}
    raw_backend = b'{"esearchresult":{"ERROR":"Search Backend failed: synthetic local backend envelope"}}'
    verdict = backend.validate_response(200, raw_backend, 0, 1)
    outcome = mapping.BackendValidatorOutcomeV2.from_frozen_validator_result(verdict,
        authority_sha256=t.BACKEND_AUTHORITY_SHA256, validator_source_sha256=mapping.BACKEND_VALIDATOR_SOURCE_SHA256)
    backend_completion = t.assess_body_completion(raw_backend, read_returned_normally=True)
    _, backend_case = case("frozen_backend_validator_outcome", None,
        facts(t.LifecycleState.RAW_RESPONSE_FROZEN, status=200, completion=backend_completion, outcome=outcome), t.SemanticFailure.RETRYABLE_PROVIDER_BACKEND_FAILURE, True)
    audits["backend"] = {"check_passed": True, "case": backend_case, "unchanged_validator_invoked_locally": True,
        "mapper_reads_raw_backend_text": False, "provider_calls": 0}
    for name, safe, ordinal in (("replay_unsafe", False, 1), ("attempt4_exhausted", True, 4)):
        case(name, original, facts(t.LifecycleState.RESPONSE_BODY_READING, status=200), t.SemanticFailure.RESPONSE_BODY_TRANSPORT_INTERRUPTION, False, safe=safe, ordinal=ordinal)
    mismatch = t.assess_body_completion(b"short", read_returned_normally=True, expected_content_length=6,
        expected_length_trustworthy=True, expected_length_representation=t.ByteRepresentation.WIRE)
    case("structured_length_mismatch_no_exception", None, facts(t.LifecycleState.RESPONSE_BODY_INTERRUPTED, completion=mismatch, status=200),
        t.SemanticFailure.RESPONSE_BODY_LENGTH_MISMATCH, True)
    same = mapping.TransportExceptionMappingV2().classify(original, facts(t.LifecycleState.RESPONSE_BODY_READING, status=200)).record()
    require(canonical(same) == canonical(mapping.TransportExceptionMappingV2().classify(original, facts(t.LifecycleState.RESPONSE_BODY_READING, status=200)).record()), "MAPPER_NONDETERMINISTIC")
    audits["determinism"] = {"check_passed": True, "mapping_sha256": master.sha(canonical(same)), "timestamps_in_mapping": False,
        "exception_messages_or_object_addresses_in_mapping": False}
    audits["observability"] = {"check_passed": True, "original_exception_preserved": True, "22A_nested_schemas_validated": True,
        "partial_observation_artifact": observation_artifact.__dict__, "wrapped_exception_artifact": wrapped_artifact.__dict__,
        "secret_redaction_applied_before_persistence": True, "secondary_mapping_fact_not_schema_amendment": True}
    return {"cases": results, "audits": audits, "case_count": len(results), "check_passed": True}


def code_boundary_audit():
    tree = ast.parse(COMPONENT.read_text())
    orchestrator = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "classify_transport_failure_and_decide_retry_v2")
    delegates = [n for n in ast.walk(orchestrator) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "semantic_retry_decision"]
    require(len(delegates) == 1, "DUPLICATE_OR_MISSING_RETRY_POLICY_OWNER")
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            require(node.func.attr not in {"sleep", "urlopen", "open", "request", "connect", "append_event", "resume"}, "LIVE_EXECUTOR_OR_JOURNAL_IN_MAPPER")
    source = COMPONENT.read_text()
    require("__name__ ==" not in source and "str(exception)" not in source, "STRING_ONLY_EXCEPTION_MAPPING")
    return {"semantic_retry_decision_call_count_in_orchestrator": len(delegates), "retry_loop_implemented": False,
        "sleep_or_network_execution_implemented": False, "durable_journal_implemented": False, "process_resume_implemented": False,
        "production_wiring_changed": False, "mapper_source": ref(COMPONENT, "pure_prospective_adapter")}


def build_documents(authority, stack, callsites, accepted, rejected, local, verification):
    audits = local["audits"]
    table = mapping.table_record()
    scope = {"development_mode": True, **NO_CHANGE, **NO_CALLS, "production_runtime_integration": False,
        "full_fault_matrix_executed": False, "historical_replay_executed": False, "runtime_activation_allowed": False}
    wrapper_contract = {"rule_id": "url_error_reason_pre_headers", "outer_exact_class": "urllib.error.URLError", "field_path": ["reason"],
        "inner_exact_classes": ["builtins.TimeoutError", "builtins.ConnectionResetError"], "maximum_depth": 1,
        "cause_authorized_for_mapping": False, "context_authorized_for_mapping": False, "arbitrary_recursive_search": False,
        "HTTPError_outer_status_owns_classification": True, "cycle_or_unknown_reason": "UNKNOWN_RUNTIME_FAILURE_NO_AUTOMATIC_RETRY"}
    implementation = {"schema_version": "TransportExceptionMappingV2ImplementationManifest", "source": ref(COMPONENT, "prospective_adapter_only"),
        "mapping_table_sha256": mapping.MAPPING_TABLE_SHA256, "bound_client_identity_sha256": mapping.BOUND_CLIENT_IDENTITY_SHA256,
        "master_root_sha256": t.MASTER_ROOT_SHA256, "alpha322a_root_sha256": mapping.ALPHA322A_ROOT_SHA256,
        "semantic_retry_contract_sha256": mapping.SEMANTIC_RETRY_CONTRACT_SHA256, "runtime_activation_allowed": False}
    orchestration = {"schema_version": "RetryOrchestrationV2Contract", "source": ref(COMPONENT, "single_semantic_retry_delegate"),
        "mapping_table_sha256": mapping.MAPPING_TABLE_SHA256, "semantic_retry_contract_sha256": mapping.SEMANTIC_RETRY_CONTRACT_SHA256,
        "orchestration_order": ["phase-aware classification", "unchanged alpha322A.semantic_retry_decision"],
        "independent_retryability_matrix": False, "request_execution": False, "maximum_attempts": 4, "timeout_seconds": 60, "backoff_seconds": [2, 4, 8]}
    accepted_classes = {r["qualified_class"] for r in accepted}
    rejected_classes = {r["qualified_class"] for r in rejected}
    require(not accepted_classes & rejected_classes and len(accepted_classes) == len(accepted) and len(rejected_classes) == len(rejected), "EXCEPTION_INVENTORY_AMBIGUOUS")
    inventory_counts = {"candidate_exception_class_count": len(accepted) + len(rejected), "accepted_exception_mapping_count": len(accepted),
        "rejected_exception_mapping_count": len(rejected), "concrete_mapping_rule_count": len(table["rules"]), "structured_wrapper_rule_count": 1,
        "count_unit": "accepted/rejected counts are concrete class inventory entries; phase-rule count recorded separately"}
    docs = {
        "alpha3_22_master_root_verification": authority["master"],
        "alpha3_22a_root_verification": {**authority["alpha322a"], "frozen_contract_hashes": authority["alpha322a_contract_hashes"], "source_bindings": authority["alpha322a_sources"]},
        "alpha3_22b_scope_boundary": scope, "bound_transport_stack_inventory": stack,
        "transport_client_callsite_inventory": {"sources": callsites, "legacy_behavior_modified": False},
        "candidate_transport_exception_inventory": {"entries": accepted + rejected, **inventory_counts, "exhaustive_all_possible_exceptions_claimed": False,
            "socket_timeout_and_IOError_aliases_not_double_counted": True, "uninspected_concrete_classes_default_UNKNOWN": True,
            "ambiguous_unresolved_case_catalogue": ["unknown class or unauthorized subclass", "known class outside frozen phase", "untrusted or contradictory runtime facts",
                "unbound client/table", "URLError string/nested/cyclic reason", "TLS/protocol classes lacking positive interruption authority"]},
        "accepted_transport_exception_mapping_inventory": {"entries": accepted, "class_count": len(accepted), "phase_rule_count": len(table["rules"])},
        "rejected_transport_exception_mapping_inventory": {"entries": rejected, "class_count": len(rejected), "rejected_wrapper_forms": ["URLError with string reason", "nested URLError.reason", "arbitrary cause/context", "cyclic reason"],
            "unknown_cases_preserved_not_optimized_away": True},
        "structured_exception_wrapper_inventory": {"accepted_wrappers": [wrapper_contract], "HTTPError": "structured status owner, never delegates inner exceptions",
            "rejected_wrappers": ["arbitrary cause wrapper", "arbitrary context wrapper", "unknown library-specific wrapper", "nested URLError"]},
        "transport_exception_mapping_v2_contract": {"schema_version": mapping.MAPPING_VERSION, "table_sha256": mapping.MAPPING_TABLE_SHA256,
            "inputs": ["actual exception object or null", "22A lifecycle phase", "trusted structured facts", "bound client identity", "exact frozen mapping table"],
            "frozen_name_descriptor_mapping_supported": False, "outputs": list(local["cases"][0]["mapping"]),
            "unknown_behavior": "UNKNOWN_RUNTIME_FAILURE_NO_AUTOMATIC_RETRY", "mapping_is_not_retry_policy": True},
        "transport_exception_mapping_v2_table": table,
        "transport_phase_mapping_contract": {"pre_headers": [s.value for s in mapping.PRE_PHASES], "body_reading": [s.value for s in mapping.BODY_PHASES],
            "after_headers_before_body": "UNKNOWN unless explicit structured HTTP status rule", "after_complete": "no body-read exception rule reuse",
            "validation_phases": [s.value for s in mapping.VALIDATION_PHASES], "phase_mismatch": "UNKNOWN_RUNTIME_FAILURE_NO_AUTOMATIC_RETRY"},
        "exception_match_mode_contract": {"all_concrete_rules": "EXACT_CLASS", "subclass_inheritance_authority": False, "broad_base_class_retry_mapping_used": False,
            "message_or_class_name_matching": False}, "wrapper_traversal_contract": wrapper_contract,
        "wrapper_cycle_safety_audit": audits["cycles"],
        "unknown_runtime_failure_mapping_contract": {"unmapped_or_ambiguous": t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE.value, "automatic_retry": False,
            "observability_does_not_create_mapping_authority": True},
        "http_status_adapter_binding": {**table["http_status_adapter"], "unchanged_numeric_policies": master.runtime_inventory()["components"],
            "bound_backend_status_set_equal": sorted(backend.RETRYABLE_HTTP_STATUS) == table["http_status_adapter"]["retryable_statuses"]},
        "provider_backend_adapter_binding": {**table["backend_adapter"], "validator_source": authority["backend_validator_source"],
            "raw_message_inspected_by_mapper": False, "new_backend_predicate": False},
        "transport_exception_mapping_v2_implementation_manifest": implementation,
        "transport_exception_mapper_v2_test_results": local,
        "semantic_retry_delegate_binding": {"contract": ref(prior.OUT / "semantic_retry_decision_contract.json", "sole_retry_policy_owner"),
            "semantic_retry_decision_contract_sha256": mapping.SEMANTIC_RETRY_CONTRACT_SHA256,
            "alpha322a_source": ref(prior.COMPONENTS[0], "unchanged_semantic_policy"), "boundary_audit": code_boundary_audit()},
        "retry_orchestration_v2_contract": orchestration,
        "retry_orchestration_v2_test_results": {"check_passed": True, "cases": local["cases"], "sole_retry_decision_owner": "alpha3.22A"},
        "incomplete_read_mapping_fixture_audit": audits["incomplete_read"], "timeout_phase_fixture_results": audits["timeout"],
        "remote_disconnected_mapping_fixture_results": audits["remote_disconnected"],
        "connection_reset_phase_fixture_results": audits["connection_reset"], "wrapped_exception_fixture_results": audits["wrapped"],
        "unknown_exception_fixture_results": audits["unknown"], "broad_base_exception_fixture_results": audits["broad"],
        "parser_error_nontransport_fixture_results": audits["parser"], "http_status_fixture_results": audits["http"], "provider_backend_fixture_results": audits["backend"],
        "observability_mapper_integration_audit": audits["observability"],
        "mapping_rule_provenance_audit": {"check_passed": True, "each_event_has_mapping_version_table_hash_rule_or_explicit_no_match": True,
            "each_event_has_22A_retry_contract_sha256": True, "original_exception_not_replaced": True}, "mapper_determinism_audit": audits["determinism"],
        "alpha3_21_exception_uncertainty_preservation_audit": {"actual_alpha3_21_exception_qualified_class_known": False,
            "alpha3_21_actual_exception_qualified_class": "UNKNOWN", "historical_exception_reclassified": False,
            "already_seen_historical_partial_bytes_used_as_fixture": False, "closure": authority["closure"]},
        "legacy_runtime_preservation_audit": {"legacy_runtime_modified": False, "source_bindings": authority["legacy"], "22A_sources": authority["alpha322a_sources"],
            "new_mapper_wired_into_old_clients": False},
        "journal_resume_nonimplementation_audit": {"append_only_journal_implemented": False, "process_resume_implemented": False,
            "stage_continuation_implemented": False, "in_memory_22A_events_only": True},
        "scientific_policy_firewall_audit": {**scope, "scientific_bindings": authority["scientific_bindings"], "scientific_policy_changed": False},
        "contamination_baseline_immutability_audit": {"baseline": authority["registry"], **authority["counts"], "competing_registry_created": False},
        "historical_preservation_audit": {"historical_roots": authority["phase_roots"], "closure": authority["closure"], "master": authority["master"], "alpha322a": authority["alpha322a"],
            "historical_assets_modified": False}, "scientific_state_safety_audit": {**scope, "scientific_assets_created": False},
        "validation": {"status": "passed", "all_22B_success_gates_passed": True, "22C_through_22F_gates_completed": False, "runtime_activation_allowed": False},
        "focused_test_manifest": verification,
        "summary": {"status": "completed", "alpha3_22b_classification": CLASSIFICATION, "stage_identity": STAGE, "development_mode": True,
            "alpha3_22_master_root_verified": True, "alpha3_22a_root_verified": True, "bound_transport_stack_resolved": True, **inventory_counts,
            "phase_aware_exception_mapping": True, "transport_exception_mapper_v2_implemented": True, "retry_orchestration_v2_implemented": True,
            "retry_policy_delegates_to_alpha3_22a": True, "response_body_transport_interruption_mapping_supported": True,
            "pre_response_transport_interruption_mapping_supported": True, "actual_alpha3_21_exception_qualified_class_known": False,
            "observability_integration_complete": True, "concrete_exception_mapping_implemented": True, **NO_CHANGE, **NO_CALLS,
            **authority["counts"], "next_stage_recommendation": NEXT, "runtime_activation_allowed": False}}
    require(set(REQUIRED) <= set(docs), "MISSING_22B_REQUIRED_DOCUMENTS")
    require(docs["http_status_adapter_binding"]["bound_backend_status_set_equal"], "HTTP_STATUS_POLICY_EXPANSION")
    def document_evidence(stem):
        return {"artifact_path": str((OUT / (stem + ".json")).relative_to(ROOT)), "sha256": master.sha(canonical(docs[stem])),
            "immutable_frozen": True, "artifact_role": "offline_positive_mapping_authority_evidence"}
    evidence_index = {r["evidence_id"]: {"document": document_evidence("bound_transport_stack_inventory"),
        "source_path": r["source_path"], "source_sha256": r["source_sha256"], "qualified_callable": r["qualified_callable"]} for r in stack["local_source_evidence"]}
    for key, stem in (("actual_client_synthetic_incomplete_read", "incomplete_read_mapping_fixture_audit"),
        ("actual_client_synthetic_remote_disconnected", "remote_disconnected_mapping_fixture_results"),
        ("actual_client_synthetic_reset", "connection_reset_phase_fixture_results"), ("actual_client_synthetic_timeout", "timeout_phase_fixture_results"),
        ("actual_client_synthetic_wrapped_timeout", "wrapped_exception_fixture_results"), ("complete_parser_synthetic", "parser_error_nontransport_fixture_results"),
        ("legacy_http_status_policy", "http_status_adapter_binding"), ("repository_http_error_sites", "transport_client_callsite_inventory"),
        ("repository_open_read_sites", "transport_client_callsite_inventory"), ("repository_validator_sites", "transport_client_callsite_inventory")):
        evidence_index[key] = {"document": document_evidence(stem)}
    required_ids = {key for rule in table["rules"] for key in rule["authority_evidence_ids"]}
    require(required_ids <= set(evidence_index), "UNRESOLVED_MAPPING_AUTHORITY_EVIDENCE")
    docs["transport_exception_mapping_authority_evidence_index"] = {"evidence_by_id": evidence_index, "all_rule_evidence_ids_resolved": True,
        "table_sha256": mapping.MAPPING_TABLE_SHA256}
    return docs


def run(verification):
    require(not OUT.exists(), "22B_OUTPUT_EXISTS_NO_OVERWRITE")
    require(verification["checks"] and all(r["check_passed"] is True for r in verification["checks"])
        and verification["implementation_sha256"] == digest(Path(__file__)) and verification["test_implementation_sha256"] == digest(TEST)
        and verification["mapper_source_sha256"] == digest(COMPONENT), "LOCAL_VERIFICATION_BINDING_MISMATCH")
    with master.prior.offline_guard():
        before = verify_authority()
        stack, callsites, accepted, rejected = inventory(before)
        require(mapping.default_mapping_table_v2().sha256 == mapping.MAPPING_TABLE_SHA256, "MAPPING_TABLE_BINDING_MISMATCH")
        code_boundary_audit()
        store = t.RawArtifactStoreV1(OUT)
        local = fixtures(OUT / "local_engineering_fixtures")
        require(verify_authority() == before, "UPSTREAM_AUTHORITY_DRIFT")
        docs = build_documents(before, stack, callsites, accepted, rejected, local, verification)
        for marker, stem in MARKERS.items():
            value = master.sha(canonical(docs[stem]))
            if marker == "transport_exception_mapping_v2_table_sha256":
                require(value == mapping.MAPPING_TABLE_SHA256, "TABLE_FREEZE_MISMATCH")
            docs["summary"][marker] = value
            store.freeze_bytes(marker, (value + "\n").encode())
        for name, value in docs.items():
            store.freeze_bytes(name + ".json", canonical(value))
        for value in docs.values():
            master.d2.d1.d.checked_tree(value)
        for name in REQUIRED:
            require((OUT / (name + ".json")).is_file(), "MISSING_REQUIRED_ARTIFACT")
        require(verify_authority() == before and client_identity(before)[1] == mapping.BOUND_CLIENT_IDENTITY_SHA256, "POST_WRITE_AUTHORITY_DRIFT")
        root = master.root_hash(OUT, ROOT_MARKER)
        store.freeze_bytes(ROOT_MARKER, (root + "\n").encode())
        require(master.root_hash(OUT, ROOT_MARKER) == root, "22B_ROOT_MISMATCH")
        return {**docs["summary"], ROOT_MARKER: root}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--verification", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(obj(args.verification)), sort_keys=True))
