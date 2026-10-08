"""Offline C2 orchestration tests; no external requests or actual metadata."""

import json
import socket
import urllib.error
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from scripts import run_search_plan_v24_alpha321c2_metadata_execution as s


def forbid_network(*args, **kwargs):
    raise AssertionError("TEST_NETWORK_FORBIDDEN")


class SyntheticTransport:
    def __init__(self, policy):
        assert s.obj(s.OUT / "metadata_pre_network_integrity_barrier.json")["passed"]
        self.calls = 0
        self.order = []
        self.history = []
        self.policy = policy

    def fetch(self, request):
        ordinal = request["execution_ordinal"]
        pmid = request["sampled_pmids"][0]
        self.order.append(pmid)
        assert self.policy["timeout_seconds"] == 60
        kwargs = {"pmid": pmid, "pmcid": "PMC" + pmid, "doi": "10.fixture/" + pmid}
        if ordinal in (1, 2):
            kwargs["doi"] = "10.fixture/shared"
        if ordinal == 3:
            kwargs["relationships"] = '<CommentsCorrectionsList><CommentsCorrections RefType="UpdateOf"><PMID>999</PMID></CommentsCorrections></CommentsCorrectionsList>'
        if ordinal == 5:
            kwargs["pubdate"] = "<Year>2026</Year>"
        if ordinal == 6:
            kwargs["pmcid"] = None
        if ordinal == 7:
            kwargs["pmcid"] = s.preflight()["canonical_aliases"]["pmcid"]["canonical_values"][0]
        raw = s.authority.synthetic_xml(**kwargs)
        if ordinal == 8:
            raw = b"<ERROR>backend error</ERROR>"
        if ordinal == 9:
            raw = s.authority.synthetic_xml(pmid="123")
        if ordinal == 10:
            raw = raw.replace(b"</ArticleIdList>", b'<ArticleId IdType="doi">10.fixture/second</ArticleId></ArticleIdList>')
        codes = [429, 200] if ordinal == 1 else [500] * 4 if ordinal == 4 else [200]
        history = []
        for number, code in enumerate(codes, 1):
            self.calls += 1
            body = raw if code == 200 else b"synthetic transport error"
            name = f"sampled_metadata_raw_responses/{ordinal:03d}_{pmid}_attempt{number}.bin"
            raw_sha = s.put_bytes(name, body)
            history.append({"sample_ordinal": ordinal, "pmid": pmid, "attempt": number,
                "method": request["method"], "endpoint": request["endpoint"], "parameters": request["parameters"],
                "url": "synthetic_offline_not_network", "timestamp_utc": "2026-10-06T00:00:00+00:00",
                "http_status": code, "transport_error": None if code == 200 else "HTTPError",
                "raw_path": name, "raw_sha256": raw_sha, "raw_bytes": len(body)})
        self.history.extend(history)
        return (raw if codes[-1] == 200 else None), history


def test_complete_two_pass_execution_with_isolated_failures_and_frozen_barriers(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", forbid_network)
    monkeypatch.setattr(socket, "create_connection", forbid_network)
    upstream = [(s.C1, s.authority.ROOT_MARKER), (s.C, s.authority.c.ROOT_MARKER),
                (s.B, "search_plan_v24_primary_alpha3_21b_sha256")]
    before = {str(path): s.root_hash(path, marker) for path, marker in upstream}
    original_parse = s.v2.parse_source
    original_graph = s.v2.collision_components

    def guarded_parse(raw, pmid, *args):
        persisted = s.rows(s.OUT / "metadata_raw_response_manifest.jsonl")
        assert any(a["sampled_pmid"] == pmid and a["raw_response_sha256"] == s.sha(raw) for a in persisted)
        return original_parse(raw, pmid, *args)

    def guarded_graph(records):
        assert s.obj(s.OUT / "metadata_identity_freeze_before_collision_analysis.json")["all_72_logical_requests_terminal"]
        assert len(s.rows(s.OUT / "metadata_first_pass_source_facts.jsonl")) == 72
        assert len(s.rows(s.OUT / "metadata_per_source_response_terminal_states.jsonl")) == 72
        return original_graph(records)

    monkeypatch.setattr(s.v2, "parse_source", guarded_parse)
    monkeypatch.setattr(s.v2, "collision_components", guarded_graph)
    with TemporaryDirectory(prefix="alpha321c2_test_", dir=s.ROOT / "runs") as task_tmp:
        monkeypatch.setattr(s, "OUT", Path(task_tmp) / "output")
        result = s.run(SyntheticTransport)
        assert result["status"] == "completed", result
        assert result["metadata_logical_requests_executed"] == 72
        assert result["metadata_transport_attempts"] == 76
        assert result["metadata_technical_retry_count"] == 4
        assert result["metadata_valid_response_count"] == 69
        assert result["metadata_terminal_failure_count"] == 3
        assert result["same_attempt_collision_component_count"] == 1
        assert result["same_attempt_collision_source_count"] == 2
        assert result["single_record_identifier_conflict_count"] == 1
        assert result["historical_pmcid_contaminated_count"] == 1
        assert result["pre_oa_conditional_deferred_count"] == 1
        assert result["current_attempt_aliases_self_exclude"] is False
        assert result["downstream_replacement_used"] is False
        assert all(result[k] == 0 for k in s.ZERO_CALLS)
        facts = s.rows(s.OUT / "metadata_first_pass_source_facts.jsonl")
        assert all("same_attempt_alias_collision_state" not in f and "pre_oa_handoff_state" not in f for f in facts)
        final = s.rows(s.OUT / "metadata_final_source_states.jsonl")
        assert final[3]["primary_terminal_reason"] == "METADATA_TERMINAL_FAILURE"
        assert final[4]["date_resolution_state"] == s.v2.DATE_PARTIAL
        assert final[5]["metadata_state"] == "UNRESOLVED"
        assert final[9]["pre_oa_handoff_state"] == "BLOCKED"
        assert len(s.obj(s.OUT / "alpha3_21_current_attempt_metadata_identity_exposure_registry.json")["source_identities"]) == 69
        assert s.root_hash(s.OUT, s.ROOT_MARKER) == result[s.ROOT_MARKER]
        with pytest.raises(Exception, match="NO_RERUN"):
            s.run(SyntheticTransport)
    assert {str(path): s.root_hash(path, marker) for path, marker in upstream} == before


def test_integrity_failure_stops_before_transport_instantiation(monkeypatch):
    monkeypatch.setattr(s, "C1_SHA", "0" * 64)
    with TemporaryDirectory(prefix="alpha321c2_test_", dir=s.ROOT / "runs") as task_tmp:
        monkeypatch.setattr(s, "OUT", Path(task_tmp) / "output")
        result = s.run(lambda policy: pytest.fail("transport instantiated before integrity barrier"))
        assert result["status"] == "failed"
        assert result["metadata_transport_attempts"] == 0
        assert "C1_ROOT_MISMATCH" in result["failure"]


def test_collision_graph_cannot_run_without_complete_first_pass(monkeypatch):
    with TemporaryDirectory(prefix="alpha321c2_test_", dir=s.ROOT / "runs") as task_tmp:
        monkeypatch.setattr(s, "OUT", Path(task_tmp))
        s.put("metadata_identity_freeze_before_collision_analysis.json", {"all_72_logical_requests_terminal": False,
            "per_source_fact_count": 1})
        with pytest.raises(Exception, match="BEFORE_IDENTITY_FREEZE"):
            s.freeze_graph([])


def test_adapter_reuses_frozen_transport_without_touching_historical_output(monkeypatch):
    state = s.preflight()
    request = state["requests"][0]
    actual_calls, timeouts, sleeps = [], [], []
    body = s.authority.synthetic_xml(pmid=request["sampled_pmids"][0])

    class Response:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return body

    class Opener:
        def open(self, req, timeout):
            actual_calls.append(req.full_url)
            timeouts.append(timeout)
            if len(actual_calls) == 1:
                raise urllib.error.HTTPError(req.full_url, 429, "fixture", {}, None)
            return Response()

    monkeypatch.setattr(s.legacy.urllib.request, "build_opener", lambda *args: Opener())
    monkeypatch.setattr(s.legacy.time, "sleep", sleeps.append)
    monkeypatch.setattr(s.legacy.time, "monotonic", lambda: 1000)
    old_out, old_writer = s.legacy.OUT, s.legacy.write_bytes
    with TemporaryDirectory(prefix="alpha321c2_test_", dir=s.ROOT / "runs") as task_tmp:
        monkeypatch.setattr(s, "OUT", Path(task_tmp))
        adapter = s.FrozenTransportAdapter(state["transport"])
        raw, attempts = adapter.fetch(request)
        assert raw == body and len(attempts) == adapter.calls == 2
        assert timeouts == [60, 60] and 2 in sleeps
        assert actual_calls[0] == actual_calls[1]
        assert actual_calls[0].startswith(s.legacy.EFETCH + "?db=pubmed&retmode=xml&id=")
        assert all(s.digest(s.OUT / a["raw_path"]) == a["raw_sha256"] for a in attempts)
        assert s.legacy.OUT == old_out and s.legacy.write_bytes is old_writer


def test_http_success_with_bad_xml_has_no_parse_repair_retry():
    state = s.preflight()
    request = state["requests"][0]
    attempt = {"raw_response_path": "unused", "transport_terminal_state": "HTTP_SUCCESS"}
    fact = s.first_pass_fact(request, b"not XML", [attempt], state)
    assert fact["metadata_response_state"] == "SOURCE_FAILED_CLOSED"
    assert fact["direct_pmcid"] is None and fact["direct_doi"] is None
    assert fact["historical_alias_contamination_state"] == "CLEAR"


def test_zero_handoff_is_normal_completion_without_policy_changes(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", forbid_network)

    class YearOnlyTransport:
        def __init__(self, policy):
            self.calls = 0

        def fetch(self, request):
            self.calls += 1
            pmid = request["sampled_pmids"][0]
            raw = s.authority.synthetic_xml(pmid=pmid, pmcid="PMC" + pmid,
                doi="10.fixture/" + pmid, pubdate="<Year>2026</Year>")
            name = f"raw/{self.calls:03d}.xml"
            raw_sha = s.put_bytes(name, raw)
            attempt = {"attempt": 1, "method": request["method"], "endpoint": request["endpoint"],
                "parameters": request["parameters"], "http_status": 200, "transport_error": None,
                "timestamp_utc": "2026-10-06T00:00:00+00:00", "raw_path": name,
                "raw_sha256": raw_sha, "raw_bytes": len(raw)}
            return raw, [attempt]

    with TemporaryDirectory(prefix="alpha321c2_test_", dir=s.ROOT / "runs") as task_tmp:
        monkeypatch.setattr(s, "OUT", Path(task_tmp) / "output")
        result = s.run(YearOnlyTransport)
        assert result["status"] == "completed", result
        assert result["pre_oa_handoff_count"] == 0
        assert result["date_unresolved_count"] == 72
        assert result["metadata_transport_attempts"] == 72
        assert result["next_stage_recommendation"] == "CLOSE_ALPHA3_21_PRIMARY_WITH_ZERO_PRE_OA_HANDOFF"
        assert result["publication_date_policy_changed"] is False
        assert result["collision_policy_changed"] is False
