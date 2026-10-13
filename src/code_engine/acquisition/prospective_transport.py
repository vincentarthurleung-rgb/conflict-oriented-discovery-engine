"""Single-attempt prospective capture; retry/mapping authority stays in 22A/B.

The bound HTTPResponse API exposes transfer-decoded body bytes, NOT a wire
transcript. No text/content decompression, private socket inspection or repair.
"""

from __future__ import annotations

import http.client
import json
import platform
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
import urllib.response
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from code_engine import append_only_attempt_journal_v2_length_bound_v1 as j
from code_engine import transport_failure_phase_binding_v2_r2 as phase
from scripts.run_search_plan_v24_alpha319d_pmc_oa_jats_construction_eligibility import NoRedirect

t, o, b = j.t, j.o, j.b
ROOT = Path(__file__).resolve().parents[3]
HTTPResponse = http.client.HTTPResponse
IncompleteRead = http.client.IncompleteRead
STACK = ROOT / "runs/20261008_search_plan_v24_dev_alpha3_22b_exception_mapping_retry_mapper_offline/bound_transport_stack_inventory.json"
REPRESENTATION = {"byte_representation": "decoded", "interface": "HTTPResponse.read() without amt",
    "transfer_decoded": True, "content_decompressed": False, "text_decoded": False,
    "raw_wire_framing_available": False}
SAFE_HEADERS = frozenset({"content-length", "transfer-encoding", "content-encoding", "content-type",
    "date", "retry-after", "etag", "last-modified", "connection", "server", "vary"})


def utc():
    return datetime.now(timezone.utc).isoformat()


def client_identity():
    """Verify actual files/interpreter, rather than trusting R2's fixed label."""
    saved = j.strict_json(j.read_bytes(STACK))["bound_client_identity"]
    compact = json.dumps(saved, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    j.require(j.sha(compact) == b.BOUND_CLIENT_IDENTITY_SHA256, "UNSUPPORTED_BOUND_CLIENT_IDENTITY")
    modules = (http.client, urllib.request, urllib.error, urllib.response, socket, ssl)
    actual = {"python_version": platform.python_version(),
        "stdlib": [{"module": m.__name__, "source_path": m.__file__,
                    "source_sha256": j.sha(j.read_bytes(Path(m.__file__)))} for m in modules],
        "repository_client_sources": [{**r, "sha256": j.sha(j.read_bytes(ROOT / r["artifact_path"]))}
                                      for r in saved["repository_client_sources"]]}
    j.require(actual == saved, "UNSUPPORTED_BOUND_CLIENT_IDENTITY")
    return {"bound_client_identity_sha256": b.BOUND_CLIENT_IDENTITY_SHA256,
        "actual_stack": actual, "runtime_implementation_sha256": phase.implementation_identity(),
        "prospective_adapter_sha256": j.sha(j.read_bytes(Path(__file__)))}


class UrllibTransport:
    offline = False

    def __init__(self, *, authorize_live_network=False):
        j.require(authorize_live_network is True, "LIVE_NETWORK_NOT_AUTHORIZED")
        self.opener = urllib.request.build_opener(NoRedirect, urllib.request.ProxyHandler({}))

    def open(self, url, *, timeout):
        return self.opener.open(urllib.request.Request(url), timeout=timeout)


@dataclass
class CapturedAttempt:
    lifecycle: t.TransportLifecycleV2
    response: t.FrozenTransportResponseV2 | None
    http: o.HttpResponseProvenanceV1 | None
    body: o.BodyReadProvenanceV1 | None
    exception: BaseException | None
    failure: object | None
    reference: dict


def capture_once(writer, token, transport, *, credential_parameters=None):
    """Require a current durable start; at most ONE opener call, never retry."""
    identity = client_identity()  # Must fail before any dispatch on mismatch.
    j.require(writer.dispatch_authorized(token), "DURABLE_DISPATCH_TOKEN_REQUIRED")
    states, _, _ = j._reduce(writer.verified().events, writer.manifest, writer.directory)
    attempt = states[token.context.logical_request_id]["attempts"][-1]
    j.require(not attempt["progress"], "ATTEMPT_ALREADY_DISPATCHED")
    request = writer.manifest.request(token.context.logical_request_id)
    payload = request["request_payload"]
    j.require(payload["captured_representation"] == REPRESENTATION and
              payload["length_evidence_contract"] == j.lengths.length_contract(t.ByteRepresentation.DECODED),
              "UNSUPPORTED_CAPTURE_REPRESENTATION")
    credentials = credential_parameters or {}
    j.require(all(o.sensitive_key(k) and type(v) is str for k, v in credentials.items())
              and not set(credentials) & set(payload["parameters"]), "UNSAFE_CREDENTIAL_PARAMETERS")
    url = payload["endpoint"] + "?" + urllib.parse.urlencode({**payload["parameters"], **credentials})
    lifecycle = t.TransportLifecycleV2(token.context)
    lifecycle.start_attempt(token.entry_hash, timestamp=utc())
    writer.record_lifecycle(lifecycle, timestamp=utc())
    http = body = response = failure = original = None
    raw = None
    handle = None
    status = None
    expected = None
    http_ref = None
    began = None
    omitted_headers = []

    def facts():
        return b.TransportMappingFactsV2(lifecycle.state, identity["bound_client_identity_sha256"],
            headers_trusted=http is not None, http_status=status,
            http_status_origin="BOUND_HTTP_ERROR" if type(original) is urllib.error.HTTPError else
                               "BOUND_HTTP_RESPONSE" if http is not None else None,
            body_completion=lifecycle.completion)

    def headers(handle, *, error=False):
        nonlocal http, status, expected, http_ref
        if error:
            status = handle.code
            pairs = tuple(handle.headers.raw_items()) if handle.headers is not None else None
        else:
            j.require(type(handle) is HTTPResponse, "UNSUPPORTED_RESPONSE_CLIENT_TYPE")
            status, pairs = handle.status, tuple(handle.getheaders())
        omitted_headers.extend(k for k, _ in pairs or () if k.casefold() not in SAFE_HEADERS and not o.sensitive_key(k))
        pairs = tuple((k, v) for k, v in pairs or () if k.casefold() in SAFE_HEADERS or o.sensitive_key(k)) if pairs is not None else None
        lengths = [v for k, v in pairs or () if k.casefold() == "content-length"]
        expected = int(lengths[0]) if len(lengths) == 1 and lengths[0].isascii() and lengths[0].isdigit() else None
        http = o.HttpResponseProvenanceV1.capture(token.context, writer.redactor, method="GET",
            request_url=url, status=status, reason=handle.reason, headers=pairs,
            expected_length=expected, body_byte_representation="decoded", trusted=True,
            status_origin="BOUND_HTTP_ERROR" if error else "BOUND_HTTP_RESPONSE", headers_received_at=utc())
        http_ref = dict(j.atomic_freeze(writer.directory / ("http-" + token.entry_hash + ".json"), http._serialized).__dict__)
        lifecycle.receive_headers(status, trustworthy=True, evidence_reference=http_ref["sha256"], timestamp=utc())
        writer.record_lifecycle(lifecycle, timestamp=utc())
        j.require(len(set(lengths)) <= 1, "CONFLICTING_CONTENT_LENGTH_CAPTURE")

    try:
        try:
            handle = transport.open(url, timeout=j.POLICY.timeout_seconds)
        except Exception as exc:
            original = exc
            if type(exc) is urllib.error.HTTPError:
                handle = exc
                headers(exc, error=True)
            failure = phase.capture_failure(writer, lifecycle, exc, facts())
        if original is None:
            headers(handle)
            if status != 200:
                failure = phase.capture_failure(writer, lifecycle, None, facts())
            else:
                began = utc()
                lifecycle.start_body(http_ref["sha256"], timestamp=began)
                writer.record_lifecycle(lifecycle, timestamp=utc())
                try:
                    raw = handle.read()
                except Exception as exc:
                    original = exc
                    raw = exc.partial if type(exc) is IncompleteRead else b""
                    failure = phase.capture_failure(writer, lifecycle, exc, facts())
                j.require(type(raw) is bytes, "ACTUAL_BODY_BYTES_REQUIRED")
                j.require(not any(value.encode() in raw for value in writer.redactor._values),
                          "SECRET_IN_BODY_CAPTURE_DENIED")
                interrupted = failure.decision.mapping.semantic_failure_class if failure is not None else None
                completion = t.assess_body_completion(raw, read_returned_normally=original is None,
                    expected_content_length=expected, expected_length_trustworthy=expected is not None,
                    byte_representation=t.ByteRepresentation.DECODED,
                    expected_length_representation=t.ByteRepresentation.WIRE,
                    interruption_class=interrupted, timestamp=utc())
                evidence = failure.record()["occurrence"]["sha256"] if failure is not None else http_ref["sha256"]
                lifecycle.record_body(completion, evidence, timestamp=utc())
                artifact = j.atomic_freeze(writer.directory / ("raw-" + token.entry_hash + ".bin"), raw)
                response = lifecycle.freeze_response(artifact, timestamp=utc())
                writer.record_lifecycle(lifecycle, timestamp=utc())
                body = o.BodyReadProvenanceV1.capture(token.context, writer.redactor, completion,
                                                     artifact, started_at=began, parser_invoked=False)
    finally:
        if handle is not None:
            handle.close()
    record = {"schema_version": "ProspectiveCapturedAttemptV1", "context": token.context.record(),
        "manifest_sha256": writer.manifest.sha256, "start_entry_hash": token.entry_hash,
        "actual_client_identity": identity, "representation": REPRESENTATION,
        "header_capture_scope": "SAFE_ALLOWLIST_AND_REDACTED_SENSITIVE_HEADERS",
        "omitted_header_names": omitted_headers,
        "http": http.record() if http is not None else None, "http_reference": http_ref,
        "body": body.record() if body is not None else None,
        "raw_artifact": dict(response.artifact.__dict__) if response is not None else None,
        "captured_bytes": len(raw) if raw is not None else None,
        "total_received_bytes": len(raw) if raw is not None and original is None else None,
        "unavailable_reason": None if raw is not None and original is None else
                              "CLIENT_DOES_NOT_EXPOSE_TOTAL_RECEIVED_BYTES" if raw is not None else
                              "NON_ACCEPTED_STATUS_BODY_NOT_READ" if status is not None else "NO_BODY_RETURNED_BY_CLIENT",
        "failure_occurrence": failure.record() if failure is not None else None}
    clean, _ = writer.redactor.tree(record)
    reference = dict(j.atomic_freeze(writer.directory / ("capture-" + token.entry_hash + ".json"), j.canonical(clean)).__dict__)
    return CapturedAttempt(lifecycle, response, http, body, original, failure, reference)
