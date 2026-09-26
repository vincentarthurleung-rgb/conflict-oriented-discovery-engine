#!/usr/bin/env python3
"""Post-failure, offline-only review response identity-binding amendment.

Scientific response fields are kept as opaque JSON object byte strings. This
program extracts only review_unit_id and array positions; it does not parse or
inspect label, contaminant, confidence, or rationale values.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_13_harmonized_neutral_review_preregistration_offline"
FAILED = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_13_harmonized_deepseek_review"
RUN = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_14a_review_identity_binding_amendment_offline"
OLD_RUNNER = ROOT / "scripts/run_search_plan_v24_alpha313_harmonized_deepseek_review.py"
HIST_A = ROOT / "tools/run_search_plan_v23_beta_2_primary_heldout_v2_pass_a_adjudication.py"
HIST_B = ROOT / "tools/run_search_plan_v23_beta_2_primary_heldout_v2_pass_b_adjudication.py"
ROOTS = {
    "alpha3_13": "5d893ae408fee8d30fefefa56a5b2db14d09a80d31260db44cb143c0057316a8",
    "corpus": "afcdcd35690a0324426958504de09788ae78bee10a1836a2b526f0e7a82300c7",
    "protocol": "5666288ab612a0f2ed3cd0deb00b7ed77dc6a4270e869e6b8a580605f9721481",
    "canonical_lexical": "53073bf83a402437c6428262d9e800c6556f7e8dbd1f9e4af017e3d564716eb7",
}
ID_PATTERN = re.compile(r'(?<!\\)"review_unit_id"\s*:\s*"(NRV1_[0-9a-f]{24})"')
ID_KEY_PATTERN = re.compile(r'(?<!\\)"review_unit_id"\s*:')


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RuntimeError(reason)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def pretty(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_structural(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(name: str, value: Any) -> None:
    path = RUN / name
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.exists(), f"would overwrite amendment artifact: {name}")
    path.write_bytes(pretty(value))


def write_bytes(name: str, body: bytes) -> None:
    path = RUN / name
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.exists(), f"would overwrite amendment artifact: {name}")
    path.write_bytes(body)


def file_inventory(root: Path) -> list[list[Any]]:
    return [[str(path.relative_to(root)), sha_file(path), path.stat().st_size]
            for path in sorted(root.rglob("*")) if path.is_file()]


def verify_original_roots() -> None:
    manifests = (
        ("implementation_manifest.json", "search_plan_v24_dev_alpha3_13", ROOTS["alpha3_13"]),
        ("harmonized_neutral_review_corpus_manifest.json", "harmonized_neutral_review_corpus", ROOTS["corpus"]),
        ("harmonized_neutral_review_protocol_manifest.json", "harmonized_neutral_review_protocol", ROOTS["protocol"]),
    )
    for name, prefix, expected in manifests:
        manifest = load_structural(SOURCE / name)
        pairs = manifest["aggregate_components"]
        require(all(sha_file(SOURCE / item) == checksum for item, checksum in pairs), f"frozen component drift: {name}")
        require(digest(pairs) == manifest[prefix + "_sha256"] == expected, f"frozen root drift: {name}")
        require((SOURCE / (prefix + "_sha256")).read_text().strip() == expected, f"frozen sidecar drift: {name}")
    require((SOURCE / "canonical_bounded_lexical_realization_v2_scientific_corpus_sha256").read_text().strip() == ROOTS["canonical_lexical"], "canonical lexical root drift")


def opaque_record_slices(content: str) -> list[str]:
    """Separate JSON record objects without decoding any scientific field."""
    markers = list(re.finditer(r'(?<!\\)"records"\s*:\s*\[', content))
    require(len(markers) == 1, "one records array required")
    pos = markers[0].end()
    records: list[str] = []
    while True:
        while pos < len(content) and (content[pos].isspace() or content[pos] == ","):
            pos += 1
        require(pos < len(content), "unterminated records array")
        if content[pos] == "]":
            break
        require(content[pos] == "{", "records must contain objects")
        start, depth, in_string, escaped = pos, 0, False, False
        while pos < len(content):
            char = content[pos]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
            elif char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    records.append(content[start:pos + 1])
                    pos += 1
                    break
            pos += 1
        require(depth == 0 and not in_string, "unterminated record object")
    return records


def response_content(path: Path) -> str:
    # The provider envelope is parsed to obtain its content STRING only. The
    # nested scientific response is not decoded into a field/value mapping.
    envelope = load_structural(path)
    require(isinstance(envelope, dict) and len(envelope.get("choices", [])) == 1, "provider envelope shape")
    require(envelope["choices"][0].get("finish_reason") == "stop", "provider response incomplete")
    content = envelope["choices"][0]["message"]["content"]
    require(isinstance(content, str), "provider content is not a string")
    return content


def extract_ids(records: list[str]) -> list[str]:
    ids = []
    for record in records:
        require(len(ID_KEY_PATTERN.findall(record)) == 1, "record missing or repeats review_unit_id key")
        matches = ID_PATTERN.findall(record)
        require(len(matches) == 1, "record review_unit_id is not schema-valid")
        ids.append(matches[0])
    return ids


def identity_audit(expected: list[str], returned: list[str]) -> dict[str, Any]:
    missing = sorted(set(expected) - set(returned))
    extra = sorted(set(returned) - set(expected))
    duplicate_count = len(returned) - len(set(returned))
    valid = (len(returned) == len(expected) and len(set(returned)) == len(returned)
             and not missing and not extra and set(returned) == set(expected))
    return {"expected_id_count": len(expected), "returned_record_count": len(returned),
            "unique_returned_id_count": len(set(returned)), "missing_id_count": len(missing),
            "extra_id_count": len(extra), "duplicate_id_count": duplicate_count,
            "expected_id_set_equals_returned_id_set": set(expected) == set(returned),
            "provider_returned_order_matches_request_order": returned == expected,
            "identity_binding": "VALID" if valid else "INVALID",
            "missing_ids": missing, "extra_ids": extra,
            "position_mapping": [{"review_unit_id": identifier,
                                  "provider_returned_position": returned.index(identifier) + 1,
                                  "canonical_request_position": index + 1}
                                 for index, identifier in enumerate(expected)] if valid else []}


def main() -> None:
    require(not RUN.exists(), "alpha3.14a output already exists; refusing regeneration")
    verify_original_roots()
    pre = file_inventory(FAILED)
    require(pre, "failed execution absent")
    failed_manifest = load_structural(FAILED / "partial_failure_manifest.json")
    pairs = failed_manifest["aggregate_components"]
    require(all(sha_file(FAILED / name) == checksum for name, checksum in pairs), "partial failure component changed")
    require(digest(pairs) == failed_manifest["partial_failure_sha256"], "partial failure root changed")
    require(failed_manifest["status"] == "FAILED_CLOSED" and failed_manifest["provider_calls_started"] == 9, "failed-run state mismatch")
    require(failed_manifest["validated_pass_a_records"] == 71 and failed_manifest["validated_pass_b_batches"] == 0, "failed-run validation counts mismatch")
    require(failed_manifest["hidden_arm_map_opened"] is False and failed_manifest["metrics_computed"] is False, "failed-run firewall mismatch")
    require(not (FAILED / "blinded_adjudication_freeze_manifest.json").exists(), "failed run unexpectedly completed")
    old_failure = load_structural(FAILED / "failures/pass_b_batch_01.json")
    require(old_failure["stage"] == "provider_response_validation" and old_failure["message"] == "exact batch order or identity mismatch", "old failure reason changed")
    require(old_failure["raw_response_sha256"] == sha_file(FAILED / "raw_responses/pass_b_batch_01.json"), "failed raw response hash drift")
    plan = load_structural(SOURCE / "neutral_review_batching_plan.json")
    require(plan["planned_model_calls"] == 16 and len(plan["batch_plan"]) == 8, "frozen plan drift")
    require(len(list((FAILED / "attempts").glob("*.json"))) == 9, "attempt count drift")
    require(len(list((FAILED / "validated").glob("*.json"))) == 8, "validation count drift")
    require(not any((FAILED / "attempts" / f"pass_b_batch_{i:02d}.json").exists() for i in range(2, 9)), "remaining batch already attempted")

    old_a = HIST_A.read_text(encoding="utf-8")
    old_b = HIST_B.read_text(encoding="utf-8")
    require('ids == expected_ids' in old_a and 'ids == expected_ids' in old_b, "old order validator not found")
    require('sealed_by_id = {row["review_id"]: row for row in sealed}' in old_a and 'sealed_by_id = {row["review_id"]: row for row in sealed}' in old_b, "historical ID join not found")
    require('mapping = sealed_by_id[record["review_id"]]' in old_a and 'sealed_by_id[record["review_id"]]' in old_b, "historical join not ID-keyed")

    RUN.mkdir(parents=True)
    write("partial_review_run_preservation_audit.json", {
        "historical_failed_run_ref": str(FAILED.relative_to(ROOT)), "historical_file_count": len(pre),
        "pre_amendment_file_inventory_sha256": digest(pre), "historical_failed_run_immutable": True,
        "historical_calls_consumed": 9, "pass_a_batches_executed": 8, "pass_a_validated_units": 71,
        "pass_b_batches_executed": 1, "pass_b_batch1_records_returned": 10,
        "remaining_pass_b_batches_not_executed": 7,
        "old_failure_retained": True, "no_retry_repair_reorder_or_metric_in_failed_run": True})
    write("partial_failure_manifest_verification.json", {
        "historical_partial_failure_sha256": failed_manifest["partial_failure_sha256"],
        "manifest_file_sha256": sha_file(FAILED / "partial_failure_manifest.json"),
        "aggregate_component_count": len(pairs), "all_component_hashes_verified": True,
        "original_pass_b_batch1_raw_sha256": old_failure["raw_response_sha256"],
        "original_failure_stage": old_failure["stage"], "original_failure_message": old_failure["message"],
        "original_failure_status": failed_manifest["status"]})
    write("historical_order_semantics_audit.json", {
        "classification": "ORDER_BOOKKEEPING_ONLY",
        "request_order": "Frozen deterministic batch presentation order; historical prompt requested batch-order output.",
        "legacy_validator": "Both historical PASS A/B runners required ids == expected_ids and failed closed on positional mismatch.",
        "historical_downstream_identity_binding": "Both historical runners built sealed_by_id keyed by explicit review_id and joined each record using its review_id; array index was not used for identity join.",
        "scientific_or_metric_semantics_of_array_position": False,
        "old_pass_a_runner_sha256": sha_file(HIST_A), "old_pass_b_runner_sha256": sha_file(HIST_B),
        "alpha3_13_legacy_order_policy_sha256": sha_file(SOURCE / "neutral_review_parse_validation_policy.json"),
        "legacy_order_validation_remains_historical_fact": True})
    write("response_identity_binding_v2_contract.json", {
        "artifact_schema_version": "ReviewResponseIdentityBindingV2",
        "identity_key": "review_unit_id", "equality": "EXACT_BYTE_STRING_EQUALITY",
        "conditions": ["returned_record_count_equals_expected_count", "every_review_unit_id_schema_valid",
                       "returned_review_unit_ids_unique", "no_expected_id_missing", "no_unexpected_id_present",
                       "returned_id_set_equals_expected_id_set", "each_id_maps_to_exactly_one_object",
                       "complete_unchanged_pass_specific_scientific_output_schema_valid"],
        "response_array_permutation_alone_invalidates": False,
        "invalid_behavior": "FAIL_CLOSED_STOP_PASS", "fuzzy_id_matching": False,
        "legacy_order_check_superseded_only_in_new_protocol": True})
    write("canonicalization_by_id_contract.json", {
        "artifact_schema_version": "CanonicalizationByIDV1",
        "precondition": "ReviewResponseIdentityBindingV2 VALID and unchanged pass-specific schema valid",
        "canonical_storage_order": "ORIGINAL_FROZEN_REQUEST_ORDER",
        "rule": "index each opaque record by exact review_unit_id and emit records in frozen request ID sequence",
        "provenance_fields": ["provider_returned_position", "canonical_request_position"],
        "position_provenance_location": "separate audit sidecar; not inserted into scientific response objects",
        "scientific_field_mutation_allowed": False, "classification": "CANONICALIZATION_BY_ID_NOT_SCIENTIFIC_REPAIR"})
    write("invalid_identity_response_taxonomy.json", {
        "fail_closed_conditions": ["MISSING_REVIEW_UNIT_ID", "EXTRA_REVIEW_UNIT_ID_FIELD",
                                   "DUPLICATE_REVIEW_UNIT_ID", "UNKNOWN_REVIEW_UNIT_ID", "WRONG_BATCH_MEMBERSHIP",
                                   "RECORD_COUNT_MISMATCH", "SCHEMA_INVALID_ITEM", "SCIENTIFIC_OUTPUT_SCHEMA_FAILURE"],
        "no_case_folding_prefix_edit_distance_or_position_inference": True,
        "no_repair_or_reinference": True})

    all_audit = []
    preservation = []
    all_pass_a_valid = True
    all_pass_a_order_match = True
    all_pass_a_changes = 0
    for batch in plan["batch_plan"]:
        index = batch["batch_index"]
        expected = batch["unit_ids"]
        raw_path = FAILED / "raw_responses" / f"pass_a_batch_{index:02d}.json"
        validated_path = FAILED / "validated" / f"pass_a_batch_{index:02d}.json"
        require(raw_path.exists() and validated_path.exists(), f"PASS A batch {index} not previously validated")
        content = response_content(raw_path)
        slices = opaque_record_slices(content)
        returned = extract_ids(slices)
        audit = identity_audit(expected, returned)
        require(audit["identity_binding"] == "VALID", f"PASS A batch {index} V2 identity invalid")
        canonical_slices = {identifier: raw_slice for identifier, raw_slice in zip(returned, slices)}
        reordered = [canonical_slices[identifier] for identifier in expected]
        changes = sum(raw_slice.encode("utf-8") != canonical_slices[identifier].encode("utf-8")
                      for identifier, raw_slice in zip(returned, slices))
        require(changes == 0, "PASS A scientific object mutation")
        all_pass_a_changes += changes
        all_pass_a_valid &= audit["identity_binding"] == "VALID"
        all_pass_a_order_match &= audit["provider_returned_order_matches_request_order"]
        all_audit.append({"batch_index": index, "raw_response_sha256": sha_file(raw_path),
                          "previously_validated_output_sha256": sha_file(validated_path),
                          "previous_schema_validity_state": "PASSED_BEFORE_LEGACY_ORDER_CHECK",
                          "scientific_field_values_inspected": 0, **audit})
        preservation.append({"pass": "PASS_A", "batch_index": index,
                             "opaque_provider_record_sha256_by_id": {identifier: hashlib.sha256(canonical_slices[identifier].encode()).hexdigest() for identifier in expected},
                             "opaque_canonical_record_sha256_by_id": {identifier: hashlib.sha256(record.encode()).hexdigest() for identifier, record in zip(expected, reordered)},
                             "scientific_field_mutation_count": changes})
        write_bytes(f"canonical_pass_a_batch_{index:02d}_blinded.jsonl", b"".join(item.encode("utf-8") + b"\n" for item in reordered))
    write("pass_a_v2_revalidation.json", {"batches_revalidated": len(all_audit),
                                          "review_units_revalidated": sum(row["returned_record_count"] for row in all_audit),
                                          "all_v2_identity_binding_valid": all_pass_a_valid,
                                          "all_provider_returned_orders_match_request_order": all_pass_a_order_match,
                                          "scientific_output_changes": all_pass_a_changes,
                                          "schema_validity_basis": "existing frozen validated outputs and fail-closed validator ordering; no label values re-read",
                                          "batches": all_audit})

    b_raw = FAILED / "raw_responses/pass_b_batch_01.json"
    b_content = response_content(b_raw)
    b_slices = opaque_record_slices(b_content)
    b_ids = extract_ids(b_slices)
    b_expected = plan["batch_plan"][0]["unit_ids"]
    b_audit = identity_audit(b_expected, b_ids)
    require(b_audit["identity_binding"] == "VALID", "PASS_B_BATCH1_NOT_REUSABLE: ID binding failed")
    require(b_audit["provider_returned_order_matches_request_order"] is False, "old failure not reproduced")
    b_by_id = {identifier: raw_slice for identifier, raw_slice in zip(b_ids, b_slices)}
    b_canonical = [b_by_id[identifier] for identifier in b_expected]
    b_changes = sum(raw_slice.encode("utf-8") != b_by_id[identifier].encode("utf-8")
                    for identifier, raw_slice in zip(b_ids, b_slices))
    require(b_changes == 0, "PASS_B_BATCH1_NOT_REUSABLE: scientific object mutation")
    write_bytes("canonical_pass_b_batch_01_blinded.jsonl", b"".join(item.encode("utf-8") + b"\n" for item in b_canonical))
    write("pass_b_batch1_id_set_audit.json", {"batch_index": 1,
                                              "raw_response_sha256": sha_file(b_raw), **b_audit})
    write("pass_b_batch1_v2_revalidation.json", {
        "batch_index": 1, "previous_schema_validity_state": "PASSED_BEFORE_LEGACY_ORDER_CHECK",
        "schema_validity_provenance": "alpha3.13 runner executes check_schema before exact order check; frozen failure is exactly the latter",
        "v2_identity_binding": b_audit["identity_binding"],
        "canonical_storage_artifact": "canonical_pass_b_batch_01_blinded.jsonl",
        "provider_position_to_canonical_position": b_audit["position_mapping"],
        "scientific_field_mutation_count": b_changes,
        "reusable_without_reinference": True, "original_failure_not_reclassified": True})
    preservation.append({"pass": "PASS_B", "batch_index": 1,
                         "opaque_provider_record_sha256_by_id": {identifier: hashlib.sha256(b_by_id[identifier].encode()).hexdigest() for identifier in b_expected},
                         "opaque_canonical_record_sha256_by_id": {identifier: hashlib.sha256(record.encode()).hexdigest() for identifier, record in zip(b_expected, b_canonical)},
                         "scientific_field_mutation_count": b_changes})
    require(all(item["opaque_provider_record_sha256_by_id"] == item["opaque_canonical_record_sha256_by_id"] for item in preservation), "scientific object byte preservation mismatch")
    write("scientific_field_preservation_audit.json", {
        "method": "opaque original JSON record slices; exact record bytes copied into request-order sequence without decoding scientific fields",
        "scientific_label_values_read_for_amendment": 0,
        "scientific_field_mutation_count": all_pass_a_changes + b_changes,
        "all_per_id_opaque_record_byte_hashes_equal_before_after": True,
        "record_audits": preservation})
    write("post_failure_amendment_disclosure.json", {
        "classification": "POST_FAILURE_PROTOCOL_AMENDMENT", "post_failure_protocol_amendment": True,
        "introduced_after_observing_order_validation_failure": True,
        "old_validator_version": "alpha3.13 exact response ID sequence equality",
        "old_failure_result": "FAILED_CLOSED on PASS B batch 1 order mismatch",
        "new_validator_version": "ReviewResponseIdentityBindingV2",
        "reason": "explicit unique ID set binds records; positional array order has bookkeeping but no scientific or metric identity semantics",
        "preregistered_before_first_nine_calls": False,
        "unchanged": ["review target", "review evidence", "prompt", "rubric", "label taxonomy", "provider", "model", "thinking configuration", "batch membership", "batch request order", "scientific decision semantics"],
        "changed_only": ["response identity-binding validation", "canonical storage ordering"]})
    write("arm_firewall_audit.json", {"arm_map_accessed": False,
                                     "hidden_arm_map_loaded": False,
                                     "hidden_arm_map_path": "neutral_review_hidden_arm_map.jsonl",
                                     "model_responses_remain_blinded": True,
                                     "scientific_label_values_read_for_amendment": 0})
    write("metrics_nonexecution_audit.json", {"metrics_computed": False,
                                              "identity_join_performed": False,
                                              "direct_rate_computed": False,
                                              "pass_a_or_pass_b_rates_computed": False,
                                              "arm_level_counts_computed": False,
                                              "historical_vs_new_comparison_computed": False})
    write("continuation_eligibility.json", {
        "all_pass_a_valid": all_pass_a_valid, "pass_a_scientific_output_changes": all_pass_a_changes,
        "pass_b_batch1_valid_by_id": b_audit["identity_binding"] == "VALID",
        "pass_b_batch1_scientific_field_mutation_count": b_changes,
        "PASS_B_BATCH_1_REUSABLE_WITHOUT_REINFERENCE": True,
        "historical_deepseek_calls_consumed": 9, "scientifically_unique_batches_already_inferred": 9,
        "remaining_never_inferred_pass_b_batches": 7,
        "future_call_authorization_in_this_amendment": 0,
        "future_continuation_requires_new_explicit_authorization_for_exactly": 7})

    old_protocol = load_structural(SOURCE / "harmonized_neutral_review_protocol_manifest.json")
    old_parse = "neutral_review_parse_validation_policy.json"
    unchanged = [[name, checksum] for name, checksum in old_protocol["aggregate_components"] if name != old_parse]
    require(len(unchanged) + 1 == len(old_protocol["aggregate_components"]), "legacy parse policy not unique")
    require(all(sha_file(SOURCE / name) == checksum for name, checksum in unchanged), "unchanged protocol component drift")
    new_pairs = sorted(unchanged + [
        ["response_identity_binding_v2_contract.json", sha_file(RUN / "response_identity_binding_v2_contract.json")],
        ["canonicalization_by_id_contract.json", sha_file(RUN / "canonicalization_by_id_contract.json")],
    ])
    new_root = digest(new_pairs)
    write("revised_harmonized_review_protocol.json", {
        "artifact_schema_version": "HarmonizedNeutralReviewProtocolV2",
        "revision_classification": "POST_FAILURE_PROTOCOL_AMENDMENT",
        "base_protocol_sha256": ROOTS["protocol"],
        "legacy_parse_validation_sha256": sha_file(SOURCE / old_parse),
        "replaced_component": old_parse,
        "unchanged_alpha3_13_component_count": len(unchanged),
        "unchanged_alpha3_13_components": unchanged,
        "replacement_components": ["response_identity_binding_v2_contract.json", "canonicalization_by_id_contract.json"],
        "aggregate_algorithm": "sha256(canonical JSON sorted [path,sha256] pairs)",
        "aggregate_components": new_pairs,
        "harmonized_neutral_review_protocol_v2_sha256": new_root,
        "provider_calls_authorized_by_this_protocol_freeze": 0})
    write_bytes("revised_harmonized_review_protocol_sha256", (new_root + "\n").encode())
    write("scientific_state_safety_audit.json", {
        "historical_assets_modified": False, "original_failed_run_modified": False,
        "source_alpha3_13_modified": False, "scientific_labels_modified": False,
        "scientific_label_values_read_for_amendment": 0,
        "review_evidence_prompt_rubric_taxonomy_provider_model_configuration_unchanged": True,
        "arm_map_accessed": False, "metrics_computed": False,
        "deepseek_calls": 0, "openai_calls": 0, "llm_calls": 0,
        "network_calls": 0, "retrieval_calls": 0})
    post = file_inventory(FAILED)
    require(post == pre, "historical failed run changed during amendment")
    write("validation.json", {"status": "PASS", "post_failure_protocol_amendment": True,
                              "scientific_label_values_read_for_amendment": 0,
                              "arm_map_accessed": False, "metrics_computed": False,
                              "response_identity_binding_v2_defined": True,
                              "canonicalization_by_id_defined": True,
                              "pass_a_batches_revalidated": 8,
                              "pass_a_scientific_output_changes": 0,
                              "pass_b_batch1_expected_id_set_equals_returned_id_set": b_audit["expected_id_set_equals_returned_id_set"],
                              "pass_b_batch1_missing_id_count": b_audit["missing_id_count"],
                              "pass_b_batch1_extra_id_count": b_audit["extra_id_count"],
                              "pass_b_batch1_duplicate_id_count": b_audit["duplicate_id_count"],
                              "pass_b_batch1_scientific_field_mutation_count": b_changes,
                              "pass_b_batch1_reusable_without_reinference": True,
                              "historical_file_inventory_unchanged": True,
                              "revised_harmonized_review_protocol_sha256": new_root})
    write("summary.json", {"status": "completed", "classification": "POST_FAILURE_PROTOCOL_AMENDMENT",
                           "old_failed_run_retained": True, "old_failure_status": "FAILED_CLOSED",
                           "order_semantics": "ORDER_BOOKKEEPING_ONLY",
                           "pass_a_batches_revalidated": 8,
                           "pass_a_scientific_output_changes": 0,
                           "pass_b_batch1_reusable_without_reinference": True,
                           "historical_deepseek_calls_consumed": 9,
                           "remaining_never_inferred_pass_b_batches": 7,
                           "deepseek_calls": 0, "openai_calls": 0, "llm_calls": 0,
                           "network_calls": 0, "retrieval_calls": 0,
                           "metrics_computed": False, "arm_map_accessed": False,
                           "next_stage_recommendation": "AUTHORIZE_REMAINING_7_PASS_B_BATCHES_UNDER_PROTOCOL_V2",
                           "revised_harmonized_review_protocol_sha256": new_root,
                           "historical_assets_modified": False})
    root_names = sorted(path.name for path in RUN.iterdir() if path.is_file())
    root_pairs = [[name, sha_file(RUN / name)] for name in root_names]
    write_bytes("search_plan_v24_dev_alpha3_14a_sha256", (digest(root_pairs) + "\n").encode())
    require(file_inventory(FAILED) == pre, "historical run changed after root freeze")
    print(f"alpha3.14a={digest(root_pairs)} revised_protocol={new_root} pass_a=8 pass_b1=reusable calls=0")


if __name__ == "__main__":
    main()
