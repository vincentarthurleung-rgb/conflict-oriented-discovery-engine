"""Unwired representation-bound journal checks; frozen A owns completion.

This is not a new transport or retry policy. The request freezes the configured
adapter's byte representation before dispatch; a mutable HTTP label cannot
change it. Existing observation context, raw hashes and journal bindings remain
mandatory. No Content-Encoding or transfer-encoding inference is performed.
"""

import hashlib
from pathlib import Path

from . import transport_lifecycle_v2 as t
from . import transport_observability_v1 as o

RUNTIME_ACTIVATION_ALLOWED = False


def source_identity():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def length_contract(actual_representation=t.ByteRepresentation.WIRE):
    t.require(type(actual_representation) is t.ByteRepresentation
              and actual_representation != t.ByteRepresentation.UNKNOWN, "UNSUPPORTED_LENGTH_REPRESENTATION")
    return {"schema_version": "FrozenAdapterLengthBindingV1",
            "actual_representation": actual_representation.value,
            "expected_representation": t.ByteRepresentation.WIRE.value,
            "body_contract_sha256": t.MASTER_ROOT_SHA256}


def verify_complete_length(body, http, raw, context, request):
    """Verify already hash-bound complete bytes, without a cross-rep equality.

The frozen V1 observation schema has no expected-representation field. A NEW
request payload binds that missing adapter fact explicitly. It cannot be
inferred from compression headers or selected after seeing a length mismatch.
"""
    t.require(type(raw) is bytes and type(body) is dict and type(http) is dict,
              "LENGTH_EVIDENCE_REQUIRED")
    for record in (body, http):
        t.require(all(record.get(key) == value for key, value in context.record().items()),
                  "LENGTH_EVIDENCE_CONTEXT_MISMATCH")
    t.require(request["request_id"] == context.logical_request_id
              and request["request_payload_sha256"] == context.request_payload_sha256,
              "LENGTH_EVIDENCE_REQUEST_MISMATCH")
    contract = request["request_payload"].get("length_evidence_contract")
    t.require(type(contract) is dict and set(contract) == set(length_contract()), "LENGTH_REPRESENTATION_BINDING_REQUIRED")
    try:
        representation = t.ByteRepresentation(contract["actual_representation"])
    except (ValueError, TypeError) as exc:
        raise t.TransportContractError("UNSUPPORTED_LENGTH_REPRESENTATION") from exc
    t.require(contract == length_contract(representation), "UNSUPPORTED_LENGTH_REPRESENTATION")
    t.require(body.get("completion_state") == t.BodyState.COMPLETE.value
              and body.get("read_returned_normally") is True
              and body.get("semantic_failure_state") is None, "COMPLETE_LENGTH_ACQUISITION_REQUIRED")
    t.require(body.get("bytes_read") == len(raw)
              and body.get("complete_body_sha256") == hashlib.sha256(raw).hexdigest(), "LENGTH_ARTIFACT_BINDING_MISMATCH")
    expected = body.get("expected_content_length_bytes")
    t.require(expected is None or type(expected) is int and expected >= 0, "INVALID_EXPECTED_LENGTH")
    http_expected = http.get("expected_content_length_bytes")
    t.require(http_expected is None or type(http_expected) is int and http_expected >= 0, "INVALID_EXPECTED_LENGTH")
    t.require(http_expected is None or http_expected == expected, "HTTP_BODY_LENGTH_PROVENANCE_CONFLICT")
    label = http.get("body_byte_representation")
    # Missing labels cannot yield a MATCH. Missing expected length remains the
    # frozen normal-read/no-authoritative-length UNAVAILABLE case.
    t.require(label == representation.value or label is None and expected is None,
              "LENGTH_REPRESENTATION_PROVENANCE_MISMATCH")
    if http_expected is not None:
        t.require(http.get("HTTP_provenance_trusted") is True, "UNTRUSTED_LENGTH_PROVENANCE")
        headers = [pair["value"] for pair in http.get("response_headers") or []
                   if pair["name"].casefold() == "content-length"]
        if headers:
            t.require(len(headers) == 1 and headers[0].isascii() and headers[0].isdigit()
                      and int(headers[0]) == expected and http.get("content_length_raw") == headers[0],
                      "HTTP_BODY_LENGTH_PROVENANCE_CONFLICT")
    comparison = "UNAVAILABLE"
    if expected is not None and representation == t.ByteRepresentation.WIRE:
        comparison = "MATCH" if expected == len(raw) else "MISMATCH"
        t.require(comparison != "MISMATCH", "CONTRADICTORY_COMPLETE_BODY_EVIDENCE")
    for check in body.get("framing_integrity_checks", []):
        t.require(not check.get("authoritative") or check.get("passed") is True,
                  "CONTRADICTORY_COMPLETE_BODY_EVIDENCE")
        if check.get("check_name") == "bound_wire_content_length_v1":
            verify_wire_reference(check.get("evidence_reference"), context, expected)
    return {"content_length_match": comparison, "expected_content_length": expected,
            "actual_content_length": len(raw), "actual_representation": representation.value,
            "expected_representation": "wire", "cross_representation_comparison_performed": False}


def freeze_wire_check(directory, artifact, context, expected_length, *, read_returned_normally):
    """A separate actual wire artifact, not a transformed-count reconstruction."""
    from . import append_only_attempt_journal_v2_r2 as base
    t.require(type(artifact) is t.RawArtifactV1 and type(read_returned_normally) is bool,
              "WIRE_LENGTH_EVIDENCE_REQUIRED")
    raw = artifact.verified_bytes()
    t.require(type(expected_length) is int and expected_length >= 0, "INVALID_EXPECTED_LENGTH")
    value = {"schema_version": "BoundWireLengthEvidenceV1", "context": context.record(),
             "artifact": dict(artifact.__dict__), "expected_content_length": expected_length,
             "read_returned_normally": read_returned_normally, "byte_representation": "wire"}
    reference = base.atomic_freeze(Path(directory) / "wire-length-evidence.json", base.canonical(value))
    passed = read_returned_normally and len(raw) == expected_length
    return t.FramingEvidenceV1("bound_wire_content_length_v1", passed, True,
                              t.SemanticFailure.RESPONSE_BODY_LENGTH_MISMATCH,
                              o.canonical_bytes(dict(reference.__dict__)).decode())


def verify_wire_reference(serialized, context, expected):
    from . import append_only_attempt_journal_v2_r2 as base
    t.require(type(serialized) is str, "WIRE_LENGTH_EVIDENCE_REQUIRED")
    reference = base.strict_json(serialized.encode())
    saved = base.strict_json(base.verify_artifact(reference))
    base.exact_keys(saved, ("schema_version", "context", "artifact", "expected_content_length",
                           "read_returned_normally", "byte_representation"), "WIRE_LENGTH_EVIDENCE_FIELDS")
    t.require(saved["schema_version"] == "BoundWireLengthEvidenceV1" and saved["context"] == context.record(),
              "WIRE_LENGTH_EVIDENCE_CONTEXT_MISMATCH")
    t.require(saved["byte_representation"] == "wire" and saved["read_returned_normally"] is True,
              "WIRE_LENGTH_ACQUISITION_INCOMPLETE")
    t.require(saved["expected_content_length"] == expected and type(expected) is int,
              "WIRE_LENGTH_EXPECTATION_MISMATCH")
    raw = base.verify_artifact(saved["artifact"])
    t.require(len(raw) == expected, "WIRE_LENGTH_MISMATCH")
    return "MATCH"
