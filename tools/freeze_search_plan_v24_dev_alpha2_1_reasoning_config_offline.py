"""Freeze the offline alpha2.1 DeepSeek reasoning/transport amendment.

No provider client is created. No HTTP, LLM, or literature retrieval is used.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from code_engine.fulltext.fulltext_l1_v2 import cache_key as historical_l1_cache_key
from code_engine.search.alpha2_linked_relation_v1 import (
    ANCHOR_VERSION, BINDING_VERSION, ELIGIBILITY_VERSION,
    PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA,
)
from code_engine.search.deepseek_planner_transport_v1 import (
    DEFAULT_CONFIG as ALPHA2_CONFIG, DEEPSEEK_PROVIDER_SCHEMA, PROMPT_TEXT,
    REHYDRATOR_VERSION, VALIDATOR_VERSION,
    planner_cache_identity as alpha2_planner_cache_identity,
    static_schema_preflight,
)
from code_engine.search.deepseek_planner_transport_v1_1 import (
    API_SURFACE, DEFAULT_CONFIG, DeepSeekPlannerTransportV1_1,
    TEMPERATURE_POLICY, planner_cache_identity_v1_1,
)
from code_engine.search.proposition_aware_query_planner_v1 import (
    DEFAULT_DEVELOPMENT_CONFIG, planner_cache_key as historical_openai_cache_key,
    sha256_value,
)

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260920_search_plan_v24_dev_alpha2_1_deepseek_reasoning_config_offline"
ALPHA2 = ROOT / "runs/20260920_search_plan_v24_dev_alpha2_linked_relation_deepseek_migration_offline"
AUTOPSY = ROOT / "runs/20260920_search_plan_v24_dev_alpha1_zero_query_autopsy_and_provider_audit_offline"
AUTHORITY = ROOT / "runs/20260918_search_plan_v24_dev_planner_authority_contract_split_offline"
ALPHA2_ROOT = "918e0badbaeb70c439ae8d6e1d3bcc1eb5d5697c5df75b38dc2819357890a4e8"
AUTOPSY_ROOT = "6e04742306ca027ae0423e68ad958915aadf4a38b313dcf1819845d396ed0dc7"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def verify_root(path: Path, expected: str) -> dict:
    validation = read(path / "validation.json")
    pairs = validation["aggregate_components"]
    for name, frozen_hash in pairs:
        require(digest(path / name) == frozen_hash, f"upstream component changed: {path.name}/{name}")
    require(sha256_value(pairs) == expected, f"upstream root changed: {path.name}")
    return {"root_sha256": expected, "component_count": len(pairs), "verified": True}


def write(name: str, value) -> None:
    path = RUN / name
    require(not path.is_symlink(), f"output symlink forbidden: {name}")
    path.write_text(json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def text(name: str, value: str) -> None:
    path = RUN / name
    require(not path.is_symlink(), f"output symlink forbidden: {name}")
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def main() -> None:
    upstream = {"artifact_schema_version": "Alpha2_1UpstreamRootVerificationV1",
                "alpha2": verify_root(ALPHA2, ALPHA2_ROOT),
                "alpha1_zero_query_autopsy": verify_root(AUTOPSY, AUTOPSY_ROOT)}
    frozen_config = read(ALPHA2 / "deepseek_query_planner_config_v1.json")
    require(frozen_config["thinking_mode"] == "disabled", "expected alpha2 conflict absent")
    require(ALPHA2_CONFIG.thinking_mode == "disabled", "alpha2 code config unexpectedly changed")
    old_safety = read(ALPHA2 / "scientific_state_safety_audit.json")
    protected_source_hashes = old_safety["implementation_source_sha256"]
    for name, frozen_hash in protected_source_hashes.items():
        require(digest(ROOT / name) == frozen_hash, f"alpha2 protected source changed: {name}")
    frozen_prompt = (ALPHA2 / "planner_prompt_v2.md").read_text(encoding="utf-8")
    frozen_proposal_schema = read(ALPHA2 / "planner_proposal_payload_v2_schema.json")
    frozen_provider_schema = read(ALPHA2 / "deepseek_provider_schema.json")
    require(frozen_prompt == PROMPT_TEXT, "Planner Prompt V2 changed")
    require(sha256_value(frozen_proposal_schema) == sha256_value(PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA),
            "PlannerProposalPayloadV2 changed")
    require(sha256_value(frozen_provider_schema) == sha256_value(DEEPSEEK_PROVIDER_SCHEMA),
            "DeepSeek provider schema changed")
    require(DEFAULT_CONFIG.rehydrator_version == REHYDRATOR_VERSION
            and DEFAULT_CONFIG.validator_version == VALIDATOR_VERSION,
            "deterministic post-validation identity changed")
    require((ANCHOR_VERSION, ELIGIBILITY_VERSION, BINDING_VERSION) ==
            ("SearchAnchorCompatibilityV1", "SearchOnlyEligibilityV1_1", "RelationBindingAssessmentV1_1"),
            "scientific component version changed")
    compiler_path = "src/code_engine/search/query_compiler_v24_dev.py"
    compiler_diff = subprocess.run(["git", "diff", "--quiet", "--", compiler_path],
                                   cwd=ROOT, check=False)
    require(compiler_diff.returncode == 0, "compiler has local modifications")

    target_rows = [json.loads(line) for line in
                   (AUTHORITY / "validated_development_plans.jsonl").read_text(encoding="utf-8").splitlines()
                   if line]
    targets = [row["validated_plan"]["canonical_proposition"]["target_payload"]
               for row in target_rows if row["case_id"] == "heldout_v2_101"]
    require(len(targets) == 1, "case-101 frozen target missing or duplicated")
    target = targets[0]
    require(target["case_id"] == "heldout_v2_101", "wrong target selected")
    transport = DeepSeekPlannerTransportV1_1()
    fixture = transport.offline_request_fixture(target)
    body = json.loads(fixture["request_body_json"])
    require(body == transport.preview_request(target), "fixture differs from runtime serializer")
    require(body["model"] == "deepseek-v4-pro", "wrong model in request")
    require(body["thinking"] == {"type": "enabled"} and body["reasoning_effort"] == "high",
            "high reasoning not serialized")
    require("temperature" not in body and "top_p" not in body, "sampling control leaked into thinking mode")
    require(not ({"service_tier", "prompt_cache_key", "prompt_cache_retention"} & body.keys()),
            "OpenAI-specific request field leaked")
    require(body["messages"][0]["content"] == PROMPT_TEXT, "Planner Prompt V2 changed in request")
    require(len(body["messages"]) == 2, "unexpected provider evidence surface")
    require("Immutable target: " in body["messages"][1]["content"]
            and "Model-only JSON Schema: " in body["messages"][1]["content"],
            "target/schema request context absent")
    require(all(fragment not in fixture["request_body_json"] for fragment in
                ("alpha1 failure", "known PMID", "PASS A", "PASS B", "hit count")),
            "hidden development or evaluation material leaked to fixture")
    preflight = static_schema_preflight()
    require(preflight["passed"] and not preflight["remote_api_acceptance_verified"],
            "local schema preflight failed or claimed remote proof")
    key_new = planner_cache_identity_v1_1(target)
    key_alpha2 = alpha2_planner_cache_identity(target)
    key_openai = historical_openai_cache_key(
        target, DEFAULT_DEVELOPMENT_CONFIG,
        prompt_version=DEFAULT_DEVELOPMENT_CONFIG.prompt_version,
        schema_version=DEFAULT_DEVELOPMENT_CONFIG.schema_version)
    key_l1 = historical_l1_cache_key(
        source_fulltext_hash="0" * 64, chunk_hash="1" * 64,
        provider="deepseek", model="deepseek-v4-pro", config_hash="2" * 64,
        candidate_prior_hash="3" * 64, thinking_mode="disabled")
    require(len({key_new, key_alpha2, key_openai, key_l1}) == 4,
            "planner cache identity collided with historical identity")

    RUN.mkdir(parents=True, exist_ok=True)
    write("upstream_root_verification.json", upstream)
    write("alpha2_config_conflict_audit.json", {
        "artifact_schema_version": "Alpha2ConfigConflictAuditV1",
        "classification": "DEEPSEEK_REASONING_CONFIGURATION_AMENDMENT",
        "alpha2_thinking_mode": "disabled", "requested_reasoning_effort": "high",
        "previous_provider_requests_attempted": 0, "previous_model_inference_calls": 0,
        "reasoning_configuration_contradiction_after_amendment": False})
    write("deepseek_query_planner_config_v1_1.json", DEFAULT_CONFIG.to_dict())
    write("deepseek_api_surface_selection.json", {
        "artifact_schema_version": "DeepSeekAPISurfaceSelectionV1_1",
        "selected_surface": API_SURFACE, "endpoint": transport.endpoint,
        "method": "POST", "repository_client": "DeepSeekClient.extract_json_result",
        "responses_api_used": False, "two_runtime_mappings": False,
        "remote_api_acceptance_verified": False})
    write("deepseek_reasoning_mapping_contract.json", {
        "artifact_schema_version": "DeepSeekReasoningMappingContractV1_1",
        "logical": {"thinking_mode": "enabled", "reasoning_effort": "high"},
        "serialized": {"thinking": {"type": "enabled"}, "reasoning_effort": "high"},
        "selected_api_surface": API_SURFACE,
        "reasoning_configuration_contradiction": False,
        "sdk_extra_body_required": False,
        "serialization_mechanism": "repository raw HTTP JSON body",
        "remote_parameter_acceptance_verified": False})
    write("deepseek_request_parameter_audit.json", {
        "artifact_schema_version": "DeepSeekRequestParameterAuditV1_1",
        "implementation_source_sha256": {
            name: digest(ROOT / name) for name in (
                "src/code_engine/extraction/deepseek_client.py",
                "src/code_engine/search/deepseek_planner_transport_v1_1.py",
                "tools/freeze_search_plan_v24_dev_alpha2_1_reasoning_config_offline.py")},
        "top_level_request_fields": sorted(body),
        "model": body["model"], "thinking": body["thinking"],
        "reasoning_effort": body["reasoning_effort"],
        "response_format": body["response_format"],
        "serialized_body_sha256": fixture["request_body_sha256"],
        "request_serialization_verified_offline": True,
        "provider_calls": 0})
    write("temperature_policy_audit.json", {
        "artifact_schema_version": "DeepSeekPlannerTemperaturePolicyAuditV1_1",
        "temperature_policy": TEMPERATURE_POLICY,
        "temperature_present_in_request": "temperature" in body,
        "top_p_present_in_request": "top_p" in body,
        "temperature_effective_control_claimed": False})
    write("openai_specific_parameter_removal_audit.json", {
        "artifact_schema_version": "DeepSeekOpenAISpecificParameterAuditV1_1",
        "service_tier_present": "service_tier" in body,
        "openai_prompt_cache_fields_present": bool(
            {"prompt_cache_key", "prompt_cache_retention"} & body.keys()),
        "openai_structured_output_renderer_used": False,
        "openai_fallback_enabled": False,
        "provider_schema_is_model_only": set(DEEPSEEK_PROVIDER_SCHEMA["properties"]) == {"retrieval_intents"}})
    write("planner_cache_identity_v1_1_audit.json", {
        "artifact_schema_version": "DeepSeekPlannerCacheIdentityV1_1AuditV1",
        "case_id": "heldout_v2_101", "target_sha256": sha256_value(target),
        "config_sha256": sha256_value(DEFAULT_CONFIG.to_dict()),
        "alpha2_1_key_sha256": key_new, "alpha2_disabled_key_sha256": key_alpha2,
        "historical_openai_planner_key_sha256": key_openai,
        "historical_deepseek_l1_key_sha256": key_l1,
        "all_pairwise_distinct": True})
    write("heldout_v2_101_offline_request_fixture.json", fixture)
    write("deepseek_schema_preflight_v1_1.json", {
        **preflight, "selected_api_surface": API_SURFACE,
        "fixture_provider_schema_sha256": DEFAULT_CONFIG.provider_schema_sha256,
        "fixture_request_body_sha256": fixture["request_body_sha256"]})
    write("provider_routing_safety_audit.json", {
        "artifact_schema_version": "DeepSeekPlannerProviderRoutingSafetyV1_1",
        "planner_default_provider": "deepseek", "planner_openai_fallback_enabled": False,
        "scientific_pipeline_openai_fallback_enabled": False,
        "missing_deepseek_credentials_fail_closed": True,
        "thinking_silently_disabled": False, "provider_model_switch_enabled": False,
        "provider_calls": 0})
    write("scientific_component_immutability_audit.json", {
        "artifact_schema_version": "Alpha2_1ScientificComponentImmutabilityAuditV1",
        "protected_source_hashes_verified": protected_source_hashes,
        "planner_prompt_v2_sha256": sha256_value(PROMPT_TEXT),
        "planner_proposal_payload_v2_sha256": sha256_value(PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA),
        "provider_schema_sha256": sha256_value(DEEPSEEK_PROVIDER_SCHEMA),
        "search_anchor_version": ANCHOR_VERSION,
        "search_only_version": ELIGIBILITY_VERSION,
        "relation_binding_version": BINDING_VERSION,
        "compiler_source_sha256": digest(ROOT / compiler_path),
        "planner_prompt_v2_changed": False,
        "planner_proposal_payload_v2_changed": False,
        "search_anchor_logic_changed": False, "search_only_logic_changed": False,
        "relation_binding_logic_changed": False, "compiler_changed": False})
    write("next_smoke_authorization_boundary.json", {
        "artifact_schema_version": "Alpha2_1NextSmokeAuthorizationBoundaryV1",
        "previous_smoke_authorization_consumed": False,
        "new_frozen_configuration_requires_fresh_explicit_provider_call_authorization": True,
        "future_case_limit": ["heldout_v2_101"],
        "this_run_provider_calls": 0, "this_run_retrieval_calls": 0})
    summary = {"artifact_schema_version": "SearchPlanV24DevAlpha2_1SummaryV1",
               "status": "completed", "classification": "DEEPSEEK_REASONING_CONFIGURATION_AMENDMENT",
               "provider": "deepseek", "model": "deepseek-v4-pro",
               "deepseek_api_surface": API_SURFACE,
               "thinking_enabled": True, "reasoning_effort": "high",
               "reasoning_configuration_contradiction": False,
               "temperature_policy": TEMPERATURE_POLICY,
               "temperature_effective_control_claimed": False,
               "planner_openai_fallback_enabled": False,
               "scientific_pipeline_openai_fallback_enabled": False,
               "deepseek_request_serialization_verified_offline": True,
               "local_schema_preflight_pass": True,
               "planner_prompt_v2_changed": False,
               "planner_proposal_payload_v2_changed": False,
               "search_anchor_logic_changed": False,
               "search_only_logic_changed": False,
               "relation_binding_logic_changed": False,
               "compiler_changed": False,
               "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
               "retrieval_calls": 0, "candidate_records_seen": 0,
               "previous_smoke_authorization_consumed": False,
               "fresh_provider_call_authorization_required": True,
               "remote_parameter_acceptance_verified": False}
    write("summary.json", summary)
    components = [[path.name, digest(path)] for path in sorted(RUN.iterdir())
                  if path.is_file() and path.name not in {"validation.json", "search_plan_v24_dev_alpha2_1_sha256"}]
    root = sha256_value(components)
    write("validation.json", {
        "artifact_schema_version": "SearchPlanV24DevAlpha2_1ValidationV1",
        "status": "PASS", "aggregate_components": components,
        "search_plan_v24_dev_alpha2_1_sha256": root,
        "upstream_roots_verified": True,
        "scientific_components_immutable": True,
        "local_schema_preflight_pass": preflight["passed"],
        "exact_offline_serialization_verified": True})
    text("search_plan_v24_dev_alpha2_1_sha256", root)
    print(json.dumps({"run": str(RUN), "root": root, "request_body_sha256": fixture["request_body_sha256"]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
