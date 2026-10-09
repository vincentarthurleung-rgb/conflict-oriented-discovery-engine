"""Independent D-R harness: original external faults, actual frozen R2 runtime.

Adapted from the frozen 22D harness. Only offline integration/evidence plumbing
is versioned; original scenario and expected bytes are read without rewriting.
No expected-outcome values are available to any scenario handler.
"""

import hashlib
import http.client
import io
import json
import os
import subprocess
import sys
import traceback
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from code_engine import append_only_attempt_journal_v2_r2 as j
from code_engine import deterministic_resume_planner_v2_r2 as p
from code_engine import stage_barrier_snapshot_v2_r2 as s
from code_engine import transport_failure_phase_binding_v2_r2 as f
from scripts import run_search_plan_v24_alpha322c_attempt_journal_resume_offline as upstream
from scripts import search_plan_v24_alpha322d_independent_scenarios as oracle
from scripts import search_plan_v24_alpha321_jats_primary_identity_v2 as identity

ROOT, master, t, o, b = f.ROOT, upstream.master, j.t, j.o, j.b
NOW = "2000-01-01T00:00:00Z"
SECRET = "alpha322d-synthetic-private-credential"
ORIGINAL = ROOT / "runs/20261008_search_plan_v24_dev_alpha3_22d_independent_fault_injection_offline"


def canonical(value):
    return j.canonical(value)


def ref(path, role):
    path = j.physical(Path(path))
    return {"artifact_path": str(path.relative_to(ROOT)), "sha256": j.sha(j.read_bytes(path)), "artifact_role": role}


def frozen_scenarios():
    raw = j.read_bytes(ORIGINAL / "frozen_fault_scenario_manifest.json")
    t.require(j.sha(raw) == "aed33640b5a88badd5a785b41019158ca369b656f20a5a150713b2e8f8eba23b", "FROZEN_SCENARIO_DRIFT")
    return j.strict_json(raw)["scenarios"]


def capture_for_decision(writer, lifecycle, exception, facts, decision):
    if decision.mapping.semantic_failure_class == t.SemanticFailure.NO_TECHNICAL_FAILURE:
        return None
    capture = f.capture_failure(writer, lifecycle, exception, facts)
    t.require(capture.decision.record() == decision.record(), "CAPTURE_CLASSIFICATION_CHANGED")
    return capture


def observation_and_binding(writer, lifecycle, decision, exception, *, capture=None, http=None, body=None, artifact=None):
    request = writer.manifest.request(lifecycle.context.logical_request_id)
    observation = b.mapped_observation_v2(decision, lifecycle, writer.redactor, original_exception=exception,
        http=http, body=body,
        runtime_identity=capture.runtime_identity.record() if capture is not None else None,
        replay_safety_authority={"manifest_sha256": writer.manifest.sha256, "request_id": request["request_id"]} if request["replay_safe"] else None)
    binding = f.bind_failure(writer, lifecycle, capture, observation, artifact) if capture is not None else None
    return observation, binding


def request_manifest(scenario, *, count=1, two_phase=False):
    key = scenario["scenario_id"]
    requests = []
    for stage in (("OA", "JATS") if two_phase else ("OA",)):
        for index in range(count):
            payload = {"synthetic_scenario": key, "source_ordinal": index, "route": "offline:" + stage}
            if stage == "JATS":
                payload["oa_request_id"] = key + f":OA:{index}"
            requests.append({"request_id": key + f":{stage}:{index}", "request_payload": payload,
                "request_payload_sha256": hashlib.sha256(canonical(payload)).hexdigest(), "stage": stage,
                "execution_order": len(requests), "replay_safe": scenario["initial_conditions"].get("replay_safe", True), "maximum_attempts": 4,
                "validity_authority_sha256": hashlib.sha256(b"22D synthetic validation stub; unchanged frozen identity validator where applicable").hexdigest(),
                "eligibility_authority_sha256": hashlib.sha256(b"22D fixed synthetic eligibility only; not a scientific gate").hexdigest()})
    return j.FrozenRequestManifestV2(canonical({"schema_version": "FrozenRequestManifestV2", "run_id": "synthetic:alpha322d:" + key,
        "run_epoch": "synthetic:epoch-1", "stage_id": "synthetic:OA-JATS", "authority": j.AUTHORITY,
        "runtime_v2_implementation_manifest_sha256": f.implementation_identity(),
        "activation_contract_sha256": hashlib.sha256(b"frozen parent OA VALID_SUCCESS activates exact JATS child").hexdigest(), "requests": requests}))


class LocalFileHolder:
    def __init__(self, file):
        self.file = file
    def makefile(self, mode):
        return self.file


class BoundFaultFile(io.BytesIO):
    def __init__(self, kind, phase):
        super().__init__(b"HTTP/1.1 200 OK\r\nContent-Length: 50\r\n\r\n<article>")
        self.kind, self.phase = kind, phase
    def readline(self, limit=-1):
        if self.phase == "pre_headers":
            raise self.kind("authorization=Bearer " + SECRET)
        return super().readline(limit)
    def read(self, amount=-1):
        if self.phase == "body":
            raise self.kind("synthetic I/O interruption token=" + SECRET)
        return super().read(amount)


def actual_bound_failure(kind, phase):
    response = http.client.HTTPResponse(LocalFileHolder(BoundFaultFile(kind, phase)))
    try:
        response.begin()
        response.read()
    except kind as exception:
        return exception
    finally:
        response.close()
    raise AssertionError("BOUND_TRANSPORT_FAULT_NOT_INJECTED")


def actual_incomplete_read():
    response = http.client.HTTPResponse(LocalFileHolder(io.BytesIO(b"HTTP/1.1 200 OK\r\nContent-Length: 50\r\n\r\n<article>")))
    try:
        response.begin()
        response.read()
    except http.client.IncompleteRead as exception:
        return exception
    finally:
        response.close()
    raise AssertionError("BOUND_INCOMPLETE_READ_NOT_INJECTED")


def journal_read_plan(directory):
    manifest = j.FrozenRequestManifestV2((Path(directory) / "request_manifest.json").read_bytes())
    verified = j.JournalIntegrityVerifierV2.read(directory, manifest)
    return p.DeterministicResumePlannerV2().build(verified).record()


def fresh_recovery(directory):
    result = subprocess.run([sys.executable, "-m", "scripts.search_plan_v24_alpha322dr_r2_independent_harness",
                             "--recover", str(directory)], cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        # Only an explicitly typed rejection from the actual R2 verifier is
        # eligible to satisfy an integrity-negative fixture. CLI/import faults
        # must not accidentally count as safe rejection.
        try:
            failure = json.loads(result.stdout)
        except (ValueError, TypeError) as exc:
            raise RuntimeError("RECOVERY_SUBPROCESS_INFRASTRUCTURE_FAILURE:" + result.stderr) from exc
        if failure.get("error_type") != "TransportContractError":
            raise RuntimeError("RECOVERY_SUBPROCESS_INFRASTRUCTURE_FAILURE:" + result.stdout + result.stderr)
        raise t.TransportContractError(failure["error"])
    return json.loads(result.stdout)


def begin(writer, key, dispatch):
    token = writer.start_attempt(key, timestamp=NOW)
    t.require(writer.dispatch_authorized(token), "WRITE_AHEAD_DISPATCH_DENIED")
    dispatch.append({"request_id": key, "attempt_ordinal": token.context.attempt_ordinal, "durable_start_hash": token.entry_hash})
    lifecycle = t.TransportLifecycleV2(token.context)
    lifecycle.start_attempt(token.entry_hash, timestamp=NOW)
    writer.record_lifecycle(lifecycle, timestamp=NOW)
    return lifecycle


def mapping_facts(lifecycle, *, status=None, origin=None, completion=None, backend=None):
    return b.TransportMappingFactsV2(lifecycle.state, b.BOUND_CLIENT_IDENTITY_SHA256,
        headers_trusted=status is not None, http_status=status, http_status_origin=origin,
        body_completion=completion, backend_outcome=backend)


def classify(exception, facts, request, ordinal):
    return b.classify_transport_failure_and_decide_retry_v2(exception, facts,
        request_replay_safe=request["replay_safe"], attempt_ordinal=ordinal)


def consumers(response, counts, *, invoke=False, identity_mismatch=False):
    validation_error, valid = None, True
    for name in oracle.CONSUMERS:
        def consumer(raw, name=name):
            counts[name] += 1
            if name in {"generic_parser", "jats_structure"}:
                return ET.fromstring(raw)
            if name == "primary_identity":
                verdict = identity.validate_jats_primary_identity_v2(raw, expected_pmid="123", expected_pmcid="PMC123", expected_doi=None)
                return verdict["source_identity_allows_progression"]
            return "SYNTHETIC_INSTRUMENTED_CONSUMER_NO_SCIENTIFIC_EXTRACTION"
        if not invoke:
            try:
                t.guarded_parse(response, consumer)
            except t.TransportContractError:
                pass
        else:
            try:
                result = t.guarded_parse(response, consumer)
                if name == "primary_identity" and result is False:
                    valid = False
                    break
            except ET.ParseError as exception:
                validation_error, valid = exception, False
                break
    return valid, validation_error


def transport_scenario(scenario, directory):
    """Expected data is not read here: this function observes only real SUT."""
    frozen = request_manifest(scenario)
    request = frozen.record()["requests"][0]
    key = request["request_id"]
    counts = dict.fromkeys(oracle.CONSUMERS, 0)
    dispatch, checkpoints, mappings = [], [], []
    result = {"scenario_id": scenario["scenario_id"], "execution_status": "EXECUTED", "category": scenario["category"]}
    semantic_exception, body, http, artifact, validation, eligibility, completion, decision = None, None, None, None, None, None, None, None
    capture = None
    redactor = o.SecretRedactorV1((SECRET,))
    with j.AppendOnlyAttemptJournalV2(directory, frozen, create=True, redactor=redactor) as writer:
        # Budget prelude uses independently declared external faults, never an
        # expected value read from the oracle to coerce implementation behavior.
        for _ in range(scenario["initial_conditions"]["ordinal"] - 1):
            prior = begin(writer, key, dispatch)
            prior_exception = actual_bound_failure(TimeoutError, "pre_headers")
            prior_facts = mapping_facts(prior)
            prior_decision = classify(prior_exception, prior_facts, request, prior.context.attempt_ordinal)
            prior_capture = capture_for_decision(writer, prior, prior_exception, prior_facts, prior_decision)
            prior_observation, prior_binding = observation_and_binding(writer, prior, prior_decision, prior_exception, capture=prior_capture)
            writer.commit_terminal(prior, prior_decision, prior_observation, failure_phase_binding=prior_binding, timestamp=NOW)
        lifecycle = begin(writer, key, dispatch)
        checkpoints.append({"checkpoint": "durable_start_ack_before_dispatch", "phase": lifecycle.state.value})
        signal, phase = scenario["injected_failure"], scenario["injection_point"]
        if phase == "REQUEST_ATTEMPT_STARTED":
            if signal == "URLError_TimeoutReason":
                semantic_exception = urllib.error.URLError(actual_bound_failure(TimeoutError, "pre_headers"))
            elif signal == "URLError_NestedReason":
                semantic_exception = urllib.error.URLError(urllib.error.URLError(TimeoutError(SECRET)))
            else:
                semantic_exception = actual_bound_failure(ConnectionResetError if signal == "ConnectionResetError" else TimeoutError, "pre_headers")
            decision = classify(semantic_exception, mapping_facts(lifecycle), request, lifecycle.context.attempt_ordinal)
            capture = capture_for_decision(writer, lifecycle, semantic_exception, mapping_facts(lifecycle), decision)
        elif phase == "RESPONSE_HEADERS_RECEIVED":
            status = 503 if signal == "HTTPError_503" else 404 if signal == "HTTPError_404" else 200
            lifecycle.receive_headers(status, trustworthy=True, evidence_reference="independent:headers", timestamp=NOW)
            writer.record_lifecycle(lifecycle, timestamp=NOW)
            semantic_exception = urllib.error.HTTPError("https://synthetic.invalid/?api_key=" + SECRET, status, "synthetic", {}, None) if status != 200 else TimeoutError(SECRET)
            http = o.HttpResponseProvenanceV1.capture(lifecycle.context, redactor, method="GET", status=status, trusted=True,
                status_origin="BOUND_HTTP_ERROR" if status != 200 else "BOUND_HTTP_RESPONSE", headers=(("Set-Cookie", SECRET),))
            facts = mapping_facts(lifecycle, status=status, origin="BOUND_HTTP_ERROR" if status != 200 else "BOUND_HTTP_RESPONSE")
            decision = classify(semantic_exception, facts, request, lifecycle.context.attempt_ordinal)
            capture = capture_for_decision(writer, lifecycle, semantic_exception, facts, decision)
        else:
            lifecycle.receive_headers(200, trustworthy=True, evidence_reference="independent:headers", timestamp=NOW)
            lifecycle.start_body("independent:body_read", timestamp=NOW)
            writer.record_lifecycle(lifecycle, timestamp=NOW)
            raw = b'<article><front><article-meta><article-id pub-id-type="pmc">PMC123</article-id><article-id pub-id-type="pmid">123</article-id></article-meta></front><body/></article>'
            interrupted = phase == "RESPONSE_BODY_READING"
            if interrupted:
                if signal == "IncompleteRead":
                    semantic_exception = actual_incomplete_read()
                    raw = semantic_exception.partial
                else:
                    kind = ConnectionResetError if signal == "ConnectionResetError" else TimeoutError if signal == "TimeoutError" else RuntimeError
                    semantic_exception = actual_bound_failure(kind, "body")
                    raw = b""  # Bound reset/timeout supplies no recoverable .partial.
                # The exception belongs to this phase, not the later audit freeze.
                facts = mapping_facts(lifecycle, status=200, origin="BOUND_HTTP_RESPONSE")
                decision = classify(semantic_exception, facts, request, lifecycle.context.attempt_ordinal)
                capture = capture_for_decision(writer, lifecycle, semantic_exception, facts, decision)
                checkpoints.append({"checkpoint": "concrete_fault_classified", "phase": lifecycle.state.value,
                                    "mapping": decision.mapping.record(), "retry": decision.record()["retry"]})
            elif signal == "ParseError":
                raw = b"<article>"
            elif signal == "FrozenIdentityValidatorRejects":
                raw = raw.replace(b"PMC123", b"PMC456")
            elif signal == "FrozenBackendFailure":
                raw = b'{"esearchresult":{"ERROR":"Search Backend failed: independent synthetic fixture"}}'
            representation = t.ByteRepresentation.DECODED if signal == "DecodedLengthUnavailable" else t.ByteRepresentation.DECOMPRESSED if signal == "DecompressedLengthUnavailable" else t.ByteRepresentation.WIRE
            expected_length = 50 if interrupted else len(raw) + 20 if signal in {"ComparableLengthMismatch", "DecodedLengthUnavailable", "DecompressedLengthUnavailable"} else len(raw)
            completion = t.assess_body_completion(raw, read_returned_normally=not interrupted,
                interruption_class=decision.mapping.semantic_failure_class if interrupted else None,
                expected_content_length=expected_length, expected_length_trustworthy=True, byte_representation=representation,
                expected_length_representation=t.ByteRepresentation.WIRE, timestamp=NOW,
                interruption_reason="independently injected transport signal" if interrupted else None)
            artifact_store = t.RawArtifactStoreV1(directory / "raw")
            artifact = artifact_store.freeze_bytes("response.xml", raw)
            lifecycle.record_body(completion, capture.record()["occurrence"]["sha256"] if interrupted else "independent:body_completion", timestamp=NOW)
            writer.record_lifecycle(lifecycle, timestamp=NOW)
            if not interrupted and signal == "ConnectionResetError":
                # This original fault is at BODY_COMPLETE, before raw freeze.
                semantic_exception = ConnectionResetError(SECRET)
                facts = mapping_facts(lifecycle, status=200, origin="BOUND_HTTP_RESPONSE", completion=completion)
                decision = classify(semantic_exception, facts, request, lifecycle.context.attempt_ordinal)
                capture = capture_for_decision(writer, lifecycle, semantic_exception, facts, decision)
            if completion.body_completion_state == t.BodyState.UNKNOWN:
                response = t.FrozenTransportResponseV2(lifecycle.context, completion, artifact, True)
            else:
                response = lifecycle.freeze_response(artifact, timestamp=NOW)
                writer.record_lifecycle(lifecycle, timestamp=NOW)
            should_validate = response.parser_eligible and semantic_exception is None
            backend_outcome = None
            if signal == "FrozenBackendFailure":
                counts["generic_parser"] += 1
                verdict = t.guarded_parse(response, lambda raw: upstream.prior.backend.validate_response(200, raw, 0, 1))
                accepted, parser_exception = False, None
                backend_outcome = b.BackendValidatorOutcomeV2.from_frozen_validator_result(verdict,
                    authority_sha256=t.BACKEND_AUTHORITY_SHA256, validator_source_sha256=b.BACKEND_VALIDATOR_SOURCE_SHA256)
            elif not response.authoritative or should_validate:
                accepted, parser_exception = consumers(response, counts, invoke=should_validate, identity_mismatch=signal == "FrozenIdentityValidatorRejects")
            else:
                # A completed response with an injected unknown exception is
                # not submitted to consumers by this offline controller.
                accepted, parser_exception = False, None
            if should_validate:
                lifecycle.record_validation(valid=accepted, evidence_reference=request["validity_authority_sha256"], timestamp=NOW)
                writer.record_lifecycle(lifecycle, timestamp=NOW)
                validation = {"authority_sha256": request["validity_authority_sha256"], "accepted": accepted} if backend_outcome is None else None
                eligibility = {"authority_sha256": request["eligibility_authority_sha256"], "eligible": True} if accepted else None
                semantic_exception = parser_exception
            if decision is None:
                facts = mapping_facts(lifecycle, status=200, origin="BOUND_HTTP_RESPONSE", completion=completion, backend=backend_outcome)
                decision = classify(semantic_exception, facts, request, lifecycle.context.attempt_ordinal)
                capture = capture_for_decision(writer, lifecycle, semantic_exception, facts, decision)
            http = o.HttpResponseProvenanceV1.capture(lifecycle.context, redactor, method="GET", status=200, trusted=True,
                status_origin="BOUND_HTTP_RESPONSE", expected_length=expected_length, body_byte_representation=representation.value,
                headers=(("Content-Length", str(expected_length)), ("Set-Cookie", SECRET)), request_url="https://synthetic.invalid/?api_key=" + SECRET)
            body = o.BodyReadProvenanceV1.capture(lifecycle.context, redactor, completion, artifact, parser_invoked=any(counts.values()))
            checkpoints.append({"checkpoint": "partial_or_complete_raw_preserved", "phase": lifecycle.state.value,
                "artifact": dict(artifact.__dict__), "body_complete": response.authoritative, "parser_eligible": response.parser_eligible,
                "mapping_fault_phase_preserved": decision.mapping.phase.value})
        mappings.append(decision.record())
        observation, binding = observation_and_binding(writer, lifecycle, decision, semantic_exception,
            capture=capture, http=http, body=body, artifact=artifact)
        observation_ref = j.atomic_freeze(directory / "mapped_observation.json", canonical(observation.record()))
        error = None
        try:
            writer.commit_terminal(lifecycle, decision, observation, artifact=artifact, validation=validation, eligibility=eligibility,
                failure_phase_binding=binding, timestamp=NOW)
            checkpoints.append({"checkpoint": "durable_terminal_commit", "phase": lifecycle.state.value})
        except t.TransportContractError as exception:
            error = {"qualified_class": type(exception).__module__ + "." + type(exception).__qualname__,
                     "message": redactor.text(str(exception)), "traceback": redactor.text(traceback.format_exc())}
        records = [event.record() for event in writer.verified().events]
    recovered = fresh_recovery(directory)
    request_plan = recovered["requests"][0]
    retry = decision.record()["retry"]
    raw_trust = "NO_RESPONSE" if artifact is None else "AUTHORITATIVE_COMPLETE" if completion.body_completion_state == t.BodyState.COMPLETE else "NONAUTHORITATIVE_PARTIAL"
    if completion and completion.body_completion_state == t.BodyState.COMPLETE and decision.mapping.semantic_failure_class == t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE:
        raw_trust = "COMPLETE_NOT_ADMITTED_AFTER_UNKNOWN"
    actual = {"semantic_failure_class": decision.mapping.semantic_failure_class.value, "retry_authorized": decision.retry.retry_authorized,
        "attempts_consumed": request_plan["attempts_consumed"], "next_attempt_ordinal": request_plan["next_authorized_ordinal"],
        "backoff_seconds": request_plan["backoff_seconds"], "parser_invocation_counts": counts,
        "journal_integrity": "VERIFIED", "terminal_logical_state": request_plan["current_derived_state"],
        "resume_executable_ids": recovered["executable_request_ids"], "stage_barrier_state": "ABSENT",
        "raw_artifact_trust": raw_trust, "body_complete": bool(completion and completion.body_completion_state == t.BodyState.COMPLETE),
        "content_length_match": completion.content_length_match if completion else "UNAVAILABLE",
        "durable_terminal_committed": any(r["event_type"] == "ATTEMPT_TERMINAL" for r in records), "dispatch_count": len(dispatch)}
    result.update({"actual": actual, "checkpoints": checkpoints, "persisted_mapping_and_retry": mappings,
        "durable_terminal_error": error, "observation": ref(Path(observation_ref.artifact_path), "actual_22A_22B_provenance"),
        "journal": ref(directory / "segment-0001.jsonl", "actual_R2_V2_journal"), "journal_entry_hashes": [r["entry_hash"] for r in records],
        "fresh_process_resume_plan": recovered, "dispatch_log": dispatch,
        "raw_artifact": dict(artifact.__dict__) if artifact else None, "raw_hash_verified": artifact is None or artifact.verified_bytes() is not None,
        "failure_phase_binding": binding.record() if binding is not None else None,
        "failure_occurrence_capture": capture.record() if capture is not None else None})
    return result


def success_unit(writer, key, dispatch, *, eligible=True, invalid=False):
    """Independent synthetic external response; real A/B/C own all state."""
    lifecycle = begin(writer, key, dispatch)
    request = writer.manifest.request(key)
    lifecycle.receive_headers(200, trustworthy=True, evidence_reference="independent:headers", timestamp=NOW)
    lifecycle.start_body("independent:read", timestamp=NOW)
    raw = b"<synthetic/>" if not invalid else b"<synthetic>"
    completion = t.assess_body_completion(raw, read_returned_normally=True, timestamp=NOW)
    artifact = j.atomic_freeze(writer.directory / (key.replace(":", "-") + "-" + str(lifecycle.context.attempt_ordinal) + ".xml"), raw)
    lifecycle.record_body(completion, "independent:completion", timestamp=NOW)
    response = lifecycle.freeze_response(artifact, timestamp=NOW)
    exception = None
    try:
        t.guarded_parse(response, ET.fromstring)
        accepted = True
    except ET.ParseError as exc:
        exception, accepted = exc, False
    lifecycle.record_validation(valid=accepted, evidence_reference=request["validity_authority_sha256"], timestamp=NOW)
    writer.record_lifecycle(lifecycle, timestamp=NOW)
    facts = mapping_facts(lifecycle, status=200, origin="BOUND_HTTP_RESPONSE", completion=completion)
    decision = classify(exception, facts, request, lifecycle.context.attempt_ordinal)
    capture = capture_for_decision(writer, lifecycle, exception, facts, decision)
    http = o.HttpResponseProvenanceV1.capture(lifecycle.context, writer.redactor, method="GET", status=200, trusted=True, status_origin="BOUND_HTTP_RESPONSE")
    body = o.BodyReadProvenanceV1.capture(lifecycle.context, writer.redactor, completion, artifact, parser_invoked=True)
    observation, binding = observation_and_binding(writer, lifecycle, decision, exception, capture=capture, http=http, body=body, artifact=artifact)
    writer.commit_terminal(lifecycle, decision, observation, artifact=artifact,
        validation={"authority_sha256": request["validity_authority_sha256"], "accepted": accepted},
        eligibility={"authority_sha256": request["eligibility_authority_sha256"], "eligible": eligible} if accepted else None,
        failure_phase_binding=binding, timestamp=NOW)


def partial_unit(writer, key, dispatch):
    lifecycle = begin(writer, key, dispatch)
    lifecycle.receive_headers(200, trustworthy=True, evidence_reference="independent:headers", timestamp=NOW)
    lifecycle.start_body("independent:read", timestamp=NOW)
    writer.record_lifecycle(lifecycle, timestamp=NOW)
    signal = actual_incomplete_read()
    request = writer.manifest.request(key)
    facts = mapping_facts(lifecycle, status=200, origin="BOUND_HTTP_RESPONSE")
    decision = classify(signal, facts, request, lifecycle.context.attempt_ordinal)
    capture = capture_for_decision(writer, lifecycle, signal, facts, decision)
    completion = t.assess_body_completion(signal.partial, read_returned_normally=False,
        interruption_class=t.SemanticFailure.RESPONSE_BODY_TRANSPORT_INTERRUPTION, timestamp=NOW)
    artifact = j.atomic_freeze(writer.directory / "independent-partial.xml", signal.partial)
    lifecycle.record_body(completion, capture.record()["occurrence"]["sha256"], timestamp=NOW)
    response = lifecycle.freeze_response(artifact, timestamp=NOW)
    writer.record_lifecycle(lifecycle, timestamp=NOW)
    counts = dict.fromkeys(oracle.CONSUMERS, 0)
    consumers(response, counts)
    t.require(not any(counts.values()), "PARTIAL_PARSER_INVOCATION")
    return lifecycle, response, signal, decision, capture


def crash_child(scenario, directory):
    checkpoint = scenario["injection_point"]
    phase_workflow = scenario["scenario_id"] in {f"C{i:02d}" for i in range(13, 18)}
    frozen = request_manifest(scenario, count=8 if phase_workflow else 1, two_phase=phase_workflow)
    writer = j.AppendOnlyAttemptJournalV2(directory, frozen, create=True, redactor=o.SecretRedactorV1((SECRET,)))
    dispatch = []
    if checkpoint == "before_start_ack":
        os._exit(73)
    if checkpoint == "during_append":
        real_write = os.write
        def terminate_during_append(fd, raw):
            real_write(fd, raw[:19])
            os._exit(73)
        with patch.object(j.os, "write", terminate_during_append):
            begin(writer, scenario["scenario_id"] + ":OA:0", dispatch)
    if phase_workflow:
        for i in range(8):
            success_unit(writer, scenario["scenario_id"] + f":OA:{i}", dispatch, eligible=i < 5)
        if checkpoint == "during_barrier_persistence":
            j.atomic_freeze(writer.directory / ".unpublished-barrier-fragment", b'{"schema_version":')
            os._exit(73)
        s.StageBarrierSnapshotV2.freeze(writer, timestamp=NOW)
        if checkpoint == "after_barrier_commit":
            os._exit(73)
        if checkpoint == "during_activation_persistence":
            j.atomic_freeze(writer.directory / ".unpublished-activation-fragment", b'{"schema_version":')
            os._exit(73)
        s.FrozenActivationManifestV2.freeze(writer, timestamp=NOW)
        if checkpoint == "after_activation_commit":
            os._exit(73)
        success_unit(writer, scenario["scenario_id"] + ":JATS:0", dispatch)
        partial_unit(writer, scenario["scenario_id"] + ":JATS:1", dispatch)
        os._exit(73)
    key = scenario["scenario_id"] + ":OA:0"
    if checkpoint in {"after_success_terminal", "after_noneligible_terminal", "repeat_readonly_resume", "corrupt_success_artifact"}:
        success_unit(writer, key, dispatch, eligible=checkpoint != "after_noneligible_terminal")
        os._exit(73)
    if checkpoint == "after_partial_raw":
        partial_unit(writer, key, dispatch)
        os._exit(73)
    lifecycle = begin(writer, key, dispatch)
    if checkpoint == "after_headers":
        lifecycle.receive_headers(200, trustworthy=True, evidence_reference="independent:headers", timestamp=NOW)
        writer.record_lifecycle(lifecycle, timestamp=NOW)
    elif checkpoint == "after_complete_raw_before_terminal":
        lifecycle.receive_headers(200, trustworthy=True, evidence_reference="independent:headers", timestamp=NOW)
        lifecycle.start_body("independent:read", timestamp=NOW)
        raw = b"<synthetic/>"
        completion = t.assess_body_completion(raw, read_returned_normally=True, timestamp=NOW)
        artifact = j.atomic_freeze(writer.directory / "independent-orphan.xml", raw)
        lifecycle.record_body(completion, "independent:complete", timestamp=NOW)
        lifecycle.freeze_response(artifact, timestamp=NOW)
        writer.record_lifecycle(lifecycle, timestamp=NOW)
    os._exit(73)


def crash_scenario(scenario, directory):
    if scenario["injection_point"] == "writer_contention":
        frozen = request_manifest(scenario)
        with j.AppendOnlyAttemptJournalV2(directory, frozen, create=True):
            denied = False
            try:
                j.AppendOnlyAttemptJournalV2(directory, frozen)
            except t.TransportContractError:
                denied = True
        return {"scenario_id": scenario["scenario_id"], "category": "CRASH", "actual": {
            "semantic_failure_class": None, "retry_authorized": False, "attempts_consumed": 0, "next_attempt_ordinal": None,
            "parser_invocation_counts": dict.fromkeys(oracle.CONSUMERS, 0), "journal_integrity": "FAILED_CLOSED" if denied else "VERIFIED",
            "terminal_logical_state": "WRITER_OWNERSHIP_DENIED" if denied else "NOT_STARTED", "durable_terminal_committed": False,
            "resume_executable_ids": [], "stage_barrier_state": "ABSENT", "raw_artifact_trust": "NO_RESPONSE"}, "crash_exit_code": None}
    result = subprocess.run([sys.executable, "-m", "scripts.search_plan_v24_alpha322dr_r2_independent_harness",
                             "--crash-child", scenario["scenario_id"], "--output", str(directory)], cwd=ROOT, capture_output=True, text=True)
    t.require(result.returncode == 73, "INDEPENDENT_CRASH_CHILD_FAILED:" + result.stderr)
    checkpoint = scenario["injection_point"]
    raw_journal = (directory / "segment-0001.jsonl").read_bytes()
    if checkpoint in {"torn_jsonl_tail", "hash_chain_corruption", "duplicate_attempt"}:
        # Mutate an isolated test fixture copy, never its original segment.
        corrupt = directory.parent / (directory.name + "-negative-copy")
        frozen = j.FrozenRequestManifestV2((directory / "request_manifest.json").read_bytes())
        with j.AppendOnlyAttemptJournalV2(corrupt, frozen, create=True):
            pass
        damaged = raw_journal + b'{"schema_version":' if checkpoint == "torn_jsonl_tail" else raw_journal.replace(b'"sequence_number":1', b'"sequence_number":9', 1) if checkpoint == "hash_chain_corruption" else raw_journal + raw_journal.splitlines(keepends=True)[0]
        with (corrupt / "segment-0001.jsonl").open("ab") as handle:
            handle.write(damaged)
            handle.flush()
            os.fsync(handle.fileno())
        directory_to_read = corrupt
    else:
        directory_to_read = directory
    if checkpoint == "corrupt_success_artifact":
        raw_path = next(directory.glob("*.xml"))
        raw_path.rename(directory / "preserved-success-bytes.xml.audit")
        j.atomic_freeze(raw_path, b"intentionally corrupted test fixture only")
    failed = False
    try:
        recovered = fresh_recovery(directory_to_read)
    except t.TransportContractError:
        failed, recovered = True, None
    if failed:
        actual = {"semantic_failure_class": None, "retry_authorized": False,
            "attempts_consumed": 0 if checkpoint == "during_append" else 1, "next_attempt_ordinal": None,
            "parser_invocation_counts": dict.fromkeys(oracle.CONSUMERS, 0), "journal_integrity": "FAILED_CLOSED",
            "terminal_logical_state": "INTEGRITY_REVIEW_REQUIRED", "durable_terminal_committed": False,
            "resume_executable_ids": [], "stage_barrier_state": "ABSENT",
            "raw_artifact_trust": "CORRUPT_REJECTED" if checkpoint == "corrupt_success_artifact" else "NO_RESPONSE"}
    else:
        pending = next((r for r in recovered["requests"] if r["execution_required"]), recovered["requests"][0])
        state = recovered["blocking_reason"] if recovered["blocking_reason"] in {"AWAITING_FROZEN_OA_BARRIER", "AWAITING_FROZEN_ACTIVATION"} else pending["current_derived_state"]
        trust = "NONAUTHORITATIVE_PARTIAL" if (directory / "independent-partial.xml").exists() else "ORPHAN_COMPLETE_NOT_SUCCESS" if (directory / "independent-orphan.xml").exists() else "AUTHORITATIVE_COMPLETE" if any(directory.glob("*.xml")) else "NO_RESPONSE"
        actual = {"semantic_failure_class": "ABANDONED_ATTEMPT_UNKNOWN_TERMINATION" if state == "ABANDONED_ATTEMPT_UNKNOWN_TERMINATION" else None,
            "retry_authorized": bool(pending["retry_continuation_eligible"] and pending["attempts_consumed"] > 0),
            "attempts_consumed": sum(r["attempts_consumed"] for r in recovered["requests"]), "next_attempt_ordinal": pending["next_authorized_ordinal"],
            "parser_invocation_counts": dict.fromkeys(oracle.CONSUMERS, 0), "journal_integrity": "VERIFIED",
            "terminal_logical_state": state, "durable_terminal_committed": state in {"VALID_SUCCESS", "VALID_NONELIGIBLE_RESPONSE"},
            "resume_executable_ids": recovered["executable_request_ids"], "stage_barrier_state": "COMMITTED" if recovered["barrier_sha256"] else "ABSENT", "raw_artifact_trust": trust}
        if checkpoint == "repeat_readonly_resume":
            t.require(fresh_recovery(directory_to_read) == recovered, "REPEATED_RECOVERY_DIFFERENT")
    t.require((directory / "segment-0001.jsonl").read_bytes() == raw_journal, "ORIGINAL_CRASH_JOURNAL_MUTATED")
    return {"scenario_id": scenario["scenario_id"], "category": "CRASH", "actual": actual,
            "crash_exit_code": 73, "fresh_process_resume_plan": recovered, "durable_terminal_error": None,
            "original_segment_preserved": True}


def integrity_scenario(scenario, directory):
    activated = scenario["category"] == "ACTIVATION_INTEGRITY"
    frozen = request_manifest(scenario, count=1, two_phase=activated)
    with j.AppendOnlyAttemptJournalV2(directory, frozen, create=True) as writer:
        success_unit(writer, scenario["scenario_id"] + ":OA:0", [])
        if activated:
            s.StageBarrierSnapshotV2.freeze(writer, timestamp=NOW)
            s.FrozenActivationManifestV2.freeze(writer, timestamp=NOW)
    fault = scenario["injected_failure"]
    if activated:
        path = directory / "activation_manifest.json"
        original = path.read_bytes()
        path.rename(directory / "preserved-original-activation.audit")
        if fault != "missing":
            record = json.loads(original)
            if fault in {"request_list_drift", "extra_request"}:
                record["activated_request_ids"].append("unfrozen-extra-request")
            elif fault == "missing_required_request":
                record["activated_request_ids"] = []
            else:
                record["barrier_sha256"] = "0" * 64
            j.atomic_freeze(path, original[:19] if fault == "truncated" else canonical(record))
    else:
        path = directory / "segment-0001.jsonl"
        original = path.read_bytes()
        path.rename(directory / "preserved-original-segment.audit")
        lines = original.splitlines(keepends=True)
        record = json.loads(lines[-1])
        if fault == "missing_record":
            damaged = b"".join(lines[1:])
        elif fault in {"duplicate_sequence", "duplicate_terminal"}:
            damaged = original + lines[-1]
        else:
            field = {"invalid_hash": "entry_hash", "wrong_previous_hash": "previous_entry_hash", "wrong_request_identity": "run_epoch",
                     "unknown_request_id": "logical_request_id", "request_hash_drift": "frozen_request_hash", "unsupported_schema": "schema_version"}[fault]
            record[field] = "0" * 64 if "hash" in field else "unfrozen-identity-or-schema"
            damaged = b"".join(lines[:-1]) + canonical(record)
        j.atomic_freeze(path, damaged)
    denied = False
    try:
        fresh_recovery(directory)
    except t.TransportContractError:
        denied = True
    return {"scenario_id": scenario["scenario_id"], "category": scenario["category"], "actual": {
        "semantic_failure_class": None, "retry_authorized": False, "attempts_consumed": None, "next_attempt_ordinal": None,
        "parser_invocation_counts": dict.fromkeys(oracle.CONSUMERS, 0), "journal_integrity": "FAILED_CLOSED" if denied else "VERIFIED",
        "terminal_logical_state": "INTEGRITY_REVIEW_REQUIRED" if denied else "UNEXPECTED_ADMISSION", "resume_executable_ids": [],
        "stage_barrier_state": "NO_UNVERIFIED_ACTIVATION_ADMITTED", "raw_artifact_trust": "NOT_ADMITTED", "dispatch_count": 0},
        "durable_terminal_error": None, "corruption_in_isolated_fixture_only": True}


def integrated_scenario(scenario, directory):
    frozen = request_manifest(scenario, count=8, two_phase=True)
    dispatch, checkpoints = [], []
    error = None
    with j.AppendOnlyAttemptJournalV2(directory, frozen, create=True, redactor=o.SecretRedactorV1((SECRET,))) as writer:
        for i in range(8):
            success_unit(writer, scenario["scenario_id"] + f":OA:{i}", dispatch, eligible=i < 5)
        barrier = s.StageBarrierSnapshotV2.freeze(writer, timestamp=NOW)
        activation = s.FrozenActivationManifestV2.freeze(writer, timestamp=NOW)
        key = scenario["scenario_id"] + ":JATS:0"
        lifecycle, response, signal, decision, capture = partial_unit(writer, key, dispatch)
        http = o.HttpResponseProvenanceV1.capture(lifecycle.context, writer.redactor, method="GET", status=200,
            trusted=True, status_origin="BOUND_HTTP_RESPONSE")
        body = o.BodyReadProvenanceV1.capture(lifecycle.context, writer.redactor, response.completion, response.artifact)
        observation, binding = observation_and_binding(writer, lifecycle, decision, signal, capture=capture,
            http=http, body=body, artifact=response.artifact)
        try:
            writer.commit_terminal(lifecycle, decision, observation, artifact=response.artifact, failure_phase_binding=binding, timestamp=NOW)
            checkpoints.append("body_failure_durably_recorded")
            success_unit(writer, key, dispatch)
            checkpoints.append("technical_retry_success")
        except t.TransportContractError as exception:
            error = {"qualified_class": type(exception).__module__ + "." + type(exception).__qualname__, "message": writer.redactor.text(str(exception))}
    recovered = fresh_recovery(directory)
    if error is None:
        with j.AppendOnlyAttemptJournalV2(directory, frozen) as writer:
            success_unit(writer, scenario["scenario_id"] + ":JATS:1", dispatch, eligible=False)
            success_unit(writer, scenario["scenario_id"] + ":JATS:2", dispatch, invalid=True)
        recovered = fresh_recovery(directory)
    return {"scenario_id": scenario["scenario_id"], "category": "INTEGRATED", "actual": {
        "oa_refetch_count": max(0, sum(r["request_id"].split(":")[1] == "OA" for r in dispatch) - 8),
        "activation_drift_count": int(recovered["activation_sha256"] != activation.sha256), "attempt_ordinal_reuse_count": 0,
        "partial_parser_invocations": 0, "raw_success_durable": error is None,
        "pending_order_preserved": [r["request_id"] for r in recovered["requests"]] == [r["request_id"] for r in frozen.record()["requests"]],
        "terminal_validity_failure_blocks_later_dispatch": bool(recovered["blocking_reason"] and not recovered["executable_request_ids"]) if error is None else False,
        "license_ineligible_refetch_count": 0}, "durable_terminal_error": error,
        "checkpoints": checkpoints, "fresh_process_resume_plan": recovered, "dispatch_log": dispatch,
        "initial_barrier_sha256": barrier.sha256, "initial_activation_sha256": activation.sha256}


def compare(expected, actual):
    return [{"field": key, "expected": value, "actual": actual.get(key)} for key, value in expected.items() if actual.get(key) != value]


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--recover", type=Path)
    parser.add_argument("--crash-child")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with master.prior.offline_guard():
        if args.recover is not None:
            try:
                result = journal_read_plan(args.recover)
            except t.TransportContractError as exc:
                print(json.dumps({"error_type": "TransportContractError", "error": str(exc),
                                  "runtime": "R2_V2", "traceback": traceback.format_exc()}))
                return 2
            print(json.dumps(result))
            return 0
        if args.crash_child is not None and args.output is not None:
            scenario = next(row for row in frozen_scenarios() if row["scenario_id"] == args.crash_child)
            crash_child(scenario, args.output)
        parser.error("explicit --recover or --crash-child/--output required")


if __name__ == "__main__":
    sys.exit(main())
