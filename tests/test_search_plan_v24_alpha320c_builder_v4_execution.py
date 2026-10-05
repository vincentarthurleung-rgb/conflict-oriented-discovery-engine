"""Offline checks for the frozen alpha3.20C execution runner."""

import json
from pathlib import Path

from scripts import run_search_plan_v24_alpha320c_builder_v4_execution as c


def test_frozen_preflight_is_read_only(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(c, "OUT", tmp_path / "not_created")
    state = c.verify_preflight()
    assert len(state["rows"]) == 42
    assert state["variant_ids"] == [
        "ABSTRACTION_V1_RELATION_SENTENCE",
        "ABSTRACTION_V2_RELATION_FRAME",
        "ABSTRACTION_V3_CONTEXT_FIRST",
    ]


def test_failure_classification_is_conservative():
    assert c.provider_failure_state(400, b'{"error":{"message":"model not found"}}') == (
        "PROVIDER_NO_INFERENCE_TERMINAL_FAILURE", "PROVIDER_BINDING_FAILURE")
    assert c.provider_failure_state(429, b'{"error":{"message":"rate limit"}}') == (
        "PROVIDER_EXECUTION_AMBIGUOUS", "BUILDER_PROVIDER_EXECUTION_AMBIGUOUS")


def test_mocked_42_cell_run_never_uses_network(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(c, "OUT", tmp_path / "mock_alpha320c")
    state = c.verify_preflight()
    calls = []

    class FakeResponse:
        status_code = 200

        def __init__(self, body: bytes):
            self.content = body
            self.elapsed = self

        def total_seconds(self):
            return 0.01

        def json(self):
            return json.loads(self.content)

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def post(self, url, headers, content):
            assert url == c.URL
            assert headers["Authorization"] == "Bearer MOCK_ONLY"
            request = json.loads(content)
            token = request["messages"][1]["content"].splitlines()[0].split(": ", 1)[1]
            calls.append(token)
            envelope = {"id": "mock-response", "choices": [{
                "message": {"content": json.dumps({
                    "source_record_token": token, "candidates": []})},
                "finish_reason": "stop"}], "usage": {}}
            return FakeResponse(c.canonical(envelope))

    monkeypatch.setattr(c.httpx, "Client", FakeClient)
    c.freeze_preflight(state)
    result = c.freeze_results(state, c.execute(state, "MOCK_ONLY"))
    assert len(calls) == 42
    assert result["status"] == "completed"
    assert result["builder_scientific_inference_events"] == 42
    assert result["valid_zero"] == 42
    assert result["raw_candidate_count"] == 0
    assert result["complete_variant_triplet_count"] == 14
    assert c.root_hash(c.OUT, c.ROOT_MARKER) == (
        c.OUT / c.ROOT_MARKER).read_text().strip()
