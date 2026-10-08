"""22A component unit tests, not 22D fault-matrix or historical replay."""

from dataclasses import FrozenInstanceError, replace
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import run_search_plan_v24_alpha322a_transport_observability_offline as a

t, o = a.t, a.o


@pytest.fixture(autouse=True)
def offline_only():
    with a.master.prior.offline_guard():
        yield


@pytest.fixture
def context():
    return t.AttemptContextV1("synthetic:unit", hashlib.sha256(b"immutable request").hexdigest(), 1)


def reading(context):
    lifecycle = t.TransportLifecycleV2(context)
    lifecycle.start_attempt("synthetic-memory-only", timestamp=a.NOW)
    lifecycle.receive_headers(200, trustworthy=True, evidence_reference="synthetic_headers", timestamp=a.NOW)
    lifecycle.start_body("synthetic_read", timestamp=a.NOW)
    return lifecycle


def test_authoritative_master_closure_and_science_bindings_current():
    authority = a.verify_authority()
    assert authority["master"]["computed_sha256"] == t.MASTER_ROOT_SHA256
    assert authority["closure"]["computed_sha256"] == a.master.CLOSURE_SHA
    assert len(authority["phase_roots"]) == 12
    assert authority["counts"] == a.master.COUNTS


@pytest.mark.parametrize("state", list(t.LifecycleState))
@pytest.mark.parametrize("target", list(t.LifecycleState))
def test_transition_table_total_and_fail_closed(state, target):
    if (state, target) in t.ALLOWED_TRANSITIONS:
        t.validate_transition(state, target)
    else:
        with pytest.raises(t.TransportContractError):
            t.validate_transition(state, target)


def test_table_matches_frozen_master_and_no_skip(context):
    contract = a.obj(a.master.OUT / "transport_lifecycle_contract_v2_draft.json")
    assert t.ALLOWED_TRANSITIONS == frozenset((t.LifecycleState(r["from"]), t.LifecycleState(r["to"])) for r in contract["transitions"])
    lifecycle = t.TransportLifecycleV2(context)
    with pytest.raises(t.TransportContractError):
        lifecycle.start_body("cannot_skip")
    assert lifecycle.state == t.LifecycleState.REQUEST_NOT_STARTED and not lifecycle.events
    lifecycle.start_attempt("start")
    with pytest.raises(t.TransportContractError):
        lifecycle.start_attempt("cannot_reuse_ordinal")
    with pytest.raises(t.TransportContractError):
        lifecycle.receive_headers(200, trustworthy=False, evidence_reference="untrusted")
    unknown = t.assess_body_completion(b"partial", read_returned_normally=False)
    with pytest.raises(t.TransportContractError):
        lifecycle.record_body(unknown, "unknown_before_body")


@pytest.mark.parametrize("ordinal", [0, 5, True, 1.0, "1"])
def test_invalid_attempt_ordinal_never_started(context, ordinal):
    with pytest.raises(t.TransportContractError):
        replace(context, attempt_ordinal=ordinal)
    with pytest.raises(t.TransportContractError):
        t.semantic_retry_decision(t.SemanticFailure.RESPONSE_BODY_TRANSPORT_INTERRUPTION, request_replay_safe=True, attempt_ordinal=ordinal)


def test_context_and_completion_are_immutable(context):
    with pytest.raises(FrozenInstanceError):
        context.attempt_ordinal = 2
    completion = t.assess_body_completion(b"abc", read_returned_normally=True)
    with pytest.raises(FrozenInstanceError):
        completion.bytes_read = 4
    with pytest.raises(t.TransportContractError):
        replace(completion, read_returned_normally=False)
    with pytest.raises(t.TransportContractError):
        replace(completion, body_sha256=None)
    lifecycle = t.TransportLifecycleV2(context)
    with pytest.raises(AttributeError):
        lifecycle.context = replace(context, attempt_ordinal=2)
    assert lifecycle.context == context


@pytest.mark.parametrize("length,trust,expected_rep,read_rep,expected", [
    (3, True, t.ByteRepresentation.WIRE, t.ByteRepresentation.WIRE, "MATCH"),
    (4, True, t.ByteRepresentation.WIRE, t.ByteRepresentation.WIRE, "MISMATCH"),
    (4, False, t.ByteRepresentation.WIRE, t.ByteRepresentation.WIRE, "UNAVAILABLE"),
    (4, True, t.ByteRepresentation.WIRE, t.ByteRepresentation.DECODED, "UNAVAILABLE"),
    (4, True, None, t.ByteRepresentation.WIRE, "UNAVAILABLE"),
    (None, True, t.ByteRepresentation.WIRE, t.ByteRepresentation.WIRE, "UNAVAILABLE"),
    (4, True, t.ByteRepresentation.UNKNOWN, t.ByteRepresentation.UNKNOWN, "UNAVAILABLE")])
def test_length_only_same_authoritative_representation(length, trust, expected_rep, read_rep, expected):
    c = t.assess_body_completion(b"abc", read_returned_normally=True, expected_content_length=length,
        expected_length_trustworthy=trust, expected_length_representation=expected_rep, byte_representation=read_rep)
    assert c.content_length_match == expected
    assert (c.body_completion_state == t.BodyState.INTERRUPTED) == (expected == "MISMATCH")
    if expected == "MISMATCH":
        assert c.semantic_failure == t.SemanticFailure.RESPONSE_BODY_LENGTH_MISMATCH


@pytest.mark.parametrize("passed,failure,expected", [
    (True, t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE, t.BodyState.COMPLETE),
    (False, t.SemanticFailure.RESPONSE_BODY_TRANSPORT_INTERRUPTION, t.BodyState.INTERRUPTED),
    (False, t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE, t.BodyState.UNKNOWN),
    (None, t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE, t.BodyState.UNKNOWN)])
def test_available_authoritative_framing_checks(passed, failure, expected):
    c = t.assess_body_completion(b"abc", read_returned_normally=True,
        framing_evidence=(t.FramingEvidenceV1("synthetic_check", passed, True, failure, "synthetic_proof"),))
    assert c.body_completion_state == expected


def test_unknown_quarantine_has_no_automatic_retry(context, tmp_path):
    lifecycle = reading(context)
    c = t.assess_body_completion(b"partial", read_returned_normally=False, timestamp=a.NOW)
    lifecycle.record_body(c, "unknown_capture")
    assert lifecycle.state == t.LifecycleState.TERMINAL_TECHNICAL_FAILURE
    artifact = t.RawArtifactStoreV1(tmp_path / "raw").freeze_bytes("unknown.raw", b"partial")
    with pytest.raises(t.TransportContractError):
        lifecycle.freeze_response(artifact)
    response = t.FrozenTransportResponseV2(context, c, artifact, True)
    spy = []
    with pytest.raises(t.TransportContractError):
        t.guarded_parse(response, lambda raw: spy.append(raw))
    assert not spy and not response.authoritative
    provenance = o.BodyReadProvenanceV1.capture(context, o.SecretRedactorV1(), c, artifact).record()
    o.validate_schema(provenance, a.obj(a.master.OUT / "body_read_provenance_schema.json"))
    assert provenance["complete_body_sha256"] is None and provenance["partial_body_sha256"] == artifact.sha256
    assert not t.semantic_retry_decision(c.semantic_failure, request_replay_safe=True, attempt_ordinal=1).retry_authorized


def test_partial_storage_parser_guards_and_complete_invalid_actual_fixtures(tmp_path):
    fixtures = a.synthetic_fixtures(tmp_path / "fixtures")
    for key in ("interrupted", "length_mismatch"):
        assert not any(fixtures[key]["parser_invocation_counts"].values())
        assert fixtures[key]["retry_authorized"] and fixtures[key]["next_attempt_ordinal"] == 2
        assert fixtures[key]["remaining_attempts"] == 3
    invalid = fixtures["invalid_complete"]
    assert invalid["body_state"] == "BODY_COMPLETE"
    assert invalid["semantic_failure"] == "COMPLETE_BODY_RESPONSE_VALIDITY_FAILURE"
    assert not invalid["retry_authorized"] and invalid["parser_invocation_counts"]["XML"] == 1
    assert fixtures["complete"]["semantic_failure"] == "NO_TECHNICAL_FAILURE"
    for case in fixtures.values():
        for key in ("raw_artifact", "observation_artifact"):
            artifact = t.RawArtifactV1(**case[key])
            assert len(artifact.verified_bytes()) == artifact.byte_count


def test_storage_exclusive_no_path_escape_no_symlink(tmp_path):
    store = t.RawArtifactStoreV1(tmp_path / "raw")
    artifact = store.freeze_bytes("partial.raw", b"one")
    with pytest.raises(FileExistsError):
        store.freeze_bytes("partial.raw", b"two")
    assert artifact.verified_bytes() == b"one"
    with pytest.raises(t.TransportContractError):
        store.freeze_bytes("../escape", b"no")
    with pytest.raises(t.TransportContractError):
        t.RawArtifactStoreV1(tmp_path / "raw")
    (tmp_path / "linked").symlink_to(store.directory, target_is_directory=True)
    with pytest.raises(t.TransportContractError):
        t.RawArtifactStoreV1(tmp_path / "linked" / "new")
    (store.directory / "symlink.raw").symlink_to(Path(artifact.artifact_path))
    with pytest.raises(t.TransportContractError):
        store.freeze_bytes("symlink.raw", b"no")


def test_corrupt_artifact_denies_parser_and_nonaccepted_HTTP_denies(context, tmp_path):
    raw = b"complete"
    c = t.assess_body_completion(raw, read_returned_normally=True)
    artifact = t.RawArtifactStoreV1(tmp_path / "raw").freeze_bytes("complete.raw", raw)
    spy = []
    response = t.FrozenTransportResponseV2(context, c, artifact, False)
    with pytest.raises(t.TransportContractError):
        t.guarded_parse(response, lambda raw: spy.append(raw))
    corrupted = replace(artifact, sha256="0" * 64)
    response = t.FrozenTransportResponseV2(context, replace(c, body_sha256="0" * 64, observed_bytes_sha256="0" * 64), corrupted, True)
    with pytest.raises(t.TransportContractError):
        t.guarded_parse(response, lambda raw: spy.append(raw))
    assert not spy


@pytest.mark.parametrize("failure", list(t.SemanticFailure))
@pytest.mark.parametrize("safe", [True, False])
@pytest.mark.parametrize("ordinal", [1, 2, 3, 4])
def test_pure_semantic_retry_gates_and_attempt_budget(failure, safe, ordinal):
    d = t.semantic_retry_decision(failure, request_replay_safe=safe, attempt_ordinal=ordinal)
    retry_classes = {t.SemanticFailure.PRE_RESPONSE_TRANSPORT_INTERRUPTION, t.SemanticFailure.RESPONSE_BODY_TRANSPORT_INTERRUPTION,
                     t.SemanticFailure.RESPONSE_BODY_LENGTH_MISMATCH, t.SemanticFailure.RETRYABLE_HTTP_STATUS}
    expected = failure in retry_classes and safe and ordinal < 4
    assert d.retry_authorized is expected
    assert d.remaining_attempts_before_decision == d.remaining_attempts_after_decision == 4 - ordinal
    assert d.next_attempt_ordinal == (ordinal + 1 if expected else None)
    assert d.backoff_selected_seconds == ((2, 4, 8)[ordinal - 1] if expected else 0)


def test_backend_bound_authority_and_no_name_or_broad_exception_mapping():
    policy = t.SemanticRetryPolicyV2(provider_backend_authority=t.BACKEND_AUTHORITY_SHA256)
    assert t.semantic_retry_decision(t.SemanticFailure.RETRYABLE_PROVIDER_BACKEND_FAILURE,
        request_replay_safe=True, attempt_ordinal=1, policy=policy).retry_authorized
    for value in ("IncompleteRead", OSError("no inference"), "UNKNOWN_RUNTIME_FAILURE"):
        with pytest.raises(t.TransportContractError):
            t.semantic_retry_decision(value, request_replay_safe=True, attempt_ordinal=1)
    with pytest.raises(t.TransportContractError):
        t.SemanticRetryPolicyV2(maximum_attempts=5)


def test_exception_actual_object_chain_cycle_traceback_redaction(context):
    secret = "synthetic-private-key"
    inner = ValueError("password=" + secret)
    try:
        raise RuntimeError({"token": secret}, b"synthetic bytes") from inner
    except RuntimeError as exc:
        exc.__context__ = inner
        inner.__cause__ = exc
        original = exc
        captured = o.ExceptionProvenanceV1.capture(exc, context, o.SecretRedactorV1((secret,)))
    assert captured.provenance is not None and captured.original_exception is original
    record = captured.provenance.record()
    o.validate_schema(record, a.obj(a.master.OUT / "exception_provenance_schema.json"))
    assert record["redaction_paths"] and secret.encode() not in captured.provenance._serialized
    assert len(record["exception_nodes"]) == 2
    root, cause = record["exception_nodes"]
    assert root["module"] == "builtins" and root["qualified_class_name"] == "builtins.RuntimeError"
    assert root["cause_node_id"] == cause["node_id"] == root["context_node_id"]
    assert cause["cause_node_id"] == root["node_id"] and root["chain_cycle_detected"]
    assert root["traceback"] is not None and root["suppress_context"]
    assert root["args"][1]["length"] == len(b"synthetic bytes")


def test_unavailable_no_name_inference_and_no_object_addresses(context):
    exc = ValueError(object())
    captured = o.ExceptionProvenanceV1.capture(exc, context, o.SecretRedactorV1())
    record = captured.provenance.record()
    node = record["exception_nodes"][0]
    for key in ("traceback", "cause_node_id", "context_node_id"):
        assert node[key] is None and key in node["unavailable_fields"]
    assert "0x[ADDRESS]" in node["message"]
    assert node["args"][0]["unavailable_reason"] == "UNSUPPORTED_VALUE_NO_OBJECT_REPR"
    assert record["runtime_identity"]["client_version"] is None
    assert "runtime_identity.client_module" in record["unavailable_fields"]
    with pytest.raises(t.TransportContractError):
        o.ExceptionProvenanceV1.capture("ValueError", context, o.SecretRedactorV1())


def test_logging_failure_retains_original_no_retry(context):
    original = RuntimeError("original must not be hidden")
    with patch.object(o, "canonical_bytes", side_effect=TypeError("synthetic logging failure")):
        captured = o.ExceptionProvenanceV1.capture(original, context, o.SecretRedactorV1())
    assert captured.original_exception is original and captured.provenance is None
    assert captured.secondary_observability_failure["state"] == "OBSERVABILITY_CAPTURE_FAILED_NO_NEW_ATTEMPT"
    with pytest.raises(RuntimeError) as result:
        captured.reraise_original()
    assert result.value is original


@pytest.mark.parametrize("key", sorted(o.SENSITIVE_KEYS))
def test_sensitive_key_redaction_in_nested_arguments_and_headers(key):
    redactor = o.SecretRedactorV1()
    clean, paths = redactor.tree({"nested": {key: "never-persist"}, "header": {"name": key, "value": "never-persist"}})
    assert b"never-persist" not in o.canonical_bytes(clean) and paths
    assert redactor.tree(clean)[0] == clean


def test_redaction_URL_secret_fields_and_exception_text():
    redactor = o.SecretRedactorV1(("known-plain-secret",))
    samples = ["https://user:private-pass@synthetic.invalid/r?api_key=hidden-key&db=pmc",
        "https://synthetic.invalid/r?access_token=hidden-key#private-fragment",
        "Authorization: Basic hidden-key", "Cookie: session=hidden-key; second=hidden-key",
        "RuntimeError('Authorization: Basic hidden-key')", "RuntimeError('Cookie: a=hidden-key; b=hidden-key')",
        "password='hidden-key'", "traceback known-plain-secret"]
    for sample in samples:
        result = redactor.text(sample)
        assert all(secret not in result for secret in ("private-pass", "hidden-key", "known-plain-secret", "private-fragment"))
        assert redactor.text(result) == result
    assert redactor.url("https://synthetic.invalid:bad/r?api_key=secret") == "[UNAVAILABLE_SANITIZED_URL]"


def test_records_canonical_immutable_and_raw_observability_cannot_bypass_redaction():
    redactor = o.SecretRedactorV1()
    record = o.FrozenObservationRecordV1.from_record({"z": 1, "a": {"password": "private"}}, redactor)
    copied = record.record()
    copied["z"] = 2
    assert record.record()["z"] == 1
    with pytest.raises(t.TransportContractError):
        o.FrozenObservationRecordV1(o.canonical_bytes({"password": "private"}))
    a.crosscutting_checks()


def test_HTTP_multiplicity_and_unavailable_record_matches_master(context):
    record = o.HttpResponseProvenanceV1.capture(context, o.SecretRedactorV1(), method="GET",
        headers=(("Content-Length", "3"), ("content-length", "4"), ("Authorization", "secret"))).record()
    o.validate_schema(record, a.obj(a.master.OUT / "http_response_provenance_schema.json"))
    assert record["content_length_raw"] is None and record["status"] is None and not record["HTTP_provenance_trusted"]
    assert "content_length_raw" in record["unavailable_fields"]
    assert record["response_headers"][2]["value"] == o.REDACTED


def test_retry_provenance_identity_and_safe_declaration_required(context):
    d = t.semantic_retry_decision(t.SemanticFailure.RESPONSE_BODY_TRANSPORT_INTERRUPTION, request_replay_safe=True, attempt_ordinal=1)
    with pytest.raises(t.TransportContractError):
        o.RetryDecisionProvenanceV1.capture(context, o.SecretRedactorV1(), d)
    record = o.RetryDecisionProvenanceV1.capture(context, o.SecretRedactorV1(), d, replay_safety_authority={"frozen": True}).record()
    o.validate_schema(record, a.obj(a.master.OUT / "retry_decision_provenance_schema.json"))
    assert record["retry_decision_authority"]["next_attempt_ordinal"] == 2
    with pytest.raises(t.TransportContractError):
        o.RetryDecisionProvenanceV1.capture(replace(context, attempt_ordinal=2), o.SecretRedactorV1(), d, replay_safety_authority={"frozen": True})


@pytest.mark.parametrize("invalid", [True, "1", -1])
def test_schema_validator_types_and_unknown_keywords_fail_closed(invalid):
    with pytest.raises(t.TransportContractError):
        o.validate_schema(invalid, {"type": "integer", "minimum": 0})
    with pytest.raises(t.TransportContractError):
        o.validate_schema({}, {"oneOf": []})


def test_no_network_mapper_journal_resume_or_production_wiring():
    result = a.static_boundaries()
    assert not result["concrete_exception_mapping_implemented"] and not result["append_only_journal_implemented"]
    assert not result["process_resume_implemented"] and not t.RUNTIME_ACTIVATION_ALLOWED
    for binding in a.verify_authority()["legacy"]:
        assert a.digest(a.ROOT / binding["artifact_path"]) == binding["sha256"]
    initializer = (a.ROOT / "src/code_engine/__init__.py").read_text()
    assert "transport_lifecycle_v2" not in initializer and "transport_observability_v1" not in initializer


def test_runner_refuses_existing_output_without_write_or_execution(tmp_path, monkeypatch):
    monkeypatch.setattr(a, "OUT", tmp_path)
    with pytest.raises(t.TransportContractError, match="OUTPUT_EXISTS_NO_OVERWRITE"):
        a.run({})
    assert list(tmp_path.iterdir()) == []
