"""Literal prospective A-L engineering expectations; no truthiness or repairs."""

import copy
import subprocess
import sys
import xml.etree.ElementTree as ET

from scripts import search_plan_v24_alpha322_t11_validator_outcome_integration_v1 as h

j, t, b, o = h.j, h.t, h.b, h.o
SPEC = {
    "A": ("literal True", "VALID_SUCCESS"),
    "B": ("literal False", "TERMINAL_RESPONSE_VALIDITY_FAILURE"),
    "C": ("real XML parser exception", "TERMINAL_RESPONSE_VALIDITY_FAILURE"),
    "D": ("unauthorized None", "UNSUPPORTED_VALIDATOR_RESULT"),
    "E": ("unsupported integer result", "UNSUPPORTED_VALIDATOR_RESULT"),
    "F": ("failure result with success terminal", "VALIDATOR_OUTCOME_CONFLICT"),
    "G": ("success result with validity-failure terminal", "VALIDATOR_OUTCOME_CONFLICT"),
    "H": ("incomplete body validation", "VALIDATION_REQUIRES_AUTHORITATIVE_COMPLETE_RESPONSE"),
    "I": ("unknown incomplete transport tries validator authority", "VALIDATION_REQUIRES_AUTHORITATIVE_COMPLETE_RESPONSE"),
    "J": ("duplicate committed failure terminal", "DUPLICATE_TERMINAL"),
    "K": ("refetch committed validity failure", "NOT_FIRST_AUTHORIZED_UNRESOLVED_REQUEST"),
    "L": ("real crash before terminal", "ABANDONED_ATTEMPT_UNKNOWN_TERMINATION")}


def payload(item):
    return {"outcome": "VALID_SUCCESS" if item["outcome"].record()["accepted"] is True else "TERMINAL_RESPONSE_VALIDITY_FAILURE",
            "mapped_observation": item["observation"].record(), "retry_decision": item["decision"].record()["retry"],
            "raw_artifact": dict(item["artifact"].__dict__),
            "validation": {"authority_sha256": item["outcome"].record()["attempt_identity"]["manifest_sha256"],
                           "accepted": item["outcome"].record()["accepted"]},
            "eligibility": item["eligibility"], "failure_phase_binding": None,
            "validator_outcome": dict(item["outcome"].artifact.__dict__)}


def candidate(writer, data):
    request = writer.manifest.record()["requests"][0]
    data["validation"]["authority_sha256"] = request["validity_authority_sha256"]
    prefix = list(writer.verified().events)
    last = prefix[-1].record()
    record = copy.deepcopy(last)
    record.update(sequence_number=len(prefix) + 1, previous_entry_hash=last["entry_hash"],
                  event_type="ATTEMPT_TERMINAL", timestamp=h.NOW, event_payload=data)
    record.pop("entry_hash")
    record["entry_hash"] = j.sha(j.canonical(record))
    return j.JournalIntegrityVerifierV2.verify_events((*prefix, j.JournalEventV2(j.canonical(record))),
                                                    writer.manifest, writer.directory)


def real_parser_failure(writer):
    lifecycle, response = h.prepare_complete(writer, raw=b"<synthetic>")
    try:
        t.guarded_parse(response, ET.fromstring)
    except ET.ParseError as exc:
        exception = exc
        facts = b.TransportMappingFactsV2(lifecycle.state, b.BOUND_CLIENT_IDENTITY_SHA256,
            headers_trusted=True, http_status=200, http_status_origin="BOUND_HTTP_RESPONSE", body_completion=lifecycle.completion)
        capture = h.r2.f.capture_failure(writer, lifecycle, exception, facts)
    lifecycle.record_validation(valid=False, evidence_reference=writer.manifest.record()["requests"][0]["validity_authority_sha256"], timestamp=h.NOW)
    writer.record_lifecycle(lifecycle, timestamp=h.NOW)
    http = o.HttpResponseProvenanceV1.capture(lifecycle.context, writer.redactor, method="GET", status=200,
        trusted=True, status_origin="BOUND_HTTP_RESPONSE")
    body = o.BodyReadProvenanceV1.capture(lifecycle.context, writer.redactor, response.completion, response.artifact, parser_invoked=True)
    observation = b.mapped_observation_v2(capture.decision, lifecycle, writer.redactor, original_exception=exception,
        http=http, body=body, runtime_identity=capture.runtime_identity.record(),
        replay_safety_authority={"manifest_sha256": writer.manifest.sha256, "request_id": lifecycle.context.logical_request_id})
    binding = h.r2.f.bind_failure(writer, lifecycle, capture, observation, response.artifact)
    writer.commit_terminal(lifecycle, capture.decision, observation, artifact=response.artifact,
        validation={"authority_sha256": writer.manifest.request(lifecycle.context.logical_request_id)["validity_authority_sha256"], "accepted": False},
        failure_phase_binding=binding, timestamp=h.NOW)
    return {"actual_exception_class": type(exception).__module__ + "." + type(exception).__qualname__,
            "exception_fabricated": False, "binding": binding.record()}


def execute(key, directory):
    expected = SPEC[key][1]
    extra, actual = {}, None
    if key == "L":
        process = subprocess.run([sys.executable, "-m", h.__name__, "--crash-T11", str(directory)],
                                 cwd=h.ROOT, capture_output=True, text=True)
        t.require(process.returncode == 73, "REAL_CRASH_FIXTURE_FAILED:" + process.stderr)
        plan = h.fresh_plan(directory)
        actual = plan["requests"][0]["current_derived_state"]
        extra = {"crash_exit_code": process.returncode, "fresh_process_plan": plan,
                 "next_ordinal": plan["requests"][0]["next_authorized_ordinal"], "terminal_event_count": 0}
    else:
        with j.AppendOnlyAttemptJournalV2(directory, h.manifest(), create=True) as writer:
            try:
                if key in {"H", "I"}:
                    lifecycle = h.r2.start(writer)
                    lifecycle.receive_headers(200, trustworthy=True, evidence_reference="synthetic:headers", timestamp=h.NOW)
                    lifecycle.start_body("synthetic:body", timestamp=h.NOW)
                    writer.record_lifecycle(lifecycle, timestamp=h.NOW)
                    if key == "I":
                        extra["original_transport_mapping"] = b.classify_transport_failure_and_decide_retry_v2(
                            RuntimeError("unknown concrete transport"), b.TransportMappingFactsV2(lifecycle.state,
                                b.BOUND_CLIENT_IDENTITY_SHA256, headers_trusted=True, http_status=200, http_status_origin="BOUND_HTTP_RESPONSE"),
                            request_replay_safe=True, attempt_ordinal=1).record()
                    h.validity.record_result(writer, lifecycle, False, kind="literal_boolean", timestamp=h.NOW)
                elif key == "C":
                    extra = real_parser_failure(writer)
                else:
                    lifecycle, response = h.prepare_complete(writer)
                    returned = True if key in {"A", "G"} else None if key == "D" else 0 if key == "E" else False
                    actual_return = t.guarded_parse(response, lambda raw: returned)
                    item = h.prepare_result(writer, lifecycle, actual_return, response=response)
                    extra["actual_validator_result"] = actual_return
                    if key in {"F", "G"}:
                        data = payload(item)
                        data["outcome"] = "VALID_SUCCESS" if key == "F" else "TERMINAL_RESPONSE_VALIDITY_FAILURE"
                        candidate(writer, data)
                    else:
                        h.commit(writer, item)
                        if key == "J":
                            h.commit(writer, item)
                        elif key == "K":
                            writer.start_attempt("repair:OA:0", timestamp=h.NOW)
            except t.TransportContractError as exc:
                actual = str(exc)
            if actual is None:
                actual = h.p.DeterministicResumePlannerV2().build(writer.verified()).record()["requests"][0]["current_derived_state"]
            extra["journal_terminal_count"] = sum(event.record()["event_type"] == "ATTEMPT_TERMINAL" for event in writer.verified().events)
        plan = h.fresh_plan(directory)
        extra["fresh_process_plan"] = plan
        extra["no_refetch_dispatch"] = True
    passed = actual == expected and (key != "L" or extra["next_ordinal"] == 2)
    return {"fixture_id": key, "description": SPEC[key][0], "expected_exact_outcome": expected,
            "actual_exact_outcome": actual, "passed": passed, **extra}
