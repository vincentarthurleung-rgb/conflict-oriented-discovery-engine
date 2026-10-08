"""Offline authority/quarantine tests, not retrospective scientific processing."""

import http.client
import socket
import urllib.error
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from scripts import run_search_plan_v24_alpha321d21_runtime_failure_audit_offline as a


@pytest.fixture(autouse=True)
def forbid_network_scientific_processing_and_request_regeneration(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("NETWORK_PARSER_OR_NEW_REQUEST_FORBIDDEN")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(a.d2.identity, "select_primary_article", forbidden)
    monkeypatch.setattr(a.d2.identity, "validate_jats_primary_identity_v2", forbidden)
    monkeypatch.setattr(a.d2.body, "canonical_body", forbidden)
    monkeypatch.setattr(a.d2.legacy.frozen_rules, "canonical_jats", forbidden)
    monkeypatch.setattr(a.d2.legacy.source_policy, "build_construction_document", forbidden)
    monkeypatch.setattr(a.d2.d1.d, "requests_for", forbidden)
    monkeypatch.setattr(a.d2, "execute_oa", forbidden)
    monkeypatch.setattr(a.d2, "execute_jats", forbidden)


@pytest.fixture
def synthetic_run_dir():
    # Frozen adapter emits repository-relative provenance, so keep only this
    # synthetic disposable directory inside runs; never touch frozen directories.
    with TemporaryDirectory(prefix="alpha321d21_synthetic_", dir=a.ROOT / "runs") as path:
        yield Path(path)


@pytest.fixture
def snapshot():
    # Do not preflight with identity/canonicalizer monkeypatched: its source-hash
    # verification deliberately fails on altered callables. These read-only
    # data readers need no parser or network and have no scientific interpretation.
    attempts = a.rows(a.d2.OUT / "jats_request_attempt_log.jsonl")
    activation = a.obj(a.d2.OUT / "alpha3_21d2_jats_activation_manifest.json")
    requests = a.rows(a.d2.d1.REQUESTS)
    structural = a.rows(a.d2.OUT / "jats_structural_states.jsonl")
    rec = a.reconstruct(activation["requests"], requests, attempts, structural, 4)
    return {"attempts": attempts, "activation": activation, "requests": requests,
            "structural": structural, "rec": rec}


def test_exact_persisted_IncompleteRead_has_unresolved_module_chain_and_retry_authority(snapshot):
    failed_attempt = snapshot["rec"]["failed_attempts"][0]
    facts = a.persisted_exception_facts(failed_attempt)
    assert facts["observed_exception_name"] == "IncompleteRead"
    assert facts["observed_exception_message"] == "IncompleteRead(188590 bytes read)"
    assert facts["observed_exception_module"] is None
    assert facts["observed_qualified_exception_class"] is None
    assert facts["cause_chain"] is facts["context_chain"] is facts["traceback"] is None
    assert facts["actual_HTTP_response_status"] is None
    assert facts["logged_HTTP_status"] is None
    assert facts["local_candidate_demonstration"]["message_matches"]
    assert not facts["local_candidate_demonstration"]["matches_frozen_generic_exception_tuple"]
    policy = a.obj(a.d2.D / "alpha3_21d_technical_retry_policy.json")
    historical = a.obj(a.ROOT / policy["source"]["artifact_path"])
    jats = a.obj(a.d2.legacy.prereg.OUT / "pmc_jats_acquisition_contract.json")
    result = a.retry_scope(policy, historical, jats, facts)
    assert result["classification"] == a.CLASS_C
    assert result["primary_classification_count"] == 1
    assert result["coverage_state"] == "NOT_ESTABLISHED_NEITHER_COVERED_NOR_PROVEN_EXCLUDED"
    assert not result["runtime_recovery_within_same_primary_attempt_allowed"]
    assert not result["runtime_exception_mapping_defect"]


def test_partial_frozen_response_is_quarantined_without_any_parser(snapshot):
    attempt = snapshot["rec"]["failed_attempts"][0]
    raw = a.d2.OUT / attempt["raw_path"]
    assert raw.stat().st_size == 188590
    assert a.digest(raw) == attempt["raw_sha256"]
    for name in ("jats_structural_states", "jats_direct_identifier_extraction", "jats_primary_identity_states_v2",
                 "jats_license_states", "canonical_body_states", "canonical_body_manifest"):
        assert not any(r.get("pmid") == attempt["pmid"] for r in a.rows(a.d2.OUT / (name + ".jsonl")))
    handoff = a.obj(a.d2.OUT / "alpha3_21e_construction_source_handoff.json")
    assert not any(r["pmid"] == attempt["pmid"] for r in handoff["sources"])
    exposure = a.obj(a.d2.OUT / "alpha3_21_current_attempt_fulltext_exposure_registry.json")
    observation = exposure["untrusted_observations"][0]
    assert observation["logical_request_id"] == attempt["logical_request_id"]
    assert observation["authoritative_identity"] is False
    assert observation["canonical_future_source_identity"] is None


def test_synthetic_stdlib_candidate_escapes_frozen_catch_without_scientific_parsing(monkeypatch):
    # Synthetic candidate only: no assertion that its module was recorded in D2.
    partial = b"synthetic truncated body"
    error = http.client.IncompleteRead(partial)
    opened, persisted, writes = [], [], []

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            raise error

    class FakeOpener:
        def open(self, request, timeout):
            opened.append((request.full_url, timeout))
            return Response()

    monkeypatch.setattr(a.d2.legacy.urllib.request, "build_opener", lambda *args: FakeOpener())
    monkeypatch.setattr(a.d2.legacy.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(a.d2.legacy, "write_bytes", lambda *args: writes.append(args))
    monkeypatch.setattr(a.d2.legacy, "append_jsonl", lambda *args: persisted.append(args))
    client = a.d2.legacy.PMCTransport(attempts_max=4, timeout=60, backoff=(2, 4, 8))
    with pytest.raises(http.client.IncompleteRead) as caught:
        client.fetch("PMC_JATS", 1, "synthetic", a.d2.legacy.EF,
                     {"db": "pmc", "id": "1", "retmode": "xml"}, "unused_synthetic_only")
    assert caught.value is error
    assert caught.value.partial == partial
    assert client.calls == len(opened) == 1
    assert writes == persisted == []  # Historical handler was never reached.


def test_synthetic_candidate_adapter_preserves_partial_and_does_not_retry(monkeypatch, synthetic_run_dir, snapshot):
    tmp_path = synthetic_run_dir
    partial = b"synthetic partial NOT original primary JATS"
    error = http.client.IncompleteRead(partial)
    calls = []

    class RaisingClient:
        def __init__(self):
            self.calls = 0

        def fetch(self, *args):
            self.calls += 1
            calls.append(args)
            raise error

    # No real transport instantiated; reuse adapter only for synthetic quarantine.
    adapter = object.__new__(a.d2.FrozenTransportAdapter)
    adapter.client = RaisingClient()
    adapter.attempts, adapter.executed, adapter.current = [], set(), None
    monkeypatch.setattr(a.d2, "OUT", tmp_path)
    a.d2.put("oa_phase_completion_barrier.json", {"all_49_terminal_states_frozen": True})
    a.d2.put_rows("oa_source_states.jsonl", [])
    a.d2.mark("oa_source_states", a.digest(tmp_path / "oa_source_states.jsonl"))
    a.d2.freeze("alpha3_21d2_jats_activation_manifest", snapshot["activation"])
    with pytest.raises(http.client.IncompleteRead):
        adapter.fetch(snapshot["rec"]["failed"], 10)
    attempts = a.rows(tmp_path / "jats_request_attempt_log.jsonl")
    assert len(attempts) == len(calls) == 1
    assert attempts[0]["unhandled_frozen_client_exception"]
    assert attempts[0]["transport_attempt_state"] == "TERMINAL_UNHANDLED_FROZEN_CLIENT_EXCEPTION"
    assert (tmp_path / attempts[0]["raw_path"]).read_bytes() == partial
    assert not (tmp_path / "jats_structural_states.jsonl").exists()


def test_adding_candidate_catch_cannot_alone_make_HTTP_200_read_error_retryable(monkeypatch):
    # Reproduce the existing mapped read-error predicate, not a new mapping.
    observed = []

    class ReadErrorResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            raise TimeoutError("synthetic read interruption")

    class FakeOpener:
        def open(self, request, timeout):
            observed.append(request.full_url)
            return ReadErrorResponse()

    monkeypatch.setattr(a.d2.legacy.urllib.request, "build_opener", lambda *args: FakeOpener())
    monkeypatch.setattr(a.d2.legacy.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(a.d2.legacy, "write_bytes", lambda *args: None)
    monkeypatch.setattr(a.d2.legacy, "append_jsonl", lambda *args: None)
    client = a.d2.legacy.PMCTransport(attempts_max=4, timeout=60, backoff=(2, 4, 8))
    raw, attempts = client.fetch("PMC_JATS", 1, "synthetic", a.d2.legacy.EF,
                                 {"db": "pmc", "id": "1", "retmode": "xml"}, "unused_synthetic_only")
    assert raw is None
    assert len(observed) == len(attempts) == 1
    assert attempts[0]["http_status"] == 200
    assert attempts[0]["transport_error"] == "TimeoutError:synthetic read interruption"


def test_hypothetical_ordinal_continuity_and_budget_arithmetic(snapshot):
    rec = snapshot["rec"]
    assert rec["failed"]["pmid"] == "42731998"
    assert [r["attempt"] for r in rec["failed_attempts"]] == [1]
    assert rec["hypothetical_next_attempt"] == 2
    assert rec["remaining_attempts"] == 3
    assert rec["conditional_additional_ceiling"] == 3 + 37 * 4 == 151
    assert len(snapshot["attempts"]) + len(a.rows(a.d2.OUT / "oa_request_attempt_log.jsonl")) + 151 == 217


def test_diagnostic_order_excludes_successful_jats_and_preserves_all_untouched_requests(snapshot):
    rec = snapshot["rec"]
    diagnostic = rec["hypothetical_original_order_ids"]
    assert not set(rec["successful_ids"]) & set(diagnostic)
    assert len(rec["successful_ids"]) == 9
    assert len(diagnostic) == 38
    assert diagnostic[0] == rec["failed"]["logical_request_id"]
    assert diagnostic[1:] == [r["logical_request_id"] for r in rec["active"][10:]]
    assert diagnostic == [r["logical_request_id"] for r in rec["active"][9:]]


def test_no_oa_request_in_diagnostic_continuation_universe(snapshot):
    rec = snapshot["rec"]
    by_id = {r["logical_request_id"]: r for r in snapshot["requests"]}
    assert all(by_id[key]["request_class"] == "PMC_JATS" for key in rec["hypothetical_original_order_ids"])
    oa = {r["logical_request_id"] for r in snapshot["requests"] if r["request_class"] == "PMC_OA_SUBSET"}
    assert not oa & set(rec["hypothetical_original_order_ids"])


def test_request_identity_or_order_change_fails_closed(snapshot):
    changed = deepcopy(snapshot["activation"]["requests"])
    changed[10], changed[11] = changed[11], changed[10]
    with pytest.raises(Exception, match="ACTIVATION_ORDER"):
        a.reconstruct(changed, snapshot["requests"], snapshot["attempts"], snapshot["structural"], 4)
    changed = deepcopy(snapshot["attempts"])
    changed[-1]["attempt"] = 2
    with pytest.raises(Exception, match="NONCONTIGUOUS"):
        a.reconstruct(snapshot["activation"]["requests"], snapshot["requests"], changed, snapshot["structural"], 4)
    changed = deepcopy(snapshot["attempts"])
    changed[-1]["parameters"]["id"] = "different"
    with pytest.raises(Exception, match="BINDING_MISMATCH"):
        a.reconstruct(snapshot["activation"]["requests"], snapshot["requests"], changed, snapshot["structural"], 4)


def test_complete_audit_is_nonexecutable_append_only_and_no_source_replacement(monkeypatch, tmp_path):
    # Remove synthetic parser monkeypatches before preflight's callable hash checks.
    # Real parsing is prohibited separately by ET.fromstring/parse spies below.
    monkeypatch.undo()
    def forbidden(*args, **kwargs):
        raise AssertionError("ACTUAL_NETWORK_PARSING_OR_EXECUTION_FORBIDDEN")
    monkeypatch.setattr(a.d2.ET, "fromstring", forbidden)
    monkeypatch.setattr(a.d2.ET, "parse", forbidden)
    monkeypatch.setattr(a.d2.d1.d, "requests_for", forbidden)
    monkeypatch.setattr(a.d2, "execute_oa", forbidden)
    monkeypatch.setattr(a.d2, "execute_jats", forbidden)
    before = a.root_hash(a.d2.OUT, a.d2.ROOT_MARKER)
    request_bytes = a.d2.d1.REQUESTS.read_bytes()
    monkeypatch.setattr(a, "OUT", tmp_path / "audit")
    result = a.run()
    assert result["status"] == "completed"
    assert result["alpha3_21d21_classification"] == a.CLASS_C
    assert all(result[k] == 0 for k in a.NO_CALLS)
    assert result["maximum_additional_transport_attempts"] is None
    assert result["maximum_final_cumulative_transport_attempts"] is None
    assert not result["runtime_recovery_within_same_primary_attempt_allowed"]
    assert a.root_hash(a.OUT, a.ROOT_MARKER) == result[a.ROOT_MARKER]
    assert all((a.OUT / (stem + ".json")).is_file() for stem in a.REQUIRED)
    assert not any((a.OUT / name).exists() for name in a.A_ONLY)
    for stem in ("continuation_order_contract", "continuation_resume_point_contract", "continuation_transport_budget"):
        assert a.obj(a.OUT / (stem + ".json"))["executable"] is False
    assert a.obj(a.OUT / "blocked_jats_semantics_audit.json")["pending_source_count"] == 38
    assert result["final_construction_source_count"] == "NOT_DERIVED"
    assert not result["alpha3_21e_handoff_eligible"]
    assert a.root_hash(a.d2.OUT, a.d2.ROOT_MARKER) == before == a.D2_SHA
    assert a.d2.d1.REQUESTS.read_bytes() == request_bytes
    with pytest.raises(Exception, match="D21_OUTPUT_ALREADY_EXISTS"):
        a.run()


def test_integrity_failure_stops_before_downstream_audit(monkeypatch, tmp_path):
    def failure(*args):
        raise RuntimeError("ARTIFACT_ROOT_MISMATCH:synthetic")
    monkeypatch.setattr(a, "root_check", failure)
    monkeypatch.setattr(a, "OUT", tmp_path / "integrity_failure")
    result = a.run()
    assert result["status"] == "failed"
    assert result["alpha3_21d21_classification"] == a.CLASS_INTEGRITY
    assert result["next_stage_recommendation"] == a.NEXT_INTEGRITY
    assert not result["runtime_recovery_within_same_primary_attempt_allowed"]
    assert all(result[k] == 0 for k in a.NO_CALLS)
    assert not any((a.OUT / name).exists() for name in a.A_ONLY)
