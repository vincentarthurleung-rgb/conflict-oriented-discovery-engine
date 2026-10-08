"""22B adapter unit/regression fixtures; no full 22D or 22E execution."""

import ast
import http.client
import io
import json
import socket
import urllib.error
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import run_search_plan_v24_alpha322b_exception_mapping_offline as b

m, t, o = b.mapping, b.t, b.o


@pytest.fixture(autouse=True)
def offline():
    with b.master.prior.offline_guard():
        yield


@pytest.fixture
def mapper():
    return m.TransportExceptionMappingV2()


def complete():
    return t.assess_body_completion(b"synthetic complete bytes", read_returned_normally=True)


def test_frozen_upstream_roots_contracts_and_actual_stack():
    authority = b.verify_authority()
    stack, callsites, accepted, rejected = b.inventory(authority)
    assert stack["bound_client_identity_sha256"] == m.BOUND_CLIENT_IDENTITY_SHA256
    assert stack["response_object_type"] == "http.client.HTTPResponse"
    assert len(callsites) == 5
    assert len(accepted) == 8 and len(rejected) == 14
    assert socket.timeout is TimeoutError and IOError is OSError
    assert authority["alpha322a"]["computed_sha256"] == m.ALPHA322A_ROOT_SHA256
    assert len(authority["phase_roots"]) == 12 and authority["counts"] == b.master.COUNTS
    evidence = {r["evidence_id"]: r for r in stack["local_source_evidence"]}
    assert "raise URLError(err)" in evidence["urllib_do_open"]["source_excerpt"]
    assert "raise IncompleteRead" in evidence["http_safe_read"]["source_excerpt"]
    assert "raise RemoteDisconnected" in evidence["http_read_status"]["source_excerpt"]


@pytest.mark.parametrize("kind", [TimeoutError, ConnectionResetError])
@pytest.mark.parametrize("phase", list(t.LifecycleState))
def test_phase_matrix_known_concrete_exception_never_reused_after_complete(mapper, kind, phase):
    evidence = b.facts(phase, completion=complete() if phase in {t.LifecycleState.RESPONSE_BODY_COMPLETE, t.LifecycleState.RAW_RESPONSE_FROZEN, t.LifecycleState.RESPONSE_VALIDATION_COMPLETE} else None,
        status=200 if phase != t.LifecycleState.REQUEST_ATTEMPT_STARTED else None)
    result = mapper.classify(kind("text ignored"), evidence)
    if phase == t.LifecycleState.REQUEST_ATTEMPT_STARTED:
        assert result.semantic_failure_class == t.SemanticFailure.PRE_RESPONSE_TRANSPORT_INTERRUPTION
    elif phase == t.LifecycleState.RESPONSE_BODY_READING:
        assert result.semantic_failure_class == t.SemanticFailure.RESPONSE_BODY_TRANSPORT_INTERRUPTION
    else:
        assert result.semantic_failure_class == t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE


@pytest.mark.parametrize("kind", [TimeoutError, ConnectionResetError])
@pytest.mark.parametrize("place", ["pre_headers", "body"])
def test_signals_really_propagate_through_bound_HTTPResponse(kind, place):
    exception = b.actual_response_failure(kind, place)
    assert type(exception) is kind and exception.__traceback__ is not None
    names = []
    tb = exception.__traceback__
    while tb:
        names.append(tb.tb_frame.f_code.co_name)
        tb = tb.tb_next
    assert ("_read_status" if place == "pre_headers" else "_safe_read") in names


def test_actual_IncompleteRead_and_quarantine_observability(tmp_path):
    local = b.fixtures(tmp_path / "fixtures")
    audit = local["audits"]["incomplete_read"]
    assert local["check_passed"] and local["case_count"] == 30
    assert audit["parser_invocations"] == 0 and not audit["partial_authoritative"]
    assert audit["case"]["mapping"]["mapping_rule_id"] == "incomplete_read_body"
    partial = t.RawArtifactV1(**audit["partial_artifact"])
    assert partial.verified_bytes() == b"prefix"
    artifact = t.RawArtifactV1(**audit["observation_artifact"])
    record = json.loads(artifact.verified_bytes())
    b.prior.validate_observation(record["observation"])
    node = record["observation"]["exception_provenance"]["exception_nodes"][0]
    assert node["qualified_class_name"] == "http.client.IncompleteRead"
    assert node["traceback"] and record["mapping"]["mapping_table_sha256"] == m.MAPPING_TABLE_SHA256


@pytest.mark.parametrize("bad_partial,bad_expected", [("text", 2), (b"bytes", -1), (b"bytes", True), (b"bytes", "2")])
def test_incomplete_read_invalid_structured_fields_unknown(mapper, bad_partial, bad_expected):
    exception = http.client.IncompleteRead(b"bytes", 2)
    exception.partial, exception.expected = bad_partial, bad_expected
    result = mapper.classify(exception, b.facts(t.LifecycleState.RESPONSE_BODY_READING, status=200))
    assert result.semantic_failure_class == t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE


@pytest.mark.parametrize("kind", [TimeoutError, ConnectionResetError])
def test_exact_actual_urllib_reason_wrapper_and_context_not_equivalent_authority(mapper, kind):
    exception = b.actual_wrapped_failure(kind)
    result = mapper.classify(exception, b.facts(t.LifecycleState.REQUEST_ATTEMPT_STARTED))
    assert result.mapping_confidence == "AUTHORIZED_WRAPPED_CAUSE_MATCH" and result.matched_wrapper_path == ("reason",)
    assert result.matched_exception_class == m.qualified(kind)
    assert exception.__context__ is exception.reason
    fake = urllib.error.URLError("plain string timed out")
    fake.__cause__ = kind("must not fish")
    fake.__context__ = fake.__cause__
    result = mapper.classify(fake, b.facts(t.LifecycleState.REQUEST_ATTEMPT_STARTED))
    assert result.semantic_failure_class == t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE and not result.matched_wrapper_path


@pytest.mark.parametrize("form", ["reason_self", "nested_url", "reverse_cause", "reverse_context", "outer_cause_self", "outer_context_self", "inner_cause_self", "inner_context_self"])
def test_authorized_wrapper_cycles_and_extra_depth_fail_closed(mapper, form):
    inner = TimeoutError("inner")
    outer = urllib.error.URLError(inner)
    if form == "reason_self": outer.reason = outer
    elif form == "nested_url": outer.reason = urllib.error.URLError(inner)
    elif form == "reverse_cause": inner.__cause__ = outer
    elif form == "reverse_context": inner.__context__ = outer
    elif form == "outer_cause_self": outer.__cause__ = outer
    elif form == "outer_context_self": outer.__context__ = outer
    elif form == "inner_cause_self": inner.__cause__ = inner
    elif form == "inner_context_self": inner.__context__ = inner
    decision = m.classify_transport_failure_and_decide_retry_v2(outer, b.facts(t.LifecycleState.REQUEST_ATTEMPT_STARTED), request_replay_safe=True, attempt_ordinal=1)
    assert decision.mapping.semantic_failure_class == t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE and not decision.retry.retry_authorized


def test_wrong_phase_for_URLError_and_IncompleteRead_is_unknown(mapper):
    for exception, phase, body in ((urllib.error.URLError(TimeoutError()), t.LifecycleState.RESPONSE_BODY_READING, None),
        (http.client.IncompleteRead(b"partial", 3), t.LifecycleState.REQUEST_ATTEMPT_STARTED, None),
        (http.client.IncompleteRead(b"partial", 3), t.LifecycleState.RESPONSE_BODY_COMPLETE, complete())):
        result = mapper.classify(exception, b.facts(phase, completion=body, status=200 if phase != t.LifecycleState.REQUEST_ATTEMPT_STARTED else None))
        assert result.semantic_failure_class == t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE
        assert result.mapping_confidence == "PHASE_MISMATCH"


def test_remote_disconnected_supported_only_at_actual_pre_header_callsite(mapper):
    response = http.client.HTTPResponse(b.LocalSocket(io.BytesIO(b"")))
    with pytest.raises(http.client.RemoteDisconnected) as caught:
        try:
            response.begin()
        finally:
            response.close()
    result = mapper.classify(caught.value, b.facts(t.LifecycleState.REQUEST_ATTEMPT_STARTED))
    assert result.semantic_failure_class == t.SemanticFailure.PRE_RESPONSE_TRANSPORT_INTERRUPTION
    result = mapper.classify(caught.value, b.facts(t.LifecycleState.RESPONSE_BODY_READING, status=200))
    assert result.semantic_failure_class == t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE


@pytest.mark.parametrize("kind", [OSError, RuntimeError, ValueError, Exception, BaseException, http.client.BadStatusLine, http.client.LineTooLong,
    http.client.UnknownProtocol, http.client.ResponseNotReady, http.client.CannotSendRequest])
def test_broad_or_rejected_class_never_retry_from_its_inner_cause(kind):
    exception = kind("IncompleteRead timed out connection reset")
    exception.__cause__ = TimeoutError("not mapping authority")
    decision = m.classify_transport_failure_and_decide_retry_v2(exception, b.facts(t.LifecycleState.RESPONSE_BODY_READING, status=200), request_replay_safe=True, attempt_ordinal=1)
    assert decision.mapping.semantic_failure_class == t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE
    assert not decision.retry.retry_authorized and decision.retry.remaining_attempts_before_decision == 3


def test_spoofed_class_name_or_message_and_narrow_subclass_not_authority(mapper):
    fake = type("IncompleteRead", (Exception,), {"__module__": "http.client"})
    class DerivedTimeout(TimeoutError):
        pass
    for exception in (fake("exact misleading name"), DerivedTimeout("timed out"), RuntimeError("ConnectionResetError")):
        assert mapper.classify(exception, b.facts(t.LifecycleState.RESPONSE_BODY_READING, status=200)).semantic_failure_class == t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE
    with pytest.raises(t.TransportContractError):
        mapper.classify("TimeoutError", b.facts(t.LifecycleState.REQUEST_ATTEMPT_STARTED))
    with pytest.raises(TypeError):
        m.CONCRETE_CLASSES["timeout"] = fake


@pytest.mark.parametrize("phase", [t.LifecycleState.RESPONSE_BODY_READING, t.LifecycleState.RAW_RESPONSE_FROZEN])
@pytest.mark.parametrize("kind", [ET.ParseError, json.JSONDecodeError])
def test_complete_parser_error_not_body_interruption(mapper, phase, kind):
    exception = kind("local parse invalid") if kind is ET.ParseError else kind("local parse invalid", "{", 0)
    result = mapper.classify(exception, b.facts(phase, completion=complete() if phase == t.LifecycleState.RAW_RESPONSE_FROZEN else None, status=200))
    assert result.semantic_failure_class == (t.SemanticFailure.COMPLETE_BODY_RESPONSE_VALIDITY_FAILURE if phase == t.LifecycleState.RAW_RESPONSE_FROZEN else t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE)
    assert result.semantic_failure_class != t.SemanticFailure.RESPONSE_BODY_TRANSPORT_INTERRUPTION


@pytest.mark.parametrize("status", [403, 408, 429, 500, 502, 503, 504, 418])
def test_HTTP_status_binding_and_outer_HTTPError_precedence(status):
    expected = t.SemanticFailure.RETRYABLE_HTTP_STATUS if status in b.backend.RETRYABLE_HTTP_STATUS else t.SemanticFailure.NONRETRYABLE_HTTP_STATUS
    exception = urllib.error.HTTPError("https://synthetic.invalid/r", status, "timed out", {}, io.BytesIO())
    exception.__cause__ = TimeoutError("inner must not override outer")
    evidence = b.facts(t.LifecycleState.REQUEST_ATTEMPT_STARTED, trusted=True, status=status, origin="BOUND_HTTP_ERROR")
    decision = m.classify_transport_failure_and_decide_retry_v2(exception, evidence, request_replay_safe=True, attempt_ordinal=1)
    assert decision.mapping.semantic_failure_class == expected
    assert decision.mapping.mapping_rule_id == "http_error_status" and not decision.mapping.matched_wrapper_path
    structured = m.TransportExceptionMappingV2().classify(None, b.facts(t.LifecycleState.RESPONSE_HEADERS_RECEIVED, status=status))
    assert structured.semantic_failure_class == expected


def test_unknown_exception_dominates_favorable_status_and_complete_validation_context():
    decision = m.classify_transport_failure_and_decide_retry_v2(RuntimeError("unknown"),
        b.facts(t.LifecycleState.RESPONSE_HEADERS_RECEIVED, status=503), request_replay_safe=True, attempt_ordinal=1)
    assert decision.mapping.semantic_failure_class == t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE and not decision.retry.retry_authorized


@pytest.mark.parametrize("change", ["untrusted", "wrong_origin", "conflicting_code"])
def test_untrusted_or_conflicting_HTTPError_cannot_retry(mapper, change):
    exception = urllib.error.HTTPError("https://synthetic.invalid/r", 503, "ignored", {}, io.BytesIO())
    evidence = b.facts(t.LifecycleState.REQUEST_ATTEMPT_STARTED, trusted=True, status=503, origin="BOUND_HTTP_ERROR")
    if change == "untrusted": evidence = replace(evidence, headers_trusted=False)
    elif change == "wrong_origin": evidence = replace(evidence, http_status_origin="GUESSED")
    else: evidence = replace(evidence, http_status=502)
    assert mapper.classify(exception, evidence).semantic_failure_class == t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE


@pytest.mark.parametrize("kind,field", [(http.client.IncompleteRead, "partial"), (http.client.IncompleteRead, "expected"),
    (urllib.error.URLError, "reason"), (urllib.error.HTTPError, "code")])
def test_missing_structured_exception_field_cannot_promote_retry(mapper, kind, field):
    if kind is http.client.IncompleteRead:
        exception = kind(b"partial", 2)
        evidence = b.facts(t.LifecycleState.RESPONSE_BODY_READING, status=200)
    elif kind is urllib.error.URLError:
        exception = kind(TimeoutError())
        evidence = b.facts(t.LifecycleState.REQUEST_ATTEMPT_STARTED)
    else:
        exception = kind("https://synthetic.invalid/r", 503, "ignored", {}, io.BytesIO())
        evidence = b.facts(t.LifecycleState.REQUEST_ATTEMPT_STARTED, trusted=True, status=503, origin="BOUND_HTTP_ERROR")
    del vars(exception)[field]
    assert mapper.classify(exception, evidence).semantic_failure_class == t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE


def test_structured_length_mismatch_requires_no_exception_and_unknown_cannot_be_promoted(mapper):
    body = t.assess_body_completion(b"short", read_returned_normally=True, expected_content_length=6,
        expected_length_trustworthy=True, expected_length_representation=t.ByteRepresentation.WIRE)
    result = mapper.classify(None, b.facts(t.LifecycleState.RESPONSE_BODY_INTERRUPTED, completion=body, status=200))
    assert result.semantic_failure_class == t.SemanticFailure.RESPONSE_BODY_LENGTH_MISMATCH
    unknown = t.assess_body_completion(b"partial", read_returned_normally=False)
    for exception in (None, TimeoutError("must not promote unknown framing")):
        result = mapper.classify(exception, b.facts(t.LifecycleState.RESPONSE_BODY_READING, completion=unknown, status=200))
        assert result.semantic_failure_class == t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE


@pytest.mark.parametrize("safe", [True, False])
@pytest.mark.parametrize("ordinal", [1, 2, 3, 4])
def test_orchestrator_only_calls_frozen_semantic_policy_once(safe, ordinal):
    original = t.semantic_retry_decision
    with patch.object(t, "semantic_retry_decision", wraps=original) as delegate:
        decision = m.classify_transport_failure_and_decide_retry_v2(TimeoutError("no policy here"),
            b.facts(t.LifecycleState.RESPONSE_BODY_READING, status=200), request_replay_safe=safe, attempt_ordinal=ordinal)
    assert delegate.call_count == 1 and delegate.call_args.args == (t.SemanticFailure.RESPONSE_BODY_TRANSPORT_INTERRUPTION,)
    assert decision.retry == original(decision.mapping.semantic_failure_class, request_replay_safe=safe, attempt_ordinal=ordinal)
    assert decision.retry.retry_authorized is (safe and ordinal < 4)


def backend_facts():
    verdict = b.backend.validate_response(200, b'{"esearchresult":{"ERROR":"Search Backend failed: local synthetic"}}', 0, 1)
    outcome = m.BackendValidatorOutcomeV2.from_frozen_validator_result(verdict, authority_sha256=t.BACKEND_AUTHORITY_SHA256,
        validator_source_sha256=m.BACKEND_VALIDATOR_SOURCE_SHA256)
    return b.facts(t.LifecycleState.RAW_RESPONSE_FROZEN, status=200, completion=complete(), outcome=outcome)


def test_bound_backend_structured_outcome_uses_separate_existing_authority():
    evidence = backend_facts()
    decision = m.classify_transport_failure_and_decide_retry_v2(None, evidence, request_replay_safe=True, attempt_ordinal=1)
    assert decision.mapping.semantic_failure_class == t.SemanticFailure.RETRYABLE_PROVIDER_BACKEND_FAILURE and decision.retry.retry_authorized
    assert decision.mapping.mapping_rule_id == "frozen_esearch_backend_outcome"
    with patch.object(b.backend, "validate_response", side_effect=AssertionError("mapper must not parse backend content")):
        assert m.TransportExceptionMappingV2().classify(None, evidence) == decision.mapping


@pytest.mark.parametrize("field,value", [("authority_sha256", "0" * 64), ("validator_source_sha256", "0" * 64),
    ("schema_version", "guessed"), ("state", "message says backend failed"), ("technical_retryable", False), ("valid_page", True)])
def test_backend_authority_or_state_mismatch_unknown(field, value):
    evidence = backend_facts()
    evidence = replace(evidence, backend_outcome=replace(evidence.backend_outcome, **{field: value}))
    decision = m.classify_transport_failure_and_decide_retry_v2(None, evidence, request_replay_safe=True, attempt_ordinal=1)
    assert decision.mapping.semantic_failure_class == t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE and not decision.retry.retry_authorized


def test_table_is_exact_hash_bound_mutation_or_conflicting_rule_fails_closed():
    table = m.default_mapping_table_v2()
    assert table.sha256 == m.MAPPING_TABLE_SHA256
    record = table.record()
    duplicate = dict(record["rules"][0])
    duplicate["semantic_transport_class"] = t.SemanticFailure.NONRETRYABLE_HTTP_STATUS.value
    record["rules"].append(duplicate)
    wrong = m.TransportExceptionMappingV2(m.FrozenMappingTableV2(o.canonical_bytes(record)))
    decision = m.classify_transport_failure_and_decide_retry_v2(TimeoutError("ignored"), b.facts(t.LifecycleState.REQUEST_ATTEMPT_STARTED),
        request_replay_safe=True, attempt_ordinal=1, mapper=wrong)
    assert decision.mapping.diagnostic_state == "MAPPING_AUTHORITY_CONFLICT" and decision.mapping.mapping_confidence == "AMBIGUOUS_MAPPING"
    assert not decision.retry.retry_authorized
    record = table.record()
    record["rules"].clear()
    assert len(table.record()["rules"]) == 10
    class UnboundTable(m.FrozenMappingTableV2):
        pass
    with pytest.raises(t.TransportContractError, match="VERSIONED_MAPPING_TABLE_REQUIRED"):
        m.TransportExceptionMappingV2(UnboundTable(table.serialized))


def test_unbound_client_and_contradictory_phase_fail_closed(mapper):
    evidence = b.facts(t.LifecycleState.RESPONSE_BODY_READING, status=200)
    assert mapper.classify(TimeoutError(), replace(evidence, client_identity_sha256="0" * 64)).semantic_failure_class == t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE
    assert mapper.classify(TimeoutError(), replace(evidence, body_completion=complete())).semantic_failure_class == t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE
    assert mapper.classify(TimeoutError(), replace(evidence, headers_trusted=False)).semantic_failure_class == t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE


def test_mapping_determinism_is_independent_of_messages_addresses_and_dict_order(mapper):
    evidence = b.facts(t.LifecycleState.RESPONSE_BODY_READING, status=200)
    a = mapper.classify(TimeoutError({"a": object(), "b": "secret"}), evidence).record()
    c = mapper.classify(TimeoutError({"b": "different", "a": object()}), evidence).record()
    assert o.canonical_bytes(a) == o.canonical_bytes(c)
    assert not any(key in a for key in ("message", "repr", "traceback", "timestamp"))


def test_mapper_purity_no_io_sleep_resume_and_no_new_retry_matrix():
    audit = b.code_boundary_audit()
    assert audit["semantic_retry_decision_call_count_in_orchestrator"] == 1
    assert not audit["retry_loop_implemented"] and not audit["sleep_or_network_execution_implemented"]
    assert not m.RUNTIME_ACTIVATION_ALLOWED
    tree = ast.parse(b.COMPONENT.read_text())
    classify = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "classify")
    assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in {"str", "repr", "open"} for n in ast.walk(classify))
    class UnboundMapper(m.TransportExceptionMappingV2):
        pass
    with pytest.raises(t.TransportContractError, match="EXACT_VERSIONED_MAPPER_REQUIRED"):
        m.classify_transport_failure_and_decide_retry_v2(TimeoutError(), b.facts(t.LifecycleState.REQUEST_ATTEMPT_STARTED),
            request_replay_safe=True, attempt_ordinal=1, mapper=UnboundMapper())


def test_observability_logging_failure_reraises_original_without_retry():
    context = t.AttemptContextV1("synthetic:logging", b.master.sha(b"local request"), 1)
    attempt = t.TransportLifecycleV2(context)
    attempt.start_attempt("synthetic memory only")
    exception = TimeoutError("original")
    decision = m.classify_transport_failure_and_decide_retry_v2(exception, b.facts(t.LifecycleState.REQUEST_ATTEMPT_STARTED), request_replay_safe=True, attempt_ordinal=1)
    with patch.object(o, "canonical_bytes", side_effect=TypeError("logging failed")):
        with pytest.raises(TimeoutError) as caught:
            m.mapped_observation_v2(decision, attempt, o.SecretRedactorV1(), original_exception=exception,
                replay_safety_authority={"scope": "synthetic"})
    assert caught.value is exception


def test_existing_output_no_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(b, "OUT", tmp_path)
    with pytest.raises(t.TransportContractError, match="OUTPUT_EXISTS_NO_OVERWRITE"):
        b.run({})
    assert list(tmp_path.iterdir()) == []
