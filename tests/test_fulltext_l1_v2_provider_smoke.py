import json
import inspect
from pathlib import Path
from unittest.mock import patch

import pytest

from code_engine.cli.fulltext_l1_v2_provider_smoke_test import main
from code_engine.extraction.deepseek_client import build_deepseek_request_payload, deepseek_thinking_mode_audit
from code_engine.extraction.deepseek_client import JSONExtractionResult
from code_engine.extraction.client_factory import ConfiguredJSONClient
from code_engine.fulltext.stage import run_l35_pmc_oa_stage
from code_engine.fulltext.fulltext_l1_v2 import run_fulltext_l1_v2_extraction
from code_engine.fulltext.fulltext_l1_v2 import DEFAULT_MAX_TOKENS, PROMPT_VERSION, build_prompt, prompt_hash
from code_engine.fulltext.fulltext_l1_v2_smoke import (
    _fresh_cache_status,
    _select_empty,
    _select_nonempty,
    decide_rerun_scope,
    execute_smoke,
    schema_hash,
)
from code_engine.schemas.fulltext_observation import fulltext_l1_v2_prompt_examples


def _block():
    return {"paper_metadata": {"paper_id": "p", "pmid": "1", "pmcid": "PMC1", "title": "t"},
            "text": "CURRENT_RESULTS: HIF1A knockdown decreased target expression.", "block_id": "b", "chunk_hash": "h"}


def test_v4_prompt_and_exact_deepseek_http_body_contract():
    prompt = build_prompt({"abstract_observation_ids": []}, _block())
    _, nonempty = fulltext_l1_v2_prompt_examples()
    assert PROMPT_VERSION == "fulltext_experimental_observation_prompt_v4_schema_examples"
    assert json.dumps(nonempty, ensure_ascii=False, separators=(",", ":")) in prompt
    body = build_deepseek_request_payload(prompt, model="deepseek-v4-pro", max_tokens=DEFAULT_MAX_TOKENS,
                                          thinking_mode="disabled")
    assert body["messages"] == [{"role": "system", "content": prompt}]
    assert body["response_format"] == {"type": "json_object"}
    assert body["max_tokens"] == 32768
    assert body["thinking"] == {"type": "disabled"}
    audit = deepseek_thinking_mode_audit("disabled")
    assert audit["thinking_mode_verified"] is True and audit["thinking_parameter_sent"] is True


def test_thinking_mode_variants_and_invalid_value():
    disabled = build_deepseek_request_payload("p", model="m", thinking_mode="disabled")
    enabled = build_deepseek_request_payload("p", model="m", thinking_mode="enabled")
    default = build_deepseek_request_payload("p", model="m", thinking_mode="provider_default")
    assert disabled["thinking"] == {"type": "disabled"}
    assert enabled["thinking"] == {"type": "enabled"}
    assert "thinking" not in default
    with pytest.raises(ValueError, match="invalid DeepSeek thinking_mode"):
        build_deepseek_request_payload("p", model="m", thinking_mode="sometimes")  # type: ignore[arg-type]


def test_fulltext_defaults_disabled_and_configured_adapter_forwards_mode():
    assert inspect.signature(run_fulltext_l1_v2_extraction).parameters["thinking_mode"].default == "disabled"
    assert inspect.signature(run_l35_pmc_oa_stage).parameters["fulltext_l1_thinking_mode"].default == "disabled"
    captured = {}
    class Inner:
        def extract_json_result(self, prompt, **kwargs):
            captured.update(kwargs); return JSONExtractionResult(payload={}, raw_response="{}")
    ConfiguredJSONClient(Inner(), "deepseek-v4-pro").extract_json_result("p", thinking_mode="disabled")
    assert captured["thinking_mode"] == "disabled" and captured["model"] == "deepseek-v4-pro"


def test_cli_defaults_to_plan_only_and_requires_double_authorization(tmp_path):
    with patch("code_engine.cli.fulltext_l1_v2_provider_smoke_test.write_plan_artifacts", return_value={"api_calls": 0}) as plan:
        assert main(["--run-dir", str(tmp_path)]) == 0
        plan.assert_called_once_with(tmp_path)
    with pytest.raises(SystemExit):
        main(["--run-dir", str(tmp_path), "--execute"])
    with pytest.raises(SystemExit):
        main(["--run-dir", str(tmp_path), "--api"])


def _row(block_id, paper, count, **signals):
    defaults = {"deterministic_signal_count": 1, "human_or_patient": False, "mouse_or_in_vivo": False,
                "in_vitro_or_cell_line": False, "multi_endpoint": False, "simple_single_endpoint": False,
                "low_experiment_probability": False}
    defaults.update(signals)
    return {"block_id": block_id, "pmcid": paper, "historical_observation_count": count, "signals": defaults}


def test_sampling_is_stable_and_covers_required_categories():
    failures = [
        _row("f1", "P1", 20, in_vitro_or_cell_line=True, multi_endpoint=True),
        _row("f2", "P2", 5, human_or_patient=True, simple_single_endpoint=True),
        _row("f3", "P3", 8, mouse_or_in_vivo=True), _row("f4", "P4", 7),
        _row("f5", "P5", 6), _row("f6", "P6", 4), _row("f7", "P7", 3),
    ]
    assert [x["block_id"] for x in _select_nonempty(failures)] == [x["block_id"] for x in _select_nonempty(failures)]
    picked = _select_nonempty(failures)
    assert len(picked) == 6 and len({x["pmcid"] for x in picked}) >= 3
    assert any(x["signals"]["human_or_patient"] for x in picked)
    assert any(x["signals"]["mouse_or_in_vivo"] for x in picked)
    assert any(x["signals"]["in_vitro_or_cell_line"] for x in picked)
    empties = [
        _row("e1", "P1", 0, deterministic_signal_count=5), _row("e2", "P2", 0, deterministic_signal_count=4),
        _row("e3", "P3", 0, deterministic_signal_count=3),
        _row("e4", "P4", 0, deterministic_signal_count=0, low_experiment_probability=True),
        _row("e5", "P5", 0, deterministic_signal_count=0, low_experiment_probability=True),
        _row("e6", "P6", 0, mouse_or_in_vivo=True),
    ]
    selected = _select_empty(empties)
    assert len(selected) == 6
    assert sum(x["signals"]["deterministic_signal_count"] > 0 for x in selected) >= 3
    assert sum(x["signals"]["low_experiment_probability"] for x in selected) >= 2


def test_cache_identity_rejects_historical_prompt_and_accepts_native_v4(tmp_path):
    cache = tmp_path / "cache" / "fulltext_l1_v2"; cache.mkdir(parents=True)
    empty, _ = fulltext_l1_v2_prompt_examples()
    path = cache / "key.json"
    base = {"schema_version": "fulltext_l1_experimental_observation_schema_v2", "source_fulltext_hash": "source",
            "response": empty, "block_provenance": {"block_id": "block"}}
    path.write_text(json.dumps({**base, "prompt_version": "fulltext_experimental_observation_prompt_v3_json_bounded", "prompt_hash": "old"}))
    assert _fresh_cache_status(tmp_path, "key", "block", "source")[0] is False
    path.write_text(json.dumps({**base, "prompt_version": PROMPT_VERSION, "prompt_hash": prompt_hash(),
                                "origin": "fresh_v4_provider_smoke", "configured_thinking_mode": "disabled",
                                "effective_thinking_mode": "disabled", "thinking_parameter_sent": True}))
    assert _fresh_cache_status(tmp_path, "key", "block", "source")[0] is True


def _audit(verified=True):
    return {"thinking": {"thinking_mode_verified": verified, "effective_mode": "disabled" if verified else "unverified"}}


def test_frozen_decision_policy_all_three_outcomes():
    good_nonempty = {"direct_strict_schema_success_count": 6, "systematic_schema_drift": False}
    all_empty = {"remained_empty_count": 6, "became_nonempty_count": 0, "high_risk_valid_nonempty_count": 0}
    result = {"nonempty_failures": good_nonempty, "legacy_empty": all_empty}
    assert decide_rerun_scope("empty_results_semantically_compatible", _audit(), result)[0] == "rerun_unresolved_107_only"
    converted = {"remained_empty_count": 5, "became_nonempty_count": 1, "high_risk_valid_nonempty_count": 1}
    assert decide_rerun_scope("empty_results_semantically_compatible", _audit(), {**result, "legacy_empty": converted})[0] == "rerun_all_200_blocks"
    drift = {"direct_strict_schema_success_count": 3, "systematic_schema_drift": True}
    assert decide_rerun_scope("empty_results_semantically_compatible", _audit(), {**result, "nonempty_failures": drift})[0] == "insufficient_evidence_do_not_rerun"
    assert decide_rerun_scope("compatibility_uncertain", _audit(), result)[0] == "rerun_all_200_blocks"


def test_thinking_unverified_blocks_before_client_or_filesystem(tmp_path):
    class NeverClient:
        def extract_json_result(self, *_args, **_kwargs):
            raise AssertionError("provider called")
    with pytest.raises(RuntimeError, match="thinking_mode_unverified"):
        execute_smoke(tmp_path, api_authorized=True, client=NeverClient(),
                      _thinking_audit={"thinking_mode_verified": False, "effective_mode": "unverified"})


def test_manifest_call_limit_blocks_oversized_manifest(tmp_path):
    artifacts = tmp_path / "artifacts"; artifacts.mkdir()
    samples = [{"block_id": f"b{i}"} for i in range(13)]
    (artifacts / "fulltext_l1_v2_smoke_manifest.json").write_text(json.dumps({"samples": samples}))
    with pytest.raises(RuntimeError, match="exceeds 12"):
        execute_smoke(tmp_path, api_authorized=True, client=object(),
                      _thinking_audit={"thinking_mode_verified": True, "effective_mode": "disabled"})


def test_execution_calls_only_manifest_and_writes_fresh_v4_cache(tmp_path):
    artifacts = tmp_path / "artifacts"; cache = artifacts / "cache" / "fulltext_l1_v2"; cache.mkdir(parents=True)
    samples = []
    inventory = {}
    for index in range(2):
        block_id = f"b{index}"
        samples.append({"block_id": block_id, "sample_group": "historical_completed_empty",
                        "fresh_v4_success_cache_hit": False, "expected_cache_identity": f"key{index}",
                        "rendered_system_prompt_hash": f"rendered{index}", "parent_block_id": block_id,
                        "child_block_id": None, "legacy_empty_risk_subgroup": "high_false_negative_risk"})
        inventory[block_id] = {"paper": {"abstract_observation_ids": []}, "block": {**_block(), "block_id": block_id},
                               "source_fulltext_hash": "source"}
    (artifacts / "fulltext_l1_v2_smoke_manifest.json").write_text(json.dumps({"samples": samples}))
    calls = []
    class Client:
        def extract_json_result(self, prompt, **kwargs):
            calls.append((prompt, kwargs))
            empty, _ = fulltext_l1_v2_prompt_examples()
            return JSONExtractionResult(payload=empty, raw_response=json.dumps(empty), finish_reason="stop",
                                        usage={"completion_tokens": 10}, provider_metadata={"response_format": {"type": "json_object"}})
    with patch("code_engine.fulltext.fulltext_l1_v2_smoke._jsonl", return_value=[{"block_id": "old"}]), \
         patch("code_engine.fulltext.fulltext_l1_v2_smoke._historical_config", return_value={"max_tokens": 32768}), \
         patch("code_engine.fulltext.fulltext_l1_v2_smoke._block_inventory", return_value=inventory), \
         patch("code_engine.fulltext.fulltext_l1_v2_smoke.build_compatibility_report", return_value={"compatibility_decision": "empty_results_semantically_compatible"}), \
         patch("code_engine.fulltext.fulltext_l1_v2_smoke.build_request_chain_audit", return_value={"thinking": {}}), \
         patch("code_engine.fulltext.fulltext_l1_v2_smoke.build_rerun_plan", return_value={"decision": "insufficient_evidence_do_not_rerun"}):
        result = execute_smoke(tmp_path, api_authorized=True, client=Client(),
                               _thinking_audit={"thinking_mode_verified": True, "effective_mode": "disabled"})
    assert result["api_calls"] == 2 and len(calls) == 2
    assert all(call[1]["max_tokens"] == 32768 and call[1]["retry_on_length"] is False for call in calls)
    assert all(call[1]["thinking_mode"] == "disabled" for call in calls)
    assert sorted(path.name for path in cache.glob("*.json")) == ["key0.json", "key1.json"]
    payload = json.loads((cache / "key0.json").read_text())
    assert payload["prompt_version"] == PROMPT_VERSION and payload["schema_hash"] == schema_hash()
    assert payload["transport_metadata"]["thinking_mode"]["effective_mode"] == "disabled"
    assert result["scientific_input_complete_changed"] is False and result["publication_attempted"] is False


def test_positive_reasoning_tokens_stop_remaining_smoke_calls_fail_closed(tmp_path):
    artifacts = tmp_path / "artifacts"; cache = artifacts / "cache" / "fulltext_l1_v2"; cache.mkdir(parents=True)
    samples = []
    inventory = {}
    for index in range(3):
        block_id = f"b{index}"
        samples.append({"block_id": block_id, "sample_group": "historical_nonempty_schema_failure",
                        "fresh_v4_success_cache_hit": False, "expected_cache_identity": f"key{index}",
                        "rendered_system_prompt_hash": f"rendered{index}", "parent_block_id": block_id,
                        "child_block_id": None})
        inventory[block_id] = {"paper": {"abstract_observation_ids": []}, "block": {**_block(), "block_id": block_id},
                               "source_fulltext_hash": "source"}
    (artifacts / "fulltext_l1_v2_smoke_manifest.json").write_text(json.dumps({"samples": samples}))
    calls = []
    class Client:
        def extract_json_result(self, prompt, **kwargs):
            calls.append((prompt, kwargs)); empty, _ = fulltext_l1_v2_prompt_examples()
            return JSONExtractionResult(payload=empty, raw_response=json.dumps(empty), finish_reason="stop",
                                        usage={"completion_tokens": 20, "completion_tokens_details": {"reasoning_tokens": 7}},
                                        provider_metadata={"reasoning_content_present": False})
    with patch("code_engine.fulltext.fulltext_l1_v2_smoke._jsonl", return_value=[{"block_id": "old", "status": "parse_error"}]), \
         patch("code_engine.fulltext.fulltext_l1_v2_smoke._historical_config", return_value={"max_tokens": 32768}), \
         patch("code_engine.fulltext.fulltext_l1_v2_smoke._block_inventory", return_value=inventory), \
         patch("code_engine.fulltext.fulltext_l1_v2_smoke.build_compatibility_report", return_value={"compatibility_decision": "empty_results_semantically_compatible"}), \
         patch("code_engine.fulltext.fulltext_l1_v2_smoke.build_request_chain_audit", return_value={"thinking": {}}):
        result = execute_smoke(tmp_path, api_authorized=True, client=Client(),
                               _thinking_audit={"thinking_mode_verified": True, "effective_mode": "disabled"})
    assert len(calls) == result["api_calls"] == 1
    assert result["provider_thinking_disable_not_honored"] is True and result["stopped_early"] is True
    assert result["rerun_decision"] == "insufficient_evidence_do_not_rerun"
    assert not list(cache.glob("key*.json"))
    assert result["scientific_input_complete_changed"] is False and result["publication_attempted"] is False


def test_schema_hash_is_stable():
    assert schema_hash() == schema_hash()
    assert len(schema_hash()) == 64
