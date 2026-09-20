"""Offline-only regression tests for the alpha2.1 transport amendment."""

from dataclasses import replace
from copy import deepcopy
import hashlib
import json
import os
from unittest.mock import patch

import pytest

from code_engine.extraction.deepseek_client import DeepSeekClient, build_deepseek_request_payload
from code_engine.extraction.client_factory import build_json_client_from_config
from code_engine.search.alpha2_linked_relation_v1 import PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA
from code_engine.search.deepseek_planner_transport_v1 import (
    DEFAULT_CONFIG as ALPHA2_CONFIG, DEEPSEEK_PROVIDER_SCHEMA, PROMPT_TEXT,
    planner_cache_identity, static_schema_preflight,
)
from code_engine.search.deepseek_planner_transport_v1_1 import (
    DEFAULT_CONFIG, DeepSeekPlannerTransportV1_1, planner_cache_identity_v1_1,
)
from code_engine.search.proposition_aware_query_planner_v1 import sha256_value

TARGET = {"artifact_schema_version": "ScientificPropositionTargetV1",
          "subject": "EGF", "object": "ERK1/2", "relation_family": "increases",
          "measurement_property_endpoint": "phosphorylation",
          "context_qualifier_dimensions": {"biological_unit": ["epidermal keratinocyte"]}}


def test_high_cannot_coexist_with_disabled_thinking():
    with pytest.raises(ValueError):
        replace(DEFAULT_CONFIG, thinking_mode="disabled")
    with pytest.raises(ValueError):
        build_deepseek_request_payload("JSON object", model="deepseek-v4-pro",
                                       thinking_mode="disabled", reasoning_effort="high")


def test_chat_completions_mapping_and_omitted_sampling_controls():
    payload = DeepSeekPlannerTransportV1_1().preview_request(TARGET)
    assert payload["model"] == "deepseek-v4-pro"
    assert payload["thinking"] == {"type": "enabled"}
    assert payload["reasoning_effort"] == "high"
    assert payload["response_format"] == {"type": "json_object"}
    assert "temperature" not in payload and "top_p" not in payload
    assert "service_tier" not in payload and "prompt_cache_key" not in payload


def test_exact_fixture_matches_adapter_builder():
    transport = DeepSeekPlannerTransportV1_1()
    fixture = transport.offline_request_fixture(TARGET)
    actual = json.loads(fixture["request_body_json"])
    assert actual == transport.preview_request(TARGET)
    assert hashlib.sha256(fixture["request_body_json"].encode()).hexdigest() == fixture["request_body_sha256"]
    assert fixture["endpoint"] == "https://api.deepseek.com/v1/chat/completions"
    assert fixture["authorization_header_value_recorded"] is False


def test_actual_adapter_serializes_fixture_body_without_network():
    transport = DeepSeekPlannerTransportV1_1()
    captured = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                    "usage": {"total_tokens": 1}}

    def fake_post(endpoint, *, content, headers, timeout):
        captured.update(endpoint=endpoint, content=content, headers=headers)
        return FakeResponse()

    with patch("code_engine.extraction.deepseek_client.httpx.post", side_effect=fake_post):
        result = DeepSeekClient(api_key="fake", max_retries=0).extract_json_result(
            transport.preview_request(TARGET)["messages"], model="deepseek-v4-pro",
            thinking_mode="enabled", reasoning_effort="high", temperature=None, top_p=None,
            raw_response_sink=lambda raw: captured.update(raw_response=raw),
        )
    assert captured["content"] == transport.serialized_body(TARGET)
    assert captured["endpoint"] == transport.endpoint
    assert captured["raw_response"] == b"{}"
    assert result.provider_metadata["reasoning_effort"] == "high"


def test_no_openai_fallback_missing_deepseek_credentials():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "fake"}, clear=True):
        assert build_json_client_from_config() is None
        with patch("code_engine.search.deepseek_planner_transport_v1_1.DeepSeekClient") as client:
            with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
                DeepSeekPlannerTransportV1_1().execute_result(
                    target=TARGET, api_key=None, raw_response_sink=lambda _: None,
                    explicitly_authorized=True)
            client.assert_not_called()


def test_separate_authorization_and_raw_sink_required():
    with patch("code_engine.search.deepseek_planner_transport_v1_1.DeepSeekClient") as client:
        with pytest.raises(PermissionError):
            DeepSeekPlannerTransportV1_1().execute_result(
                target=TARGET, api_key="fake", raw_response_sink=lambda _: None)
        with pytest.raises(ValueError, match="sink"):
            DeepSeekPlannerTransportV1_1().execute_result(
                target=TARGET, api_key="fake", raw_response_sink=None,
                explicitly_authorized=True)
        client.assert_not_called()


def test_cache_changes_from_alpha2_and_prompt_schema_unchanged():
    assert planner_cache_identity_v1_1(TARGET) != planner_cache_identity(TARGET, ALPHA2_CONFIG)
    assert DEFAULT_CONFIG.prompt_v2_sha256 == sha256_value(PROMPT_TEXT)
    assert DEFAULT_CONFIG.proposal_schema_sha256 == sha256_value(PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA)
    assert DEFAULT_CONFIG.provider_schema_sha256 == sha256_value(DEEPSEEK_PROVIDER_SCHEMA)
    assert static_schema_preflight()["passed"] is True
    assert static_schema_preflight()["remote_api_acceptance_verified"] is False


def test_frozen_rehydrator_uses_amended_cache_identity():
    from tests.test_alpha2_linked_relation_deepseek_offline import TARGET as VALID_TARGET, proposal

    result = DeepSeekPlannerTransportV1_1().validate_and_rehydrate(
        proposal(), target_id="development-only", target=VALID_TARGET)
    assert result["planner_cache_key_sha256"] == planner_cache_identity_v1_1(VALID_TARGET)


def test_builder_legacy_defaults_unchanged():
    old = build_deepseek_request_payload("JSON object", model="deepseek-v4-pro",
                                         thinking_mode="disabled")
    assert old["thinking"] == {"type": "disabled"}
    assert old["temperature"] == 0.0 and old["top_p"] == 1.0
    assert "reasoning_effort" not in old
