"""Synthetic transport tests; no fresh OA/JATS observation or network."""

import io
import json
import socket
import urllib.error
import urllib.parse
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from scripts import run_search_plan_v24_alpha321d2_pmc_execution as s


@pytest.fixture(autouse=True)
def prohibit_real_network_and_forbidden_documents(monkeypatch):
    def prohibited(*args, **kwargs):
        raise AssertionError("REAL_NETWORK_OR_CONSTRUCTION_DOCUMENT_FORBIDDEN")
    monkeypatch.setattr(socket.socket, "connect", prohibited)
    monkeypatch.setattr(socket, "create_connection", prohibited)
    monkeypatch.setattr(s.legacy.source_policy, "build_construction_document", prohibited)
    monkeypatch.setattr(s.d1.d, "requests_for", prohibited)
    monkeypatch.setattr(s.d1, "run", prohibited)
    monkeypatch.setattr(s.d1.d, "run", prohibited)


class Response:
    status = 200

    def __init__(self, raw):
        self.raw = raw

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        return self.raw


def fixture_jats(source, *, mismatch=None, license_uri="https://creativecommons.org/licenses/by/4.0/", body=True, methods=True):
    ids = {"pmc": source["pmcid"][3:], "pmid": source["pmid"], "doi": source["doi"]}
    if mismatch == "both_secondary":
        ids["pmid"], ids["doi"] = "999", "10.synthetic/wrong"
    elif mismatch:
        ids[mismatch] = "999" if mismatch != "doi" else "10.synthetic/wrong"
    identifiers = ''.join(f'<article-id pub-id-type="{kind}">{value}</article-id>' for kind, value in ids.items() if value is not None)
    license_node = f'<permissions><license href="{license_uri}"/></permissions>' if license_uri else ""
    body_xml = '<body><sec><title>' + ("Methods" if methods else "Other") + '</title><p>Synthetic procedure</p></sec><sec><title>Results</title><p>Synthetic observation</p></sec></body>' if body else '<body/>'
    return ('<pmc-articleset><article article-type="research-article"><front><article-meta>' + identifiers + license_node + '</article-meta></front>' + body_xml + '</article></pmc-articleset>').encode()


class FakeOpener:
    def __init__(self, state, *, mode="positive", retries=False):
        self.state, self.mode, self.retries = state, mode, retries
        self.sources = state["input_sources"]
        self.by_pmcid = {source["pmcid"][3:]: source for source in self.sources}
        self.calls, self.attempts = [], {}
        self.jats_options = {}

    def open(self, request, timeout):
        assert timeout == 60
        parsed = urllib.parse.urlsplit(request.full_url)
        endpoint = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
        params = {key: values[0] for key, values in urllib.parse.parse_qs(parsed.query).items()}
        matching = [f for f in self.state["requests"] if f["request_payload"]["endpoint"] == endpoint and f["request_payload"]["parameters"] == params]
        assert len(matching) == 1
        frozen = matching[0]
        key = frozen["logical_request_id"]
        self.attempts[key] = self.attempts.get(key, 0) + 1
        self.calls.append((frozen["request_class"], frozen["pmid"], self.attempts[key]))
        if self.mode == "unhandled" and len(self.calls) == 2:
            raise RuntimeError("NCBI_REDIRECT_FORBIDDEN")
        if endpoint == s.legacy.ES:
            assert not any(stage == "PMC_JATS" for stage, *_ in self.calls)
            ordinal = frozen["source_input_ordinal"]
            if self.mode == "zero":
                count, idlist = 0, []
            elif self.mode == "mixed" and ordinal == 49:
                raise urllib.error.HTTPError(request.full_url, 403, "synthetic", {}, io.BytesIO(b"forbidden"))
            elif self.mode == "mixed" and ordinal == 48:
                count, idlist = 0, []
            else:
                count, idlist = 1, [frozen["pmcid"][3:]]
            if self.retries and ordinal == 1 and self.attempts[key] == 1:
                raise urllib.error.HTTPError(request.full_url, 502, "synthetic", {}, io.BytesIO(b"retryable"))
            return Response(json.dumps({"esearchresult": {"count": str(count), "retstart": "0", "retmax": str(len(idlist)),
                "idlist": idlist, "querytranslation": "synthetic preserved request"}}).encode())
        assert (s.OUT / "oa_phase_completion_barrier.json").is_file()
        assert (s.OUT / "alpha3_21d2_jats_activation_manifest_sha256").is_file()
        assert len(s.rows(s.OUT / "oa_source_states.jsonl")) == 49
        assert s.digest(s.OUT / "oa_source_states.jsonl") == (s.OUT / "oa_source_states_sha256").read_text().strip()
        if self.mode == "jats_unhandled":
            raise RuntimeError("NCBI_REDIRECT_FORBIDDEN")
        source = self.by_pmcid[params["id"]]
        options = self.jats_options.get(source["pmid"], {})
        if options.get("transport_failure"):
            raise urllib.error.HTTPError(request.full_url, 502, "synthetic", {}, io.BytesIO(b"temporary"))
        if options.get("malformed"):
            return Response(b'<article>')
        return Response(fixture_jats(source, **options))


def mocked_run(monkeypatch, opener):
    monkeypatch.setattr(s.legacy.urllib.request, "build_opener", lambda *args: opener)
    monkeypatch.setattr(s.legacy.time, "sleep", lambda seconds: None)
    return s.run()


def upstream_hashes():
    return [s.root_hash(directory, marker) for directory, marker in ((s.D1, s.d1.ROOT_MARKER), (s.D, s.d1.d.ROOT_MARKER),
        (s.C2, s.d1.d.c2.ROOT_MARKER), (s.MASTER, s.d1.MASTER_MARKER))]


def test_complete_two_phase_run_has_valid_handoff_and_preserves_all_frozen_assets(monkeypatch):
    state = s.preflight()
    before = upstream_hashes()
    requests_bytes = s.d1.REQUESTS.read_bytes()
    original_hooks = (s.legacy.write_bytes, s.legacy.append_jsonl)
    opener = FakeOpener(state, retries=True)
    with TemporaryDirectory(prefix="alpha321d2_positive_test_", dir=s.ROOT / "runs") as task_tmp:
        monkeypatch.setattr(s, "OUT", Path(task_tmp) / "output")
        result = mocked_run(monkeypatch, opener)
        assert result["status"] == "completed"
        assert result["oa_logical_requests_executed"] == result["jats_logical_requests_activated"] == result["jats_logical_requests_executed"] == 49
        assert result["total_logical_requests_executed"] == 98
        assert result["total_transport_attempts"] == 99
        assert result["oa_technical_retry_count"] == 1
        assert result["jats_identity_exact_bound_count"] == 49
        assert result["deferred_reached_structural_resolution_count"] == 3
        assert result["deferred_clear_count"] + result["deferred_ineligible_count"] + result["deferred_unresolved_count"] == 3
        assert s.root_hash(s.OUT, s.ROOT_MARKER) == result[s.ROOT_MARKER]
        assert s.obj(s.OUT / "protocol_compliance_audit.json")["complete_authorized_execution"] is True
        assert (s.OUT / "alpha3_21d2_oa_source_states.jsonl").read_bytes() == (s.OUT / "oa_source_states.jsonl").read_bytes()
        handoff = s.obj(s.OUT / "alpha3_21e_construction_source_handoff.json")
        assert handoff["source_count"] == result["construction_source_count"]
        for source in handoff["sources"]:
            assert source["JATS_identity_state"] == s.identity.SUCCESS
            assert source["oa_state"] == "OA_SUBSET_ELIGIBLE"
            assert source["license_state"] == "ELIGIBLE"
            assert s.digest(s.ROOT / source["canonical_BODY"]["artifact_path"]) == source["canonical_BODY_sha256"]
            paragraphs = s.obj(s.ROOT / source["BODY_paragraph_provenance"]["artifact_path"])["paragraphs"]
            assert all("span_id" not in paragraph for paragraph in paragraphs)
        assert all(result[k] == 0 for k in s.NO_CALLS)
        assert result["construction_evidence_document_generation_started"] is False
        assert result["source_record_tokens_generated"] == result["BODY_span_anchors_generated"] == 0
        with pytest.raises(Exception, match="NO_RERUN_OR_REFRESH"):
            s.run()
    assert upstream_hashes() == before
    assert s.d1.REQUESTS.read_bytes() == requests_bytes
    assert original_hooks == (s.legacy.write_bytes, s.legacy.append_jsonl)


def test_per_source_failures_isolate_identity_license_body_transport_and_exposure(monkeypatch):
    state = s.preflight()
    opener = FakeOpener(state, mode="mixed")
    sources = state["input_sources"]
    options = [{"mismatch": "pmc"}, {"mismatch": "pmid"}, {"mismatch": "both_secondary"},
        {"license_uri": "https://creativecommons.org/licenses/by-nc/4.0/"}, {"license_uri": None},
        {"body": False}, {"methods": False}, {"malformed": True}, {"transport_failure": True}]
    for source, case in zip(sources, options):
        opener.jats_options[source["pmid"]] = case
    with TemporaryDirectory(prefix="alpha321d2_mixed_test_", dir=s.ROOT / "runs") as task_tmp:
        monkeypatch.setattr(s, "OUT", Path(task_tmp) / "output")
        result = mocked_run(monkeypatch, opener)
        assert result["status"] == "completed"
        assert result["oa_eligible_count"] == result["jats_logical_requests_executed"] == 47
        assert result["oa_ineligible_count"] == result["oa_terminal_failure_count"] == 1
        assert result["jats_identity_failure_count"] == 3
        assert result["jats_pmcid_mismatch_count"] == 1
        assert result["jats_pmid_mismatch_count"] == 2
        assert result["jats_doi_mismatch_count"] == 1
        assert result["jats_structural_failure_count"] == result["jats_terminal_transport_failure_count"] == 1
        assert result["jats_technical_retry_count"] == 3
        assert result["license_ineligible_count"] == result["license_unresolved_or_missing_count"] == result["canonical_body_unusable_count"] == 1
        by_pmid = {r["pmid"]: r for r in s.rows(s.OUT / "d2_per_source_dimension_states.jsonl")}
        expected = ["BLOCKED_PRIMARY_IDENTITY"] * 3 + ["BLOCKED_LICENSE"] * 2 + ["BLOCKED_BODY_UNAVAILABLE", "BLOCKED_SOURCE_TYPE", "BLOCKED_JATS", "BLOCKED_JATS"]
        for source, terminal in zip(sources, expected):
            assert by_pmid[source["pmid"]]["construction_source_state"] == terminal
        assert all(by_pmid[source["pmid"]]["license_state"] == "NOT_EVALUATED_UPSTREAM_GATE" for source in sources[:3])
        registry = s.obj(s.OUT / "alpha3_21_current_attempt_fulltext_exposure_registry.json")
        assert registry["current_exclusion_authority"] is False
        assert registry["authoritative_exposure_count"] == result["jats_identity_exact_bound_count"]
        bad_pmids = {source["pmid"] for source in sources[:3]}
        assert not bad_pmids & {r["pmid"] for r in registry["source_identities"]}
        assert all(r["authoritative_identity"] is False for r in registry["untrusted_observations"])
        assert len(registry["all_JATS_request_observations"]) == 47
        assert result["downstream_replacement_used"] is False


def test_zero_oa_and_zero_construction_handoff_is_valid_no_jats_requests(monkeypatch):
    state = s.preflight()
    opener = FakeOpener(state, mode="zero")
    with TemporaryDirectory(prefix="alpha321d2_zero_test_", dir=s.ROOT / "runs") as task_tmp:
        monkeypatch.setattr(s, "OUT", Path(task_tmp) / "output")
        result = mocked_run(monkeypatch, opener)
        assert result["status"] == "completed"
        assert result["oa_ineligible_count"] == 49
        assert result["jats_logical_requests_executed"] == result["construction_source_count"] == 0
        assert result["deferred_not_reached_due_to_prior_terminal_state_count"] == 3
        assert result["next_stage_recommendation"] == "CLOSE_ALPHA3_21_PRIMARY_WITH_ZERO_CONSTRUCTION_SOURCES"
        assert s.obj(s.OUT / "alpha3_21e_construction_source_handoff.json")["sources"] == []
        assert s.digest(s.OUT / "canonical_body_manifest.jsonl") == s.sha(b"")


@pytest.mark.parametrize("mode", ["unhandled", "jats_unhandled"])
def test_unhandled_frozen_client_exception_stops_preserves_started_attempt_and_does_not_retry(monkeypatch, mode):
    opener = FakeOpener(s.preflight(), mode=mode)
    with TemporaryDirectory(prefix="alpha321d2_abort_test_", dir=s.ROOT / "runs") as task_tmp:
        monkeypatch.setattr(s, "OUT", Path(task_tmp) / "output")
        result = mocked_run(monkeypatch, opener)
        assert result["status"] == "failed"
        assert result["alpha3_21d2_classification"] == s.CLASS_FAIL
        assert result["total_transport_attempts"] == (2 if mode == "unhandled" else 50)
        assert "NCBI_REDIRECT_FORBIDDEN" in result["failure"]
        assert s.obj(s.OUT / "network_execution_accounting.json")["every_attempt_raw_artifact_verified"] is True
        stream = "oa_request_attempt_log.jsonl" if mode == "unhandled" else "jats_request_attempt_log.jsonl"
        assert s.rows(s.OUT / stream)[-1]["transport_attempt_state"] == "TERMINAL_UNHANDLED_FROZEN_CLIENT_EXCEPTION"
        assert s.obj(s.OUT / "alpha3_21e_construction_source_handoff.json")["complete_D2_execution"] is False
        if mode == "jats_unhandled":
            registry = s.obj(s.OUT / "alpha3_21_current_attempt_fulltext_exposure_registry.json")
            assert len(registry["all_JATS_request_observations"]) == 1
            assert registry["all_JATS_request_observations"][0]["authoritative_identity"] is False


def test_pre_network_mismatch_never_constructs_transport_or_creates_output(monkeypatch):
    monkeypatch.setattr(s, "D1_SHA", "0" * 64)
    def prohibited(*args, **kwargs):
        raise AssertionError("TRANSPORT_BEFORE_INTEGRITY_BARRIER")
    monkeypatch.setattr(s, "FrozenTransportAdapter", prohibited)
    with TemporaryDirectory(prefix="alpha321d2_bad_hash_test_", dir=s.ROOT / "runs") as task_tmp:
        monkeypatch.setattr(s, "OUT", Path(task_tmp) / "output")
        with pytest.raises(Exception, match="D1_ROOT_MISMATCH_STOP_BEFORE_NETWORK"):
            s.run()
        assert not s.OUT.exists()
