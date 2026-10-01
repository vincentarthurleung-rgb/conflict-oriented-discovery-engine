"""Offline-only one-attempt transport doubles for frozen Builder V3."""
import json

import pytest

from scripts import run_search_plan_v24_alpha318b2_builder_v3 as runner


def fake_response(request_bytes, *, abstract_invalid=False):
    request = json.loads(request_bytes)
    token = request["messages"][1]["content"].split("Source token: ", 1)[1].split("\n", 1)[0]
    candidates = []
    if abstract_invalid:
        candidates = [{"actor_or_intervention": "synthetic", "action": "treatment",
            "relation_direction": "DECREASES", "response_or_endpoint": "endpoint",
            "biological_unit": "cells", "species": None, "intrinsic_conditioning": None,
            "intrinsic_therapy_context": None,
            "intrinsic_disease_or_genotype_context": None,
            "neutral_proposition": "Synthetic treatment decreases endpoint.",
            "construction_evidence_span": {"source_field": "abstract",
                "exact_text": "Synthetic text.", "start_offset": 0, "end_offset": 15}}]
    content = json.dumps({"source_record_token": token, "candidates": candidates})
    envelope = {"id": "synthetic-v3", "choices": [
        {"message": {"content": content}, "finish_reason": "stop"}]}
    raw = json.dumps(envelope).encode()

    class Response:
        status_code = 200
        elapsed = type("Elapsed", (), {"total_seconds": lambda self: 0.01})()
        content = raw

        def json(self):
            return envelope

    return Response()


def test_28_zero_candidate_v3_calls_freeze_empty_quality_manifest(tmp_path, monkeypatch):
    out = tmp_path / "run"
    monkeypatch.setattr(runner, "OUT", out)
    monkeypatch.setattr(runner.base, "key", lambda: "synthetic-only")

    class Client:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def post(self, url, headers, content):
            assert url == runner.URL
            assert headers["Authorization"] == "Bearer synthetic-only"
            return fake_response(content)

    monkeypatch.setattr(runner.httpx, "Client", Client)
    runner.execute()
    summary = json.loads((out / "summary.json").read_text())
    assert summary["builder_v3_valid_zero"] == 28
    assert summary["builder_v3_scientific_inference_events"] == 28
    assert summary["cumulative_builder_scientific_inference_events"] == 56
    assert summary["actual_quality_adjudication_call_count"] == 0
    assert (out / "proposition_quality_v2_request_manifest_v3.jsonl").read_bytes() == b""


def test_v3_abstract_schema_invalid_does_not_reinfer(tmp_path, monkeypatch):
    out = tmp_path / "run"
    monkeypatch.setattr(runner, "OUT", out)
    monkeypatch.setattr(runner.base, "key", lambda: "synthetic-only")
    calls = []

    class Client:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def post(self, _url, _headers=None, **kwargs):
            calls.append(1)
            return fake_response(kwargs["content"], abstract_invalid=len(calls) == 1)

    monkeypatch.setattr(runner.httpx, "Client", Client)
    runner.execute()
    summary = json.loads((out / "summary.json").read_text())
    assert len(calls) == 28
    assert summary["builder_v3_response_invalid"] == 1
    assert summary["builder_v3_valid_zero"] == 27


def test_ambiguous_v3_transport_stops_without_next_attempt(tmp_path, monkeypatch):
    out = tmp_path / "run"
    monkeypatch.setattr(runner, "OUT", out)
    monkeypatch.setattr(runner.base, "key", lambda: "synthetic-only")

    class Client:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def post(self, *_args, **_kwargs):
            raise RuntimeError("synthetic uncertain transport")

    monkeypatch.setattr(runner.httpx, "Client", Client)
    with pytest.raises(RuntimeError, match="BUILDER_PROVIDER_EXECUTION_AMBIGUOUS"):
        runner.execute()
    assert (out / "attempts/01.json").exists()
    assert not (out / "attempts/02.json").exists()
    assert json.loads((out / "runtime_failure.json").read_text())["failure_code"] == (
        "BUILDER_PROVIDER_EXECUTION_AMBIGUOUS")
