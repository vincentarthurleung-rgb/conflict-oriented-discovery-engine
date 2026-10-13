#!/usr/bin/env python3
"""Freeze one Quality V2 request for the authentic pilot Builder V4 output."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from code_engine.construction import handoff_adapter
from scripts.search_plan_v24_alpha317c_reconcile_builder_offline import (
    candidate_id,
)
from scripts.search_plan_v24_alpha318b_post_builder_prechecks import (
    build_quality_payload,
    build_quality_request,
    private_identity_from_jats,
    validate_builder_response,
)
from scripts.search_plan_v24_alpha320a_v4_localizer import (
    SUCCESS as LOCALIZATION_SUCCESS,
    localize_exact_body_quote,
)


BUILDER_EXEC = ROOT / "runs/20261012_code_first_pilot_bound_builder_v4_development_execution"
BUILDER_EXEC_MARKER = "code_first_pilot_bound_builder_v4_development_execution_sha256"
BUILDER_EXEC_ROOT = "bebb5b6be579bd39a99f463e7f7f9d71e00001a05b7047ba9c60930f0a60c44f"
BUILDER_FREEZE = ROOT / "runs/20261012_code_pilot_bound_builder_v4_request_freeze_offline"
BUILDER_FREEZE_MARKER = "code_pilot_bound_builder_v4_request_freeze_sha256"
BUILDER_FREEZE_ROOT = "0ebf44c361fc9e2cde04b7562b5e559c2ee0c25602383083cb62471b3fde307e"
ADAPTER = ROOT / "runs/20261012_code_minimal_immutable_handoff_to_construction_adapter_offline"
ADAPTER_MARKER = "code_minimal_immutable_handoff_to_construction_adapter_sha256"
ADAPTER_ROOT = "d8a05a63f48f0fa71c319c25d4f0cf622127cbcee866465e01b7228181f709ea"
QUALITY = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17d_independent_quality_adjudication_v2_preregistration_offline"
QUALITY_MARKER = "search_plan_v24_dev_alpha3_17d_sha256"
QUALITY_ROOT = "1f96a0f276ba8ab58f4ad0959c1140fab0d0949c03eb75a3e10dd2af3cad42e9"
QUALITY_EXEC_PREREG = ROOT / "runs/20261001_search_plan_v24_dev_alpha3_18c_quality_execution_preregistration_offline"
QUALITY_EXEC_PREREG_MARKER = "search_plan_v24_dev_alpha3_18c_prereg_sha256"
QUALITY_EXEC_PREREG_ROOT = "f8cab0d34ac2de3c376ec8a2176f624091fcad1aecff4617ed9a66400356f2e0"
PRIMARY_MASTER = ROOT / "runs/20261005_search_plan_v24_primary_alpha3_21_fresh_primary_master_preregistration_offline"
PRIMARY_MASTER_MARKER = "search_plan_v24_primary_alpha3_21_master_prereg_sha256"
PRIMARY_MASTER_ROOT = "47c0ba15f6acb4e1e581d148edbfa0674a7dc1e82261764876cef20f4184d935"

BUILDER_REQUEST_SHA256 = "88fd33cea837ed688368ac8b3fe057c7b2e1021453fd85d627ca115642770b25"
BUILDER_RESPONSE_SHA256 = "a7edfb40d2d84847007e996764161469873863765475f3a76577636367271315"
DOCUMENT_SHA256 = "5b6750308b2cfdf496200f21383399ae27431c75923c1d7af18cca5a24476c8f"
QUALITY_PROTOCOL_SHA256 = "89009283963c1db3dd00d57917d932b4d0a542dcb27863ad071dc30f8c0cd751"

OUT = ROOT / "runs/20261012_code_pilot_bound_quality_v2_request_freeze_offline"
ROOT_MARKER = "code_pilot_bound_quality_v2_request_freeze_sha256"
REQUEST_ID = "code_pilot_quality_v2_development_request_001"


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RuntimeError(reason)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    require(type(value) is dict, "JSON_OBJECT_REQUIRED:" + str(path))
    return value


def verify_root(directory: Path, marker: str, expected: str) -> dict[str, Any]:
    actual = handoff_adapter.root_hash(directory, marker)
    recorded = (directory / marker).read_text(encoding="ascii").strip()
    require(actual == recorded == expected, "ROOT_MISMATCH:" + directory.name)
    return {"artifact_path": directory.relative_to(ROOT).as_posix(),
            "root_marker": marker, "sha256": actual,
            "verified": True, "immutable_frozen": True}


def file_ref(path: Path, expected: str | None = None) -> dict[str, Any]:
    require(path.is_file() and not path.is_symlink(),
            "ARTIFACT_MISSING_OR_SYMLINK:" + str(path))
    actual = sha(path.read_bytes())
    if expected is not None:
        require(actual == expected, "ARTIFACT_HASH_MISMATCH:" + str(path))
    return {"artifact_path": path.relative_to(ROOT).as_posix(),
            "sha256": actual, "immutable_frozen": True}


def write_json(name: str, value: Any, *, private: bool = False) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                     indent=2).encode("utf-8") + b"\n"
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
    roots = {
        "builder_execution": verify_root(BUILDER_EXEC, BUILDER_EXEC_MARKER,
                                         BUILDER_EXEC_ROOT),
        "builder_request_freeze": verify_root(BUILDER_FREEZE, BUILDER_FREEZE_MARKER,
                                              BUILDER_FREEZE_ROOT),
        "construction_adapter": verify_root(ADAPTER, ADAPTER_MARKER, ADAPTER_ROOT),
        "quality_v2_protocol": verify_root(QUALITY, QUALITY_MARKER, QUALITY_ROOT),
        "quality_execution_preregistration": verify_root(
            QUALITY_EXEC_PREREG, QUALITY_EXEC_PREREG_MARKER,
            QUALITY_EXEC_PREREG_ROOT),
        "fresh_primary_master": verify_root(PRIMARY_MASTER, PRIMARY_MASTER_MARKER,
                                            PRIMARY_MASTER_ROOT),
    }

    builder_manifest = read_json(BUILDER_FREEZE / "builder_request_manifest.json")
    require(builder_manifest["request_sha256"] == BUILDER_REQUEST_SHA256 and
            sha(canonical(builder_manifest["request"])) == BUILDER_REQUEST_SHA256 and
            builder_manifest["construction_document_sha256"] == DOCUMENT_SHA256,
            "BUILDER_REQUEST_BINDING_MISMATCH")
    provider_ref = file_ref(BUILDER_EXEC / "provider_response.json",
                            BUILDER_RESPONSE_SHA256)
    provider = read_json(BUILDER_EXEC / "provider_response.json")
    require(provider.get("model") == "deepseek-flash" and
            type(provider.get("choices")) is list and len(provider["choices"]) == 1 and
            provider["choices"][0].get("finish_reason") == "stop" and
            type(provider["choices"][0].get("message", {}).get("content")) is str,
            "AUTHENTIC_PROVIDER_RESPONSE_INVALID")
    builder_validation = read_json(BUILDER_EXEC / "builder_validation.json")
    builder_diagnostics = read_json(BUILDER_EXEC / "proposition_diagnostics.json")
    require(builder_validation["schema_validation_passed"] is True and
            builder_validation["source_token_binding_valid"] is True and
            builder_validation["proposition_count"] == 3 and
            builder_diagnostics["raw_proposition_count"] == 3 and
            builder_diagnostics["valid_proposition_count"] == 3 and
            builder_diagnostics["invalid_proposition_count"] == 0 and
            builder_diagnostics["unsupported_anchor_count"] == 0,
            "BUILDER_VALIDATION_AUTHORITY_MISMATCH")

    source_manifest_path = ADAPTER / "source_manifest.json"
    source_manifest = read_json(source_manifest_path)
    require((source_manifest_path.stat().st_mode & 0o777) == 0o600,
            "SOURCE_MANIFEST_NOT_PRIVATE")
    envelope = source_manifest["verified_construction_input"]
    token_authority = source_manifest["opaque_source_token_authority"]
    document = envelope["construction_document"]
    token = token_authority["opaque_source_token"]
    handoff_adapter.validate_construction_document(document, token)
    require(envelope["construction_document_sha256"] == DOCUMENT_SHA256 and
            sha(canonical(document)) == DOCUMENT_SHA256 and
            sha(token.encode("utf-8")) == token_authority[
                "opaque_source_token_sha256"],
            "CONSTRUCTION_DOCUMENT_OR_TOKEN_MISMATCH")

    builder_schema = builder_manifest["expected_response_schema"]
    parsed = validate_builder_response(
        provider["choices"][0]["message"]["content"].encode("utf-8"),
        token, builder_schema)
    require(len(parsed["candidates"]) == 3,
            "AUTHENTIC_BUILDER_CANDIDATE_COUNT_MISMATCH")

    prompt_system_path = QUALITY / "quality_adjudicator_system_prompt.txt"
    prompt_user_path = QUALITY / "quality_adjudicator_user_prompt_template.txt"
    response_schema_path = QUALITY / "proposition_quality_adjudication_v2_schema.json"
    machine_path = QUALITY / "quality_machine_output_contract.json"
    criteria_path = QUALITY / "quality_criteria_contract.json"
    grouping_path = QUALITY / "one_source_per_quality_call_contract.json"
    visibility_path = QUALITY / "quality_visibility_contract.json"
    context_path = QUALITY / "quality_source_context_contract.json"
    invalid_path = QUALITY / "quality_invalid_response_policy.json"
    provider_projection_path = (QUALITY_EXEC_PREREG /
                                "quality_execution_provider_binding_v2_1.json")
    retry_path = QUALITY_EXEC_PREREG / "quality_transport_retry_contract.json"
    primary_runtime_path = PRIMARY_MASTER / "alpha3_21_quality_runtime_binding.json"
    primary_protocol_path = PRIMARY_MASTER / "alpha3_21_quality_v2_binding.json"
    envelope_binding_path = (PRIMARY_MASTER /
                             "alpha3_21_quality_response_envelope_v3_binding.json")

    contract_refs = {
        "system_prompt": file_ref(prompt_system_path,
            "3f365d6fe52bbf195dd66446408523688e9b6ce0c0e4c3ffd83e2e702dabf0e1"),
        "user_prompt_template": file_ref(prompt_user_path,
            "aec138b19a40db10b821a237d227cf7ece7d6bce9721ff3bdd06c5e6f48f124e"),
        "output_schema": file_ref(response_schema_path,
            "319ed025b152e7deb14f72c7264fffe4e013dfd99184f47390ba60bf699cea09"),
        "machine_output_contract": file_ref(machine_path,
            "62f605fec479296e39338ff95ab487468258b2e31dd6df68d0895cab43f1f375"),
        "quality_criteria": file_ref(criteria_path,
            "5c3d989ea89c746fa5169fe9e35eb9fa66a5ef475c6e54becc021768cdd69c17"),
        "source_grouping": file_ref(grouping_path,
            "360463ea312ff28aa9156f5b59af253eb78180967e7afc4cd34136c74fe8c231"),
        "visibility": file_ref(visibility_path,
            "bda8bfb94c8e026d01fa74d6edb3ec5e154f0f8897d9cee395720819d0f56671"),
        "source_context": file_ref(context_path,
            "d73cf04221f5d9bd16cb56bdf3c37dfdee7ad56369ad67bc457bd9a8c3819b2e"),
        "invalid_response_policy": file_ref(invalid_path,
            "91e0fde711e7f4fa3c8db2a3642355383ead2973afbe0e0fb803d830747e6c38"),
        "provider_projection": file_ref(provider_projection_path,
            "bdf4d844f22466c5d748671b2d35c4b3db1ea4c1fd05d6e4baee33f194893db5"),
        "retry_policy": file_ref(retry_path,
            "1c985d478557b418f2f82a6bd9104e75965ffa75491409c3ff9b88cab1029042"),
        "primary_runtime_binding": file_ref(primary_runtime_path,
            "91e63025080a3f82410661d4676696e2418716c7fb4afe2a1684df291516b1d9"),
        "primary_protocol_binding": file_ref(primary_protocol_path,
            "49ae5de55a5dd0fc3cc8b41551c56f88ddbd65cad23ad3e8dbf5b8b4177a53b9"),
        "quality_response_envelope_v3_binding": file_ref(envelope_binding_path,
            "550dce74f1fb22015d11b2110c8cd729bdeca7b33d6e195d89b1ecd3d6fd5a39"),
    }
    protocol_marker = (QUALITY /
        "proposition_quality_adjudication_v2_protocol_sha256").read_text(
            encoding="ascii").strip()
    require(protocol_marker == QUALITY_PROTOCOL_SHA256,
            "QUALITY_V2_PROTOCOL_MARKER_MISMATCH")
    grouping = read_json(grouping_path)
    visibility = read_json(visibility_path)
    context = read_json(context_path)
    projection = read_json(provider_projection_path)
    retry = read_json(retry_path)
    primary_runtime = read_json(primary_runtime_path)
    require(grouping["one_source_article_per_call"] is True and
            grouping["surviving_candidates_per_call_minimum"] == 1 and
            grouping["surviving_candidates_per_call_maximum"] == 3 and
            grouping["cross_source_candidate_batching"] is False and
            visibility["private_source_token_not_in_payload"] is True and
            context["full_article_visible"] is False and
            "240 Unicode code points" in context["local_context"] and
            projection["provider_configuration"]["provider"] == "DeepSeek" and
            projection["provider_configuration"]["model"] == "deepseek-flash" and
            projection["request_projection"] ==
                "copy each frozen request; replace only top-level model at outbound serialization" and
            retry["automatic_retry"] is False and
            retry["scientific_inference_attempts_per_group"] == 1 and
            primary_runtime["provider"] == "DeepSeek" and
            primary_runtime["model"] == "deepseek-flash" and
            primary_runtime["one_request_per_nonempty_source_group"] is True,
            "QUALITY_GROUPING_RUNTIME_OR_VISIBILITY_MISMATCH")

    normalized_ref = envelope["controller_private_provenance"][
        "normalized_jats_reference"]
    normalized_path = Path(normalized_ref["artifact_path"])
    normalized_path = normalized_path if normalized_path.is_absolute() else ROOT / normalized_path
    require(sha(normalized_path.read_bytes()) == normalized_ref["sha256"],
            "NORMALIZED_JATS_HASH_MISMATCH")
    private_binding = token_authority["binding"]
    private_identity = private_identity_from_jats(
        normalized_path.read_bytes(), private_binding["pmid"],
        private_binding["pmcid"], private_binding["doi"])

    original_order = []
    enriched_by_id: dict[str, dict[str, Any]] = {}
    payload_hashes: set[str] = set()
    for position, candidate in enumerate(parsed["candidates"]):
        payload_sha = sha(canonical(candidate))
        cid = candidate_id(token, candidate)
        require(payload_sha not in payload_hashes and cid not in enriched_by_id,
                "DUPLICATE_BUILDER_PROPOSITION")
        payload_hashes.add(payload_sha)
        localized = localize_exact_body_quote(
            candidate["construction_evidence_span"]["exact_text"],
            document["body_text"], document["paragraphs"])
        require(localized["development_v4_localization_state"] ==
                LOCALIZATION_SUCCESS, "BUILDER_EVIDENCE_LOCALIZATION_FAILURE")
        enriched = copy.deepcopy(candidate)
        enriched["construction_evidence_span"] = {
            "source_field": "body",
            "start_offset": localized["body_document_start_offset"],
            "end_offset": localized["body_document_end_offset"],
            "exact_text": candidate["construction_evidence_span"]["exact_text"],
        }
        original_order.append({
            "original_array_position": position,
            "candidate_id": cid,
            "candidate_payload_sha256": payload_sha,
            "exact_evidence_sha256": sha(candidate[
                "construction_evidence_span"]["exact_text"].encode("utf-8")),
            "anchor_id": localized["anchor_id"],
            "source_field": "body",
            "body_start_offset": localized["body_document_start_offset"],
            "body_end_offset": localized["body_document_end_offset"],
            "coordinate_end_semantics": "exclusive",
            "paragraph_ordinal": localized["paragraph_ordinal"],
        })
        enriched_by_id[cid] = {
            "candidate_id": cid,
            "candidate_payload_sha256": payload_sha,
            "candidate": enriched,
            "original_array_positions": [position],
        }
    require(len(original_order) == len(enriched_by_id) == 3,
            "BUILDER_PROPOSITION_IDENTITY_COUNT_MISMATCH")
    survivors = sorted(enriched_by_id.values(), key=lambda item: (
        item["candidate_payload_sha256"], item["candidate_id"]))
    payload = build_quality_payload(token, survivors, document,
                                    {**private_identity,
                                     "private_source_token": token})
    require(len(payload["candidate_packets"]) == 3 and
            {packet["candidate_id"] for packet in payload["candidate_packets"]} ==
                set(enriched_by_id), "QUALITY_PAYLOAD_MEMBERSHIP_MISMATCH")

    system_prompt = prompt_system_path.read_text(encoding="utf-8")
    user_template = prompt_user_path.read_text(encoding="utf-8")
    output_schema_wrapper = read_json(response_schema_path)
    output_schema = output_schema_wrapper["schema"]
    machine_output = read_json(machine_path)["appendix_utf8"]
    historical_request = build_quality_request(
        payload, output_schema, system_prompt, user_template, machine_output)
    require(historical_request["model"] == "deepseek-v4-pro",
            "HISTORICAL_QUALITY_REQUEST_MODEL_MISMATCH")
    request = copy.deepcopy(historical_request)
    request["model"] = "deepseek-flash"
    delta = {key for key in request if request[key] != historical_request[key]}
    require(delta == {"model"} and request["thinking"] == {"type": "enabled"} and
            request["reasoning_effort"] == "high" and
            request["response_format"] == {"type": "json_object"} and
            request["stream"] is False and
            not any(key in request for key in
                    ("temperature", "top_p", "service_tier", "max_tokens",
                     "max_output_tokens")),
            "QUALITY_PROVIDER_PROJECTION_MISMATCH")
    request_sha256 = sha(canonical(request))

    serialized_payload = canonical(payload).decode("utf-8")
    serialized_request = canonical(request).decode("utf-8")
    require(token not in serialized_payload and token not in serialized_request and
            all(private_binding[key] not in serialized_request
                for key in ("pmid", "pmcid", "doi")) and
            all(original in request["messages"][1]["content"]
                for original in (payload["source_group_id"],
                    canonical(payload["candidate_packets"]).decode("utf-8"),
                    canonical(output_schema).decode("utf-8"), machine_output)),
            "QUALITY_MODEL_VISIBLE_PRIVACY_OR_REQUEST_BINDING_FAILURE")

    quality_order = []
    for packet_position, packet in enumerate(payload["candidate_packets"]):
        original = next(row for row in original_order
                        if row["candidate_id"] == packet["candidate_id"])
        quality_order.append({
            "quality_packet_position": packet_position,
            "candidate_id": packet["candidate_id"],
            "original_builder_array_position": original["original_array_position"],
            "candidate_payload_sha256": original["candidate_payload_sha256"],
            "packet_sha256": sha(canonical(packet)),
            "evidence_sha256": sha(canonical(packet["evidence"])),
            "bounded_local_context_sha256": sha(packet["evidence"][
                "bounded_local_context"].encode("utf-8")),
        })
    require([row["candidate_payload_sha256"] for row in quality_order] ==
            sorted(row["candidate_payload_sha256"] for row in quality_order),
            "QUALITY_PACKET_CANONICAL_ORDER_MISMATCH")

    protected_before = {name: record["sha256"] for name, record in roots.items()}
    component_before = {name: record["sha256"] for name, record in contract_refs.items()}
    OUT.mkdir()
    manifest_sha = write_json("quality_request_manifest.json", {
        "schema_version": "CODEPilotBoundQualityV2RequestManifestV1",
        "controller_private": True,
        "file_mode_required": "0600",
        "request_id": REQUEST_ID,
        "request_id_role": "CONTROLLER_ONLY_NOT_MODEL_VISIBLE",
        "execution_authorized": False,
        "quality_logical_request_count": 1,
        "source_group_count": 1,
        "source_group_id": payload["source_group_id"],
        "private_source_token_sha256": sha(token.encode("utf-8")),
        "builder_execution_root_sha256": BUILDER_EXEC_ROOT,
        "builder_request_sha256": BUILDER_REQUEST_SHA256,
        "builder_response_sha256": BUILDER_RESPONSE_SHA256,
        "construction_document_sha256": DOCUMENT_SHA256,
        "builder_candidate_count": 3,
        "original_builder_candidate_order": original_order,
        "quality_request_canonical_packet_order": quality_order,
        "candidate_set_preserved": True,
        "candidate_filtering_or_substitution": False,
        "quality_v2_protocol_sha256": QUALITY_PROTOCOL_SHA256,
        "provider": "DeepSeek", "api_surface": "Chat Completions",
        "model": "deepseek-flash",
        "generation_parameters": {
            "thinking": {"type": "enabled"}, "reasoning_effort": "high",
            "response_format": {"type": "json_object"}, "stream": False,
            "temperature": "omitted", "top_p": "omitted",
            "service_tier": "omitted", "max_output_tokens": "omitted",
        },
        "quality_payload": payload,
        "expected_response_schema": output_schema,
        "request": request,
        "request_canonicalization":
            "UTF-8 compact canonical JSON; sorted keys; no final LF",
        "request_sha256": request_sha256,
        "private_source_token_present_in_model_visible_payload": False,
        "private_anchor_ids_present_in_model_visible_payload": False,
        "bibliographic_identity_present_in_model_visible_payload": False,
    }, private=True)

    contract_sha = write_json("quality_contract_binding.json", {
        "schema_version": "CODEPilotBoundQualityV2ContractBindingV1",
        "authoritative_roots": roots,
        "quality_v2_protocol_sha256": QUALITY_PROTOCOL_SHA256,
        "quality_v2_scientific_protocol_unchanged": True,
        "contract_components": contract_refs,
        "request_grouping": {
            "logical_request_count": 1,
            "one_source_article_per_call": True,
            "candidate_count_in_group": 3,
            "cross_source_batching": False,
            "canonical_packet_order_is_not_a_scientific_ranking": True,
            "original_builder_order_preserved_in_controller_binding": True,
        },
        "evidence_visibility": {
            "exact_candidate_evidence_span": True,
            "bounded_local_context_code_points_each_side": 240,
            "same_frozen_body_field_only": True,
            "full_article_visible": False,
            "title_visible": False,
            "source_token_visible": False,
            "anchor_id_visible": False,
        },
        "provider_projection": {
            "historical_protocol_model": "deepseek-v4-pro",
            "frozen_operational_model": "deepseek-flash",
            "only_request_delta": "top-level model",
            "provider": "DeepSeek", "thinking": {"type": "enabled"},
            "reasoning_effort": "high",
            "response_format": {"type": "json_object"}, "stream": False,
        },
        "retry_semantics": {
            "one_scientific_inference_attempt_per_source_group": True,
            "automatic_retry": False,
            "known_no_inference_transport_retry_enabled": False,
            "scientific_repair_or_second_opinion": False,
            "ambiguous_execution_action": "STOP_WITHOUT_REPLACEMENT_CALL",
            "completed_invalid_response_action": "FREEZE_INVALID_NO_REINFERENCE",
        },
        "cache_semantics": {
            "exact_pilot_quality_response_found": False,
            "cached_quality_output_used": False,
            "request_sha256_is_frozen_request_identity": True,
            "cache_substitution_authorized": False,
        },
        "quality_result_semantics": {
            "QUALITY_PASS": "all ten criteria exactly PASS",
            "QUALITY_FAIL": "one or more criteria FAIL",
            "QUALITY_UNRESOLVED": "no FAIL and one or more UNRESOLVED",
            "controller_scientific_reinterpretation": False,
            "ranking_or_score": False,
        },
        "separate_execution_authorization_required": True,
    })

    checks = {
        "builder_execution_root_verified": True,
        "builder_request_sha256_verified": True,
        "builder_response_sha256_verified": True,
        "construction_document_sha256_verified": True,
        "authentic_candidate_count_exactly_three": True,
        "builder_schema_valid_candidate_count_three": True,
        "source_token_binding_verified": True,
        "all_evidence_anchors_verified": True,
        "all_offsets_exact_and_within_body": True,
        "unsupported_anchor_count_zero": True,
        "no_missing_candidate": True,
        "no_duplicate_candidate": True,
        "no_substituted_candidate": True,
        "original_builder_order_recorded": True,
        "quality_contract_canonical_packet_order_verified": True,
        "quality_request_grouping_verified": True,
        "quality_v2_protocol_verified": True,
        "prompt_hashes_verified": True,
        "provider_projection_verified": True,
        "expected_output_schema_verified": True,
        "quality_payload_allowlist_audit_passed": True,
        "private_source_mapping_absent_from_model_payload": True,
        "bibliographic_identity_absent_from_model_payload": True,
        "private_anchor_ids_absent_from_model_payload": True,
        "no_evidence_outside_frozen_span_and_bounded_context": True,
        "scientific_policy_unchanged": True,
        "quality_not_executed": True,
    }
    validation_sha = write_json("request_validation.json", {
        "schema_version": "CODEPilotBoundQualityV2RequestValidationV1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "request_id": REQUEST_ID,
        "quality_request_sha256": request_sha256,
        "quality_request_manifest_sha256": manifest_sha,
        "builder_propositions_bound": 3,
        "quality_logical_request_count": 1,
        "checks": checks,
        "check_count": len(checks),
        "pass_count": sum(value is True for value in checks.values()),
    })
    require(all(checks.values()), "REQUEST_VALIDATION_FAILED")

    roots_after = {
        "builder_execution": verify_root(BUILDER_EXEC, BUILDER_EXEC_MARKER,
                                         BUILDER_EXEC_ROOT),
        "builder_request_freeze": verify_root(BUILDER_FREEZE,
                                              BUILDER_FREEZE_MARKER,
                                              BUILDER_FREEZE_ROOT),
        "construction_adapter": verify_root(ADAPTER, ADAPTER_MARKER,
                                            ADAPTER_ROOT),
        "quality_v2_protocol": verify_root(QUALITY, QUALITY_MARKER,
                                           QUALITY_ROOT),
        "quality_execution_preregistration": verify_root(
            QUALITY_EXEC_PREREG, QUALITY_EXEC_PREREG_MARKER,
            QUALITY_EXEC_PREREG_ROOT),
        "fresh_primary_master": verify_root(PRIMARY_MASTER,
                                            PRIMARY_MASTER_MARKER,
                                            PRIMARY_MASTER_ROOT),
    }
    protected_after = {name: record["sha256"] for name, record in roots_after.items()}
    component_after = {name: sha((ROOT / record["artifact_path"]).read_bytes())
                       for name, record in contract_refs.items()}
    require(protected_before == protected_after and
            component_before == component_after,
            "HISTORICAL_OR_CONTRACT_ASSET_CHANGED")
    preservation_sha = write_json("historical_preservation.json", {
        "schema_version": "CODEPilotBoundQualityV2HistoricalPreservationV1",
        "authoritative_roots_before": protected_before,
        "authoritative_roots_after": protected_after,
        "contract_component_hashes_before": component_before,
        "contract_component_hashes_after": component_after,
        "authoritative_artifacts_unchanged": True,
        "builder_reexecuted": False,
        "quality_executed": False,
        "fresh_primary_started": False,
        "pilot_source_remains_seen_development_evidence": True,
        "scientific_policy_changed": False,
        "historical_assets_modified": False,
        "network_calls": 0, "llm_calls": 0, "quality_calls": 0,
    })

    write_json("summary.json", {
        "schema_version": "CODEPilotBoundQualityV2RequestFreezeSummaryV1",
        "quality_request_freeze_status": "PASS",
        "mode": "OFFLINE_REQUEST_PREREGISTRATION_NO_MODEL_EXECUTION",
        "builder_propositions_bound": 3,
        "quality_logical_request_count": 1,
        "quality_contract_verified": True,
        "all_evidence_anchors_verified": True,
        "quality_request_sha256": request_sha256,
        "quality_request_manifest_sha256": manifest_sha,
        "quality_contract_binding_sha256": contract_sha,
        "request_validation_sha256": validation_sha,
        "historical_preservation_sha256": preservation_sha,
        "quality_executed": False,
        "builder_reexecuted": False,
        "fresh_primary_started": False,
        "network_calls": 0, "llm_calls": 0, "quality_calls": 0,
        "scientific_policy_changed": False,
        "historical_assets_modified": False,
        "next_stage_recommendation":
            "AWAIT_SEPARATE_AUTHORIZATION_FOR_ONE_FROZEN_QUALITY_V2_DEVELOPMENT_REQUEST",
        "root_marker": ROOT_MARKER,
        "root_hash_algorithm":
            "SHA256(compact canonical JSON of sorted [relative_path,SHA256(file)] pairs; root marker excluded; no final LF in hashed JSON)",
    })
    final_root = output_root()
    marker_path = OUT / ROOT_MARKER
    with marker_path.open("xb") as handle:
        handle.write((final_root + "\n").encode("ascii"))
        handle.flush()
        os.fsync(handle.fileno())
    marker_path.chmod(0o644)
    require(output_root() == final_root,
            "FINAL_ROOT_RECOMPUTATION_FAILED")
    require((OUT / "quality_request_manifest.json").stat().st_mode & 0o777 == 0o600,
            "PRIVATE_REQUEST_MANIFEST_MODE_INVALID")
    print(json.dumps({
        "status": "PASS", "builder_propositions_bound": 3,
        "quality_logical_request_count": 1,
        "quality_request_sha256": request_sha256,
        "freeze_root_sha256": final_root,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
