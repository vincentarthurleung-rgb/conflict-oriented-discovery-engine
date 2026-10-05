#!/usr/bin/env python3
"""Offline, non-scientific audit of the frozen alpha3.20E1 invalid response."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path

from scripts import run_search_plan_v24_alpha320e1_semantic_adjudication_execution as e1


ROOT = Path(__file__).resolve().parents[1]
E = e1.E
E1 = e1.OUT
OUT = ROOT / "runs/20261003_search_plan_v24_dev_alpha3_20e11_incomplete_semantic_response_audit_offline"
ROOT_MARKER = "search_plan_v24_dev_alpha3_20e11_sha256"
E1_ROOT = "e1cfd1ccb098d85a779abf52ed991c76268b501f84e8b057c4bfb469ea7f7253"
INVALID_RAW_SHA = "b285286c07444b5c9d73d3439756d71d390065d9aa8d56018e438c09e806cb10"
INVALID_GROUP = "sg_e515ee2e6d9377fd5079daef1a934e70"
CLASSIFICATION = "SEMANTIC_RESPONSE_MODEL_SERIALIZATION_NONCONFORMANCE"
REPLICATION = "FULL_BLINDED_REPLICATION_PROTOCOL_ALLOWED"
NEXT = "PREREGISTER_ALPHA3_20E1R_FULL_BLINDED_SEMANTIC_REPLICATION"


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RuntimeError(reason)


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_bytes())


def put(name: str, value: object) -> None:
    path = OUT / name
    with path.open("xb") as handle:
        handle.write(canonical(value) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())


def structural_scan(content: str) -> dict:
    """Return only JSON punctuation facts; never expose string values."""
    in_string = False
    escape = False
    stack: list[tuple[str, int]] = []
    trailing_commas = []
    mismatched_closers = []
    for pos, char in enumerate(content):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "{[":
            stack.append((char, pos))
        elif char in "}]":
            if not stack or stack[-1][0] != ({"}": "{", "]": "["}[char]):
                mismatched_closers.append({"position": pos, "type": char})
            else:
                stack.pop()
        elif char == ",":
            following = pos + 1
            while following < len(content) and content[following].isspace():
                following += 1
            if following < len(content) and content[following] in "}]":
                trailing_commas.append({"position": pos,
                                        "next_closer": content[following]})
    return {"trailing_commas_outside_strings": trailing_commas,
            "unclosed_structures": [{"type": kind, "position": pos}
                                    for kind, pos in stack],
            "mismatched_closers": mismatched_closers,
            "unterminated_string": in_string,
            "markdown_fence_count": content.count("```"),
            "leading_nonjson_prose": not content.lstrip().startswith("{"),
            "trailing_nonjson_prose": not content.rstrip().endswith("}"),
            "top_level_object_prefix": content.lstrip().startswith("{"),
            "content_character_count": len(content)}


def independent_strict_json(content: str) -> dict:
    # Node's JSON.parse is independent of the production Python json.loads path.
    program = ("let s='';process.stdin.on('data',x=>s+=x);"
               "process.stdin.on('end',()=>{try{JSON.parse(s);"
               "console.log(JSON.stringify({valid:true}))}catch(e){"
               "console.log(JSON.stringify({valid:false,name:e.name,"
               "message:e.message}))}})")
    result = subprocess.run(["node", "-e", program], input=content.encode("utf-8"),
                            capture_output=True, check=True, timeout=10)
    return {"implementation": "Node.js JSON.parse", **json.loads(result.stdout)}


def diagnostic_transformations(content: str, scan: dict) -> dict:
    """Parseability only, in memory; no changed response is persisted."""
    commas = [row["position"] for row in scan["trailing_commas_outside_strings"]]
    without_commas = content
    for pos in reversed(commas):
        without_commas = without_commas[:pos] + without_commas[pos + 1:]

    def parseable(value: str) -> bool:
        try:
            json.loads(value)
        except json.JSONDecodeError:
            return False
        return True

    # The last array closer is located by the frozen raw syntax; this is only
    # a diagnostic and is never sent to the adjudication validator.
    final_array_close = content.rfind("]")
    inserted_brace = (content[:final_array_close] + "}" +
                      content[final_array_close:])
    final_array_close_without_commas = without_commas.rfind("]")
    combined = (without_commas[:final_array_close_without_commas] + "}" +
                without_commas[final_array_close_without_commas:])
    return {
        "markdown_fence_removal_alone_applicable": "```" in content,
        "leading_or_trailing_prose_removal_alone_applicable":
            scan["leading_nonjson_prose"] or scan["trailing_nonjson_prose"],
        "remove_trailing_commas_only_parseable": parseable(without_commas),
        "insert_missing_object_closer_only_parseable": parseable(inserted_brace),
        "remove_two_trailing_commas_and_insert_object_closer_parseable":
            len(commas) == 2 and parseable(combined),
        "unescaped_quote_correction_indicated": False,
        "missing_bracket_correction_indicated": False,
        "json_substring_extraction_authorized": False,
        "diagnostic_only_no_modified_content_persisted": True,
        "diagnostic_parseability_does_not_change_e1_validity": True,
    }


def run() -> None:
    require(not OUT.exists(), "E11_OUTPUT_ALREADY_EXISTS")
    require((E1 / e1.ROOT_MARKER).read_text().strip() == E1_ROOT
            and e1.e.d.c.root_hash(E1, e1.ROOT_MARKER) == E1_ROOT,
            "E1_ROOT_MISMATCH")
    require((E / "search_plan_v24_dev_alpha3_20e_sha256").read_text().strip()
            == e1.E_ROOT and e1.e.d.c.root_hash(E,
                "search_plan_v24_dev_alpha3_20e_sha256") == e1.E_ROOT,
            "E_ROOT_MISMATCH")
    frozen = (("semantic_adjudication_request_manifest.jsonl", e1.REQUEST_SHA),
              ("development_semantic_fidelity_rubric_v1.json", e1.RUBRIC_SHA),
              ("development_semantic_adjudication_response_envelope_v1.json",
               e1.ENVELOPE_SHA),
              ("semantic_adjudication_prompt_template.txt", e1.PROMPT_SHA))
    require(all(digest(E / name) == expected for name, expected in frozen),
            "FINAL_INTERFACE_BINDING_MISMATCH")
    historical = load(E1 / "validation.json")
    require(historical["alpha3_20e1_classification"] ==
            "SEMANTIC_ADJUDICATION_EXECUTED_WITH_INCOMPLETE_VALID_RESPONSE_SET"
            and historical["semantic_scientific_inference_events"] == 28
            and historical["valid_semantic_group_count"] == 27
            and historical["invalid_semantic_group_count"] == 1
            and historical["valid_candidate_judgment_set_count"] == 81
            and historical["provider_execution_ambiguous_count"] == 0
            and historical["unblinding_performed"] is False,
            "E1_HISTORICAL_STATE_MISMATCH")
    validity = load(E1 / "validation_events/12.json")
    terminal = load(E1 / "terminal_events/12.json")
    transport = load(E1 / "transport_events/12.json")
    raw_path = E1 / "raw_provider_response_bytes/12.bin"
    require(digest(raw_path) == INVALID_RAW_SHA
            and transport["raw_response_sha256"] == INVALID_RAW_SHA
            and validity["blinded_group_token"] == INVALID_GROUP
            and validity["reason"] == "SEMANTIC_RESPONSE_MALFORMED_JSON"
            and terminal["terminal_state"] == "COMPLETED_SEMANTIC_RESPONSE_INVALID"
            and terminal["scientific_inference_occurrence"] == "YES",
            "INVALID_GROUP_BINDING_MISMATCH")
    provider_envelope = json.loads(raw_path.read_bytes())
    require(len(provider_envelope["choices"]) == 1,
            "PROVIDER_ENVELOPE_CHOICES_MISMATCH")
    choice = provider_envelope["choices"][0]
    content = choice["message"]["content"]
    require(choice["finish_reason"] == "stop" and isinstance(content, str),
            "INVALID_RESPONSE_FINISH_MISMATCH")
    request = [json.loads(line) for line in
               (E / "semantic_adjudication_request_manifest.jsonl").read_text().splitlines()][11]
    require(request["future_execution_ordinal"] == 12
            and request["blinded_group_token"] == INVALID_GROUP,
            "FROZEN_REQUEST_IDENTITY_MISMATCH")
    envelope = load(E / "development_semantic_adjudication_response_envelope_v1.json")
    prompt = (E / "semantic_adjudication_prompt_template.txt").read_text()
    require("Return one JSON object" in prompt and "Do not add Markdown" in prompt
            and request["request"]["response_format"] == {"type": "json_object"},
            "FINAL_MODEL_VISIBLE_JSON_AUTHORITY_MISMATCH")
    # Re-enter the exact production validation function without changing bytes.
    parsed, result, diagnostics = e1.validate_response(
        content, choice["finish_reason"],
        request["blinded_candidate_tokens_in_display_order"],
        envelope["model_owned_payload_schema"])
    require(parsed is None and result["reason"] ==
            "SEMANTIC_RESPONSE_MALFORMED_JSON", "PRODUCTION_FAILURE_NOT_REPRODUCED")
    try:
        json.loads(content)
    except json.JSONDecodeError as exc:
        parser_error = {"error_class": type(exc).__name__, "message": exc.msg,
                        "position_zero_based": exc.pos, "line": exc.lineno,
                        "column_one_based": exc.colno}
    else:
        raise RuntimeError("ORIGINAL_RAW_RESPONSE_IS_VALID_JSON")
    independent = independent_strict_json(content)
    require(independent["valid"] is False,
            "INDEPENDENT_JSON_PARSER_DISAGREES")
    scan = structural_scan(content)
    require(len(scan["trailing_commas_outside_strings"]) == 2
            and parser_error["position_zero_based"] == 1200
            and not scan["unterminated_string"],
            "EXPECTED_STRUCTURAL_FAILURE_NOT_FOUND")
    transformations = diagnostic_transformations(content, scan)
    require(transformations[
        "remove_two_trailing_commas_and_insert_object_closer_parseable"],
        "EXPECTED_DIAGNOSTIC_PARSEABILITY_NOT_FOUND")
    token_counts = [content.count(token) for token in
                    request["blinded_candidate_tokens_in_display_order"]]
    criterion_keys = envelope["model_owned_payload_schema"]["properties"][
        "candidate_reviews"]["items"]["properties"]["criteria"]["required"]
    criterion_literal_counts = {name: content.count('"' + name + '"')
                                for name in criterion_keys}
    private_refs = load(E1 / "semantic_private_mapping_preservation_audit.json")[
        "private_mapping_refs"]
    for name, ref in private_refs.items():
        path = E / name
        require(path.is_file() and not path.is_symlink()
                and stat.S_IMODE(path.stat().st_mode) & 0o077 == 0
                and digest(path) == ref["sha256"], "PRIVATE_MAPPING_CHANGED")
    snapshot = {str(path.relative_to(ROOT)): digest(path) for path in
                (E / "search_plan_v24_dev_alpha3_20e_sha256",
                 E / "semantic_adjudication_request_manifest.jsonl",
                 E1 / e1.ROOT_MARKER,
                 E1 / "semantic_raw_judgment_manifest_blinded.jsonl",
                 raw_path)}

    OUT.mkdir()
    put("alpha3_20e1_root_verification.json", {"verified": True,
        "sha256": E1_ROOT, "classification_preserved": historical[
            "alpha3_20e1_classification"]})
    put("alpha3_20e_root_verification.json", {"verified": True,
        "sha256": e1.E_ROOT, "final_authority_only": True})
    put("e1_incomplete_response_set_preservation.json", {
        "historical_semantic_inference_events": 28, "valid_groups": 27,
        "invalid_completed_groups": 1, "valid_blinded_candidate_judgment_sets": 81,
        "technical_retries": 0, "unblinding_performed": False,
        "arm_aggregation_performed": False, "variant_selection_performed": False,
        "classification": historical["alpha3_20e1_classification"]})
    put("invalid_group_12_raw_response_binding.json", {
        "execution_ordinal": 12, "blinded_group_token": INVALID_GROUP,
        "raw_provider_response_sha256": INVALID_RAW_SHA,
        "model_content_sha256": hashlib.sha256(content.encode()).hexdigest(),
        "finish_reason": "stop", "scientific_inference_confirmed": True,
        "request_sha256": request["request_sha256"]})
    put("invalid_group_12_parser_failure_reproduction.json", {
        "production_implementation": "scripts.run_search_plan_v24_alpha320e1_semantic_adjudication_execution",
        "production_entry_point": "validate_response",
        "production_reason": result["reason"], "reproduced": True,
        "underlying_parser": "Python json.loads with duplicate-key hook",
        "underlying_exception": parser_error,
        "raw_provider_response_sha256": INVALID_RAW_SHA,
        "diagnostics_uninterpreted": diagnostics})
    put("final_response_interface_authority_timeline.json", {
        "master_development_identity": "POST_ALPHA3_19_SEEN_DATA_DEVELOPMENT",
        "master_semantic_trigger": "separately preregistered independent development semantic adjudication if needed",
        "alpha3_20b_semantic_trigger": "semantic truth not established by mechanical structure checks",
        "superseded_pre_handoff_snapshot_authority": False,
        "final_alpha3_20e_root_sha256": e1.E_ROOT,
        "final_request_manifest_sha256": e1.REQUEST_SHA,
        "final_prompt_sha256": e1.PROMPT_SHA,
        "final_envelope_sha256": e1.ENVELOPE_SHA,
        "response_format": {"type": "json_object"},
        "final_interface_authority_resolved": True})
    matrix = [
        ("top_level_type", "one JSON object", "object", "one object", "json.loads then schema", "aligned"),
        ("candidate_structure", "candidate_reviews array of exactly three objects", "array length three", "same", "schema min/max 3", "aligned"),
        ("candidate_token", "candidate_token string exactly once per supplied token", "string", "same", "exact set and no duplicates", "aligned"),
        ("criterion_fields", "six named criterion objects", "six required keys", "same", "schema required/additionalProperties false", "aligned"),
        ("rationale", "nonempty string per criterion", "minLength 1 string", "same", "schema minLength 1", "aligned"),
        ("extra_prose", "none; one JSON object", "object payload only", "none", "strict whole-content json.loads", "aligned"),
        ("markdown_fences", "prohibited", "JSON object only", "prohibited", "strict whole-content json.loads", "aligned"),
        ("extra_keys", "no other keys", "additionalProperties false", "same", "schema", "aligned"),
        ("strict_json_syntax", "JSON object", "JSON object", "response_format json_object", "strict json.loads", "aligned"),
        ("duplicate_keys", "each key exactly once", "single declared property each", "no duplicate keys", "object_pairs_hook rejection", "aligned"),
        ("null", "judgments and rationales required", "string/object types, no null", "no null specified", "schema rejects null", "aligned"),
    ]
    put("prompt_envelope_parser_consistency_matrix.json", {
        "rows": [dict(zip(("dimension", "prompt", "envelope", "model_visible_format",
                            "production_parser_validator", "conclusion"), row))
                 for row in matrix], "material_interface_inconsistency_count": 0})
    put("invalid_response_strict_json_diagnostic.json", {
        "original_content_strict_json_valid": False,
        "production_parser_error": parser_error,
        "independent_parser": independent,
        "structural_scan": scan,
        "expected_candidate_token_literal_counts": token_counts,
        "required_criterion_key_literal_counts": criterion_literal_counts,
        "literal_presence_is_not_validity_or_scientific_salvage": True,
        "raw_provider_response_sha256": INVALID_RAW_SHA})
    put("invalid_response_nonmutating_conformance_audit.json", {
        "raw_response_conforms_to_frozen_serialization_contract": False,
        "strict_json_original": False,
        "prompt_required_one_json_object": True,
        "response_envelope_required_object": True,
        "json_object_response_mode_frozen": True,
        "independent_of_production_parser_result": True,
        "scientific_fields_not_interpreted": True})
    put("invalid_response_diagnostic_transformations.json", transformations)
    put("semantic_response_invalidity_primary_classification.json", {
        "classification": CLASSIFICATION,
        "parser_implementation_defect": False,
        "interface_contract_defect": False,
        "model_serialization_nonconformance": True,
        "basis": "original content violates aligned strict JSON contract: two trailing commas and one missing object closer",
        "no_scientific_judgment_interpreted": True})
    put("offline_response_validation_replay_eligibility.json", {
        "eligible": False,
        "reason": "original response requires mutation to parse; production parser correctly rejects it",
        "response_validation_replay_manifest_sha256": None,
        "replay_performed": False})
    put("e1_exact_experiment_completeness.json", {
        "alpha3_20e1_exact_experiment_complete_for_selection": False,
        "required_valid_groups": 28, "actual_valid_groups": 27,
        "selection_rule_weakened": False, "unblinding_allowed": False})
    put("single_group_retry_prohibition.json", {
        "group_12_scientific_retry_performed": False,
        "future_single_group_replacement_authorized": False,
        "e1_completed_group_12_inference_count": 1,
        "reason": "one completed inference per frozen group; no post-hoc replacement"})
    put("e1_semantic_judgment_quarantine_contract.json", {
        "state": "SEEN_DEVELOPMENT_INCOMPLETE_EXPERIMENT_NOT_SELECTION_ELIGIBLE",
        "frozen_valid_blinded_judgment_sets": 81,
        "selection_eligible": False, "mix_with_future_replication": False,
        "historical_provenance_preserved": True})
    put("full_blinded_replication_authority_audit.json", {
        "authority": REPLICATION,
        "interpretation": "new versioned protocol may be preregistered within seen-development master; no calls authorized now",
        "same_complete_28_group_universe_required": True,
        "uniform_fresh_independent_calls_required": True,
        "e1_results_not_mixed_or_reused_for_selection": True,
        "same_scientific_rubric_unless_separately_justified": True,
        "serialization_only_hardening_may_be_considered": True,
        "new_requests_constructed_here": False,
        "new_master_required": False,
        "provider_calls_authorized_here": 0})
    put("future_serialization_hardening_options.json", {
        "adopted_here": [],
        "options_subject_to_separate_offline_freeze": [
            "explicit single-object strict JSON and no trailing commas reminder",
            "schema-constrained response mode only after separately authorized capability verification",
            "controller-owned wrapper simplification without scientific-rubric change"],
        "provider_capability_network_check_performed": False,
        "scientific_rubric_change_authorized": False})
    put("unblinding_nonuse_audit.json", {
        "unblinding_performed": False, "candidate_overall_state_derived": False,
        "arm_aggregation_performed": False,
        "semantic_dominance_evaluated": False,
        "variant_selection_performed": False})
    put("private_mapping_nonuse_audit.json", {
        "private_mapping_existence_permission_and_hash_verified": True,
        "private_mapping_contents_read": False,
        "private_arm_mapping_used_for_comparison": False,
        "private_mapping_hashes_unchanged": True,
        "private_mapping_sha256_by_filename": {name: ref["sha256"]
                                                  for name, ref in private_refs.items()}})
    put("historical_inference_accounting.json", {
        "alpha3_18_builder": 56, "alpha3_18_quality": 1,
        "alpha3_19_builder": 14, "alpha3_19_quality": 0,
        "alpha3_20c_builder_v4_development": 42,
        "alpha3_20e1_semantic_adjudication": 28,
        "alpha3_20e11_new_scientific_inferences": 0,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0})
    put("development_contamination_update.json", {
        "role": "SEEN_DEVELOPMENT_INCOMPLETE_EXPERIMENT_NOT_SELECTION_ELIGIBLE",
        "e1_root_sha256": E1_ROOT, "e1_blinded_judgment_manifest_sha256":
            digest(E1 / "semantic_raw_judgment_manifest_blinded.jsonl"),
        "future_fresh_heldout_reuse_prohibited": True,
        "new_source_or_candidate_added": False})
    require(all(digest(ROOT / path) == value for path, value in snapshot.items()),
            "HISTORICAL_ASSET_CHANGED_DURING_AUDIT")
    put("historical_preservation_audit.json", {
        "before_after_sha256": snapshot,
        "upstream_roots_verified": True,
        "historical_assets_modified": False})
    put("scientific_state_safety_audit.json", {
        "raw_response_repaired": False, "model_judgments_salvaged": False,
        "scientific_judgments_interpreted": False,
        "candidate_overall_state_derived": False,
        "unblinding_performed": False, "variant_selection_performed": False,
        "group_12_retry_performed": False})
    validation = {
        "status": "completed", "alpha3_20e1_root_verified": True,
        "alpha3_20e_root_verified": True, "historical_semantic_inference_events": 28,
        "historical_valid_group_count": 27,
        "historical_invalid_group_count": 1,
        "invalid_group_token": INVALID_GROUP,
        "invalid_raw_response_sha256": INVALID_RAW_SHA,
        "invalid_response_finish_reason": "stop",
        "production_parser_failure_reproduced": True,
        "final_interface_authority_resolved": True,
        "semantic_response_invalidity_primary_classification": CLASSIFICATION,
        "raw_response_conforms_to_frozen_serialization_contract": False,
        "offline_response_validation_replay_eligible": False,
        "alpha3_20e1_exact_experiment_complete_for_selection": False,
        "group_12_scientific_retry_performed": False,
        "full_blinded_replication_authority": REPLICATION,
        "e1_judgments_selection_eligible": False,
        "unblinding_performed": False,
        "private_arm_mapping_used_for_comparison": False,
        "candidate_overall_state_derived": False,
        "arm_aggregation_performed": False,
        "semantic_dominance_evaluated": False,
        "variant_selection_performed": False,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "alpha3_20e1_2_response_validation_replay_manifest_sha256": None,
        "next_stage_recommendation": NEXT,
        "historical_assets_modified": False}
    put("validation.json", validation)
    put("summary.json", {
        "classification": CLASSIFICATION,
        "e1_experiment_selection_complete": False,
        "offline_replay_eligible": False,
        "full_blinded_replication_protocol_allowed": True,
        "next_stage_recommendation": NEXT,
        "status": "completed"})
    root = e1.e.d.c.root_hash(OUT, ROOT_MARKER)
    with (OUT / ROOT_MARKER).open("x", encoding="utf-8") as handle:
        handle.write(root + "\n")
    print(root)


if __name__ == "__main__":
    run()
