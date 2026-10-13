#!/usr/bin/env python3
"""Freeze one pilot-bound Builder V4 request without executing it."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from code_engine.construction import handoff_adapter


OUT = ROOT / "runs/20261012_code_pilot_bound_builder_v4_request_freeze_offline"
ROOT_MARKER = "code_pilot_bound_builder_v4_request_freeze_sha256"
REQUEST_ID = "code_pilot_builder_v4_development_request_001"

ADAPTER_DIR = Path("runs/20261012_code_minimal_immutable_handoff_to_construction_adapter_offline")
SMOKE_DIR = Path("runs/20261012_code_post_pilot_scientific_handoff_smoke_offline")
PILOT_DIR = Path("runs/20261012_search_plan_v24_dev_alpha3_22f_first_controlled_live_pilot")
BUILDER_DIR = Path("runs/20261004_search_plan_v24_dev_alpha3_20f_final_builder_v4_contract_freeze_offline")
BUILDER_B_DIR = Path("runs/20261002_search_plan_v24_dev_alpha3_20b_proposition_abstraction_prompt_freeze_offline")
MASTER_DIR = Path("runs/20261002_search_plan_v24_dev_alpha3_20_post_alpha3_19_development_master_preregistration_offline")

ROOTS = {
    "construction_adapter": (ADAPTER_DIR,
        "code_minimal_immutable_handoff_to_construction_adapter_sha256",
        "d8a05a63f48f0fa71c319c25d4f0cf622127cbcee866465e01b7228181f709ea"),
    "post_pilot_smoke": (SMOKE_DIR, "code_post_pilot_scientific_handoff_smoke_sha256",
        "53a79c029ae6a3b7127ccf3a1e1cd0c7df63c60d94638e7a4debc3471108a902"),
    "controlled_live_pilot": (PILOT_DIR,
        "search_plan_v24_dev_alpha3_22f_first_controlled_live_pilot_sha256",
        "fd24d7ff2303259ba674823f01403ac2b694082ed5e8e6035f76ff084300230c"),
    "builder_v4_final_contract": (BUILDER_DIR, "search_plan_v24_dev_alpha3_20f_sha256",
        "cc76b168c80634510168a759815dbf7ab905d5e67292b3393a6b9c6a537847c6"),
}

CONSTRUCTION_DOCUMENT_SHA256 = "5b6750308b2cfdf496200f21383399ae27431c75923c1d7af18cca5a24476c8f"
SOURCE_MANIFEST_SHA256 = "74ba6583ee37c23b87b747217bb7a5733ca7b546bd21d402b3458a7f362becc5"
HANDOFF_SHA256 = "d7ff77546c41dc910483483e7ae74f550c7100c421c30be42fe64e55480ce84f"
FINAL_CONTRACT_SHA256 = "53b50a78694b6ed53369347fa8ade3675fd9d28395735b3607f2e3329871436e"
PROMPT_SHA256 = "6af5b7f3cd8b23cc65e4ee9c3e85eb955d760f7f06e88a48722be213454d7592"
OUTPUT_SCHEMA_SHA256 = "e6b65571708d196b9fb7a4b8c4af71f46e8680b4b078a6ebedd9ece28658f1c1"
RUNTIME_POLICY_SHA256 = "2e967f51ac9535b5a94caa4b49105e5f3b9552d2b8389dde2c5806882a0feafa"
RETRY_POLICY_SHA256 = "00b7822953140ca9760e69db1a77a15b3d87dd79cbbb8c008de47f8ad0a5724c"
FIREWALL_SHA256 = "50707639cf2ce541e27b0323a825819793eb173b84141d36e55110c60a8ea8d1"
GROUNDING_SHA256 = "429a11294f1df2c40564f4249ea9f54ce637824cbca13d3450b7afef83c4717b"
EVIDENCE_REFERENCE_SHA256 = "156424459bd499272f6dba5a466216ffbe72fe96039045ae8bc44dd7b40b5612"
ABSTRACTION_SHA256 = "5ab84eebd9fb8b6a4d7d7600869c5860aa19fbd815ad6dc4c139a6332550fc99"
OWNERSHIP_SHA256 = "3adac94437bd46e7c0ebc1a0a2497080fda7784cca97d64d6c1671ba97eef64c"
CARDINALITY_SHA256 = "8ddaaebf68bc1eefe1eebbd33de657ab1efed5a444447057dca816adc96126e7"
LEAKAGE_SHA256 = "78f4ac87eca3ce3422298ebd7a2ca35fbd0ec2da327b577b4f456a2ef519fbd4"
POSTPROCESS_SHA256 = "923386078ca83177b0f43beba49974ba61050969588a2b8e0968966e4b9bc08c"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def read_json(relative: Path) -> dict[str, Any]:
    value = json.loads((ROOT / relative).read_bytes())
    require(type(value) is dict, "JSON_OBJECT_REQUIRED:" + relative.as_posix())
    return value


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RuntimeError(reason)


def file_ref(relative: Path, expected: str) -> dict[str, Any]:
    path = ROOT / relative
    require(path.is_file() and not path.is_symlink(), "ARTIFACT_MISSING_OR_SYMLINK:" + str(relative))
    actual = sha(path.read_bytes())
    require(actual == expected, "ARTIFACT_HASH_MISMATCH:" + str(relative))
    return {"artifact_path": relative.as_posix(), "sha256": actual,
            "immutable_frozen": True}


def verify_root(relative: Path, marker: str, expected: str) -> dict[str, Any]:
    directory = ROOT / relative
    actual = handoff_adapter.root_hash(directory, marker)
    recorded = (directory / marker).read_text(encoding="ascii").strip()
    require(actual == recorded == expected, "ROOT_MISMATCH:" + str(relative))
    return {"artifact_path": relative.as_posix(), "root_marker": marker,
            "sha256": actual, "verified": True, "immutable_frozen": True}


def write_json(name: str, value: Any, *, private: bool = False) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"
    path = OUT / name
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    path.chmod(0o600 if private else 0o644)
    return sha(raw)


def output_root() -> str:
    entries = [[path.relative_to(OUT).as_posix(), sha(path.read_bytes())]
               for path in sorted(OUT.rglob("*"))
               if path.is_file() and path.name != ROOT_MARKER]
    return sha(canonical(entries))


def main() -> None:
    require(not OUT.exists(), "OUTPUT_ALREADY_EXISTS_NO_OVERWRITE")
    verified_roots = {name: verify_root(*spec) for name, spec in ROOTS.items()}

    source_manifest_ref = file_ref(ADAPTER_DIR / "source_manifest.json", SOURCE_MANIFEST_SHA256)
    source_manifest = read_json(ADAPTER_DIR / "source_manifest.json")
    require(source_manifest.get("controller_private") is True and
            (ROOT / ADAPTER_DIR / "source_manifest.json").stat().st_mode & 0o777 == 0o600,
            "SOURCE_MANIFEST_PRIVACY_INVALID")
    envelope = source_manifest.get("verified_construction_input")
    token_authority = source_manifest.get("opaque_source_token_authority")
    require(type(envelope) is dict and type(token_authority) is dict,
            "VERIFIED_INPUT_OR_TOKEN_AUTHORITY_MISSING")
    document = envelope.get("construction_document")
    token = token_authority.get("opaque_source_token")
    require(type(document) is dict and type(token) is str,
            "CONSTRUCTION_DOCUMENT_OR_TOKEN_MISSING")
    handoff_adapter.validate_construction_document(document, token)
    require(sha(canonical(document)) == envelope.get("construction_document_sha256") ==
            CONSTRUCTION_DOCUMENT_SHA256, "CONSTRUCTION_DOCUMENT_HASH_MISMATCH")
    provenance = envelope.get("controller_private_provenance")
    require(type(provenance) is dict and
            provenance.get("pilot_root_sha256") == ROOTS["controlled_live_pilot"][2] and
            provenance.get("handoff_sha256") == HANDOFF_SHA256 and
            provenance.get("opaque_source_token") == token and
            provenance.get("opaque_source_token_sha256") == sha(token.encode("utf-8")) ==
                token_authority.get("opaque_source_token_sha256") and
            token_authority.get("visibility") ==
                "CONTROLLER_PRIVATE_NOT_MODEL_VISIBLE_WITH_SOURCE_MAPPING",
            "PILOT_HANDOFF_OR_TOKEN_BINDING_MISMATCH")
    require(len(document["body_text"]) == 60000 and len(document["paragraphs"]) == 38,
            "FROZEN_BODY_TRUNCATION_MISMATCH")

    final_contract_ref = file_ref(BUILDER_DIR / "search_plan_builder_v4_final_contract.json",
                                  FINAL_CONTRACT_SHA256)
    final_contract = read_json(BUILDER_DIR / "search_plan_builder_v4_final_contract.json")
    require(final_contract.get("schema_version") == "SearchPlanBuilderV4FinalContract" and
            final_contract.get("selected_abstraction_variant") == "V1" and
            final_contract.get("selected_abstraction_mode") == "relation_sentence" and
            final_contract.get("source_identity_firewall_preserved") is True,
            "FINAL_BUILDER_V4_CONTRACT_MISMATCH")

    prompt_path = BUILDER_DIR / "final_selected_builder_v4_prompt.txt"
    prompt_ref = file_ref(prompt_path, PROMPT_SHA256)
    prompt = (ROOT / prompt_path).read_text(encoding="utf-8")
    require(prompt.startswith("SYSTEM:\n") and prompt.count("\nUSER:\n") == 1,
            "FROZEN_PROMPT_SHAPE_INVALID")
    system_prompt, user_template = prompt[len("SYSTEM:\n"):].split("\nUSER:\n", 1)
    require(user_template == ("Source token: {source_record_token}\n"
        "Abstract: {frozen_abstract}\nBody: {frozen_body}\n"
        "Output schema: {output_schema_json}\n"), "FROZEN_USER_TEMPLATE_MISMATCH")

    schema_path = BUILDER_B_DIR / "builder_output_schema_v4.json"
    schema_ref = file_ref(schema_path, OUTPUT_SCHEMA_SHA256)
    schema_wrapper = read_json(schema_path)
    response_schema = schema_wrapper.get("schema")
    require(type(response_schema) is dict and
            schema_wrapper.get("schema_version") == "BuilderOutputSchemaV4" and
            schema_wrapper.get("candidate_cardinality") == {"minimum": 0, "maximum": 3},
            "OUTPUT_SCHEMA_V4_MISMATCH")
    response_schema_json = canonical(response_schema).decode("utf-8")

    runtime_path = BUILDER_B_DIR / "alpha3_20c_runtime_policy.json"
    runtime_ref = file_ref(runtime_path, RUNTIME_POLICY_SHA256)
    runtime = read_json(runtime_path)
    require(runtime.get("provider") == "DeepSeek" and
            runtime.get("api_surface") == "Chat Completions" and
            runtime.get("model") == "deepseek-flash" and
            runtime.get("thinking") == {"type": "enabled"} and
            runtime.get("reasoning_effort") == "high" and
            runtime.get("response_format") == {"type": "json_object"} and
            runtime.get("temperature") == "omitted" and
            runtime.get("top_p") == "omitted" and
            runtime.get("max_output_tokens") == "omitted as in frozen development baseline" and
            runtime.get("stream") == "omitted" and
            runtime.get("automatic_retry") is False and
            runtime.get("known_no_inference_transport_retry_enabled") is False and
            runtime.get("fallback_provider_or_model") is False,
            "RUNTIME_POLICY_MISMATCH")

    components = {
        "evidence_reference_contract_v4": file_ref(
            MASTER_DIR / "evidence_reference_contract_v4.json", EVIDENCE_REFERENCE_SHA256),
        "builder_grounding_contract_v4": file_ref(
            BUILDER_B_DIR / "builder_grounding_contract_v4.json", GROUNDING_SHA256),
        "proposition_abstraction_contract_v1": file_ref(
            MASTER_DIR / "proposition_abstraction_contract_v1.json", ABSTRACTION_SHA256),
        "model_controller_ownership": file_ref(
            BUILDER_B_DIR / "builder_v4_model_controller_ownership_matrix.json", OWNERSHIP_SHA256),
        "candidate_cardinality": file_ref(
            MASTER_DIR / "builder_v4_design_constraints.json", CARDINALITY_SHA256),
        "source_identity_firewall": file_ref(
            BUILDER_B_DIR / "builder_v4_source_identity_firewall.json", FIREWALL_SHA256),
        "lexical_leakage_policy": file_ref(
            BUILDER_B_DIR / "leakage_policy_preservation.json", LEAKAGE_SHA256),
        "retry_policy": file_ref(BUILDER_DIR / "final_builder_v4_retry_policy.json",
                                 RETRY_POLICY_SHA256),
        "postprocessing_order": file_ref(
            BUILDER_DIR / "final_builder_v4_postprocessing_order.json", POSTPROCESS_SHA256),
    }
    retry = read_json(BUILDER_DIR / "final_builder_v4_retry_policy.json")
    require(retry.get("one_scientific_inference_per_frozen_request") is True and
            retry.get("completed_invalid_response_counts_inference") is True and
            retry.get("completed_invalid_response_scientific_retry") is False,
            "RETRY_POLICY_MISMATCH")

    user_prompt = user_template.format(
        source_record_token=token,
        frozen_abstract=document["abstract_text"],
        frozen_body=document["body_text"],
        output_schema_json=response_schema_json,
    )
    request = {
        "model": "deepseek-flash",
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    request_sha256 = sha(canonical(request))
    scientific_input_sha256 = sha(canonical({
        "abstract_text": document["abstract_text"],
        "body_text": document["body_text"],
    }))

    private_identity = token_authority.get("binding")
    require(type(private_identity) is dict, "PRIVATE_IDENTITY_BINDING_MISSING")
    forbidden_values = [private_identity.get(key) for key in ("pmid", "pmcid", "doi")]
    require(all(type(value) is str and value not in user_prompt for value in forbidden_values),
            "FORBIDDEN_BIBLIOGRAPHIC_IDENTITY_LEAKAGE")
    require(user_prompt.startswith("Source token: " + token + "\n") and
            user_prompt.count("Abstract: " + document["abstract_text"]) == 1 and
            user_prompt.count("Body: " + document["body_text"]) == 1 and
            user_prompt.endswith("Output schema: " + response_schema_json + "\n") and
            set(request) == {"model", "thinking", "reasoning_effort", "response_format", "messages"} and
            not any(key in request for key in ("temperature", "top_p", "max_tokens",
                                                "max_output_tokens", "stream")),
            "REQUEST_PAYLOAD_NOT_BYTE_FAITHFUL_TO_FROZEN_CONTRACT")
    require(all(document["body_text"][p["start_offset"]:p["end_offset"]] == p["text"]
                for p in document["paragraphs"]), "MODEL_VISIBLE_ANCHOR_OUT_OF_RANGE")
    require(re.fullmatch(r"src_[0-9a-f]{64}", token) is not None,
            "OPAQUE_SOURCE_TOKEN_SHAPE_INVALID")

    smoke_results_ref = file_ref(SMOKE_DIR / "scientific_handoff_results.json",
        "b86676b1e7a95467afe6b4bca4bb643d2dfcb06f06c75f52aa114960634df1a7")
    blockers_ref = file_ref(SMOKE_DIR / "fresh_primary_blockers.json",
        "41d4a159d4226210054190c43ce0676156c2348625100421232832785c0db404")
    smoke_results = read_json(SMOKE_DIR / "scientific_handoff_results.json")
    blockers = read_json(SMOKE_DIR / "fresh_primary_blockers.json")
    require(smoke_results["cached_model_output_check"]["builder_cache_reuse_allowed"] is False and
            smoke_results["cached_model_output_check"]["matching_source_identity_count"] == 0 and
            blockers["pilot_source_must_be_excluded"] is True and
            blockers["seen_enforcement"]["registry_coverage_verified"] is True,
            "CACHE_OR_FUTURE_PRIMARY_BOUNDARY_MISMATCH")

    protected_before = {relative.as_posix(): expected for _, (relative, _, expected) in ROOTS.items()}
    component_before = {ref["artifact_path"]: ref["sha256"] for ref in
        [source_manifest_ref, final_contract_ref, prompt_ref, schema_ref, runtime_ref,
         smoke_results_ref, blockers_ref, *components.values()]}

    OUT.mkdir()
    request_manifest_sha = write_json("builder_request_manifest.json", {
        "schema_version": "CODEPilotBoundBuilderV4RequestManifestV1",
        "controller_private": True,
        "file_mode_required": "0600",
        "request_id": REQUEST_ID,
        "request_id_role": "CONTROLLER_ONLY_NOT_MODEL_VISIBLE",
        "request_count": 1,
        "execution_ordinal": 1,
        "development_role": "SEEN_DATA_DEVELOPMENT",
        "execution_authorized": False,
        "construction_document_sha256": CONSTRUCTION_DOCUMENT_SHA256,
        "scientific_source_input_sha256": scientific_input_sha256,
        "opaque_source_token_sha256": sha(token.encode("utf-8")),
        "builder_v4_version": "SearchPlanBuilderV4FinalContract",
        "selected_abstraction_variant": "V1",
        "prompt_sha256": PROMPT_SHA256,
        "provider": "DeepSeek",
        "api_surface": "Chat Completions",
        "model": "deepseek-flash",
        "generation_parameters": {
            "thinking": {"type": "enabled"}, "reasoning_effort": "high",
            "response_format": {"type": "json_object"}, "temperature": "omitted",
            "top_p": "omitted", "max_output_tokens": "omitted", "stream": "omitted",
        },
        "expected_response_schema": response_schema,
        "expected_response_schema_artifact_sha256": OUTPUT_SCHEMA_SHA256,
        "request": request,
        "request_canonicalization": "UTF-8 compact canonical JSON; sorted keys; no final LF",
        "request_sha256": request_sha256,
        "model_visible_fields": ["opaque source_record_token", "frozen Abstract context",
                                 "frozen canonical BODY", "BuilderOutputSchemaV4"],
        "hidden_bibliographic_identity_fields_present": False,
        "private_source_token_mapping_present": False,
    }, private=True)

    binding_sha = write_json("builder_contract_binding.json", {
        "schema_version": "CODEPilotBoundBuilderV4ContractBindingV1",
        "authoritative_roots": verified_roots,
        "source_authority": {
            "source_manifest": source_manifest_ref,
            "construction_document_sha256": CONSTRUCTION_DOCUMENT_SHA256,
            "committed_pilot_handoff_sha256": HANDOFF_SHA256,
            "canonical_body_sha256": provenance["canonical_body_reference"]["sha256"],
            "canonical_body_byte_count": provenance["canonical_body_reference"]["byte_count"],
            "body_truncation_characters": 60000,
            "body_truncation_frozen": True,
            "authorized_anchor_count": len(document["paragraphs"]),
            "opaque_token_authority_preserved": True,
            "opaque_token_regenerated": False,
        },
        "builder_v4": {
            "final_contract": final_contract_ref,
            "prompt": prompt_ref,
            "output_schema": schema_ref,
            "runtime_policy": runtime_ref,
            "components": components,
            "provider": "DeepSeek", "api_surface": "Chat Completions",
            "model": "deepseek-flash", "thinking": {"type": "enabled"},
            "reasoning_effort": "high", "response_format": {"type": "json_object"},
            "selected_abstraction_variant": "V1", "selected_abstraction_mode": "relation_sentence",
        },
        "cache_semantics": {
            "exact_pilot_bound_cached_builder_response_exists": False,
            "cache_reuse_allowed": False,
            "evidence": smoke_results_ref,
            "request_sha256_is_frozen_request_identity": True,
        },
        "retry_semantics": {
            "automatic_retry": False,
            "known_no_inference_transport_retry_enabled": False,
            "completed_invalid_response_counts_inference": True,
            "completed_invalid_response_scientific_retry": False,
            "ambiguous_execution_action": "STOP_NO_SECOND_SCIENTIFIC_INFERENCE",
        },
        "later_one_shot_execution_plan": {
            "separate_authorization_required": True,
            "exactly_one_frozen_request": True,
            "maximum_scientific_inference_events": 1,
            "adaptive_prompt_revisions": False,
            "multiple_output_cherry_picking": False,
            "model_or_configuration_substitution": False,
            "raw_output_and_validation_evidence_must_be_preserved": True,
            "schema_violations_and_unsupported_spans_must_be_recorded": True,
            "failure_replacement_allowed": False,
            "builder_output_role": "SEEN_DATA_DEVELOPMENT_EVIDENCE",
            "quality_v2_requires_separate_authorization": True,
        },
    })

    validation_checks = {
        "authoritative_roots_verified": all(r["verified"] for r in verified_roots.values()),
        "construction_document_schema_valid": True,
        "construction_document_sha256_matches": True,
        "committed_pilot_handoff_bound": True,
        "canonical_body_source_bound": True,
        "body_truncation_exactly_60000_characters": len(document["body_text"]) == 60000,
        "opaque_token_reused_not_regenerated": True,
        "opaque_token_authority_private": True,
        "prompt_sha256_matches": True,
        "builder_v4_contract_verified": True,
        "provider_model_configuration_verified": True,
        "request_shape_matches_frozen_builder_v4": True,
        "expected_response_schema_matches": True,
        "all_anchors_within_model_visible_body": True,
        "private_source_mapping_absent_from_model_visible_payload": True,
        "forbidden_bibliographic_metadata_absent_from_model_visible_payload": True,
        "no_external_evidence_added": True,
        "pilot_identity_future_primary_excluded": True,
        "builder_not_executed": True,
        "quality_not_executed": True,
    }
    validation_sha = write_json("request_validation.json", {
        "schema_version": "CODEPilotBoundBuilderV4RequestValidationV1",
        "status": "PASS" if all(validation_checks.values()) else "FAIL",
        "request_id": REQUEST_ID,
        "request_sha256": request_sha256,
        "request_manifest_sha256": request_manifest_sha,
        "checks": validation_checks,
        "check_count": len(validation_checks),
        "pass_count": sum(value is True for value in validation_checks.values()),
        "model_visible_payload_character_count": len(system_prompt) + len(user_prompt),
        "abstract_character_count": len(document["abstract_text"]),
        "body_character_count": len(document["body_text"]),
        "anchor_count": len(document["paragraphs"]),
    })
    require(all(validation_checks.values()), "REQUEST_VALIDATION_FAILED")

    protected_after = {relative.as_posix(): handoff_adapter.root_hash(ROOT / relative, marker)
                       for _, (relative, marker, _) in ROOTS.items()}
    component_after = {path: sha((ROOT / path).read_bytes()) for path in component_before}
    require(protected_before == protected_after and component_before == component_after,
            "HISTORICAL_OR_CONTRACT_ARTIFACT_CHANGED")
    preservation_sha = write_json("historical_preservation.json", {
        "schema_version": "CODEPilotBoundBuilderV4HistoricalPreservationV1",
        "authoritative_roots_before": protected_before,
        "authoritative_roots_after": protected_after,
        "component_hashes_before": component_before,
        "component_hashes_after": component_after,
        "authoritative_artifacts_unchanged": True,
        "pilot_identity_future_primary_excluded": True,
        "seen_registry_evidence": {
            "pilot_registry": {
                "artifact_path": (PILOT_DIR / "contamination_registry/index.json").as_posix(),
                "sha256": "0d9ab43e800609e82f8efd0f9ceaaedd2b384edbb2ade93479539d29b5976b39",
            },
            "fresh_primary_blockers": blockers_ref,
        },
        "scientific_policy_changed": False,
        "runtime_source_modified": False,
        "historical_assets_modified": False,
        "network_calls": 0, "llm_calls": 0, "builder_calls": 0, "quality_calls": 0,
    })

    write_json("summary.json", {
        "schema_version": "CODEPilotBoundBuilderV4RequestFreezeSummaryV1",
        "status": "PASS",
        "mode": "OFFLINE_REQUEST_PREREGISTRATION_NO_MODEL_EXECUTION",
        "request_id": REQUEST_ID,
        "builder_request_count": 1,
        "construction_input_verified": True,
        "construction_document_sha256": CONSTRUCTION_DOCUMENT_SHA256,
        "builder_v4_contract_verified": True,
        "prompt_config_frozen": True,
        "request_sha256": request_sha256,
        "builder_request_manifest_sha256": request_manifest_sha,
        "builder_contract_binding_sha256": binding_sha,
        "request_validation_sha256": validation_sha,
        "historical_preservation_sha256": preservation_sha,
        "builder_executed": False,
        "quality_executed": False,
        "fresh_primary_started": False,
        "network_calls": 0, "llm_calls": 0, "builder_calls": 0, "quality_calls": 0,
        "scientific_policy_changed": False,
        "runtime_source_modified": False,
        "historical_assets_modified": False,
        "next_stage_recommendation": "AWAIT_SEPARATE_AUTHORIZATION_FOR_ONE_FROZEN_BUILDER_V4_DEVELOPMENT_REQUEST",
        "root_marker": ROOT_MARKER,
        "root_hash_algorithm": "SHA256(compact canonical JSON of sorted [relative_path,SHA256(file)] pairs; root marker excluded; no final LF in hashed JSON)",
    })

    final_root = output_root()
    marker_path = OUT / ROOT_MARKER
    with marker_path.open("xb") as handle:
        handle.write((final_root + "\n").encode("ascii"))
        handle.flush()
        os.fsync(handle.fileno())
    marker_path.chmod(0o644)
    require(output_root() == final_root, "FINAL_ROOT_RECOMPUTATION_FAILED")
    require((OUT / "builder_request_manifest.json").stat().st_mode & 0o777 == 0o600,
            "REQUEST_MANIFEST_FILE_MODE_INVALID")
    print(json.dumps({"status": "PASS", "request_count": 1,
                      "request_sha256": request_sha256,
                      "freeze_root_sha256": final_root}, sort_keys=True))


if __name__ == "__main__":
    main()
