"""Offline execution-boundary checks for the frozen alpha3.21A1 runner."""

from __future__ import annotations

import json
import tempfile
import urllib.error
import urllib.parse
from pathlib import Path

import pytest

from scripts import run_search_plan_v24_alpha321a1_source_acquisition as acquisition


class Response:
    status = 200
    headers = {"Content-Type": "application/json"}

    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.body


class SimulatedPubMed:
    def __init__(self, *, drift=False, fail_first=False):
        self.drift = drift
        self.fail_first = fail_first
        self.calls = []

    def open(self, request, timeout):
        assert timeout == 60
        values = urllib.parse.parse_qs(urllib.parse.urlsplit(request.full_url).query)
        self.calls.append(values)
        if self.fail_first:
            raise urllib.error.HTTPError(request.full_url, 503, "test", {}, None)
        first_stratum = '"Signal Transduction"[MeSH Terms]' in values["term"][0]
        start = int(values["retstart"][0])
        count = (52 if self.drift and start == 50 else 51) if first_stratum else 0
        ids = [str(10000000 + start + position)
               for position in range(min(50, max(0, count - start)))]
        body = {"esearchresult": {"count": str(count),
            "retstart": str(start), "retmax": str(len(ids)),
            "idlist": ids, "querytranslation": "simulated"}}
        return Response(json.dumps(body).encode("utf-8"))


@pytest.fixture
def execution_parent():
    with tempfile.TemporaryDirectory(prefix="alpha321a1_sim_",
                                     dir=acquisition.RUNS) as directory:
        yield Path(directory)


def execute(execution_parent, monkeypatch, **kwargs):
    state = acquisition.preflight()
    monkeypatch.setattr(acquisition, "OUT", execution_parent / "test_run")
    opener = SimulatedPubMed(**kwargs)
    transport = acquisition.Transport(state["retry"], opener=opener,
                                      sleep=lambda _seconds: None,
                                      monotonic=lambda: 0.0)
    result = acquisition.run_with_transport(state, transport)
    return result, opener


def test_frozen_expansion_completes_without_scientific_postprocessing(execution_parent, monkeypatch):
    result, opener = execute(execution_parent, monkeypatch)
    assert result["status"] == "completed"
    assert result["first_page_valid_success_count"] == 6
    assert result["remaining_page_required_count"] == 1
    assert result["remaining_page_not_required_count"] == 17
    assert result["remaining_page_executed_count"] == 1
    assert result["raw_pmid_occurrence_count"] == 51
    assert len(opener.calls) == 7
    assert result["deduplication_performed"] is False
    assert result["preexisting_seen_exclusion_performed"] is False
    assert (acquisition.OUT / "alpha3_21a1_raw_acquisition_corpus.jsonl").exists()
    assert acquisition.root_hash(acquisition.OUT, acquisition.ROOT_MARKER) == \
        result[acquisition.ROOT_MARKER]


def test_count_drift_stops_and_preserves_exposed_ids(execution_parent, monkeypatch):
    result, opener = execute(execution_parent, monkeypatch, drift=True)
    assert result["status"] == "failed"
    assert result["result_set_count_drift_count"] == 1
    assert result["raw_pmid_occurrence_count"] == 52
    assert result["alpha3_21a1_raw_acquisition_corpus_sha256"] is None
    assert len(opener.calls) == 7
    assert (acquisition.OUT / "alpha3_21a1_partial_raw_acquisition_corpus.jsonl").exists()


def test_technical_failure_exhausts_only_frozen_attempts(execution_parent, monkeypatch):
    result, opener = execute(execution_parent, monkeypatch, fail_first=True)
    assert result["status"] == "failed"
    assert result["first_page_logical_requests_executed"] == 1
    assert result["total_transport_attempts"] == 4
    assert result["technical_retry_count"] == 3
    assert result["remaining_page_executed_count"] == 0
    assert len(opener.calls) == 4
