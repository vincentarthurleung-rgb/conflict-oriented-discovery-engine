"""Offline preflight, strict validation, and mocked 28-cell E1 execution."""

import json

from scripts import run_search_plan_v24_alpha320e1_semantic_adjudication_execution as x


def test_frozen_preflight_without_provider(monkeypatch, tmp_path):
    monkeypatch.setattr(x, "OUT", tmp_path / "not_created")
    state = x.preflight()
    assert len(state["requests"]) == 28
    assert len(state["private_refs"]) == 3


def test_strict_candidate_token_and_enum_validation():
    schema = x.obj(x.E /
        "development_semantic_adjudication_response_envelope_v1.json")[
            "model_owned_payload_schema"]
    expected = ["a", "b", "c"]
    item = lambda token: {"candidate_token": token, "criteria": {
        key: {"state": "PASS", "rationale": "supported by supplied context"}
        for key in x.e.CRITERIA}}
    good = {"candidate_reviews": [item(t) for t in expected]}
    assert x.validate_response(json.dumps(good), "stop", expected, schema)[1][
        "status"] == "SEMANTIC_RESPONSE_VALID"
    bad_token = {"candidate_reviews": [item("a"), item("b"), item("b")]}
    parsed, result, diagnostics = x.validate_response(json.dumps(bad_token), "stop",
                                                       expected, schema)
    assert parsed is None and result["status"] == "SEMANTIC_RESPONSE_INVALID"
    assert diagnostics["candidate_token_set_failure"]
    bad_enum = {"candidate_reviews": [item(t) for t in expected]}
    bad_enum["candidate_reviews"][0]["criteria"][x.e.CRITERIA[0]]["state"] = "MOSTLY_PASS"
    parsed, result, diagnostics = x.validate_response(json.dumps(bad_enum), "stop",
                                                       expected, schema)
    assert parsed is None and diagnostics["criterion_enum_failure_count"] == 1
    parsed, result, diagnostics = x.validate_response('{"candidate_reviews":[],"candidate_reviews":[]}',
                                                       "stop", expected, schema)
    assert parsed is None
    assert result["reason"].startswith("SEMANTIC_RESPONSE_DUPLICATE_JSON_KEY")


def test_mocked_28_group_run_never_uses_network(monkeypatch, tmp_path):
    monkeypatch.setattr(x, "OUT", tmp_path / "mock_e1")
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
            assert url == x.URL
            assert headers["Authorization"] == "Bearer MOCK_ONLY"
            request = json.loads(content)
            visible = json.loads(request["messages"][1]["content"].split("\n", 1)[1])
            calls.append(visible["blinded_group_token"])
            reviews = [{"candidate_token": candidate["candidate_token"],
                "criteria": {key: {"state": "PASS", "rationale": "source-supported"}
                             for key in x.e.CRITERIA}}
                for candidate in visible["candidates"]]
            envelope = {"id": "mock", "choices": [{"message": {
                "content": json.dumps({"candidate_reviews": reviews})},
                "finish_reason": "stop"}], "usage": {}}
            return FakeResponse(x.canonical(envelope))

    monkeypatch.setattr(x.httpx, "Client", FakeClient)
    x.freeze_preflight(state)
    result = x.freeze_results(state, x.execute(state, "MOCK_ONLY"))
    assert len(calls) == len(set(calls)) == 28
    assert result["status"] == "completed"
    assert result["valid_semantic_group_count"] == 28
    assert result["valid_candidate_judgment_set_count"] == 84
    assert result["unblinding_performed"] is False
    assert x.e.d.c.root_hash(x.OUT, x.ROOT_MARKER) == (
        x.OUT / x.ROOT_MARKER).read_text().strip()
