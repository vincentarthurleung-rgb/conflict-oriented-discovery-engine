"""22F acceptance: actual bound HTTPResponse, synthetic bytes, no network."""

import http.client
import io
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch
from email.message import Message
from urllib.error import HTTPError

import pytest

from code_engine.acquisition import prospective_transport as tr
from code_engine.acquisition import prospective_workflow as w
from scripts import search_plan_v24_alpha322_length_bound_r2_integration_v1 as fixtures

j, t = w.j, w.t
OA = json.dumps({"esearchresult": {"count": "1", "retstart": "0", "retmax": "1", "idlist": ["123"]}}).encode()
JATS = b'''<article article-type="research-article" xmlns:xlink="http://www.w3.org/1999/xlink">
<front><article-meta><article-id pub-id-type="pmc">PMC123</article-id>
<article-id pub-id-type="pmid">123</article-id><permissions>
<license xlink:href="https://creativecommons.org/licenses/by/4.0/"/></permissions></article-meta></front>
<body><sec><title>Methods</title><p>Synthetic method fixture.</p></sec>
<sec><title>Results</title><p>Synthetic result fixture, not science.</p></sec></body></article>'''


def block_network():
    def forbidden(*args, **kwargs):
        raise AssertionError("REAL_NETWORK_FORBIDDEN")
    socket.socket.connect = forbidden
    socket.socket.connect_ex = forbidden
    socket.create_connection = forbidden
    socket.getaddrinfo = forbidden


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, lambda *a, **k: pytest.fail("REAL_NETWORK_FORBIDDEN"))
    for name in ("create_connection", "getaddrinfo"):
        monkeypatch.setattr(socket, name, lambda *a, **k: pytest.fail("REAL_NETWORK_FORBIDDEN"))


class MemorySocket:
    def __init__(self, raw):
        self.stream = io.BytesIO(raw)

    def makefile(self, mode):
        assert mode == "rb"
        return self.stream


class SyntheticTransport:
    offline = True

    def __init__(self, replies=(OA, JATS), *, headers=(), chunked=False):
        self.replies = list(replies)
        self.headers = headers
        self.calls = 0
        self.responses = []
        self.chunked = chunked

    def open(self, url, *, timeout):
        assert timeout == 60
        self.calls += 1
        reply = self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        if reply in ("partial", "reset"):
            response = http.client.HTTPResponse(fixtures.LocalSocketAdapter(reply))
        else:
            headers = b"".join((k + ": " + v + "\r\n").encode() for k, v in self.headers)
            if self.chunked:
                framed = (b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n" + headers + b"\r\n" +
                          format(len(reply), "x").encode() + b"\r\n" + reply + b"\r\n0\r\n\r\n")
            else:
                framed = (b"HTTP/1.1 200 OK\r\nContent-Length: " + str(len(reply)).encode() +
                          b"\r\n" + headers + b"\r\n" + reply)
            response = http.client.HTTPResponse(MemorySocket(framed))
        response.begin()
        self.responses.append(response)
        return response


class NoDispatch:
    offline = True

    def open(self, *args, **kwargs):
        raise AssertionError("DUPLICATE_OR_UNAUTHORIZED_DISPATCH")


def prepare(directory, *, replay_safe=False, deferred=False, publication_types=None):
    directory.mkdir()
    source = {"source_id": "synthetic-source", "pmid": "123", "pmcid": "PMC123", "doi": None,
        "publication_types": publication_types or ["Journal Article"],
        "correction_relationships": [{"ref_type": "UpdateOf", "linked_pmid": "122", "ref_source": None}] if deferred else [],
        "pre_oa_handoff_state": "PRE_OA_CONDITIONAL_UPDATEOF" if deferred else "PRE_OA_CLEAR",
        "synthetic_fixture_not_fresh_primary": True}
    ref = dict(j.atomic_freeze(directory / "source.json", j.canonical(source)).__dict__)
    manifest = w.build_manifest([ref], run_id="synthetic:22f:offline-acceptance", replay_safe=replay_safe)
    j.atomic_freeze(directory / "input_manifest.json", manifest.serialized)
    return manifest, directory / "journal"


def initialized(directory, manifest):
    writer = j.AppendOnlyAttemptJournalV2(directory, manifest, create=True)
    w.freeze_same(directory / "configuration.json", w.configuration(manifest))
    return writer


def fresh(directory, mode="inspect", manifest=None):
    bootstrap = ("import runpy,sys; m=runpy.run_path(sys.argv[1]); m['block_network'](); "
                 "m['child'](sys.argv[2],sys.argv[3],sys.argv[4])")
    process = subprocess.run([sys.executable, "-c", bootstrap, __file__, str(directory), mode,
                              str(manifest) if manifest else ""], cwd=w.ROOT, capture_output=True, text=True)
    return process


def child(directory, mode, manifest):
    directory = Path(directory)
    if mode == "crash_start":
        frozen = j.FrozenRequestManifestV2(j.read_bytes(Path(manifest)))
        with initialized(directory, frozen) as writer:
            writer.start_attempt(frozen.record()["requests"][0]["request_id"], timestamp=tr.utc())
            os._exit(73)
    elif mode == "crash_terminal":
        frozen = j.FrozenRequestManifestV2(j.read_bytes(Path(manifest)))
        with initialized(directory, frozen) as writer:
            for request in frozen.record()["requests"]:
                if request["stage"] == "JATS":
                    w.barriers.StageBarrierSnapshotV2.freeze(writer, timestamp=tr.utc())
                    w.barriers.FrozenActivationManifestV2.freeze(writer, timestamp=tr.utc())
                token = writer.start_attempt(request["request_id"], timestamp=tr.utc())
                w.commit_capture(writer, tr.capture_once(writer, token, SyntheticTransport((OA if request["stage"] == "OA" else JATS,))))
            os._exit(74)
    elif mode == "resume":
        result = w.resume(directory, transport=NoDispatch())
        print(json.dumps(result))
    elif mode == "continue":
        delays = []
        result = w.resume(directory, transport=SyntheticTransport(), sleep=delays.append)
        print(json.dumps({"index": result, "delays": delays}))
    elif mode == "archive":
        print(json.dumps(w.read_archive(directory)))
    else:
        print(json.dumps(w.inspect(directory)))


def test_a_complete_commit_activation_handoff_archive(tmp_path, record_property):
    chosen = os.environ.get("ALPHA322F_EVIDENCE_DIR")
    root = Path(chosen) if chosen else tmp_path / "complete"
    manifest, directory = prepare(root, deferred=True)
    transport = SyntheticTransport(headers=(("ETag", "first"), ("ETag", "second")))
    index = w.run(directory, manifest, transport=transport)
    assert transport.calls == 2 and all(r.closed for r in transport.responses)
    assert index["handoff"] and index["journal_integrity"] == "VERIFIED"
    assert w.read_archive(directory) == index
    captured = j.strict_json(j.verify_artifact(index["attempts"][1]["capture"]))
    assert captured["representation"] == tr.REPRESENTATION
    assert captured["representation"]["raw_wire_framing_available"] is False
    assert captured["http"]["response_headers"][-2:] == [{"name": "ETag", "value": "first"}, {"name": "ETag", "value": "second"}]
    assert captured["raw_artifact"]["sha256"] == j.sha(JATS)
    process = fresh(directory, "archive")
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == index
    record_property("offline_handoff_passed", bool(index["handoff"]))
    record_property("journal_integrity", index["journal_integrity"])


def test_b_partial_quarantine_no_parsers_or_science(tmp_path, record_property):
    manifest, directory = prepare(tmp_path / "partial")
    transport = SyntheticTransport(("partial",))
    with patch.object(w, "evaluate", side_effect=AssertionError("PARTIAL_PARSER_CALLED")) as parser:
        index = w.run(directory, manifest, transport=transport)
        record_property("partial_parser_invocations", parser.call_count)
    assert transport.calls == 1 and index["handoff"] is None
    capture = j.strict_json(j.verify_artifact(index["attempts"][0]["capture"]))
    assert capture["body"]["completion_state"] == "BODY_INTERRUPTED"
    assert capture["body"]["parser_invoked"] is False and capture["captured_bytes"] == 6
    assert capture["total_received_bytes"] is None
    assert j.verify_artifact(capture["raw_artifact"]) == b"prefix"
    assert w.read_archive(directory) == index


def test_c_actual_validator_false_terminal_no_retry(tmp_path, record_property):
    manifest, directory = prepare(tmp_path / "invalid", replay_safe=True)
    transport = SyntheticTransport((OA, b"<invalid/>", JATS))
    index = w.run(directory, manifest, transport=transport)
    plan = w.inspect(directory)
    assert transport.calls == 2 and plan["requests"][1]["current_derived_state"] == "TERMINAL_RESPONSE_VALIDITY_FAILURE"
    assert plan["requests"][1]["next_authorized_ordinal"] is None and index["handoff"] is None
    assert w.resume(directory, transport=NoDispatch()) == index
    record_property("unauthorized_retries", transport.calls - 2)


def test_d_committed_terminal_fresh_recovery_no_dispatch(tmp_path):
    manifest, directory = prepare(tmp_path / "committed")
    index = w.run(directory, manifest, transport=SyntheticTransport())
    before = j.read_bytes(directory / "segment-0001.jsonl")
    process = fresh(directory, "resume")
    assert process.returncode == 0, process.stderr
    assert json.loads(process.stdout) == index and j.read_bytes(directory / "segment-0001.jsonl") == before


@pytest.mark.parametrize("safe", [False, True])
def test_e_crash_start_consumed_ordinal_existing_recovery(tmp_path, safe):
    manifest, directory = prepare(tmp_path / "abandoned", replay_safe=safe)
    crashed = fresh(directory, "crash_start", directory.parent / "input_manifest.json")
    assert crashed.returncode == 73, crashed.stderr
    process = fresh(directory)
    assert process.returncode == 0, process.stderr
    item = json.loads(process.stdout)["requests"][0]
    assert item["attempts_consumed"] == 1 and item["next_authorized_ordinal"] == (2 if safe else None)
    if safe:
        process = fresh(directory, "continue")
        assert process.returncode == 0, process.stderr
        result = json.loads(process.stdout)
        assert result["delays"] == [2] and result["index"]["handoff"]
        assert w.inspect(directory)["requests"][0]["attempts_consumed"] == 2
    else:
        result = w.resume(directory, transport=NoDispatch())
        assert result["handoff"] is None and w.inspect(directory)["requests"][0]["attempts_consumed"] == 1


def test_f_unsupported_real_client_fails_before_start_or_dispatch(tmp_path, monkeypatch):
    manifest, directory = prepare(tmp_path / "unsupported")
    monkeypatch.setattr(tr.platform, "python_version", lambda: "UNSUPPORTED")
    transport = SyntheticTransport()
    with pytest.raises(t.TransportContractError, match="UNSUPPORTED_BOUND_CLIENT_IDENTITY"):
        w.run(directory, manifest, transport=transport)
    assert transport.calls == 0 and not directory.exists()


@pytest.mark.parametrize("mutation", ["representation", "missing_source", "endpoint", "gate_authority"])
def test_g_unsafe_request_fails_before_dispatch(tmp_path, mutation):
    manifest, directory = prepare(tmp_path / "unsafe")
    record = manifest.record()
    first = record["requests"][0]
    if mutation == "representation":
        first["request_payload"]["length_evidence_contract"]["actual_representation"] = "wire"
    elif mutation == "missing_source":
        first["request_payload"]["source_reference"]["sha256"] = "0" * 64
    elif mutation == "endpoint":
        first["request_payload"]["endpoint"] = "https://untrusted.invalid/"
    else:
        first["eligibility_authority_sha256"] = "0" * 64
    first["request_payload_sha256"] = j.sha(j.canonical(first["request_payload"]))
    altered = j.FrozenRequestManifestV2(j.canonical(record))
    transport = SyntheticTransport()
    with pytest.raises(t.TransportContractError):
        w.run(directory, altered, transport=transport)
    assert transport.calls == 0 and not directory.exists()


def test_h_sensitive_headers_url_exception_redacted_before_persistence(tmp_path):
    manifest, directory = prepare(tmp_path / "redacted")
    secret = "synthetic-credential-never-persist-22f"
    transport = SyntheticTransport(headers=(("Set-Cookie", secret), ("Authorization", "Bearer " + secret), ("X-Echo", secret)))
    index = w.run(directory, manifest, transport=transport, credential_parameters={"api_key": secret})
    assert index["handoff"]
    for path in directory.rglob("*"):
        if path.is_file():
            assert secret.encode() not in path.read_bytes()
    headers = j.strict_json(j.verify_artifact(index["attempts"][0]["capture"]))["http"]
    assert "REDACTED" in headers["request_url_without_secrets"]
    failed_manifest, failed_dir = prepare(tmp_path / "exception-redacted")
    failure = SyntheticTransport((TimeoutError("Authorization: Bearer " + secret),))
    result = w.run(failed_dir, failed_manifest, transport=failure, credential_parameters={"api_key": secret})
    assert result["handoff"] is None
    assert all(secret.encode() not in p.read_bytes() for p in failed_dir.rglob("*") if p.is_file())


def test_i_crash_terminal_before_handoff_idempotent_fresh_recovery(tmp_path):
    manifest, directory = prepare(tmp_path / "terminal-crash")
    crashed = fresh(directory, "crash_terminal", directory.parent / "input_manifest.json")
    assert crashed.returncode == 74, crashed.stderr
    assert not (directory / "handoff.json").exists()
    before = j.read_bytes(directory / "segment-0001.jsonl")
    first = fresh(directory, "resume")
    assert first.returncode == 0, first.stderr
    assert json.loads(first.stdout)["handoff"] and j.read_bytes(directory / "segment-0001.jsonl") == before
    second = fresh(directory, "resume")
    assert second.returncode == 0 and json.loads(second.stdout) == json.loads(first.stdout)


def test_j_handoff_before_gates_and_direct_dispatch_rejected(tmp_path):
    manifest, directory = prepare(tmp_path / "early")
    transport = SyntheticTransport()
    with initialized(directory, manifest) as writer:
        with pytest.raises(t.TransportContractError, match="HANDOFF_REQUIRES"):
            w.freeze_handoff(writer)
        token = writer.start_attempt(manifest.record()["requests"][0]["request_id"], timestamp=tr.utc())
        captured = tr.capture_once(writer, token, transport)
        with pytest.raises(t.TransportContractError, match="ATTEMPT_ALREADY_DISPATCHED"):
            tr.capture_once(writer, token, transport)
        with pytest.raises(t.TransportContractError, match="HANDOFF_REQUIRES"):
            w.freeze_handoff(writer)
        w.commit_capture(writer, captured)
    assert transport.calls == 1 and not (directory / "handoff.json").exists()


@pytest.mark.parametrize("bad", ["license", "identity", "structure", "updateof", "non_oa"])
def test_handoff_excludes_unqualified_source(tmp_path, bad, record_property):
    manifest, directory = prepare(tmp_path / "ineligible")
    raw = JATS
    oa = OA
    if bad == "license":
        raw = JATS.replace(b"https://creativecommons.org/licenses/by/4.0/", b"https://unknown.invalid/license")
    elif bad == "identity":
        raw = JATS.replace(b">PMC123<", b">PMC999<")
    elif bad == "structure":
        raw = JATS.replace(b"<title>Results</title>", b"<title>Other</title>")
    elif bad == "updateof":
        # Frozen metadata with an unresolved non-UpdateOf citation is rejected
        # at the pre-OA boundary, never rescued using scientific content.
        source = j.strict_json(j.read_bytes(directory.parent / "source.json"))
        source["correction_relationships"] = [{"ref_type": "ErratumIn"}]
        ref = dict(j.atomic_freeze(directory.parent / "unresolved.json", j.canonical(source)).__dict__)
        with pytest.raises(t.TransportContractError, match="FROZEN_PRE_OA"):
            w.build_manifest([ref], run_id="synthetic:unresolved")
        return
    elif bad == "non_oa":
        oa = json.dumps({"esearchresult": {"count": "0", "retstart": "0", "retmax": "0", "idlist": []}}).encode()
    transport = SyntheticTransport((oa, raw))
    result = w.run(directory, manifest, transport=transport)
    record_property("unsafe_handoffs", int(bool(result["handoff"])))
    assert result["handoff"] is None and not (directory / "handoff.json").exists()
    assert transport.calls == (1 if bad == "non_oa" else 2)


def test_corrupt_artifact_and_missing_capture_fail_readback(tmp_path):
    manifest, directory = prepare(tmp_path / "tamper")
    result = w.run(directory, manifest, transport=SyntheticTransport())
    capture_ref = result["attempts"][1]["capture"]
    capture_path = Path(capture_ref["artifact_path"])
    with patch.object(j, "read_bytes", side_effect=lambda p: b"corrupt" if Path(p) == capture_path else Path(p).read_bytes()):
        with pytest.raises((t.TransportContractError, ValueError)):
            w.read_archive(directory)
    assert w.read_archive(directory) == result


def test_entrypoint_defaults_no_network_and_requires_explicit_authorization(tmp_path):
    process = subprocess.run([sys.executable, "-m", "scripts.run_search_plan_v24_prospective_acquisition",
        str(tmp_path / "not-created"), "--execute"], cwd=w.ROOT, capture_output=True, text=True)
    assert process.returncode == 2 and "LIVE_NETWORK_NOT_AUTHORIZED" in process.stderr
    assert not (tmp_path / "not-created").exists()
    with pytest.raises(t.TransportContractError, match="LIVE_NETWORK_NOT_AUTHORIZED"):
        tr.UrllibTransport()


@pytest.mark.parametrize("kind,safe,expected_calls,expected_delay", [
    ("http503", True, 3, [2]), ("http503", False, 1, []),
    ("http404", True, 1, []), ("backend", True, 3, [2]), ("unknown", True, 1, [])])
def test_existing_mapping_and_retry_policy_not_replaced(tmp_path, kind, safe, expected_calls, expected_delay):
    manifest, directory = prepare(tmp_path / "policy", replay_safe=safe)
    headers = Message()
    headers["Content-Type"] = "application/xml"
    if kind.startswith("http"):
        first = HTTPError("https://eutils.ncbi.nlm.nih.gov/", int(kind[4:]), "Synthetic failure", headers, io.BytesIO(b"not read"))
    elif kind == "backend":
        first = json.dumps({"esearchresult": {"ERROR": w.backend_policy.BACKEND_PREFIX + " synthetic fixture"}}).encode()
    else:
        first = RuntimeError("timeout-like text is not retry authority")
    transport = SyntheticTransport((first, OA, JATS))
    delays = []
    result = w.run(directory, manifest, transport=transport, sleep=delays.append)
    assert transport.calls == expected_calls and delays == expected_delay
    assert bool(result["handoff"]) is (expected_calls == 3)
    assert w.read_archive(directory) == result


def test_reset_does_not_invent_received_byte_count(tmp_path):
    manifest, directory = prepare(tmp_path / "reset")
    result = w.run(directory, manifest, transport=SyntheticTransport(("reset",)))
    capture = j.strict_json(j.verify_artifact(result["attempts"][0]["capture"]))
    assert capture["captured_bytes"] == 0 and capture["total_received_bytes"] is None
    assert capture["body"]["completion_state"] == "BODY_INTERRUPTED" and result["handoff"] is None


def test_known_secret_in_body_fails_without_persisting_secret_or_handoff(tmp_path):
    manifest, directory = prepare(tmp_path / "body-secret")
    secret = "unique-synthetic-sensitive-value"
    with pytest.raises(t.TransportContractError, match="SECRET_IN_BODY_CAPTURE_DENIED"):
        w.run(directory, manifest, transport=SyntheticTransport((secret.encode(),)), credential_parameters={"api_key": secret})
    assert not (directory / "handoff.json").exists()
    assert all(secret.encode() not in p.read_bytes() for p in directory.rglob("*") if p.is_file())
    assert w.inspect(directory)["requests"][0]["attempts_consumed"] == 1


def test_readback_does_not_create_missing_handoff(tmp_path):
    manifest, directory = prepare(tmp_path / "read-only")
    crashed = fresh(directory, "crash_terminal", directory.parent / "input_manifest.json")
    assert crashed.returncode == 74
    before = {str(p): p.read_bytes() for p in directory.rglob("*") if p.is_file()}
    with pytest.raises(t.TransportContractError, match="EVIDENCE_INDEX_MISSING"):
        w.read_archive(directory)
    assert before == {str(p): p.read_bytes() for p in directory.rglob("*") if p.is_file()}


def test_frozen_attempt_budget_and_backoff_exhaustion(tmp_path):
    manifest, directory = prepare(tmp_path / "budget", replay_safe=True)
    transport = SyntheticTransport(tuple(TimeoutError("synthetic pre-response timeout") for _ in range(4)))
    delays = []
    result = w.run(directory, manifest, transport=transport, sleep=delays.append)
    assert transport.calls == 4 and delays == [2, 4, 8] and result["handoff"] is None
    assert [r["attempt_ordinal"] for r in result["attempts"]] == [1, 2, 3, 4]
    assert w.resume(directory, transport=NoDispatch()) == result


def test_actual_chunk_decoding_not_mislabeled_wire(tmp_path):
    manifest, directory = prepare(tmp_path / "chunked")
    result = w.run(directory, manifest, transport=SyntheticTransport(chunked=True))
    capture = j.strict_json(j.verify_artifact(result["attempts"][1]["capture"]))
    assert result["handoff"] and j.verify_artifact(capture["raw_artifact"]) == JATS
    assert capture["representation"]["byte_representation"] == "decoded"
    assert capture["http"]["transfer_encoding"] == "chunked" and capture["http"]["content_length_raw"] is None


def test_conflicting_length_headers_stop_before_body_admission(tmp_path):
    manifest, directory = prepare(tmp_path / "conflicting-length")
    transport = SyntheticTransport(headers=(("Content-Length", "999"),))
    with patch.object(w, "evaluate", side_effect=AssertionError("UNSAFE_PARSER_CALLED")):
        with pytest.raises(t.TransportContractError, match="CONFLICTING_CONTENT_LENGTH_CAPTURE"):
            w.run(directory, manifest, transport=transport)
    assert transport.calls == 1 and not (directory / "handoff.json").exists()


def test_mutated_gate_companion_cannot_establish_handoff(tmp_path):
    manifest, directory = prepare(tmp_path / "gate-tamper")
    result = w.run(directory, manifest, transport=SyntheticTransport())
    path = Path(result["attempts"][1]["gates"]["artifact_path"])
    gate = j.strict_json(path.read_bytes())
    gate["actual"]["license"]["state"] = "CONSTRUCTION_OA_UNRESOLVED"
    before = (directory / "handoff.json").read_bytes()
    with j.AppendOnlyAttemptJournalV2(directory, manifest) as writer:
        with patch.object(j, "read_bytes", side_effect=lambda p: j.canonical(gate) if Path(p) == path else Path(p).read_bytes()):
            with pytest.raises(t.TransportContractError, match="FROZEN_RAW_ARTIFACT_MISMATCH"):
                w.freeze_handoff(writer)
    assert (directory / "handoff.json").read_bytes() == before
