"""Offline authority and mocked one-call-per-group E1R1 execution tests."""

import json

import pytest

from scripts import run_search_plan_v24_alpha320e1r1_full_blinded_semantic_replication_execution as x


def test_authoritative_manifest_hash_preflight(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(x, "OUT", tmp_path / "not-created")
    state = x.preflight()
    assert state["manifest_sha"] == x.MANIFEST_SHA
    assert len(state["requests"]) == 28
    assert len(state["private_refs"]) == 3
    assert len(x.MANIFEST_SHA) == 64


@pytest.mark.parametrize("malformed_ordinal,expected_valid", [(None, 28), (12, 27)])
def test_mocked_exact_28_fresh_inferences(monkeypatch, tmp_path,
                                          malformed_ordinal, expected_valid) -> None:
    monkeypatch.setattr(x, "OUT", tmp_path / "mock_replication")
    state = x.preflight()
    calls = []

    class FakeResponse:
        status_code = 200

        def __init__(self, raw):
            self.content = raw
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
            assert url == x.e1.URL
            assert headers["Authorization"] == "Bearer MOCK_ONLY"
            request = json.loads(content)
            payload = json.loads(request["messages"][1]["content"].split("\n", 1)[1])
            calls.append(payload["blinded_group_token"])
            reviews = [{"candidate_token": candidate["candidate_token"],
                "criteria": {key: {"state": "PASS", "rationale": "source-supported"}
                             for key in x.r.e.CRITERIA}}
                for candidate in payload["candidates"]]
            content_text = json.dumps({"candidate_reviews": reviews})
            if len(calls) == malformed_ordinal:
                content_text = content_text[:-1] + ",}"
            envelope = {"id": "mock", "choices": [{"message": {
                "content": content_text}, "finish_reason": "stop"}], "usage": {}}
            return FakeResponse(x.r.canonical(envelope))

    monkeypatch.setattr(x.httpx, "Client", FakeClient)
    x.freeze_preflight(state)
    result = x.freeze_results(state, x.execute(state, "MOCK_ONLY"))
    assert len(calls) == len(set(calls)) == 28
    assert result["replication_semantic_scientific_inference_events"] == 28
    assert result["valid_replication_group_count"] == expected_valid
    assert result["valid_replication_candidate_judgment_set_count"] == expected_valid * 3
    assert result["invalid_replication_group_count"] == 28 - expected_valid
    assert result["replication_selection_eligible"] is (malformed_ordinal is None)
    assert result["unblinding_performed"] is False
    assert result["semantic_scientific_retry_used"] is False
    assert x.r.e.d.c.root_hash(x.OUT, x.ROOT_MARKER) == (
        x.OUT / x.ROOT_MARKER).read_text().strip()
