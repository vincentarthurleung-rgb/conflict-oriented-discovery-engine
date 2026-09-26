#!/usr/bin/env python3
"""Offline-only Pass B machine-output contract hardening after schema failure."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_13_harmonized_neutral_review_preregistration_offline"
AMENDMENT = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_14a_review_identity_binding_amendment_offline"
FAILED_314B = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_14b_harmonized_review_continuation"
AUTOPSY = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_14c_pass_b_batch3_schema_failure_autopsy_offline"
RUN = ROOT / "runs/20260926_search_plan_v24_dev_alpha3_14d_pass_b_output_contract_hardening_offline"
CLIENT = ROOT / "src/code_engine/extraction/deepseek_client.py"
EXPECTED_AUTOPSY = "78095a25aa4c60a0c2eb96ce888a1e7cb4b0132c40d0f7bf9eb0d33a676fc8b1"
EXPECTED_PROTOCOL_V2 = "a1d975f2e2915e286abdb7202e9741921e65f6055791207d4282aff4c9217727"


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise RuntimeError(reason)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(name: str, value: Any) -> None:
    path = RUN / name
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.exists(), f"refusing overwrite: {name}")
    path.write_bytes(canonical(value) + b"\n")


def write_lines(name: str, rows: list[Any]) -> None:
    path = RUN / name
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.exists(), f"refusing overwrite: {name}")
    path.write_bytes(b"".join(canonical(row) + b"\n" for row in rows))


def inventory(root: Path) -> list[list[Any]]:
    return [[str(path.relative_to(root)), sha(path), path.stat().st_size]
            for path in sorted(root.rglob("*")) if path.is_file()]


def schema_failures(value: Any, schema: dict[str, Any], path: str = "$") -> list[dict[str, str]]:
    """Return only schema failure paths/categories, never scientific values."""
    failures: list[dict[str, str]] = []
    kinds = schema.get("type")
    if kinds is not None:
        kinds = kinds if isinstance(kinds, list) else [kinds]
        checks = {"object": lambda x: isinstance(x, dict), "array": lambda x: isinstance(x, list),
                  "string": lambda x: isinstance(x, str), "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
                  "null": lambda x: x is None, "boolean": lambda x: isinstance(x, bool)}
        if not any(checks[k](value) for k in kinds):
            return [{"path": path, "failure": "TYPE"}]
    if "enum" in schema and value not in schema["enum"]:
        failures.append({"path": path, "failure": "ENUM"})
    if "const" in schema and value != schema["const"]:
        failures.append({"path": path, "failure": "CONST"})
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                failures.append({"path": f"{path}.{name}", "failure": "MISSING_REQUIRED"})
        if schema.get("additionalProperties") is False:
            for name in sorted(set(value) - set(props)):
                failures.append({"path": f"{path}.{name}", "failure": "EXTRA_PROHIBITED"})
        for name in sorted(set(value) & set(props)):
            failures.extend(schema_failures(value[name], props[name], f"{path}.{name}"))
    elif isinstance(value, list):
        if not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", float("inf")):
            failures.append({"path": path, "failure": "ARRAY_LENGTH"})
        for index, item in enumerate(value):
            failures.extend(schema_failures(item, schema.get("items", {}), f"{path}[{index}]"))
    elif isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            failures.append({"path": path, "failure": "MIN_LENGTH"})
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            failures.append({"path": path, "failure": "PATTERN"})
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        if not schema.get("minimum", float("-inf")) <= value <= schema.get("maximum", float("inf")):
            failures.append({"path": path, "failure": "NUMBER_BOUND"})
    return failures


def validate_batch(response: dict[str, Any], expected_ids: list[str], schema: dict[str, Any]) -> dict[str, Any]:
    failures = schema_failures(response, schema)
    records = response.get("records") if isinstance(response, dict) else None
    ids = [record.get("review_unit_id") if isinstance(record, dict) else None for record in records] if isinstance(records, list) else []
    all_ids_strings = all(isinstance(identifier, str) for identifier in ids)
    unique_ids = len(set(ids)) == len(ids) if all_ids_strings else False
    exact_set = set(ids) == set(expected_ids) if all_ids_strings else False
    identity_valid = (isinstance(records, list) and len(records) == len(expected_ids)
                      and all_ids_strings and unique_ids and exact_set)
    if not isinstance(records, list) or len(records) != len(expected_ids):
        failures.append({"path": "$.records", "failure": "EXPECTED_BATCH_COUNT"})
    if not all_ids_strings:
        failures.append({"path": "$.records[*].review_unit_id", "failure": "INVALID_ID_TYPE"})
    elif not unique_ids:
        failures.append({"path": "$.records[*].review_unit_id", "failure": "DUPLICATE_ID"})
    if all_ids_strings and set(expected_ids) - set(ids):
        failures.append({"path": "$.records[*].review_unit_id", "failure": "MISSING_EXPECTED_ID"})
    if all_ids_strings and set(ids) - set(expected_ids):
        failures.append({"path": "$.records[*].review_unit_id", "failure": "EXTRA_UNKNOWN_ID"})
    valid = identity_valid and not failures
    canonical_records = ([{**next(record for record in records if record["review_unit_id"] == identifier)}
                          for identifier in expected_ids] if valid else None)
    return {"valid": valid, "identity_valid": identity_valid, "schema_failure_count": len(schema_failures(response, schema)),
            "failures": failures, "provider_returned_order_matches_request_order": ids == expected_ids,
            "canonical_records": canonical_records}


def synthetic_cases(schema: dict[str, Any]) -> list[dict[str, Any]]:
    item = schema["properties"]["records"]["items"]
    props = item["properties"]
    valid_relevance = props["relevance_state"]["enum"][0]
    valid_contaminant = props["contaminant_class"]["enum"][0]
    contaminant_only = next(value for value in props["contaminant_class"]["enum"] if isinstance(value, str) and value not in props["relevance_state"]["enum"])
    relevance_only = next(value for value in props["relevance_state"]["enum"] if value not in props["contaminant_class"]["enum"])
    ids = ["NRV1_" + "a" * 24, "NRV1_" + "b" * 24]

    def record(identifier: str) -> dict[str, Any]:
        return {"review_unit_id": identifier, "relevance_state": valid_relevance,
                "matched_target_components": [], "mismatched_target_components": [],
                "fulltext_resolved_fields": [], "remaining_unresolved_fields": [],
                "contaminant_class": valid_contaminant, "rationale": "synthetic schema test only",
                "confidence": None, "reviewer_type": props["reviewer_type"]["const"]}

    baseline = [record(ids[0]), record(ids[1])]
    altered_relevance = [dict(row) for row in baseline]
    altered_relevance[0]["relevance_state"] = "SYNTHETIC_INVALID_LABEL"
    leak_contaminant = [dict(row) for row in baseline]
    leak_contaminant[0]["relevance_state"] = contaminant_only
    leak_relevance = [dict(row) for row in baseline]
    leak_relevance[0]["contaminant_class"] = relevance_only
    return [
        {"case_id": "VALID_RELEVANCE_ENUM", "expected_ids": ids, "records": baseline, "expected_valid": True},
        {"case_id": "INVALID_RELEVANCE_ENUM", "expected_ids": ids, "records": altered_relevance, "expected_valid": False},
        {"case_id": "CONTAMINANT_VALUE_IN_RELEVANCE_STATE", "expected_ids": ids, "records": leak_contaminant, "expected_valid": False},
        {"case_id": "RELEVANCE_VALUE_IN_CONTAMINANT_CLASS", "expected_ids": ids, "records": leak_relevance, "expected_valid": False},
        {"case_id": "DUPLICATE_ID", "expected_ids": ids, "records": [record(ids[0]), record(ids[0])], "expected_valid": False},
        {"case_id": "MISSING_ID", "expected_ids": ids, "records": [record(ids[0])], "expected_valid": False},
        {"case_id": "EXTRA_ID", "expected_ids": ids, "records": baseline + [record("NRV1_" + "c" * 24)], "expected_valid": False},
        {"case_id": "OUT_OF_ORDER_VALID_IDS", "expected_ids": ids, "records": list(reversed(baseline)), "expected_valid": True},
    ]


def main() -> None:
    require(not RUN.exists(), "alpha3.14d already exists; refusing regeneration")
    old_autopsy = load(AUTOPSY / "summary.json")
    require(old_autopsy["status"] == "completed" and old_autopsy["failure_class"] == "SEMANTIC_NEAR_ALIAS_REQUIRING_INTERPRETATION", "alpha3.14c conclusion drift")
    autopsy_pairs = [[path.name, sha(path)] for path in sorted(AUTOPSY.iterdir()) if path.is_file() and path.name != "search_plan_v24_dev_alpha3_14c_sha256"]
    require(digest(autopsy_pairs) == EXPECTED_AUTOPSY == (AUTOPSY / "search_plan_v24_dev_alpha3_14c_sha256").read_text().strip(), "authoritative alpha3.14c root drift")
    revised = load(AMENDMENT / "revised_harmonized_review_protocol.json")
    require(digest(revised["aggregate_components"]) == EXPECTED_PROTOCOL_V2 == (AMENDMENT / "revised_harmonized_review_protocol_sha256").read_text().strip(), "authoritative protocol V2 root drift")
    replacements = set(revised["replacement_components"])
    require(all(sha((AMENDMENT if name in replacements else SOURCE) / name) == checksum for name, checksum in revised["aggregate_components"]), "revised protocol component drift")
    failed_summary = load(FAILED_314B / "summary.json")
    require(failed_summary["historical_deepseek_calls_preserved"] == 9 and failed_summary["new_actual_deepseek_calls"] == 2 and failed_summary["total_unique_inferred_batches"] == 11, "inference accounting drift")
    autopsy_inventory = inventory(AUTOPSY)
    failed_inventory = inventory(FAILED_314B)
    prompt_templates = load(SOURCE / "neutral_review_prompt_template.txt")
    original_template = prompt_templates["PASS_B"]
    schema_all = load(SOURCE / "neutral_review_output_schema.json")
    output_schema = schema_all["PASS_B"]
    item_props = output_schema["properties"]["records"]["items"]["properties"]
    relevance_enum = item_props["relevance_state"]["enum"]
    contaminant_enum = item_props["contaminant_class"]["enum"]
    historical = load(SOURCE / "historical_review_label_schema.json")
    require(relevance_enum == historical["properties"]["relevance_state"]["enum"], "historical relevance enum drift")
    require(contaminant_enum == historical["properties"]["contaminant_class"]["enum"], "historical contaminant enum drift")
    require(set(relevance_enum).isdisjoint(set(contaminant_enum)), "field-specific enum domains overlap")
    # Compare the historical record schema after the known review_id -> review_unit_id projection.
    projected = json.loads(json.dumps(historical))
    projected["properties"].pop("review_id")
    projected["properties"]["review_unit_id"] = item_props["review_unit_id"]
    projected["required"] = ["review_unit_id" if key == "review_id" else key for key in projected["required"]]
    require(projected["required"] == output_schema["properties"]["records"]["items"]["required"], "required field set drift")
    require({key: projected["properties"][key] for key in projected["properties"]} == item_props, "record property schema drift")
    client_source = CLIENT.read_text(encoding="utf-8")
    require('DEEPSEEK_JSON_RESPONSE_FORMAT = {"type": "json_object"}' in client_source, "provider JSON mode audit drift")
    require('"response_format": dict(DEEPSEEK_JSON_RESPONSE_FORMAT)' in client_source, "provider request format audit drift")
    require("json_schema" not in client_source and "strict" not in client_source, "local adapter may have stronger schema enforcement; re-audit required")
    require(original_template.count("\n\n--- RESPONSE SCHEMA ---\n") == 1 and original_template.count("\n--- PASS B PACKETS ---\n") == 1, "prompt template boundary drift")
    scientific_prompt = original_template.split("\n\n--- RESPONSE SCHEMA ---\n", 1)[0]
    old_serialization = original_template.split("\n\n--- RESPONSE SCHEMA ---\n", 1)[1].split("\n--- PASS B PACKETS ---\n", 1)[0]
    enum_relevance_json = canonical(relevance_enum).decode("utf-8")
    enum_contaminant_json = canonical(contaminant_enum).decode("utf-8")
    appendix = ("--- MACHINE OUTPUT CONTRACT V2: SERIALIZATION ONLY ---\n"
                "Return exactly one JSON object containing only `records`. Each record must contain exactly the fields required by the frozen response schema.\n"
                f"`relevance_state` is a JSON string and MUST be copied byte-for-byte from this field's allowed values only: {enum_relevance_json}\n"
                f"`contaminant_class` is a JSON string or null and MUST be copied exactly from this separate field's allowed values only: {enum_contaminant_json}\n"
                "These are independent fields. Never place a value from one field's enum in the other field. Do not invent labels, synonyms, natural-language reformulations, case changes, hyphen changes, underscore changes, or semantic aliases.\n"
                "Use each packet's exact `review_unit_id` once; return one record per packet, in the supplied batch order. Do not add fields.\n"
                "This section constrains machine serialization only; make scientific judgments solely under the unchanged instruction and evidence above.")
    revised_template = original_template.replace("\n--- PASS B PACKETS ---\n{batch_json}", "\n--- MACHINE OUTPUT CONTRACT V2 ---\n" + appendix + "\n--- PASS B PACKETS ---\n{batch_json}")
    require(revised_template != original_template and revised_template.split("\n\n--- RESPONSE SCHEMA ---\n", 1)[0] == scientific_prompt, "scientific prompt changed")
    new_serialization = revised_template.split("\n\n--- RESPONSE SCHEMA ---\n", 1)[1].split("\n--- PASS B PACKETS ---\n", 1)[0]
    require(new_serialization.startswith(old_serialization), "old serialization contract removed or rewritten")
    fields = []
    item_schema = output_schema["properties"]["records"]["items"]
    for field in ("relevance_state", "contaminant_class"):
        prop = item_props[field]
        values = prop["enum"]
        fields.append({"field_name": field, "exact_allowed_enum_values": values,
                       "exact_json_type": "string_or_null" if None in values else prop["type"],
                       "required": field in item_schema["required"],
                       "other_enum_field": "contaminant_class" if field == "relevance_state" else "relevance_state",
                       "cross_field_prohibition": "EXACT_STRINGS_FROM_OTHER_FIELD_NOT_ALLOWED_UNLESS_OWN_ENUM_ALSO_CONTAINS_THEM",
                       "source_schema_sha256": sha(SOURCE / "neutral_review_output_schema.json")})
    contract = {"artifact_schema_version": "PassBOutputContractV2",
                "classification": "POST_FAILURE_SCIENTIFIC_SCHEMA_SERIALIZATION_AMENDMENT",
                "frozen_scientific_output_schema_sha256": sha(SOURCE / "neutral_review_output_schema.json"),
                "field_enum_domains": fields,
                "required_record_fields": item_schema["required"],
                "reviewer_type_const": item_props["reviewer_type"]["const"],
                "exact_enum_serialization_required": True,
                "no_synonyms_paraphrases_case_hyphen_or_underscore_variants": True,
                "cross_field_enum_leakage_guard_defined": True,
                "provider_response_format": {"type": "json_object"},
                "provider_native_exact_enum_enforcement_used": False,
                "local_fail_closed_schema_validation": True,
                "review_response_identity_binding_protocol_sha256": EXPECTED_PROTOCOL_V2,
                "scientific_prompt_sha256": hashlib.sha256(scientific_prompt.encode()).hexdigest(),
                "serialization_appendix": appendix,
                "revised_pass_b_prompt_template": revised_template,
                "no_scientific_examples": True,
                "prompt_batch_membership_and_evidence_placeholders_unchanged": True}
    RUN.mkdir(parents=True)
    write("prior_inference_event_preservation_audit.json", {"original_alpha3_13_inference_events": 9,
                                                            "alpha3_14b_continuation_inference_events": 2,
                                                            "total_provider_inference_events_already_occurred": 11,
                                                            "valid_batch_adjudications": 10,
                                                            "schema_invalid_batch_adjudications": 1,
                                                            "never_inferred_batch_identities": 5,
                                                            "invalid_batch3_inference_permanently_preserved": True,
                                                            "alpha3_14c_root_sha256": EXPECTED_AUTOPSY,
                                                            "alpha3_14b_inventory_sha256": digest(failed_inventory)})
    write("batch3_failure_fact_verification.json", {"source_autopsy_sha256": EXPECTED_AUTOPSY,
                                                     "returned_records": 10, "id_binding_valid": True,
                                                     "schema_enum_violations": 7,
                                                     "relevance_state_enum_violations": 6,
                                                     "other_enum_violations": 1,
                                                     "first_invalid_relevance_token": "WRONG_BIOLOGICAL_UNIT",
                                                     "failure_class": "SEMANTIC_NEAR_ALIAS_REQUIRING_INTERPRETATION",
                                                     "deterministic_normalization_exists": False,
                                                     "batch3_reusable": False})
    write("existing_pass_b_output_contract_audit.json", {"frozen_pass_b_prompt_template_sha256": sha(SOURCE / "neutral_review_prompt_template.txt"),
                                                       "frozen_output_schema_sha256": sha(SOURCE / "neutral_review_output_schema.json"),
                                                       "frozen_request_schema_sha256": sha(SOURCE / "neutral_review_request_schema.json"),
                                                       "prompt_embeds_exact_output_schema": True,
                                                       "prompt_relevance_enum": relevance_enum,
                                                       "prompt_contaminant_enum": contaminant_enum,
                                                       "request_schema_has_exact_enums": False,
                                                       "output_schema_has_exact_enums": True,
                                                       "validator_accepts_only_frozen_field_specific_enums": True,
                                                       "field_specific_boundaries_structurally_present_but_serialization_instruction_not_separate": True,
                                                       "observed_failure_mode": "contaminant_class_like_value_emitted_in_relevance_state",
                                                       "provider_request_json_object_only": True})
    write("field_enum_domain_matrix.json", {"field_enum_domains": fields,
                                            "exact_domain_intersection": [],
                                            "cross_field_enum_leakage_guard_defined": True,
                                            "no_new_label_values": True})
    write("provider_structured_output_capability_audit.json", {"audit_scope": "repository_local_adapter_and_prior_frozen_requests_only",
                                                               "deepseek_client_sha256": sha(CLIENT),
                                                               "existing_adapter_response_format": {"type": "json_object"},
                                                               "existing_adapter_exact_schema_constraint_support": False,
                                                               "existing_adapter_json_schema_parameter_support": False,
                                                               "provider_global_capability_not_claimed": True,
                                                               "provider_native_schema_enforcement_available": False,
                                                               "provider_native_schema_enforcement_used_in_v2": False,
                                                               "new_external_dependency_added": False,
                                                               "network_research_performed": False,
                                                               "fallback": "separately_versioned_machine_output_instruction_appendix_plus_local_fail_closed_schema_validation"})
    write("pass_b_output_contract_v2.json", contract)
    contract_sha = sha(RUN / "pass_b_output_contract_v2.json")
    (RUN / "pass_b_output_contract_v2_sha256").write_text(contract_sha + "\n", encoding="utf-8")
    write("scientific_prompt_immutability_audit.json", {"scientific_prompt_hash_before": hashlib.sha256(scientific_prompt.encode()).hexdigest(),
                                                        "scientific_prompt_hash_after": hashlib.sha256(revised_template.split("\n\n--- RESPONSE SCHEMA ---\n", 1)[0].encode()).hexdigest(),
                                                        "scientific_prompt_byte_identical": True,
                                                        "pass_b_scientific_task_changed": False,
                                                        "review_evidence_or_target_changed": False,
                                                        "rubric_changed": False,
                                                        "old_full_template_sha256": hashlib.sha256(original_template.encode()).hexdigest(),
                                                        "new_full_template_sha256": hashlib.sha256(revised_template.encode()).hexdigest()})
    write("serialization_contract_delta.json", {"serialization_contract_hash_before": hashlib.sha256(old_serialization.encode()).hexdigest(),
                                                  "serialization_contract_hash_after": hashlib.sha256(new_serialization.encode()).hexdigest(),
                                                  "old_serialization_contract_preserved_as_prefix": True,
                                                  "new_appendix_sha256": hashlib.sha256(appendix.encode()).hexdigest(),
                                                  "delta": "append field-specific exact enum and cross-field separation instructions before unchanged packet placeholder",
                                                  "scientific_rubric_changed": False,
                                                  "scientific_label_taxonomy_changed": False,
                                                  "evidence_changed": False, "target_changed": False})
    write("replacement_inference_policy.json", {"existing_batch3_inference_status": "INVALID_SUPERSEDED_INFERENCE_IF_FUTURE_REPLACEMENT_AUTHORIZED",
                                               "original_invalid_inference_must_be_preserved": True,
                                               "old_labels_may_not_be_compared_with_replacement_to_choose_retained_output": True,
                                               "replacement_allowed_only_after_new_explicit_authorization": True,
                                               "replacement_batch_index": 3,
                                               "unchanged": ["same 10 review units", "same order", "same targets", "same evidence packets", "same scientific rubric", "same provider/model/thinking/reasoning configuration"],
                                               "only_permitted_difference": "frozen PassBOutputContractV2 serialization appendix",
                                               "automatic_retry_or_repair": False})
    write("sequential_continuation_gate.json", {"step_1": "one newly authorized PASS B batch 3 replacement inference under OutputContractV2",
                                                "step_1_validation": "full unchanged scientific output schema plus ReviewResponseIdentityBindingV2 and exact enum constraints",
                                                "step_2_condition": "execute PASS B batches 4-8 only if replacement batch 3 is fully valid",
                                                "if_step_1_fails": "STOP_WITHOUT_CALLING_BATCHES_4_TO_8",
                                                "max_future_new_calls_if_all_valid": 6,
                                                "calls_authorized_in_alpha3_14d": 0,
                                                "gate_frozen": True})
    write("future_call_accounting_contract.json", {"planned_batch_identities": 16,
                                                   "valid_final_batch_adjudications_if_success": 16,
                                                   "historical_provider_inference_events": 11,
                                                   "future_maximum_authorized_calls_next_stage": 6,
                                                   "provider_inference_events_if_success": 17,
                                                   "schema_invalid_superseded_inference_events": 1,
                                                   "reinferred_batch_identities": 1,
                                                   "never_reinferred_valid_batch_identities": 15,
                                                   "never_inferred_batch_identities_before_next_stage": 5,
                                                   "no_call_authorization_in_this_stage": True})
    cases = synthetic_cases(output_schema)
    results = []
    for case in cases:
        result = validate_batch({"records": case["records"]}, case["expected_ids"], output_schema)
        require(result["valid"] is case["expected_valid"], f"synthetic contract expectation failed: {case['case_id']}")
        if case["case_id"] == "OUT_OF_ORDER_VALID_IDS":
            require(result["provider_returned_order_matches_request_order"] is False, "out-of-order case did not permute")
            require([record["review_unit_id"] for record in result["canonical_records"]] == case["expected_ids"], "canonicalization failed")
        results.append({"case_id": case["case_id"], "expected_valid": case["expected_valid"],
                        "actual_valid": result["valid"], "identity_valid": result["identity_valid"],
                        "schema_failure_count": result["schema_failure_count"],
                        "failure_categories": [entry["failure"] for entry in result["failures"]],
                        "canonical_request_order_restored": [record["review_unit_id"] for record in result["canonical_records"]] == case["expected_ids"] if result["canonical_records"] else False})
    write_lines("synthetic_schema_validation_cases.jsonl", cases)
    write("synthetic_schema_validation_results.json", {"case_count": len(cases), "all_expected_outcomes_match": True,
                                                       "scientific_examples_used": False, "results": results})
    write("reviewer_blinding_audit.json", {"arm_exposed": False, "architecture_exposed": False,
                                          "case_id_exposed": False, "query_exposed": False,
                                          "tier_or_selection_rank_exposed": False,
                                          "historical_labels_exposed": False,
                                          "pass_a_output_exposed": False,
                                          "appendix_contains_no_scientific_unit_examples": True,
                                          "evidence_packet_placeholder_unchanged": True})
    write("arm_firewall_audit.json", {"arm_map_accessed": False, "hidden_arm_map_loaded_or_parsed": False,
                                     "identity_join_performed": False})
    write("metrics_nonexecution_audit.json", {"metrics_computed": False, "direct_rates_computed": False,
                                              "arm_comparisons_computed": False})
    unchanged = revised["aggregate_components"]
    protocol_pairs = sorted(unchanged + [["pass_b_output_contract_v2.json", contract_sha]])
    protocol_v4_root = digest(protocol_pairs)
    write("harmonized_review_protocol_v4_manifest.json", {"artifact_schema_version": "HarmonizedReviewProtocolV4",
                                                       "base_protocol_v2_sha256": EXPECTED_PROTOCOL_V2,
                                                       "unchanged_protocol_v2_components": unchanged,
                                                       "new_output_contract_sha256": contract_sha,
                                                       "aggregate_algorithm": "sha256(canonical JSON sorted [path,sha256] pairs)",
                                                       "aggregate_components": protocol_pairs,
                                                       "harmonized_review_protocol_v4_sha256": protocol_v4_root,
                                                       "post_failure_protocol_amendment": True,
                                                       "scientific_protocol_changed": False,
                                                       "provider_calls_authorized": 0})
    (RUN / "harmonized_review_protocol_v4_sha256").write_text(protocol_v4_root + "\n", encoding="utf-8")
    require(inventory(AUTOPSY) == autopsy_inventory and inventory(FAILED_314B) == failed_inventory, "prior artifacts changed")
    write("scientific_state_safety_audit.json", {"historical_assets_modified": False,
                                                "scientific_rubric_changed": False,
                                                "label_taxonomy_changed": False,
                                                "evidence_changed": False,
                                                "target_changed": False,
                                                "provider_model_thinking_reasoning_changed": False,
                                                "batch_membership_or_mixed_ordering_changed": False,
                                                "arm_map_accessed": False, "metrics_computed": False,
                                                "deepseek_calls": 0, "openai_calls": 0, "llm_calls": 0,
                                                "network_calls": 0, "retrieval_calls": 0})
    write("validation.json", {"status": "PASS", "post_failure_protocol_amendment": True,
                              "pass_b_output_contract_v2_defined": True,
                              "scientific_rubric_changed": False,
                              "label_taxonomy_changed": False,
                              "evidence_changed": False, "target_changed": False,
                              "field_specific_enum_domains_explicit": True,
                              "cross_field_enum_leakage_guard_defined": True,
                              "replacement_batch3_policy_frozen": True,
                              "sequential_continuation_gate_frozen": True,
                              "planned_batch_identities": 16,
                              "historical_provider_inference_events": 11,
                              "future_maximum_authorized_calls_next_stage": 6,
                              "arm_map_accessed": False, "metrics_computed": False,
                              "deepseek_calls": 0, "openai_calls": 0, "llm_calls": 0,
                              "network_calls": 0, "retrieval_calls": 0,
                              "synthetic_contract_test_count": len(cases),
                              "synthetic_contract_tests_passed": len(cases)})
    write("summary.json", {"status": "completed", "post_failure_protocol_amendment": True,
                           "pass_b_output_contract_v2_sha256": contract_sha,
                           "harmonized_review_protocol_v4_sha256": protocol_v4_root,
                           "provider_native_schema_enforcement_available": False,
                           "provider_native_schema_enforcement_used_in_v2": False,
                           "next_stage_recommendation": "AUTHORIZE_BATCH3_REPLACEMENT_THEN_REMAINING_5_PASS_B_BATCHES",
                           "future_maximum_authorized_calls_next_stage": 6,
                           "deepseek_calls": 0, "openai_calls": 0, "llm_calls": 0,
                           "network_calls": 0, "retrieval_calls": 0,
                           "historical_assets_modified": False})
    pairs = [[path.name, sha(path)] for path in sorted(RUN.iterdir()) if path.is_file()]
    root = digest(pairs)
    (RUN / "search_plan_v24_dev_alpha3_14d_sha256").write_text(root + "\n", encoding="utf-8")
    require(inventory(AUTOPSY) == autopsy_inventory and inventory(FAILED_314B) == failed_inventory, "prior artifacts changed after root freeze")
    print(f"alpha3.14d={root} output_contract={contract_sha} protocol_v4={protocol_v4_root} calls=0")


if __name__ == "__main__":
    main()
