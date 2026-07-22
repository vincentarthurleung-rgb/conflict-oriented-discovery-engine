from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest

import code_engine.fulltext.fulltext_l1_v2 as module
from code_engine.extraction.deepseek_client import DeepSeekClient, DeepSeekExtractionError
from code_engine.fulltext.fulltext_l1_v2 import run_fulltext_l1_v2_extraction
from code_engine.schemas.fulltext_observation_draft import DRAFT_SCHEMA_VERSION
from code_engine.integration.atlas_publish import publish_completed_scientific_run


def _setup(tmp_path, monkeypatch, block_ids=("b1", "b2")):
    artifacts = tmp_path / "run" / "artifacts"
    article = artifacts / "fulltext" / "pmc_oa" / "PMC1"
    article.mkdir(parents=True)
    (artifacts / "candidates.jsonl").write_text(
        json.dumps({"paper_id": "P1", "pmid": "1", "pmcid": "PMC1"}) + "\n",
        encoding="utf-8",
    )
    (article / "article_text.json").write_text(json.dumps({"sections": []}), encoding="utf-8")
    blocks = [{
        "block_id": block_id,
        "section": {"section_title": "Results"},
        "text": f"text for {block_id}",
        "chunk_hash": module._hash(block_id),
        "paper_metadata": {"paper_id": "P1", "pmid": "1", "pmcid": "PMC1", "title": "fixture"},
        "context_sources": ["current_evidence_span"],
    } for block_id in block_ids]
    monkeypatch.setattr(module, "build_experiment_blocks", lambda *_args, **_kwargs: blocks)
    return {
        "run_dir": tmp_path / "run",
        "fulltext_candidates_path": artifacts / "candidates.jsonl",
        "parsed_articles_dir": artifacts / "fulltext/pmc_oa",
        "l1_provider": "deepseek",
        "l1_model": "fixture-model",
        "api_enabled": True,
        "network_enabled": True,
    }


def _response():
    return {"schema_version": DRAFT_SCHEMA_VERSION, "experimental_observations": []}


def _malformed(message="Unterminated string starting at: line 4948 column 36 (char 170288)", raw='{"secret":"sk-sensitive12345'):
    cause = json.JSONDecodeError(message.split(": line", 1)[0], raw, min(3, len(raw)))
    error = DeepSeekExtractionError(
        "deepseek_extraction_failed", message, 3, error_kind="malformed_json",
        retryable=True, raw_response=raw, finish_reason="length", cause=cause,
    )
    error.provider = "deepseek"
    error.model = "fixture-model"
    return error


def test_malformed_json_fails_closed_audits_and_continues(tmp_path, monkeypatch):
    args = _setup(tmp_path, monkeypatch)

    class Client:
        calls = 0

        def extract_json(self, *_args, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                raise _malformed()
            return _response()

    client = Client()
    result = run_fulltext_l1_v2_extraction(**args, client=client)

    assert client.calls == 2
    assert result["observations"] == []
    assert [row["status"] for row in result["executions"]] == ["parse_error", "completed_empty"]
    summary = result["summary"]
    assert summary["fulltext_l1_status"] == "completed_with_block_failures"
    assert summary["planned_block_count"] == 2
    assert summary["completed_block_count"] == 1
    assert summary["parse_error_block_count"] == 1
    assert summary["retryable_exhausted_block_count"] == 1
    assert summary["api_calls_made"] == 2
    assert summary["actual_llm_call_count"] == 4
    assert summary["failed_block_ids"] == ["b1"]
    assert summary["scientific_input_complete"] is False
    record = result["executions"][0]
    assert record["error_kind"] == "malformed_json"
    assert record["json_line"] == 1
    assert record["raw_response_character_count"] > 0
    raw = open(record["raw_response_path"], encoding="utf-8").read()
    assert "sk-sensitive12345" not in raw and "[REDACTED]" in raw
    error_artifact = json.load(open(record["raw_error_artifact"], encoding="utf-8"))
    assert "raw_response" not in error_artifact


def test_unterminated_string_compatibility_fallback_records_real_position(tmp_path, monkeypatch):
    args = _setup(tmp_path, monkeypatch, ("b1", "b2"))

    class Client:
        calls = 0

        def extract_json(self, *_args, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                raise DeepSeekExtractionError(
                    "deepseek_extraction_failed",
                    "Unterminated string starting at: line 4948 column 36 (char 170288)",
                    2,
                )
            return _response()

    result = run_fulltext_l1_v2_extraction(**args, client=Client())
    failed = result["executions"][0]
    assert failed["error_kind"] == "malformed_json"
    assert (failed["json_line"], failed["json_column"], failed["json_character_position"]) == (4948, 36, 170288)
    assert result["executions"][1]["status"] == "completed_empty"


@pytest.mark.parametrize("kind", ["authentication", "authorization", "configuration", "unknown"])
def test_fatal_deepseek_errors_are_not_swallowed(tmp_path, monkeypatch, kind):
    args = _setup(tmp_path, monkeypatch)

    class Client:
        calls = 0

        def extract_json(self, *_args, **_kwargs):
            self.calls += 1
            raise DeepSeekExtractionError("deepseek_extraction_failed", "invalid API key or model", 1, error_kind=kind)

    client = Client()
    with pytest.raises(DeepSeekExtractionError):
        run_fulltext_l1_v2_extraction(**args, client=client)
    assert client.calls == 1


def test_client_configuration_value_error_is_not_mistaken_for_response_parse_failure(tmp_path, monkeypatch):
    args = _setup(tmp_path, monkeypatch)

    class Client:
        calls = 0

        def extract_json(self, *_args, **_kwargs):
            self.calls += 1
            raise ValueError("invalid model configuration")

    client = Client()
    with pytest.raises(ValueError, match="invalid model configuration"):
        run_fulltext_l1_v2_extraction(**args, client=client)
    assert client.calls == 1


def test_resume_reuses_success_cache_and_recovers_only_failed_block(tmp_path, monkeypatch):
    args = _setup(tmp_path, monkeypatch, ("b1", "b2", "b3"))

    class First:
        calls = 0

        def extract_json(self, *_args, **_kwargs):
            self.calls += 1
            if self.calls == 2:
                raise _malformed(raw='{"unfinished":')
            return _response()

    first = run_fulltext_l1_v2_extraction(**args, client=First())
    assert first["summary"]["newly_failed"] == ["b2"]

    class Recovery:
        calls = 0

        def extract_json(self, *_args, **_kwargs):
            self.calls += 1
            return _response()

    recovery = Recovery()
    second = run_fulltext_l1_v2_extraction(**args, client=recovery)
    assert recovery.calls == 1
    assert second["summary"]["cache_hit_block_count"] == 2
    assert second["summary"]["previously_failed_now_recovered"] == ["b2"]
    assert second["summary"]["partial_block_failures"] is False
    assert list((tmp_path / "run/artifacts/cache/fulltext_l1_v2").glob("*.raw_error.json"))


def test_publication_is_blocked_without_changing_active_projection(tmp_path):
    run = tmp_path / "runs" / "run-partial"
    artifacts = run / "artifacts"
    artifacts.mkdir(parents=True)
    (artifacts / "case_domain_profile.json").write_text(json.dumps({"case_id": "case-1"}), encoding="utf-8")
    (artifacts / "fulltext_l1_v2_summary.json").write_text(json.dumps({
        "scientific_input_complete": False, "partial_block_failures": True,
    }), encoding="utf-8")
    output = tmp_path / "atlas"
    output.mkdir()
    registry = {"cases": {"case-1": {"active_projection_id": "projection-old"}}}
    (output / "active_projections_by_case.json").write_text(json.dumps(registry), encoding="utf-8")

    result = publish_completed_scientific_run(
        run, atlas_config={"runs_root": tmp_path / "runs", "output_root": output},
        publication_source="test",
    )
    assert result["atlas_sync_status"] == "blocked"
    assert result["active_projection_id"] == "projection-old"
    assert result["aggregate_projection_changed"] is False
    assert json.loads((output / "active_projections_by_case.json").read_text()) == registry


def test_deepseek_client_preserves_parse_cause_raw_response_and_finish_reason():
    raw = '{"unterminated":"value'
    response = httpx.Response(200, request=httpx.Request("POST", "https://api.deepseek.com"), json={
        "choices": [{"message": {"content": raw}, "finish_reason": "length"}],
    })
    with patch("httpx.post", return_value=response) as post:
        with pytest.raises(DeepSeekExtractionError) as raised:
            DeepSeekClient("fake", max_retries=1, sleep_fn=lambda _: None).extract_json("prompt")
    error = raised.value
    assert post.call_count == 2
    assert error.error_kind == "malformed_json"
    assert error.retryable is True
    assert error.raw_response == raw
    assert error.finish_reason == "length"
    assert error.cause is error.__cause__
    assert isinstance(error.cause.__cause__, json.JSONDecodeError)


def test_deepseek_authentication_failure_is_structured_and_not_retried():
    response = httpx.Response(401, request=httpx.Request("POST", "https://api.deepseek.com"), json={"error": "invalid key"})
    with patch("httpx.post", return_value=response) as post:
        with pytest.raises(DeepSeekExtractionError) as raised:
            DeepSeekClient("fake", max_retries=3, sleep_fn=lambda _: None).extract_json("prompt")
    assert post.call_count == 1
    assert raised.value.error_kind == "authentication"
    assert raised.value.retryable is False
    assert raised.value.status_code == 401
