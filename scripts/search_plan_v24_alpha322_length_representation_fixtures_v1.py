"""Literal L01-L14 development expectations, separate from the original oracle."""

import copy
import dataclasses
import xml.etree.ElementTree as ET

from scripts import search_plan_v24_alpha322_length_bound_r2_integration_v1 as h
from scripts import search_plan_v24_alpha322_length_bound_t11_fixtures_v1 as validator_fixtures

j, t, b, o, lengths = h.j, h.t, h.b, h.o, h.j.lengths
SPEC = {
    "L01": "MATCH", "L02": "PARTIAL_OR_UNAUTHORITATIVE_RESPONSE_QUARANTINED",
    "L03": "MISMATCH", "L04": "UNAVAILABLE", "L05": "UNAVAILABLE", "L06": "MATCH",
    "L07": "PARTIAL_OR_UNAUTHORITATIVE_RESPONSE_QUARANTINED",
    "L08": "LENGTH_REPRESENTATION_PROVENANCE_MISMATCH",
    "L09": "LENGTH_REPRESENTATION_PROVENANCE_MISMATCH",
    "L10": "UNPROVEN_BODY_COMPLETION", "L11": "CONTRADICTORY_COMPLETE_BODY_EVIDENCE",
    "L12": "NESTED_PROVENANCE_CONTEXT", "L13": "UNSUPPORTED_LENGTH_REPRESENTATION",
    "L14": "TERMINAL_RESPONSE_VALIDITY_FAILURE"}


def manifest(representation):
    value = h.manifest().record()
    request = value["requests"][0]
    request["request_payload"]["length_evidence_contract"] = lengths.length_contract(representation)
    request["request_payload_sha256"] = j.sha(j.canonical(request["request_payload"]))
    return j.FrozenRequestManifestV2(j.canonical(value))


def prepare(writer, *, raw, expected, representation=t.ByteRepresentation.WIRE,
            normal=True, wire_raw=None):
    lifecycle = h.start(writer)
    lifecycle.receive_headers(200, trustworthy=True, evidence_reference="local:headers", timestamp=h.NOW)
    lifecycle.start_body("local:read", timestamp=h.NOW)
    writer.record_lifecycle(lifecycle, timestamp=h.NOW)
    framing = ()
    if wire_raw is not None:
        wire_artifact = j.atomic_freeze(writer.directory / "wire.bin", wire_raw)
        framing = (lengths.freeze_wire_check(writer.directory, wire_artifact, lifecycle.context, expected,
                                            read_returned_normally=True),)
    completion = t.assess_body_completion(raw, read_returned_normally=normal,
        expected_content_length=expected, expected_length_trustworthy=expected is not None,
        expected_length_representation=t.ByteRepresentation.WIRE,
        byte_representation=representation, framing_evidence=framing,
        interruption_class=t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE if not normal else None, timestamp=h.NOW)
    artifact = j.atomic_freeze(writer.directory / "response.bin", raw)
    lifecycle.record_body(completion, "local:actual-completion", timestamp=h.NOW)
    writer.record_lifecycle(lifecycle, timestamp=h.NOW)
    if completion.body_completion_state == t.BodyState.UNKNOWN:
        response = t.FrozenTransportResponseV2(lifecycle.context, completion, artifact, True)
    else:
        response = lifecycle.freeze_response(artifact, timestamp=h.NOW)
        writer.record_lifecycle(lifecycle, timestamp=h.NOW)
    http = o.HttpResponseProvenanceV1.capture(lifecycle.context, writer.redactor, method="GET", status=200,
        trusted=True, status_origin="BOUND_HTTP_RESPONSE", body_byte_representation=representation.value,
        expected_length=expected, headers=(("Content-Length", str(expected)),) if expected is not None else ())
    body = o.BodyReadProvenanceV1.capture(lifecycle.context, writer.redactor, completion, artifact)
    return lifecycle, response, http, body


def success_payload(writer, lifecycle, response, http, body):
    request = writer.manifest.request(lifecycle.context.logical_request_id)
    lifecycle.record_validation(valid=True, evidence_reference=request["validity_authority_sha256"], timestamp=h.NOW)
    writer.record_lifecycle(lifecycle, timestamp=h.NOW)
    facts = b.TransportMappingFactsV2(lifecycle.state, b.BOUND_CLIENT_IDENTITY_SHA256,
        headers_trusted=True, http_status=200, http_status_origin="BOUND_HTTP_RESPONSE", body_completion=lifecycle.completion)
    decision = b.classify_transport_failure_and_decide_retry_v2(None, facts, request_replay_safe=True, attempt_ordinal=1)
    mapped = b.mapped_observation_v2(decision, lifecycle, writer.redactor, http=http, body=body,
        replay_safety_authority={"manifest_sha256": writer.manifest.sha256, "request_id": request["request_id"]})
    payload = {"outcome": "VALID_SUCCESS", "mapped_observation": mapped.record(),
        "retry_decision": decision.record()["retry"], "raw_artifact": dict(response.artifact.__dict__),
        "validation": {"authority_sha256": request["validity_authority_sha256"], "accepted": True},
        "eligibility": {"authority_sha256": request["eligibility_authority_sha256"], "eligible": True},
        "failure_phase_binding": None}
    return payload, decision, mapped


def candidate(writer, payload):
    return validator_fixtures.candidate(writer, payload)


def execute(key, directory):
    expected_verdict = SPEC[key]
    representation = t.ByteRepresentation.DECODED if key in {"L05", "L06", "L07"} else t.ByteRepresentation.WIRE
    raw = b"x" * (100 if key in {"L05", "L06", "L07"} else 0 if key in {"L02", "L03", "L10"} else 50)
    expected = None if key == "L04" else 50
    actual, extra, first_rejection = None, {}, None
    parser_invocations = []
    frozen = manifest(representation)
    if key == "L14":
        frozen = validator_fixtures.h.manifest()
    with j.AppendOnlyAttemptJournalV2(directory, frozen, create=True) as writer:
        before = None
        try:
            if key == "L14":
                extra = validator_fixtures.real_parser_failure(writer)
                actual = validator_fixtures.h.p.DeterministicResumePlannerV2().build(writer.verified()).record()["requests"][0]["current_derived_state"]
                extra.update(transport_body_complete=True, response_validity_accepted=False)
            else:
                lifecycle, response, http, body = prepare(writer, raw=raw, expected=expected,
                    representation=representation, normal=key not in {"L03", "L10"},
                    wire_raw=b"w" * (40 if key == "L07" else 50) if key in {"L06", "L07"} else None)
                completion = lifecycle.completion
                extra.update(content_length_match=completion.content_length_match,
                    semantic_failure=completion.semantic_failure.value, body_state=completion.body_completion_state.value,
                    read_returned_normally=completion.read_returned_normally,
                    trusted_expected_length_preserved=completion.expected_content_length,
                    acquired_bytes=response.artifact.byte_count, actual_representation=representation.value)
                if key == "L10":
                    dataclasses.replace(completion, body_completion_state=t.BodyState.COMPLETE,
                        semantic_failure=t.SemanticFailure.NO_TECHNICAL_FAILURE, body_sha256=completion.observed_bytes_sha256)
                elif key in {"L02", "L07"}:
                    t.guarded_parse(response, lambda value: parser_invocations.append(value))
                elif key == "L03":
                    actual = completion.content_length_match
                    extra["retry_authorized"] = t.semantic_retry_decision(completion.semantic_failure,
                        request_replay_safe=True, attempt_ordinal=1).retry_authorized
                    try:
                        t.guarded_parse(response, lambda value: parser_invocations.append(value))
                    except t.TransportContractError as exc:
                        extra["parser_first_rejection"] = str(exc)
                else:
                    payload, decision, mapped = success_payload(writer, lifecycle, response, http, body)
                    observation = payload["mapped_observation"]["observation"]
                    before = j.read_bytes(writer.directory / "segment-0001.jsonl")
                    if key == "L08":
                        observation["http_response_provenance"]["body_byte_representation"] = "decoded"
                    elif key == "L09":
                        observation["http_response_provenance"]["body_byte_representation"] = None
                    elif key == "L11":
                        observation["body_read_provenance"]["expected_content_length_bytes"] = 40
                        observed_http = observation["http_response_provenance"]
                        observed_http.update(expected_content_length_bytes=40, content_length_raw="40",
                            response_headers=[{"name":"Content-Length", "value":"40"}])
                    elif key == "L12":
                        observation["body_read_provenance"]["attempt_ordinal"] = 2
                    elif key == "L13":
                        altered_request = copy.deepcopy(writer.manifest.record()["requests"][0])
                        altered_request["request_payload"]["length_evidence_contract"]["actual_representation"] = "transfer-decoded-is-gzip"
                        lengths.verify_complete_length(body.record(), http.record(), raw, lifecycle.context, altered_request)
                    if key in {"L08", "L09", "L11", "L12"}:
                        candidate(writer, payload)
                    else:
                        checked = lengths.verify_complete_length(body.record(), http.record(), raw, lifecycle.context,
                                                                 writer.manifest.request(lifecycle.context.logical_request_id))
                        writer.commit_terminal(lifecycle, decision, mapped, artifact=response.artifact,
                            validation=payload["validation"], eligibility=payload["eligibility"], timestamp=h.NOW)
                        actual = lengths.verify_wire_reference(completion.framing_integrity_evidence[0].evidence_reference,
                            lifecycle.context, expected) if key == "L06" else checked["content_length_match"]
                        extra.update(journal_committed=True, verified_length=checked)
        except t.TransportContractError as exc:
            first_rejection = actual = str(exc)
        if before is not None and first_rejection is not None:
            extra["negative_rejection_did_not_append"] = before == j.read_bytes(writer.directory / "segment-0001.jsonl")
        extra["journal_terminal_count"] = sum(event.record()["event_type"] == "ATTEMPT_TERMINAL" for event in writer.verified().events)
    extra["fresh_process_plan"] = h.fresh_plan(directory)
    checks = [actual == expected_verdict, not parser_invocations]
    if key == "L03":
        checks += [extra["semantic_failure"] == "UNKNOWN_RUNTIME_FAILURE", extra["body_state"] == "BODY_COMPLETION_UNKNOWN",
                   extra["retry_authorized"] is False, extra["parser_first_rejection"] == "PARTIAL_OR_UNAUTHORITATIVE_RESPONSE_QUARANTINED"]
    if key in {"L02", "L07"}:
        checks += [extra["semantic_failure"] == "RESPONSE_BODY_LENGTH_MISMATCH", extra["journal_terminal_count"] == 0]
    if key in {"L08", "L09", "L11", "L12", "L13"}:
        checks += [extra["negative_rejection_did_not_append"], extra["journal_terminal_count"] == 0]
    return {"fixture_id":key, "expected_exact_outcome":expected_verdict, "actual_exact_outcome":actual,
        "actual_first_rejection":first_rejection, "passed":all(checks), "parser_invocations":len(parser_invocations), **extra}
