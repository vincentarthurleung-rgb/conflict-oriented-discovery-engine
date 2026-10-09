# R2 mechanical version fork; original R1 remains byte-frozen.
"""Explicit offline V2 controller fixtures and fresh-process read-only entrypoint.

Not an acquisition client. No sockets, sleeps, scientific input, or dispatch.
Actual HTTPResponse reads are supplied only by an in-memory file adapter.
"""

import argparse
import http.client
import io
import json
import os
import subprocess
import sys
from pathlib import Path

from code_engine import append_only_attempt_journal_v2_r2 as j
from code_engine import deterministic_resume_planner_v2_r2 as p
from code_engine import transport_failure_phase_binding_v2_r2 as f
from scripts import run_search_plan_v24_alpha322r0_phase_binding_repair_design_offline as r0

t, o, b = j.t, j.o, j.b
ROOT = f.ROOT
NOW = "2000-01-01T00:00:00Z"


def manifest(keys=("repair:OA:0",), *, safe=True, two_phase=False):
    requests = []
    for key in keys:
        stage = "JATS" if ":JATS:" in key else "OA"
        payload = {"opaque_synthetic_identity": key, "route": "offline:" + stage}
        if stage == "JATS":
            payload["oa_request_id"] = key.replace(":JATS:", ":OA:")
        requests.append({"request_id": key, "request_payload": payload,
            "request_payload_sha256": j.sha(j.canonical(payload)), "stage": stage, "execution_order": len(requests),
            "replay_safe": safe, "maximum_attempts": 4,
            "validity_authority_sha256": j.sha(b"synthetic complete response validator"),
            "eligibility_authority_sha256": j.sha(b"synthetic fixture boolean; not source eligibility")})
    return j.FrozenRequestManifestV2(j.canonical({"schema_version": "FrozenRequestManifestV2",
        "run_id": "synthetic:repair-validation", "run_epoch": "epoch-1", "stage_id": "synthetic:OA-JATS",
        "authority": j.AUTHORITY, "runtime_v2_implementation_manifest_sha256": f.implementation_identity(),
        "activation_contract_sha256": j.sha(b"activate JATS iff frozen parent OA terminal VALID_SUCCESS"),
        "requests": requests}))


def start(writer, key="repair:OA:0"):
    token = writer.start_attempt(key, timestamp=NOW)
    j.require(writer.dispatch_authorized(token), "WRITE_AHEAD_ACK_REQUIRED")
    lifecycle = t.TransportLifecycleV2(token.context)
    lifecycle.start_attempt(token.entry_hash, timestamp=NOW)
    writer.record_lifecycle(lifecycle, timestamp=NOW)
    return lifecycle


class LocalReadFile(io.BytesIO):
    def __init__(self, mode):
        self.mode = mode
        super().__init__(b"HTTP/1.1 200 OK\r\nContent-Length: 20\r\n\r\n" + (b"prefix" if mode == "partial" else b""))

    def read(self, size=-1):
        if self.mode == "reset":
            raise ConnectionResetError("synthetic body failure")
        return super().read(size)


class LocalSocketAdapter:
    def __init__(self, mode):
        self.file = LocalReadFile(mode)

    def makefile(self, mode):
        assert mode == "rb"
        return self.file


def failed_attempt(writer, lifecycle, *, mode="reset", commit=True):
    """Capture in the except block at actual phase, before any state advance."""
    response, raw, http_provenance, body = None, b"", None, None
    exception = None
    if mode != "unknown":
        local = http.client.HTTPResponse(LocalSocketAdapter(mode))
        local.begin()
        lifecycle.receive_headers(local.status, trustworthy=True, evidence_reference="synthetic:local-headers", timestamp=NOW)
        writer.record_lifecycle(lifecycle, timestamp=NOW)
        lifecycle.start_body("synthetic:actual-local-HTTPResponse.read", timestamp=NOW)
        writer.record_lifecycle(lifecycle, timestamp=NOW)
        try:
            local.read()
            raise AssertionError("EXPECTED_ACTUAL_READ_FAILURE")
        except (ConnectionResetError, http.client.IncompleteRead) as exc:
            exception = exc
            raw = exc.partial if type(exc) is http.client.IncompleteRead else b""
            facts = b.TransportMappingFactsV2(lifecycle.state, b.BOUND_CLIENT_IDENTITY_SHA256,
                headers_trusted=True, http_status=200, http_status_origin="BOUND_HTTP_RESPONSE")
            capture = f.capture_failure(writer, lifecycle, exc, facts)
        finally:
            # Only the local in-memory HTTPResponse fixture is closed here.
            # Capture remains inside except, before any lifecycle progression.
            # Do not leave traceback cycles to finalize the response/file in an
            # arbitrary order; no warning filter or transport-policy change.
            local.close()
        completion = t.assess_body_completion(raw, read_returned_normally=False,
            expected_content_length=20, expected_length_trustworthy=True,
            expected_length_representation=t.ByteRepresentation.WIRE,
            interruption_class=capture.decision.mapping.semantic_failure_class,
            interruption_reason="actual synthetic bound read failure", timestamp=NOW)
        lifecycle.record_body(completion, capture.record()["occurrence"]["sha256"], timestamp=NOW)
        writer.record_lifecycle(lifecycle, timestamp=NOW)
        artifact = j.atomic_freeze(writer.directory / ("raw-" + str(lifecycle.context.attempt_ordinal) + ".xml"), raw)
        response = lifecycle.freeze_response(artifact, timestamp=NOW)
        writer.record_lifecycle(lifecycle, timestamp=NOW)
        http_provenance = o.HttpResponseProvenanceV1.capture(lifecycle.context, writer.redactor, method="GET", status=200,
            trusted=True, status_origin="BOUND_HTTP_RESPONSE", expected_length=20,
            headers=(("Content-Length", "20"),))
        body = o.BodyReadProvenanceV1.capture(lifecycle.context, writer.redactor, completion, artifact, parser_invoked=False)
    else:
        try:
            raise RuntimeError("timeout-like text confers no retry authority")
        except RuntimeError as exc:
            exception = exc
            facts = b.TransportMappingFactsV2(lifecycle.state, b.BOUND_CLIENT_IDENTITY_SHA256)
            capture = f.capture_failure(writer, lifecycle, exc, facts)
        artifact = None
    request = writer.manifest.request(lifecycle.context.logical_request_id)
    observation = b.mapped_observation_v2(capture.decision, lifecycle, writer.redactor, original_exception=exception,
        http=http_provenance, body=body, runtime_identity=capture.runtime_identity.record(),
        replay_safety_authority={"manifest_sha256": writer.manifest.sha256, "request_id": request["request_id"]} if request["replay_safe"] else None)
    binding = f.bind_failure(writer, lifecycle, capture, observation, artifact)
    item = {"lifecycle": lifecycle, "decision": capture.decision, "observation": observation,
            "artifact": artifact, "binding": binding, "capture": capture, "response": response,
            "exception": exception, "parser_invocations": 0, "retry_dispatches": 0}
    if commit:
        commit_failure(writer, item)
    return item


def commit_failure(writer, item):
    return writer.commit_terminal(item["lifecycle"], item["decision"], item["observation"], artifact=item["artifact"],
        failure_phase_binding=item["binding"], timestamp=NOW)


def success(writer, lifecycle, *, eligible=True):
    lifecycle.receive_headers(200, trustworthy=True, evidence_reference="synthetic:local-headers", timestamp=NOW)
    lifecycle.start_body("synthetic:local-body", timestamp=NOW)
    raw = b"<synthetic/>"
    completion = t.assess_body_completion(raw, read_returned_normally=True, expected_content_length=len(raw),
        expected_length_trustworthy=True, expected_length_representation=t.ByteRepresentation.WIRE, timestamp=NOW)
    lifecycle.record_body(completion, "synthetic:complete-body", timestamp=NOW)
    artifact = j.atomic_freeze(writer.directory / (lifecycle.context.logical_request_id.replace(":", "-") + ".xml"), raw)
    lifecycle.freeze_response(artifact, timestamp=NOW)
    request = writer.manifest.request(lifecycle.context.logical_request_id)
    lifecycle.record_validation(valid=True, evidence_reference=request["validity_authority_sha256"], timestamp=NOW)
    writer.record_lifecycle(lifecycle, timestamp=NOW)
    decision = b.classify_transport_failure_and_decide_retry_v2(None, b.TransportMappingFactsV2(lifecycle.state,
        b.BOUND_CLIENT_IDENTITY_SHA256, headers_trusted=True, http_status=200, http_status_origin="BOUND_HTTP_RESPONSE", body_completion=completion),
        request_replay_safe=request["replay_safe"], attempt_ordinal=lifecycle.context.attempt_ordinal)
    http = o.HttpResponseProvenanceV1.capture(lifecycle.context, writer.redactor, method="GET", status=200, trusted=True, status_origin="BOUND_HTTP_RESPONSE")
    body = o.BodyReadProvenanceV1.capture(lifecycle.context, writer.redactor, completion, artifact, parser_invoked=False)
    observation = b.mapped_observation_v2(decision, lifecycle, writer.redactor, http=http, body=body,
        replay_safety_authority={"manifest_sha256": writer.manifest.sha256, "request_id": request["request_id"]} if request["replay_safe"] else None)
    writer.commit_terminal(lifecycle, decision, observation, artifact=artifact,
        validation={"authority_sha256": request["validity_authority_sha256"], "accepted": True},
        eligibility={"authority_sha256": request["eligibility_authority_sha256"], "eligible": eligible}, timestamp=NOW)


def read_plan(directory):
    manifest_v2 = j.FrozenRequestManifestV2(j.read_bytes(Path(directory) / "request_manifest.json"))
    return p.DeterministicResumePlannerV2().build(j.JournalIntegrityVerifierV2.read(directory, manifest_v2)).record()


def fresh_plan(directory):
    process = subprocess.run([sys.executable, "-m", __name__, "--inspect", str(directory)], cwd=ROOT,
                             capture_output=True, text=True, check=False)
    j.require(process.returncode == 0, "FRESH_V2_READER_FAILED:" + process.stderr)
    return json.loads(process.stdout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inspect")
    parser.add_argument("--crash-before-terminal")
    args = parser.parse_args()
    with r0.d.master.prior.offline_guard():
        if args.inspect:
            print(json.dumps(read_plan(args.inspect), sort_keys=True))
        elif args.crash_before_terminal:
            writer = j.AppendOnlyAttemptJournalV2(Path(args.crash_before_terminal), manifest(), create=True)
            failed_attempt(writer, start(writer), commit=False)
            os._exit(73)  # real isolated process termination, not a synthetic reducer state
        else:
            parser.error("explicit offline operation required")


if __name__ == "__main__":
    main()
