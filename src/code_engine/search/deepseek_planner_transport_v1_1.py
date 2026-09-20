"""Offline-verifiable high-reasoning DeepSeek planner transport amendment.

This module changes request configuration only. The frozen alpha2 prompt,
proposal schema, scientific validator, and deterministic rehydrator are reused.
No request is sent without fresh authorization and a raw-response sink.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any, Callable

from code_engine.extraction.deepseek_client import (
    DeepSeekClient, JSONExtractionResult, build_deepseek_request_payload,
)
from code_engine.search.alpha2_linked_relation_v1 import PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA
from code_engine.search.deepseek_planner_transport_v1 import (
    DEEPSEEK_PROVIDER_SCHEMA, PROMPT_TEXT, REHYDRATOR_VERSION,
    VALIDATOR_VERSION, DeepSeekPlannerTransportV1, rehydrate_provider_response,
    static_schema_preflight,
)
from code_engine.search.proposition_aware_query_planner_v1 import canonical_target_hash, sha256_value

CONFIG_VERSION = "DeepSeekQueryPlannerConfigV1_1"
TRANSPORT_VERSION = "DeepSeekPlannerTransportV1_1"
API_SURFACE = "CHAT_COMPLETIONS_API"
TEMPERATURE_POLICY = "OMIT_IN_THINKING_MODE"
FALLBACK_POLICY = "DEEPSEEK_ONLY_FAIL_CLOSED"
CACHE_IDENTITY_VERSION = "DeepSeekPlannerCacheIdentityV1_1"


@dataclass(frozen=True)
class DeepSeekQueryPlannerConfigV1_1:
    provider: str = "deepseek"
    model: str = "deepseek-v4-pro"
    api_surface: str = API_SURFACE
    thinking_mode: str = "enabled"
    reasoning_effort: str = "high"
    temperature_policy: str = TEMPERATURE_POLICY
    maximum_attempts: int = 1
    repair_policy: str = "FAIL_CLOSED_NO_AUTOMATIC_RETRY_OR_REPAIR"
    provider_fallback_policy: str = FALLBACK_POLICY
    transport_version: str = TRANSPORT_VERSION
    prompt_v2_sha256: str = sha256_value(PROMPT_TEXT)
    proposal_schema_sha256: str = sha256_value(PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA)
    provider_schema_sha256: str = sha256_value(DEEPSEEK_PROVIDER_SCHEMA)
    rehydrator_version: str = REHYDRATOR_VERSION
    validator_version: str = VALIDATOR_VERSION
    cache_identity_version: str = CACHE_IDENTITY_VERSION

    def __post_init__(self) -> None:
        frozen = {
            "provider": "deepseek", "model": "deepseek-v4-pro", "api_surface": API_SURFACE,
            "thinking_mode": "enabled", "reasoning_effort": "high",
            "temperature_policy": TEMPERATURE_POLICY, "maximum_attempts": 1,
            "repair_policy": "FAIL_CLOSED_NO_AUTOMATIC_RETRY_OR_REPAIR",
            "provider_fallback_policy": FALLBACK_POLICY, "transport_version": TRANSPORT_VERSION,
            "prompt_v2_sha256": sha256_value(PROMPT_TEXT),
            "proposal_schema_sha256": sha256_value(PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA),
            "provider_schema_sha256": sha256_value(DEEPSEEK_PROVIDER_SCHEMA),
            "rehydrator_version": REHYDRATOR_VERSION,
            "validator_version": VALIDATOR_VERSION,
            "cache_identity_version": CACHE_IDENTITY_VERSION,
        }
        if any(getattr(self, name) != expected for name, expected in frozen.items()):
            raise ValueError("DeepSeek planner alpha2.1 configuration deviates from frozen mapping")

    def to_dict(self) -> dict[str, Any]:
        return {"artifact_schema_version": CONFIG_VERSION, **asdict(self)}


DEFAULT_CONFIG = DeepSeekQueryPlannerConfigV1_1()


def planner_cache_identity_v1_1(target: dict[str, Any],
                                config: DeepSeekQueryPlannerConfigV1_1 = DEFAULT_CONFIG) -> str:
    return sha256_value({
        "cache_identity_version": config.cache_identity_version,
        "provider": config.provider, "model": config.model,
        "canonical_target_sha256": canonical_target_hash(target),
        "planner_config_sha256": sha256_value(config.to_dict()),
        "planner_prompt_v2_sha256": config.prompt_v2_sha256,
        "proposal_schema_sha256": config.proposal_schema_sha256,
        "provider_transport_schema_sha256": config.provider_schema_sha256,
        "rehydrator_version": config.rehydrator_version,
        "validator_version": config.validator_version,
    })


class DeepSeekPlannerTransportV1_1:
    """One-attempt Chat Completions transport; no implicit credentials or fallback."""

    endpoint = DeepSeekClient.endpoint

    def __init__(self, config: DeepSeekQueryPlannerConfigV1_1 = DEFAULT_CONFIG):
        self.config = config
        if not static_schema_preflight()["passed"]:
            raise ValueError("frozen local DeepSeek provider-schema preflight failed")

    def preview_request(self, target: dict[str, Any]) -> dict[str, Any]:
        canonical_target_hash(target)
        # The V1 alpha2 request messages are frozen; only provider controls change.
        messages = DeepSeekPlannerTransportV1().preview_request(target)["messages"]
        payload = build_deepseek_request_payload(
            messages, model=self.config.model, thinking_mode=self.config.thinking_mode,
            reasoning_effort=self.config.reasoning_effort, temperature=None, top_p=None,
        )
        if (payload.get("thinking") != {"type": "enabled"}
                or payload.get("reasoning_effort") != "high"
                or "temperature" in payload or "top_p" in payload
                or any(key in payload for key in ("service_tier", "prompt_cache_key", "prompt_cache_retention"))):
            raise ValueError("DeepSeek reasoning request mapping contradicted frozen configuration")
        return payload

    def serialized_body(self, target: dict[str, Any]) -> bytes:
        """Exact JSON bytes DeepSeekClient sends with its current serializer."""
        return json.dumps(self.preview_request(target)).encode("utf-8")

    def offline_request_fixture(self, target: dict[str, Any]) -> dict[str, Any]:
        body = self.serialized_body(target)
        return {"artifact_schema_version": "DeepSeekPlannerOfflineRequestFixtureV1_1",
                "api_surface": API_SURFACE, "method": "POST", "endpoint": self.endpoint,
                "content_type": "application/json", "authorization_header_value_recorded": False,
                "request_body_json": body.decode("utf-8"),
                "request_body_sha256": hashlib.sha256(body).hexdigest(),
                "provider_calls": 0, "remote_acceptance_verified": False}

    def execute_result(self, *, target: dict[str, Any], api_key: str | None,
                       raw_response_sink: Callable[[bytes], Any] | None,
                       explicitly_authorized: bool = False) -> JSONExtractionResult:
        """Future separately-authorized call; caller freezes result before validation."""
        if not explicitly_authorized:
            raise PermissionError("fresh DeepSeek planner call requires separate authorization")
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY required; no provider fallback")
        if raw_response_sink is None:
            raise ValueError("durable raw-response sink required before provider call")
        request = self.preview_request(target)
        client = DeepSeekClient(api_key=api_key, max_retries=0)
        return client.extract_json_result(
            request["messages"], model=self.config.model, thinking_mode="enabled",
            reasoning_effort="high", temperature=None, top_p=None,
            raw_response_sink=raw_response_sink,
        )

    def validate_and_rehydrate(self, response: dict[str, Any], *, target_id: str,
                               target: dict[str, Any]) -> dict[str, Any]:
        """Run only after the raw provider response has been independently frozen."""
        result = rehydrate_provider_response(response, target_id=target_id,
                                             target=target, config=self.config)
        # V1's deterministic rehydrator derives its key from config. Its
        # identity material is equivalent to the versioned V1.1 key here.
        if result["planner_cache_key_sha256"] != planner_cache_identity_v1_1(target, self.config):
            raise ValueError("planner cache identity mismatch")
        return result
