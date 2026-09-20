"""Prospective DeepSeek-only alpha2 planner transport; no implicit execution.

DeepSeek JSON object mode is a transport format, not remote schema enforcement.
Every response is checked locally and request identity is rehydrated locally.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from copy import deepcopy
from typing import Any

from code_engine.extraction.deepseek_client import DeepSeekClient, build_deepseek_request_payload
from code_engine.search.alpha2_linked_relation_v1 import (
    PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA, validate_planner_proposal_v2,
)
from code_engine.search.proposition_aware_query_planner_v1 import canonical_bytes, canonical_target_hash, sha256_value

CONFIG_VERSION = "DeepSeekQueryPlannerConfigV1"
TRANSPORT_VERSION = "DeepSeekPlannerTransportV1"
PREFLIGHT_VERSION = "StaticDeepSeekPlannerSchemaPreflightV1"
PROMPT_VERSION = "PlannerPromptV2"
REHYDRATOR_VERSION = "DeepSeekPlannerRequestRehydratorV1"
VALIDATOR_VERSION = "PlannerProposalPayloadV2ValidatorV1"

PROMPT_TEXT = """You are PROPOSITION_AWARE_QUERY_PLANNER. Propose retrieval language only,
not scientific truth or entity identity. Return one JSON object following the supplied
PlannerProposalPayloadV2 schema. For EVERY relation-applicable blueprint, provide at
least one LinkedRelationCandidateV1. Explicitly link the actor or intervention to
the response endpoint in a single phrase, rather than independent keyword bags.
Represent subject, relation family, direction, response target, endpoint property,
and required nested conditioning treatment or therapy as distinct roles. Preserve
target-specific canonical surface forms from the immutable request when reasonably
possible, especially in linked phrases. Propose lexical alternatives separately.
Never add authority labels, references, validator judgments, coverage, compiler
results, canonical target echoes, cache IDs, or claims of scientific relevance.
"""


@dataclass(frozen=True)
class DeepSeekQueryPlannerConfigV1:
    provider: str = "deepseek"
    model: str = "deepseek-v4-pro"
    endpoint_mechanism: str = "repository.DeepSeekClient"
    prompt_version: str = PROMPT_VERSION
    proposal_schema_version: str = "PlannerProposalPayloadV2"
    transport_version: str = TRANSPORT_VERSION
    thinking_mode: str = "disabled"
    temperature: float = 0.0
    top_p: float = 1.0
    maximum_attempts: int = 1
    repair_policy: str = "FAIL_CLOSED_NO_AUTOMATIC_RETRY_OR_REPAIR"
    cache_identity_version: str = "DeepSeekPlannerCacheIdentityV2"

    def __post_init__(self) -> None:
        if self.provider != "deepseek" or self.model != "deepseek-v4-pro":
            raise ValueError("prospective planner provider/model must be frozen DeepSeek configuration")
        if self.maximum_attempts != 1 or self.thinking_mode != "disabled" or self.temperature != 0:
            raise ValueError("planner attempt/thinking/temperature policy mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {"artifact_schema_version": CONFIG_VERSION, **asdict(self)}


DEFAULT_CONFIG = DeepSeekQueryPlannerConfigV1()
DEEPSEEK_PROVIDER_SCHEMA = deepcopy(PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA)
DEEPSEEK_PROVIDER_SCHEMA_SHA256 = sha256_value(DEEPSEEK_PROVIDER_SCHEMA)


def static_schema_preflight(schema: dict[str, Any] = DEEPSEEK_PROVIDER_SCHEMA) -> dict[str, Any]:
    """Local projection check only; makes no assertion about remote API support."""
    forbidden = {"canonical_target", "target_id", "authority_reference", "proposal_class",
                 "validator_decision", "coverage", "compiler_result", "cache_identity",
                 "artifact_schema_version", "deterministic_classification"}
    errors: list[str] = []

    def walk(node: Any, path: str) -> None:
        if not isinstance(node, dict):
            errors.append(f"{path}: schema node not object")
            return
        type_spec = node.get("type")
        if type_spec == "object":
            props = node.get("properties")
            if node.get("additionalProperties") is not False or not isinstance(props, dict):
                errors.append(f"{path}: object is not closed")
                return
            if set(node.get("required", [])) != set(props):
                errors.append(f"{path}: required fields differ from properties")
            if set(props) & forbidden:
                errors.append(f"{path}: provider owns forbidden fields")
            for name, child in props.items():
                walk(child, f"{path}.{name}")
        elif type_spec == "array" or (isinstance(type_spec, list) and "array" in type_spec):
            if "items" not in node:
                errors.append(f"{path}: array lacks items")
            else:
                walk(node["items"], path + "[]")
        elif type_spec not in ("string", "boolean", ["string", "null"]):
            errors.append(f"{path}: unsupported local schema shape")

    walk(schema, "$root")
    if set(schema.get("properties", {})) != {"retrieval_intents"}:
        errors.append("provider projection root must contain only retrieval_intents")
    hash_matches_frozen = sha256_value(schema) == DEEPSEEK_PROVIDER_SCHEMA_SHA256
    if not hash_matches_frozen:
        errors.append("provider schema differs from frozen projection")
    stable = sha256_value(schema) == sha256_value(deepcopy(schema))
    if not stable:
        errors.append("schema hash instability")
    return {"artifact_schema_version": PREFLIGHT_VERSION, "passed": not errors,
            "errors": errors, "schema_sha256": sha256_value(schema),
            "provider_projection_deterministic": stable,
            "schema_hash_matches_frozen": hash_matches_frozen,
            "remote_api_acceptance_verified": False, "network_calls": 0}


def planner_cache_identity(target: dict[str, Any], config: DeepSeekQueryPlannerConfigV1 = DEFAULT_CONFIG) -> str:
    return sha256_value({
        "provider": config.provider, "model": config.model,
        "canonical_target_sha256": canonical_target_hash(target),
        "planner_config_sha256": sha256_value(config.to_dict()),
        "planner_prompt_v2_sha256": sha256_value(PROMPT_TEXT),
        "proposal_schema_sha256": sha256_value(PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA),
        "provider_transport_schema_sha256": sha256_value(DEEPSEEK_PROVIDER_SCHEMA),
        "rehydrator_version": REHYDRATOR_VERSION, "validator_version": VALIDATOR_VERSION,
        "cache_identity_version": config.cache_identity_version,
    })


def rehydrate_provider_response(response: dict[str, Any], *, target_id: str,
                                target: dict[str, Any], config: DeepSeekQueryPlannerConfigV1 = DEFAULT_CONFIG) -> dict[str, Any]:
    validate_planner_proposal_v2(response, target=target)
    return {"artifact_schema_version": "RehydratedPlannerProposalV2",
            "target_id": target_id, "canonical_target_sha256": canonical_target_hash(target),
            "planner_config_sha256": sha256_value(config.to_dict()),
            "planner_prompt_sha256": sha256_value(PROMPT_TEXT),
            "planner_cache_key_sha256": planner_cache_identity(target, config),
            "planner_proposal_payload": deepcopy(response),
            "planner_proposal_sha256": sha256_value(response),
            "rehydrator_version": REHYDRATOR_VERSION, "validator_version": VALIDATOR_VERSION}


class DeepSeekPlannerTransportV1:
    """Explicit-call-only transport; no fallback, retry, repair, or implicit key lookup."""

    def __init__(self, config: DeepSeekQueryPlannerConfigV1 = DEFAULT_CONFIG):
        self.config = config
        if not static_schema_preflight()["passed"]:
            raise ValueError("local DeepSeek planner preflight failed")

    def preview_request(self, target: dict[str, Any]) -> dict[str, Any]:
        # JSON-object instruction is required by the repository DeepSeek adapter.
        canonical_target_hash(target)
        return build_deepseek_request_payload(
            [{"role": "system", "content": PROMPT_TEXT},
             {"role": "user", "content": "Return a JSON object. Immutable target: "
              + canonical_bytes(target).decode("utf-8") + "\nModel-only JSON Schema: "
              + canonical_bytes(DEEPSEEK_PROVIDER_SCHEMA).decode("utf-8")}],
            model=self.config.model, temperature=self.config.temperature,
            top_p=self.config.top_p, thinking_mode=self.config.thinking_mode,
        )

    def execute(self, *, target_id: str, target: dict[str, Any], api_key: str | None,
                explicitly_authorized: bool = False) -> dict[str, Any]:
        if not explicitly_authorized:
            raise PermissionError("fresh DeepSeek planner call requires separate authorization")
        if not api_key:
            raise ValueError("DeepSeek API key required; OpenAI fallback disabled")
        client = DeepSeekClient(api_key=api_key, max_retries=0)
        result = client.extract_json_result(self.preview_request(target)["messages"],
                                            model=self.config.model, temperature=0,
                                            top_p=1, thinking_mode=self.config.thinking_mode)
        if result.attempt_count != 1:
            raise RuntimeError("planner attempt policy violated")
        if result.warnings or result.finish_reason != "stop":
            raise RuntimeError("planner response incomplete or required parser repair")
        return rehydrate_provider_response(result.payload, target_id=target_id,
                                           target=target, config=self.config)
