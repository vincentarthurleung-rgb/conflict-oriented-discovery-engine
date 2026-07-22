from __future__ import annotations

import json
from unittest.mock import patch

import httpx

from code_engine.extraction.deepseek_client import DeepSeekClient, DeepSeekExtractionError
from code_engine.fulltext.fulltext_l1_v2 import (
    DEFAULT_MAX_TOKENS, FulltextTokenBudget, deterministic_child_blocks,
    merge_child_observations, run_fulltext_l1_v2_extraction, token_budget_preflight,
)


def _block(text: str) -> dict:
    return {"block_id": "parent", "section": {"section_title": "Results"}, "text": text,
            "chunk_hash": "stable", "paper_metadata": {"paper_id": "P1", "pmcid": "PMC1"},
            "context_sources": ["current_evidence_span"]}


def test_large_multi_experiment_parent_splits_stably_before_provider():
    block = _block("Human cells increased A.\n\nMurine tumors decreased B.\n\nFigure 2 increased C.")
    budget = FulltextTokenBudget(safe_input_tokens=10)
    assert token_budget_preflight({}, block, budget)["preflight_decision"] == "split_before_provider_call"
    one = deterministic_child_blocks(block, reason="test", budget=budget)
    two = deterministic_child_blocks(block, reason="test", budget=budget)
    assert [x["child_block_id"] for x in one] == [x["child_block_id"] for x in two]
    assert [x["chunk_hash"] for x in one] == [x["chunk_hash"] for x in two]
    assert all(not ({"human", "murine"} <= {h.casefold() for h in x["species_experiment_boundary_hints"]}) for x in one)


def test_deepseek_real_body_has_json_output_and_bounded_max_tokens():
    response = httpx.Response(200, request=httpx.Request("POST", "https://api.deepseek.com"), json={
        "choices": [{"message": {"content": '{"ok":true}'}, "finish_reason": "stop"}], "usage": {}})
    with patch("httpx.post", return_value=response) as post:
        DeepSeekClient("fake", max_retries=0).extract_json_result("return json", max_tokens=DEFAULT_MAX_TOKENS)
    body = json.loads(post.call_args.kwargs["content"])
    assert body["response_format"] == {"type": "json_object"}
    assert body["max_tokens"] == DEFAULT_MAX_TOKENS
    assert body["max_tokens"] != 384_000


def test_length_does_not_retry_identical_result_request():
    response = httpx.Response(200, request=httpx.Request("POST", "https://api.deepseek.com"), json={
        "choices": [{"message": {"content": '{"unfinished":"x'}, "finish_reason": "length"}]})
    with patch("httpx.post", return_value=response) as post:
        try:
            DeepSeekClient("fake", max_retries=3, sleep_fn=lambda _: None).extract_json_result("return json", max_tokens=1024)
        except DeepSeekExtractionError as exc:
            assert exc.error_kind == "output_truncated"
        else:
            raise AssertionError("expected truncated output failure")
    assert post.call_count == 1


def test_provider_never_receives_unsplit_parent(tmp_path, monkeypatch):
    artifacts = tmp_path / "run/artifacts"; article = artifacts / "fulltext/pmc_oa/PMC1"; article.mkdir(parents=True)
    candidates = artifacts / "candidates.jsonl"; candidates.write_text(json.dumps({"paper_id": "P1", "pmcid": "PMC1"}) + "\n")
    (article / "article_text.json").write_text(json.dumps({"sections": []}))
    parent = _block("Human cells increased A.\n\nMurine tumors decreased B.")
    monkeypatch.setattr("code_engine.fulltext.fulltext_l1_v2.build_experiment_blocks", lambda *_a, **_k: [parent])
    class Client:
        prompts = []
        def extract_json(self, prompt, **kwargs):
            self.prompts.append(prompt)
            assert kwargs["max_tokens"] == DEFAULT_MAX_TOKENS
            return {"schema_version": "fulltext_l1_experimental_observation_schema_v2", "experimental_observations": []}
    client = Client()
    run_fulltext_l1_v2_extraction(run_dir=tmp_path / "run", fulltext_candidates_path=candidates,
        parsed_articles_dir=artifacts / "fulltext/pmc_oa", l1_provider="fixture", l1_model="fixture",
        api_enabled=True, network_enabled=True, client=client, safe_input_tokens=10)
    assert len(client.prompts) >= 2
    assert all("Human cells" not in prompt or "Murine tumors" not in prompt for prompt in client.prompts)


def test_child_merge_requires_all_children_and_keeps_distinct_endpoints():
    a = {"observation_id": "a", "measurement": {"outcome_mention": "A"}}
    b = {"observation_id": "b", "measurement": {"outcome_mention": "B"}}
    complete = merge_child_observations([
        {"child_block_id": "c1", "status": "completed", "observations": [a]},
        {"child_block_id": "c2", "status": "completed_empty", "observations": []},
        {"child_block_id": "c3", "status": "completed", "observations": [b]},
    ], ["c1", "c2", "c3"])
    assert complete["parent_complete"] is True
    assert [x["observation_id"] for x in complete["observations"]] == ["a", "b"]
    failed = merge_child_observations([
        {"child_block_id": "c1", "status": "completed", "observations": [a]},
        {"child_block_id": "c2", "status": "parse_error", "observations": []},
    ], ["c1", "c2"])
    assert failed["parent_complete"] is False and failed["observations"] == []
