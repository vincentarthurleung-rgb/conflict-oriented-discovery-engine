"""Offline transport doubles for alpha3.18B execution control flow."""
import json

import pytest

from scripts import run_search_plan_v24_alpha318b_builder as runner


def test_28_frozen_requests_zero_candidate_path_without_network(tmp_path, monkeypatch):
    out = tmp_path / "run"
    monkeypatch.setattr(runner, "OUT", out)
    monkeypatch.setattr(runner, "key", lambda: "test-only-not-a-provider-key")

    class Response:
        status_code = 200
        elapsed = type("Elapsed", (), {"total_seconds": lambda self: 0.01})()

        def __init__(self, body):
            request = json.loads(body)
            token = request["messages"][1]["content"].split("Source token: ", 1)[1].split("\n", 1)[0]
            content = json.dumps({"source_record_token": token, "candidates": []})
            self.content = json.dumps({"id": "synthetic", "choices": [
                {"message": {"content": content}, "finish_reason": "stop"}]}).encode()

        def json(self):
            return json.loads(self.content)

    class Client:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def post(self, url, headers, content):
            assert url == runner.URL
            assert headers["Authorization"].startswith("Bearer test-only-")
            return Response(content)

    monkeypatch.setattr(runner.httpx, "Client", Client)
    runner.execute()
    summary = json.loads((out / "summary.json").read_text())
    assert summary["builder_valid_zero"] == 28
    assert summary["actual_quality_adjudication_call_count"] == 0
    assert (out / "proposition_quality_v2_request_manifest.jsonl").read_bytes() == b""
    assert (out / runner.ROOT_NAME).read_text().strip() == runner.frozen.a6.base.prior.all_file_root(
        out, runner.ROOT_NAME)


def test_ambiguous_transport_stops_without_later_attempt(tmp_path, monkeypatch):
    out = tmp_path / "run"
    monkeypatch.setattr(runner, "OUT", out)
    monkeypatch.setattr(runner, "key", lambda: "test-only-not-a-provider-key")

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
    assert (out / "attempts/01.json").is_file()
    assert not (out / "attempts/02.json").exists()
    assert json.loads((out / "runtime_failure.json").read_text())["failure_code"] == (
        "BUILDER_PROVIDER_EXECUTION_AMBIGUOUS")
