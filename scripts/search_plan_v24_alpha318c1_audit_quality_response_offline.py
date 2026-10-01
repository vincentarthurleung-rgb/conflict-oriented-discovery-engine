#!/usr/bin/env python3
"""Read-only structural/authority audit of the failed alpha3.18C response."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts import search_plan_v24_alpha318c_preregister_quality_offline as prereg
from scripts import run_search_plan_v24_alpha318c_quality as execution


ROOT = prereg.ROOT
FAILED = execution.OUT
PREREG = prereg.OUT
B2 = prereg.B2
Q2 = prereg.Q2
OUT = ROOT / "runs/20261001_search_plan_v24_dev_alpha3_18c1_quality_response_contract_audit_offline"
ROOT_MARKER = "search_plan_v24_dev_alpha3_18c1_sha256"
FAILED_SHA = "16d14ef5c55573c8892696a3e5200d80f49d2c8236e1aecf5c49ba918ce40419"
RAW_SHA = "4cec76b7e4681288b8e7261f3a2ab5155015fdf87097ded3849faf9eafb5efc7"
PREREG_SHA = execution.PREREG_SHA
MANIFEST_SHA = execution.MANIFEST_SHA
BINDING_SHA = execution.BINDING_SHA
REQUEST_SHA = prereg.REQUEST_SHA
VERSION = prereg.quality.QUALITY_VERSION


def require(ok: bool, code: str) -> None:
    if not ok:
        raise RuntimeError(code)


def write(name: str, value: Any) -> str:
    path = OUT / name
    with path.open("xb") as handle:
        handle.write(prereg.canonical(value) + b"\n")
    return prereg.digest(path)


def ref(path: Path) -> dict[str, str]:
    return {"path": str(path.relative_to(ROOT)), "sha256": prereg.digest(path)}


def parse_structural_response() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    raw_path = FAILED / "raw_provider_responses/01.json"
    require(prereg.digest(raw_path) == RAW_SHA, "GROUP1_RAW_RESPONSE_HASH_MISMATCH")
    envelope = json.loads(raw_path.read_bytes())
    require(isinstance(envelope, dict) and isinstance(envelope.get("choices"), list) and
        len(envelope["choices"]) == 1, "GROUP1_PROVIDER_ENVELOPE_INVALID")
    choice = envelope["choices"][0]
    require(choice.get("finish_reason") == "stop" and
        isinstance(choice.get("message", {}).get("content"), str),
        "GROUP1_PROVIDER_ENVELOPE_INVALID")
    body = json.loads(choice["message"]["content"])
    require(isinstance(body, dict), "GROUP1_RESPONSE_NOT_OBJECT")
    schema = prereg.load(Q2 / "proposition_quality_adjudication_v2_schema.json")["schema"]
    return envelope, body, schema


def structural_audit(body: dict[str, Any], schema: dict[str, Any],
                     request_row: dict[str, Any]) -> dict[str, Any]:
    """Return shape/domain booleans only; never persist criterion values."""
    required_top = set(schema["required"])
    records = body.get("judgments")
    require(isinstance(records, list), "GROUP1_JUDGMENTS_NOT_ARRAY")
    item_schema = schema["properties"]["judgments"]["items"]
    required_item = set(item_schema["required"])
    criterion_schema = item_schema["properties"]["criteria"]
    criterion_names = set(criterion_schema["required"])
    packets = prereg.packets_from_frozen_request(request_row["request"])
    packets_by_id = {packet["candidate_id"]: packet for packet in packets}
    expected_ids = set(request_row["candidate_ids"])
    ids = [item.get("candidate_id") if isinstance(item, dict) else None for item in records]
    shape_records = []
    for index, item in enumerate(records, 1):
        if not isinstance(item, dict):
            shape_records.append({"array_index": index, "object": False,
                "missing_required_fields": sorted(required_item), "extra_fields": [],
                "criteria_shape_valid": False, "enum_domain_valid": False,
                "evidence_reference_structurally_valid": False})
            continue
        criteria = item.get("criteria")
        criteria_object = isinstance(criteria, dict)
        criteria_keys_valid = criteria_object and set(criteria) == criterion_names
        enum_domain_valid = bool(criteria_keys_valid and all(
            isinstance(criteria[name], str) and
            criteria[name] in criterion_schema["properties"][name]["enum"]
            for name in criterion_names))
        candidate_id = item.get("candidate_id")
        packet = packets_by_id.get(candidate_id)
        reference = item.get("evidence_support_reference")
        reference_type_and_length = reference is None or (
            isinstance(reference, str) and 1 <= len(reference) <= 240)
        visible = None if packet is None else (
            packet["evidence"]["exact_evidence_span"] + "\n" +
            packet["evidence"]["bounded_local_context"])
        reference_in_visible = reference is None or (
            isinstance(reference, str) and visible is not None and reference in visible)
        resolved_reference_present = bool(criteria_object and
            (criteria.get("EVIDENCE_SUPPORTS_PROPOSITION") not in ("PASS", "FAIL") or
             reference is not None))
        shape_records.append({"array_index": index, "object": True,
            "missing_required_fields": sorted(required_item - set(item)),
            "extra_fields": sorted(set(item) - required_item),
            "schema_version_present": "schema_version" in item,
            "schema_version_exact_if_present": item.get("schema_version") == VERSION
                if "schema_version" in item else None,
            "candidate_id_type_valid": isinstance(candidate_id, str),
            "candidate_id_in_frozen_set": candidate_id in expected_ids,
            "criteria_shape_valid": criteria_keys_valid,
            "enum_domain_valid": enum_domain_valid,
            "evidence_reference_structurally_valid": bool(reference_type_and_length and
                reference_in_visible and resolved_reference_present)})
    other_errors = []
    if not isinstance(body.get("schema_version"), str) or body.get("schema_version") != VERSION:
        other_errors.append("TOP_LEVEL_SCHEMA_VERSION_INVALID")
    if set(body) != required_top:
        other_errors.append("TOP_LEVEL_FIELD_SET_INVALID")
    if body.get("source_group_id") != request_row["source_group_id"]:
        other_errors.append("SOURCE_GROUP_ID_MISMATCH")
    if len(records) != len(expected_ids) or len(ids) != len(set(ids)) or set(ids) != expected_ids:
        other_errors.append("CANDIDATE_ID_SET_INVALID")
    for row in shape_records:
        if not row["object"] or not row.get("candidate_id_type_valid") or not row.get("candidate_id_in_frozen_set"):
            other_errors.append("JUDGMENT_ID_OR_TYPE_INVALID")
        if row["extra_fields"]:
            other_errors.append("JUDGMENT_EXTRA_FIELD")
        if any(name != "schema_version" for name in row["missing_required_fields"]):
            other_errors.append("MODEL_AUTHORED_JUDGMENT_FIELD_MISSING")
        if row.get("schema_version_present") and not row.get("schema_version_exact_if_present"):
            other_errors.append("JUDGMENT_SCHEMA_VERSION_INVALID")
        if not row["criteria_shape_valid"]:
            other_errors.append("CRITERIA_SHAPE_INVALID")
        if not row["enum_domain_valid"]:
            other_errors.append("ENUM_DOMAIN_INVALID")
        if not row["evidence_reference_structurally_valid"]:
            other_errors.append("EVIDENCE_REFERENCE_STRUCTURALLY_INVALID")
    return {"response_parseable_json": True,
        "top_level_required_fields": sorted(required_top),
        "top_level_missing_fields": sorted(required_top - set(body)),
        "top_level_extra_fields": sorted(set(body) - required_top),
        "top_level_schema_version_present": "schema_version" in body,
        "top_level_schema_version_exact": body.get("schema_version") == VERSION,
        "candidate_id_set_present": all(isinstance(x, str) for x in ids),
        "candidate_id_set_exact": len(ids) == len(set(ids)) and set(ids) == expected_ids,
        "candidate_count": len(records), "expected_candidate_count": len(expected_ids),
        "judgment_shapes": shape_records,
        "missing_schema_version_count": sum(
            "schema_version" in row["missing_required_fields"] for row in shape_records),
        "other_structural_errors": sorted(set(other_errors)),
        "criterion_scientific_values_recorded": False}


def main() -> None:
    require(not OUT.exists(), "ALPHA3_18C1_AUDIT_ALREADY_EXISTS")
    require(prereg.root(FAILED, execution.ROOT_MARKER) == FAILED_SHA and
        (FAILED / execution.ROOT_MARKER).read_text().strip() == FAILED_SHA,
        "FAILED_ALPHA3_18C_ROOT_MISMATCH")
    require(prereg.root(PREREG, prereg.ROOT_MARKER) == PREREG_SHA and
        (PREREG / prereg.ROOT_MARKER).read_text().strip() == PREREG_SHA and
        prereg.digest(PREREG / "alpha3_18c_quality_execution_manifest.json") == MANIFEST_SHA and
        prereg.digest(PREREG / "quality_execution_provider_binding_v2_1.json") == BINDING_SHA and
        prereg.digest(B2 / "proposition_quality_v2_request_manifest_v3.jsonl") == REQUEST_SHA,
        "ALPHA3_18C_PREREG_OR_REQUEST_MISMATCH")
    candidates, groups, requests = prereg.verify_upstream()
    require((len(candidates), len(groups), len(requests)) == (5, 3, 3),
        "QUALITY_INPUT_MEMBERSHIP_MISMATCH")
    accounting = prereg.load(FAILED / "quality_execution_accounting.json")
    summary = prereg.load(FAILED / "summary.json")
    require(accounting["requests_attempted"] == 1 and
        accounting["scientific_inference_events"] == 1 and
        accounting["valid_responses"] == 0 and accounting["invalid_responses"] == 1 and
        summary["failure_code"] == "QUALITY_RESPONSE_INVALID" and
        (FAILED / "all_quality_outputs_freeze_barrier.json").is_file(),
        "FAILED_EXECUTION_ACCOUNTING_MISMATCH")
    barrier = prereg.load(FAILED / "all_quality_outputs_freeze_barrier.json")
    require(barrier["crossed"] is False and
        not any((FAILED / name).exists() for name in (
            "quality_pass_candidate_manifest.jsonl", "quality_fail_candidate_manifest.jsonl",
            "quality_unresolved_candidate_manifest.jsonl")) and
        len(list((FAILED / "attempts").glob("*.json"))) == 1,
        "FAILED_EXECUTION_PRESERVATION_MISMATCH")
    envelope, body, schema = parse_structural_response()
    structure = structural_audit(body, schema, requests[0])
    require(structure["missing_schema_version_count"] == 1 and
        not structure["other_structural_errors"] and
        structure["candidate_id_set_exact"] and
        structure["top_level_schema_version_exact"],
        "GROUP1_STRUCTURAL_FAILURE_NOT_ISOLATED")
    req = requests[0]["request"]
    user = req["messages"][1]["content"]
    schema_text = user.split("Output JSON schema:\n", 1)[1].split(
        "\nMachine-output appendix:\n", 1)[0]
    prompt_schema = json.loads(schema_text)
    require(prompt_schema == schema and
        prompt_schema["properties"]["schema_version"] == {"const": VERSION} and
        prompt_schema["properties"]["judgments"]["items"]["properties"]["schema_version"] ==
        {"const": VERSION} and
        "schema_version" in prompt_schema["properties"]["judgments"]["items"]["required"] and
        "Return exactly one JSON object matching the output schema" in user,
        "MODEL_VISIBLE_SCHEMA_VERSION_UNRESOLVED")
    transport = prereg.rows(FAILED / "quality_transport_provenance.jsonl")[0]
    require(transport["http_status"] == 200 and
        transport["raw_response_sha256"] == RAW_SHA and
        req["response_format"] == {"type": "json_object"} and
        envelope["choices"][0]["finish_reason"] == "stop",
        "PROVIDER_RESPONSE_MODE_UNRESOLVED")
    actual_schema = prereg.load(Q2 / "proposition_quality_adjudication_v2_schema.json")["schema"]
    require(actual_schema == schema and
        prereg.load(PREREG / "quality_response_schema_contract.json")["schema_version"] == VERSION,
        "QUALITY_V2_SCHEMA_DRIFT")
    # Deterministic metadata may be known to the controller while still being
    # explicitly assigned to model-output serialization by this executed contract.
    semantics = "DETERMINISTIC_PROTOCOL_METADATA"
    visibility = "EXPLICIT_AND_EXACT"
    provider_mode = "JSON_OBJECT_ONLY"
    classification = "NO_INTERFACE_DEFECT_MODEL_OMISSION"
    structurally_replayable_in_a_different_contract = True
    next_stage = "INTERPRET_ALPHA3_18C_FAILURE_UNDER_VALID_QUALITY_CONTRACT"
    OUT.mkdir()
    write("alpha3_18c_failure_verification.json", {"failed_root_sha256": FAILED_SHA,
        "failed_run_marker": ref(FAILED / execution.ROOT_MARKER),
        "requests_planned": 3, "requests_attempted": 1,
        "scientific_inference_events": 1, "valid_responses": 0,
        "invalid_responses": 1, "groups_2_3_unattempted": True,
        "all_output_barrier_crossed": False, "candidate_final_states_derived": False})
    write("group1_raw_response_integrity.json", {"raw_response": ref(FAILED /
        "raw_provider_responses/01.json"), "expected_sha256": RAW_SHA,
        "hash_verified": True, "provider_http_status": 200,
        "finish_reason": "stop", "provider_envelope_parseable": True,
        "response_body_parseable_json": True, "scientific_judgments_not_reported": True})
    write("group1_structural_field_audit.json", structure)
    timeline = [
        {"stage": "QualityV2 scientific protocol", "source": ref(Q2 /
            "proposition_quality_adjudication_v2_schema.json"),
            "authority": "constant schema metadata; required at top level and per judgment",
            "value_known_before_inference": True},
        {"stage": "Quality request construction", "source": ref(ROOT /
            "scripts/search_plan_v24_alpha318b_post_builder_prechecks.py"),
            "authority": "renders frozen complete schema into user message",
            "value_known_before_inference": True},
        {"stage": "model-visible frozen group-1 request", "source": ref(B2 /
            "proposition_quality_v2_request_manifest_v3.jsonl"),
            "authority": "exact constant and judgment required-field list visible",
            "value_known_before_inference": True},
        {"stage": "DeepSeek provider serialization", "source": ref(PREREG /
            "quality_execution_provider_binding_v2_1.json"),
            "authority": "JSON object mode only; no provider-native strict schema",
            "value_known_before_inference": True},
        {"stage": "local response validator", "source": ref(ROOT /
            "scripts/search_plan_v24_alpha317d_preregister_quality_v2_offline.py"),
            "authority": "requires exact judgment field set and fixed version value",
            "value_known_before_inference": True},
        {"stage": "alpha3.18C execution manifest", "source": ref(PREREG /
            "alpha3_18c_quality_execution_manifest.json"),
            "authority": "binds frozen V2 schema and fail-closed validator",
            "value_known_before_inference": True},
    ]
    write("quality_schema_version_authority_timeline.json", {"timeline": timeline,
        "top_level_and_judgment_value_identical": True})
    write("quality_schema_version_semantics.json", {"classification": semantics,
        "constant_for_all_three_requests": True, "candidate_independent": True,
        "source_independent": True, "scientifically_non_evaluative": True,
        "fully_known_before_provider_execution": True,
        "executed_contract_assigns_model_serialization_responsibility": True,
        "deterministic_semantics_do_not_override_executed_required_output_field": True})
    write("quality_model_visible_schema_audit.json", {"status": visibility,
        "frozen_group1_request_sha256": requests[0]["request_sha256"],
        "output_schema_json_visible": True,
        "top_level_version_const_visible": True,
        "per_judgment_version_const_visible": True,
        "per_judgment_version_required_visible": True,
        "machine_appendix_requires_exact_schema_and_field_names": True})
    write("quality_provider_response_format_audit.json", {"mode": provider_mode,
        "request_response_format": req["response_format"],
        "provider_native_strict_schema_used": False,
        "provider_json_syntax_constraint_only": True,
        "model_visible_schema_is_prompt_text": True,
        "local_schema_validation_required": True})
    write("quality_local_validator_ownership_audit.json", {
        "validator_source": ref(ROOT /
            "scripts/search_plan_v24_alpha317d_preregister_quality_v2_offline.py"),
        "requires_per_judgment_schema_version": True,
        "requirement_model_visible": True,
        "required_value_controller_known_before_inference": True,
        "missing_field_invalid_under_executed_contract": True,
        "generic_missing_field_injection_allowed": False,
        "prospective_controller_envelope_would_be_contract_change_not_historical_correction": True})
    matrix = [
        {"layer": "scientific_Quality_V2_protocol", "required": True,
         "model_serialization_required": True, "controller_known_value": True,
         "provider_enforced": False, "validator_enforced": True},
        {"layer": "model_visible_request", "required": True,
         "model_serialization_required": True, "controller_known_value": True,
         "provider_enforced": False, "validator_enforced": False},
        {"layer": "provider_response_format", "required": False,
         "model_serialization_required": False, "controller_known_value": True,
         "provider_enforced": False, "validator_enforced": False},
        {"layer": "local_response_validator", "required": True,
         "model_serialization_required": True, "controller_known_value": True,
         "provider_enforced": False, "validator_enforced": True},
    ]
    write("quality_response_four_way_consistency_matrix.json", {"schema_version": matrix,
        "prompt_and_validator_requirements_consistent": True,
        "provider_native_schema_enforcement_claimed": False,
        "json_object_mode_is_not_strict_schema": True})
    write("quality_response_defect_classification.json", {"classification": classification,
        "basis": ["exact required field and constant were model-visible",
                  "local validator enforced the same frozen field and value",
                  "JSON-object-only provider mode was explicit, not misrepresented as strict schema",
                  "deterministic metadata semantics alone do not imply a broken interface"],
        "observed_failure": "model omitted one required non-scientific per-judgment field",
        "scientific_candidate_content_used": False})
    write("historical_group1_disposition.json", {"state":
        "QUALITY_RESPONSE_INVALID_UNDER_ALPHA3_18C_EXECUTED_CONTRACT",
        "raw_response_sha256": RAW_SHA, "historical_inference_events": 1,
        "response_rewritten": False, "candidate_states_derived": False,
        "replay_authorized": False, "reinference_authorized": False})
    write("offline_structural_replay_eligibility.json", {"classification":
        "OFFLINE_STRUCTURAL_REPLAY_ELIGIBLE" if structurally_replayable_in_a_different_contract else
        "OFFLINE_STRUCTURAL_REPLAY_NOT_ELIGIBLE",
        "all_non_version_structural_fields_valid": True,
        "exact_candidate_id_set": True, "enum_normalization_needed": False,
        "scientific_field_repair_needed": False,
        "interface_defect_confirmed": False,
        "actual_historical_replay_permitted": False,
        "reason": "mechanical structural eligibility is not authorization to change an executed valid contract"})
    write("candidate_content_nonuse_audit.json", {"contract_design_inputs": [
        "frozen Quality V2 schema and validator", "frozen group-1 request structure",
        "provider response-format setting", "raw response field shape and enum-domain membership"],
        "criterion_values_persisted_in_audit": False,
        "criterion_outcomes_interpreted": False,
        "scientific_candidate_content_used_for_contract_design": False,
        "candidate_final_states_derived": False})
    write("groups_2_3_freeze_verification.json", {"request_manifest": ref(B2 /
        "proposition_quality_v2_request_manifest_v3.jsonl"),
        "groups": [{"order_index": index, "source_group_id": row["source_group_id"],
            "request_sha256": row["request_sha256"],
            "candidate_ids": sorted(row["candidate_ids"]), "request_attempted": False}
            for index, row in enumerate(requests[1:], 2)],
        "request_hashes_unchanged": True, "evidence_and_context_hashes_unchanged": True})
    write("quality_inference_accounting_policy.json", {"historical_quality_inference_events": 1,
        "historical_invalid_inference_events": 1,
        "future_provider_calls_authorized_by_this_audit": 0,
        "future_provider_calls_under_selected_no_defect_branch": 0,
        "hypothetical_path_A_cumulative_events": 3,
        "hypothetical_path_B_cumulative_events": 4,
        "historical_invalid_inference_never_erased": True})
    write("historical_preservation_audit.json", {"failed_alpha3_18c_root_still_verified":
        prereg.root(FAILED, execution.ROOT_MARKER) == FAILED_SHA,
        "prereg_alpha3_18c_root_still_verified":
        prereg.root(PREREG, prereg.ROOT_MARKER) == PREREG_SHA,
        "group1_raw_response_sha256_still_verified":
        prereg.digest(FAILED / "raw_provider_responses/01.json") == RAW_SHA,
        "B2_root_still_verified": prereg.root(B2, "search_plan_v24_dev_alpha3_18b2_sha256") ==
            prereg.B2_SHA, "historical_assets_modified": False})
    write("scientific_state_safety_audit.json", {"provider_calls": 0, "llm_calls": 0,
        "network_calls": 0, "quality_retries": 0, "groups_2_3_calls": 0,
        "scientific_response_interpretation": False,
        "candidate_final_states_derived": False,
        "pool_finalization": False})
    write("validation.json", {"status": "PASS", "historical_alpha3_18c_preserved": True,
        "historical_quality_inference_events": 1,
        "group1_raw_response_hash_verified": True,
        "schema_version_ownership_resolved": True,
        "schema_version_model_visibility_resolved": True,
        "provider_response_enforcement_mode_resolved": True,
        "quality_response_contract_defect_classification_resolved": True,
        "groups_2_3_requests_unchanged": True,
        "quality_scientific_protocol_changed": False,
        "deepseek_model": prereg.MODEL,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0})
    write("summary.json", {"status": "completed", "defect_classification": classification,
        "schema_version_semantics": semantics,
        "schema_version_model_visibility": visibility,
        "provider_response_enforcement_mode": provider_mode,
        "group1_missing_schema_version_count": 1,
        "group1_other_structural_error_count": 0,
        "offline_structural_replay_eligible_in_different_contract": True,
        "actual_replay_or_rerun_authorized": False,
        "future_quality_provider_call_count": 0,
        "quality_response_envelope_v2_2_sha256": None,
        "alpha3_18c2_quality_execution_manifest_sha256": None,
        "next_stage_recommendation": next_stage})
    require(prereg.root(FAILED, execution.ROOT_MARKER) == FAILED_SHA and
        prereg.root(PREREG, prereg.ROOT_MARKER) == PREREG_SHA and
        prereg.digest(FAILED / "raw_provider_responses/01.json") == RAW_SHA,
        "HISTORICAL_ASSET_MUTATION_DETECTED")
    root_sha = prereg.root(OUT, ROOT_MARKER)
    with (OUT / ROOT_MARKER).open("x", encoding="ascii") as handle:
        handle.write(root_sha + "\n")
    print(json.dumps({"status": "completed", "root_sha256": root_sha,
        "defect_classification": classification,
        "next_stage_recommendation": next_stage}, sort_keys=True))


if __name__ == "__main__":
    main()
