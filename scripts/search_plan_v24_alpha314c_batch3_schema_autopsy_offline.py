#!/usr/bin/env python3
"""Offline-only alpha3.14c schema-failure autopsy, without arm or metric access."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import unicodedata
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_13_harmonized_neutral_review_preregistration_offline"
FAILED_313 = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_13_harmonized_deepseek_review"
AMENDMENT = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_14a_review_identity_binding_amendment_offline"
FAILED_314B = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_14b_harmonized_review_continuation"
RUN = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_14c_pass_b_batch3_schema_failure_autopsy_offline"
EXPECTED_314B_ROOT = "0d9595e7d1b0a27b14133dc4c79ed9ea911c5564b25a9f716ef78acb3b8ba5e8"
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


def inventory(root: Path) -> list[list[Any]]:
    return [[str(path.relative_to(root)), sha(path), path.stat().st_size]
            for path in sorted(root.rglob("*")) if path.is_file()]


def validate_structure(value: Any, schema: dict[str, Any], path: str = "$") -> list[dict[str, str]]:
    """Validate the frozen schema; return paths/categories, never field values."""
    errors: list[dict[str, str]] = []
    kinds = schema.get("type")
    if kinds is not None:
        kinds = kinds if isinstance(kinds, list) else [kinds]
        checks = {"object": lambda x: isinstance(x, dict), "array": lambda x: isinstance(x, list),
                  "string": lambda x: isinstance(x, str), "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
                  "null": lambda x: x is None, "boolean": lambda x: isinstance(x, bool)}
        if not any(checks[kind](value) for kind in kinds):
            return [{"path": path, "failure": "TYPE"}]
    if "enum" in schema and value not in schema["enum"]:
        errors.append({"path": path, "failure": "ENUM"})
    if "const" in schema and value != schema["const"]:
        errors.append({"path": path, "failure": "CONST"})
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append({"path": f"{path}.{key}", "failure": "MISSING_REQUIRED"})
        if schema.get("additionalProperties") is False:
            for key in sorted(set(value) - set(props)):
                errors.append({"path": f"{path}.{key}", "failure": "EXTRA_PROHIBITED"})
        for key in sorted(set(value) & set(props)):
            errors.extend(validate_structure(value[key], props[key], f"{path}.{key}"))
    elif isinstance(value, list):
        if not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", float("inf")):
            errors.append({"path": path, "failure": "ARRAY_LENGTH"})
        for index, item in enumerate(value):
            errors.extend(validate_structure(item, schema.get("items", {}), f"{path}[{index}]"))
    elif isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append({"path": path, "failure": "MIN_LENGTH"})
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            errors.append({"path": path, "failure": "PATTERN"})
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        if not schema.get("minimum", float("-inf")) <= value <= schema.get("maximum", float("inf")):
            errors.append({"path": path, "failure": "NUMBER_BOUND"})
    return errors


def main() -> None:
    require(not RUN.exists(), "alpha3.14c already exists; refusing regeneration")
    prior = load(FAILED_314B / "continuation_partial_failure_manifest.json")
    require(prior["status"] == "FAILED_CLOSED" and prior["new_actual_deepseek_calls"] == 2, "partial execution state drift")
    require(prior["historical_deepseek_calls_preserved"] == 9 and prior["total_unique_inferred_batches"] == 11, "inference accounting drift")
    require(prior["pass_a_completed_batches"] == 8 and prior["pass_b_completed_batches"] == 2, "completed batch accounting drift")
    require(prior["never_inferred_pass_b_batches_after_stop"] == [4, 5, 6, 7, 8], "never-inferred set drift")
    require(all(sha(FAILED_314B / name) == checksum for name, checksum in prior["aggregate_components"]), "partial failure component drift")
    require(digest(prior["aggregate_components"]) == prior["partial_continuation_sha256"], "partial failure aggregate drift")
    root_pairs = [[path.name, sha(path)] for path in sorted(FAILED_314B.iterdir()) if path.is_file() and path.name != "search_plan_v24_dev_alpha3_14b_sha256"]
    require(digest(root_pairs) == EXPECTED_314B_ROOT == (FAILED_314B / "search_plan_v24_dev_alpha3_14b_sha256").read_text().strip(), "authoritative alpha3.14b root drift")
    revised = load(AMENDMENT / "revised_harmonized_review_protocol.json")
    require(digest(revised["aggregate_components"]) == EXPECTED_PROTOCOL_V2 == revised["harmonized_neutral_review_protocol_v2_sha256"], "authoritative protocol V2 root drift")
    require((AMENDMENT / "revised_harmonized_review_protocol_sha256").read_text().strip() == EXPECTED_PROTOCOL_V2, "protocol V2 sidecar drift")
    # Validate protocol components, but never open or parse the hidden arm map.
    replacements = set(revised["replacement_components"])
    require(all(sha((AMENDMENT if name in replacements else SOURCE) / name) == checksum for name, checksum in revised["aggregate_components"]), "protocol component drift")
    pre_313 = inventory(FAILED_313)
    pre_314b = inventory(FAILED_314B)
    raw_path = FAILED_314B / "raw_responses/pass_b_batch_03.json"
    failure = load(FAILED_314B / "failures/pass_b_batch_03.json")
    require(failure["status"] == "FAILED_CLOSED" and failure["message"] == "schema enum at $.records[1].relevance_state", "frozen failure changed")
    require(sha(raw_path) == failure["raw_response_sha256"], "failed raw response hash drift")
    envelope = load(raw_path)
    require(envelope["choices"][0]["finish_reason"] == "stop", "provider response incomplete")
    content = envelope["choices"][0]["message"]["content"]
    output = json.loads(content)
    require(set(output) == {"records"} and isinstance(output["records"], list), "response outer shape drift")
    records = output["records"]
    require(len(records) == 10, "batch-3 record count not ten")
    plan = load(SOURCE / "neutral_review_batching_plan.json")
    expected = plan["batch_plan"][2]["unit_ids"]
    returned = [record.get("review_unit_id") if isinstance(record, dict) else None for record in records]
    binding = {"batch3_record_count": len(records), "expected_id_count": len(expected),
               "returned_unique_id_count": len(set(returned)),
               "missing_id_count": len(set(expected) - set(returned)),
               "extra_id_count": len(set(returned) - set(expected)),
               "duplicate_id_count": len(returned) - len(set(returned)),
               "id_set_equal": set(returned) == set(expected),
               "array_order_equal": returned == expected}
    binding["batch3_id_binding_valid"] = (binding["batch3_record_count"] == binding["expected_id_count"]
                                          and binding["duplicate_id_count"] == 0
                                          and binding["missing_id_count"] == 0
                                          and binding["extra_id_count"] == 0
                                          and all(isinstance(identifier, str) and re.fullmatch(r"NRV1_[0-9a-f]{24}", identifier) for identifier in returned))
    schema = load(SOURCE / "neutral_review_output_schema.json")["PASS_B"]
    errors = validate_structure(output, schema)
    relevance_enum_errors = [error for error in errors if error["failure"] == "ENUM" and error["path"].endswith(".relevance_state")]
    other_errors = [error for error in errors if error not in relevance_enum_errors]
    require(relevance_enum_errors and relevance_enum_errors[0]["path"] == "$.records[1].relevance_state", "original first failure not reproduced")
    invalid_record = records[1]
    invalid = invalid_record["relevance_state"]
    require(isinstance(invalid, str) and invalid == "WRONG_BIOLOGICAL_UNIT", "failed token not as diagnosed")
    lexemes = re.findall(r'"relevance_state"\s*:\s*("(?:\\.|[^"\\])*")', content)
    require(len(lexemes) == len(records) and json.loads(lexemes[1]) == invalid, "exact raw token lexeme not isolated")
    enum = schema["properties"]["records"]["items"]["properties"]["relevance_state"]["enum"]
    contaminant_enum = schema["properties"]["records"]["items"]["properties"]["contaminant_class"]["enum"]
    historical_schema = load(SOURCE / "historical_review_label_schema.json")
    historical_enum = historical_schema["properties"]["relevance_state"]["enum"]
    historical_contaminants = historical_schema["properties"]["contaminant_class"]["enum"]
    require(enum == historical_enum and contaminant_enum == historical_contaminants, "current/historical enum drift")
    frozen_prompt = load(FAILED_313 / "requests/pass_b_batch_03.json")["messages"][0]["content"]
    prompt_contract = frozen_prompt.split("--- PASS B PACKETS ---", 1)[0]
    require(len(frozen_prompt.split("--- PASS B PACKETS ---")) == 2, "frozen prompt boundary not unique")
    embedded_schema = prompt_contract.split("--- RESPONSE SCHEMA ---\n", 1)[1].rstrip()
    require(json.loads(embedded_schema) == schema, "prompt's embedded schema differs from machine schema")
    require(invalid not in prompt_contract, "invalid token explicitly allowed by prompt; needs different classification")
    require("wrong_biological_unit" in prompt_contract and "WRONG_ENTITY" in prompt_contract, "expected field-specific label spellings absent")
    source_metrics = load(ROOT / "runs/20260915_search_plan_v23_beta_protocol_freeze_offline/metrics_spec_v2.json")
    require(source_metrics["categorical_mappings"]["relevance_state"] == enum, "historical metrics relevance enum drift")
    require(source_metrics["categorical_mappings"]["contaminant_class"] == contaminant_enum, "historical metrics contaminant enum drift")
    classification = "SEMANTIC_NEAR_ALIAS_REQUIRING_INTERPRETATION"
    RUN.mkdir(parents=True)
    write("partial_alpha3_14b_preservation_audit.json", {"authoritative_alpha3_14b_root_sha256": EXPECTED_314B_ROOT,
                                                         "partial_manifest_sha256": sha(FAILED_314B / "continuation_partial_failure_manifest.json"),
                                                         "pre_autopsy_file_inventory_sha256": digest(pre_314b),
                                                         "historical_alpha3_13_file_inventory_sha256": digest(pre_313),
                                                         "historical_alpha3_13_calls": 9, "new_alpha3_14b_calls": 2,
                                                         "total_unique_batches_inferred": 11,
                                                         "valid_pass_a_batches": 8, "valid_pass_b_batches": 2,
                                                         "schema_invalid_pass_b_batches": 1,
                                                         "never_inferred_pass_b_batches": 5,
                                                         "original_review_artifacts_modified": False})
    write("batch3_raw_response_verification.json", {"raw_response_ref": str(raw_path.relative_to(ROOT)),
                                                    "raw_response_sha256": sha(raw_path),
                                                    "failure_record_sha256": sha(FAILED_314B / "failures/pass_b_batch_03.json"),
                                                    "original_failure_status": "FAILED_CLOSED",
                                                    "original_failure_field_path": "$.records[1].relevance_state",
                                                    "raw_response_preserved_unchanged": True})
    write("batch3_identity_binding_audit.json", {"review_unit_id_at_failed_record": invalid_record["review_unit_id"],
                                                "batch3_id_binding_audited": True, **binding})
    write("batch3_schema_failure_inventory.json", {"batch3_record_count": len(records),
                                                   "batch3_schema_failure_count": len(errors),
                                                   "batch3_relevance_state_enum_failure_count": len(relevance_enum_errors),
                                                   "batch3_other_schema_failure_count": len(other_errors),
                                                   "schema_failure_paths_and_categories": errors,
                                                   "scientific_label_distributions_computed": False})
    write("invalid_relevance_state_raw_token.json", {"record_index_zero_based": 1,
                                                    "review_unit_id": invalid_record["review_unit_id"],
                                                    "json_string_lexeme": lexemes[1],
                                                    "raw_model_value": invalid,
                                                    "raw_value_utf8_hex": invalid.encode("utf-8").hex(),
                                                    "unicode_codepoints": [f"U+{ord(c):04X}" for c in invalid],
                                                    "unicode_normalization_unchanged": {form: unicodedata.normalize(form, invalid) == invalid for form in ("NFC", "NFD", "NFKC", "NFKD")},
                                                    "leading_whitespace_count": len(invalid) - len(invalid.lstrip()),
                                                    "trailing_whitespace_count": len(invalid) - len(invalid.rstrip()),
                                                    "case_preserved": True, "punctuation_and_underscore_preserved": True,
                                                    "raw_response_sha256": sha(raw_path)})
    write("frozen_enum_contract.json", {"relevance_state_enum": enum, "contaminant_class_enum": contaminant_enum,
                                       "invalid_token_in_relevance_state_enum": invalid in enum,
                                       "lowercase_form_in_contaminant_class_enum": invalid.lower() in contaminant_enum,
                                       "distinct_machine_output_fields": True,
                                       "source_pass_b_output_schema_sha256": sha(SOURCE / "neutral_review_output_schema.json")})
    write("prompt_vs_schema_consistency_audit.json", {"frozen_request_sha256": sha(FAILED_313 / "requests/pass_b_batch_03.json"),
                                                     "prompt_header_only_inspected": True,
                                                     "embedded_response_schema_matches_frozen_output_schema": True,
                                                     "invalid_token_explicitly_permitted_or_demanded_by_prompt": False,
                                                     "biological_unit_mentioned_as_scientific_dimension": True,
                                                     "lowercase_wrong_biological_unit_appears_only_in_contaminant_enum": True,
                                                     "prompt_schema_contract_mismatch": False,
                                                     "evidence_content_read_for_schema_diagnosis": False})
    write("historical_label_contract_audit.json", {"historical_pass_b_label_schema_sha256": sha(SOURCE / "historical_review_label_schema.json"),
                                                    "historical_contaminant_schema_sha256": sha(SOURCE / "historical_review_contaminant_schema.json"),
                                                    "historical_metrics_spec_sha256": sha(ROOT / "runs/20260915_search_plan_v23_beta_protocol_freeze_offline/metrics_spec_v2.json"),
                                                    "historical_relevance_enum_equals_frozen_enum": True,
                                                    "historical_contaminant_enum_equals_frozen_enum": True,
                                                    "explicit_one_to_one_alias_for_invalid_relevance_token": False,
                                                    "historical_machine_spelling_for_biological_unit_is_contaminant_class_only": True,
                                                    "historical_label_for_this_review_unit_inspected": False})
    write("batch3_failure_classification.json", {"failure_class": classification,
                                                 "classification_scope": "original first invalid relevance_state token only",
                                                 "batch_has_additional_schema_failures": len(errors) > 1,
                                                 "pure_representational_format_only": False,
                                                 "prompt_schema_contract_mismatch": False,
                                                 "explicit_historical_alias": False,
                                                 "novel_machine_relevance_token": True,
                                                 "reason": "The invalid uppercase token is not in the relevance_state enum. The similar lowercase spelling belongs to contaminant_class, a different output axis. No frozen one-to-one relevance_state alias is defined; choosing a permitted relevance label would require scientific interpretation.",
                                                 "automatic_salvage_allowed": False})
    write("batch3_other_fields_schema_audit.json", {"record_count": 10, "required_field_failures": 0,
                                                    "extra_prohibited_field_failures": 0,
                                                    "non_relevance_field_schema_failures": len(other_errors),
                                                    "all_non_relevance_fields_schema_valid": len(other_errors) == 0,
                                                    "other_relevance_state_schema_failures": len(relevance_enum_errors) - 1,
                                                    "schema_failure_inventory_ref": "batch3_schema_failure_inventory.json"})
    write("scientific_semantics_preservation_audit.json", {"raw_provider_response_modified": False,
                                                           "scientific_fields_modified": False,
                                                           "normalization_attempted": False,
                                                           "deterministic_semantics_preserving_mapping_established": False,
                                                           "scientific_interpretation_required_for_normalization": True,
                                                           "evidence_content_read_for_schema_diagnosis": False})
    write("post_failure_schema_amendment_disclosure.json", {"diagnostic_classification": "POST_FAILURE_SCHEMA_FAILURE_AUTOPSY",
                                                           "original_schema_failure_preserved": True,
                                                           "validation_contract_amended": False,
                                                           "post_failure_schema_protocol_amendment_created": False,
                                                           "preregistered_before_first_11_calls": False,
                                                           "review_enum_normalization_v1_contract_created": False,
                                                           "harmonized_review_output_validation_protocol_v3_created": False,
                                                           "reason": "No safe deterministic one-to-one mapping exists in the frozen authorities."})
    write("batch3_reuse_eligibility.json", {"batch3_id_binding_valid": binding["batch3_id_binding_valid"],
                                           "all_other_schema_fields_valid": len(other_errors) == 0,
                                           "allowed_deterministic_unique_mapping": False,
                                           "scientific_interpretation_unnecessary": False,
                                           "scientific_field_meaning_unchanged_if_mapped": "NOT_ESTABLISHED",
                                           "PASS_B_BATCH3_REUSABLE_WITHOUT_REINFERENCE": False,
                                           "deepseek_reinference_calls_in_alpha3_14c": 0})
    write("remaining_call_budget.json", {"historical_alpha3_13_calls": 9, "alpha3_14b_new_calls": 2,
                                        "total_unique_batches_already_inferred": 11,
                                        "valid_batches_before_alpha314c": 10,
                                        "schema_invalid_batches_before_alpha314c": 1,
                                        "never_inferred_batches": 5,
                                        "future_deepseek_calls_if_reusable": 5,
                                        "future_deepseek_calls_if_reinference_chosen": 6,
                                        "batch3_reinference_not_authorized_here": True,
                                        "remaining_five_calls_not_authorized_here": True,
                                        "decision_options": ["AUTHORIZE_ONE_EXPLICIT_BATCH3_REPLACEMENT_PLUS_FIVE_NEVER_INFERRED", "TERMINATE_HARMONIZED_REVIEW_INCOMPLETE"]})
    write("arm_firewall_audit.json", {"arm_map_accessed": False,
                                     "hidden_arm_map_loaded_or_parsed": False,
                                     "historical_unit_label_accessed": False,
                                     "review_unit_id_only_identity_inspection": True})
    write("metrics_nonexecution_audit.json", {"metrics_computed": False, "direct_rates_computed": False,
                                              "scientific_label_distributions_computed": False,
                                              "arm_level_metrics_computed": False,
                                              "identity_join_performed": False})
    require(inventory(FAILED_313) == pre_313 and inventory(FAILED_314B) == pre_314b, "historical execution changed")
    write("scientific_state_safety_audit.json", {"historical_review_artifacts_modified": False,
                                                "provider_raw_response_modified": False,
                                                "scientific_label_changed": False,
                                                "paper_evidence_or_target_content_inspected": False,
                                                "arm_map_accessed": False, "metrics_computed": False,
                                                "deepseek_calls": 0, "openai_calls": 0, "llm_calls": 0,
                                                "network_calls": 0, "retrieval_calls": 0})
    write("validation.json", {"status": "PASS", "batch3_id_binding_audited": True,
                              "batch3_id_binding_valid": binding["batch3_id_binding_valid"],
                              "exact_invalid_token_frozen": True, "failure_classified": True,
                              "batch3_schema_failure_count": len(errors),
                              "batch3_relevance_state_enum_failure_count": len(relevance_enum_errors),
                              "batch3_other_schema_failure_count": len(other_errors),
                              "deterministic_normalization_defined": False,
                              "pass_b_batch3_reusable_without_reinference": False,
                              "evidence_content_read_for_schema_diagnosis": False,
                              "arm_map_accessed": False, "metrics_computed": False,
                              "historical_review_artifacts_modified": False,
                              "deepseek_calls": 0, "openai_calls": 0, "llm_calls": 0,
                              "network_calls": 0, "retrieval_calls": 0})
    write("summary.json", {"status": "completed", "failure_class": classification,
                           "batch3_record_count": len(records),
                           "batch3_id_binding_valid": binding["batch3_id_binding_valid"],
                           "batch3_schema_failure_count": len(errors),
                           "batch3_relevance_state_enum_failure_count": len(relevance_enum_errors),
                           "batch3_other_schema_failure_count": len(other_errors),
                           "pass_b_batch3_reusable_without_reinference": False,
                           "harmonized_review_output_validation_protocol_v3_sha256": None,
                           "next_stage_recommendation": "DECIDE_BATCH3_REINFERENCE_AND_REMAINING_5_BATCHES",
                           "historical_assets_modified": False,
                           "deepseek_calls": 0, "openai_calls": 0, "llm_calls": 0,
                           "network_calls": 0, "retrieval_calls": 0})
    pairs = [[path.name, sha(path)] for path in sorted(RUN.iterdir()) if path.is_file()]
    root = digest(pairs)
    (RUN / "search_plan_v24_dev_alpha3_14c_sha256").write_text(root + "\n", encoding="utf-8")
    require(inventory(FAILED_313) == pre_313 and inventory(FAILED_314B) == pre_314b, "historical execution changed after root freeze")
    print(f"alpha3.14c={root} class={classification} batch3_reusable=false schema_failures={len(errors)}")


if __name__ == "__main__":
    main()
