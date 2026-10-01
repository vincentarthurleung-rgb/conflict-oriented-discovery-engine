#!/usr/bin/env python3
"""Offline alpha3.18B.1 grounding interface audit and prospective V3 freeze."""
from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from scripts import search_plan_v24_alpha318b_preregister_builder_execution_offline as prior
    from scripts import search_plan_v24_alpha318b_post_builder_prechecks as checks
except ModuleNotFoundError:
    import search_plan_v24_alpha318b_preregister_builder_execution_offline as prior
    import search_plan_v24_alpha318b_post_builder_prechecks as checks

ROOT = prior.ROOT
HISTORY = ROOT / "runs/20261001_search_plan_v24_dev_alpha3_18b_builder_execution"
OUT = ROOT / "runs/20261001_search_plan_v24_dev_alpha3_18b1_grounding_contract_consistency_audit_offline"
ROOT_MARKER = "search_plan_v24_dev_alpha3_18b1_sha256"
HISTORY_SHA = "f8453be85fd86a61df55340867b0b7f4e4c6132731f076a7d3da2f3aa513f83d"
PREREG_SHA = "01a0c81d80d9bffaf59411f45fe7b6880f63a9ed4e3b7c0e61c6e5709b9e3f4b"
MANIFEST_SHA = "58efb5ebc427d28e5677b892d6c395e3e0a52c33c85bc536f662e37ca0715fa6"
OLD_POOL = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17_new_blinded_proposition_pool_preregistration_offline"
BUILDER = prior.BUILDER_DIR
QUALITY = prior.QUALITY_DIR
AMEND = prior.a6.base.prior.AMEND
V3_VERSION = "BuilderGroundingContractV3"
DOCUMENT_CONTRACT_FILES = [
    "source_metadata_contract_v2.json", "construction_evidence_document_v1_contract.json",
    "construction_document_front_matter_policy.json", "construction_document_abstract_policy.json",
    "construction_document_body_policy.json", "construction_document_reference_policy.json",
    "construction_document_other_section_policy.json", "construction_document_canonicalization_contract.json",
    "builder_request_visibility_amendment.json", "proposition_builder_v2_1_user_prompt_template.txt"]
ANCHOR_CONTRACT_FILES = ["evidence_span_anchor_v1_contract.json",
    "evidence_span_granularity_contract.json", "builder_grounding_reference_contract.json"]


def canonical(value: Any) -> bytes:
    return prior.a6.base.canonical(value)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def digest(path: Path) -> str:
    return sha(path.read_bytes())


def ref(path: Path) -> dict[str, str]:
    return {"path": str(path.relative_to(ROOT)), "sha256": digest(path)}


def read(path: Path) -> Any:
    return json.loads(path.read_bytes())


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_bytes().splitlines() if line]


def write(name: str, value: Any) -> None:
    prior.a6.base.write_json(OUT / name, value)


def write_rows(name: str, values: list[dict[str, Any]]) -> None:
    prior.a6.base.write_bytes(OUT / name,
        b"".join(canonical(value) + b"\n" for value in values))


def marker(name: str, value: str) -> None:
    prior.a6.base.write_bytes(OUT / name, (value + "\n").encode("ascii"))


def preflight() -> dict[str, Any]:
    if OUT.exists():
        raise RuntimeError("ALPHA3_18B1_ALREADY_EXISTS_NO_OVERWRITE")
    frozen = prior.preflight()
    if (prior.OUT / prior.ROOT_MARKER).read_text().strip() != PREREG_SHA or (
        prior.a6.base.prior.all_file_root(prior.OUT, prior.ROOT_MARKER) != PREREG_SHA):
        raise RuntimeError("ALPHA3_18B_PREREG_ROOT_MISMATCH")
    if digest(prior.OUT / "alpha3_18b_builder_execution_manifest.json") != MANIFEST_SHA:
        raise RuntimeError("ALPHA3_18B_EXECUTION_MANIFEST_MISMATCH")
    if (HISTORY / "search_plan_v24_dev_alpha3_18b_sha256").read_text().strip() != HISTORY_SHA or (
        prior.a6.base.prior.all_file_root(HISTORY,
            "search_plan_v24_dev_alpha3_18b_sha256") != HISTORY_SHA):
        raise RuntimeError("ALPHA3_18B_HISTORY_ROOT_MISMATCH")
    summary = read(HISTORY / "summary.json")
    raw = rows(HISTORY / "builder_candidate_raw_manifest.jsonl")
    terminal = rows(HISTORY / "builder_source_terminal_states.jsonl")
    grounding = rows(HISTORY / "builder_grounding_reference_audit.jsonl")
    quality_manifest = HISTORY / "proposition_quality_v2_request_manifest.jsonl"
    if (len(raw) != 70 or len(terminal) != 28 or len(grounding) != 70 or
        len(list((HISTORY / "raw_provider_responses").glob("*.json"))) != 28 or
        summary["builder_raw_candidate_count"] != 70 or
        summary["grounding_reference_failures"] != 70 or
        summary["actual_quality_adjudication_call_count"] != 0 or
        any(row["terminal_state"] != "BUILDER_VALID_NONZERO" for row in terminal) or
        quality_manifest.read_bytes() or
        digest(quality_manifest) != (HISTORY /
            "proposition_quality_v2_request_manifest_sha256").read_text().strip()):
        raise RuntimeError("ALPHA3_18B_STRUCTURAL_HISTORY_MISMATCH")
    fields = Counter(row["candidate"]["construction_evidence_span"]["source_field"]
                     for row in raw)
    if fields != {"abstract": 70}:
        raise RuntimeError("CANDIDATE_STRUCTURAL_OBSERVATION_MISMATCH")
    # The audit intentionally never reads neutral_proposition or scientific slots.
    schema_v2 = read(BUILDER / "proposition_builder_output_schema_v2.json")["schema"]
    evidence_v2 = schema_v2["properties"]["candidates"]["items"]["properties"][
        "construction_evidence_span"]
    if (evidence_v2["properties"]["source_field"]["enum"] != ["abstract", "body"] or
        "source_field" not in evidence_v2["required"] or
        evidence_v2["additionalProperties"] is not False):
        raise RuntimeError("BUILDER_V2_SCHEMA_GROUNDING_UNEXPECTED")
    amendment = read(AMEND / "builder_request_visibility_amendment.json")
    body_contract = read(AMEND / "builder_grounding_reference_contract.json")
    document_contract = read(AMEND / "construction_evidence_document_v1_contract.json")
    anchor_contract = read(AMEND / "evidence_span_anchor_v1_contract.json")
    if not (body_contract["prospective_post_validation_body_only_rule"] is True and
        document_contract["body_only_candidate_grounding"] is True and
        anchor_contract["candidate_mapping"].startswith("after BuilderProtocolV2 schema validation, require BODY") and
        amendment["builder_calls_before_amendment"] == 0):
        raise RuntimeError("GROUNDING_AUTHORITY_CONFLICT_UNRESOLVED")
    if prior.a6.base.prior.aggregate(AMEND, DOCUMENT_CONTRACT_FILES) != (
        AMEND / "construction_evidence_document_v1_sha256").read_text().strip() or (
        prior.a6.base.prior.aggregate(AMEND, ANCHOR_CONTRACT_FILES) !=
        (AMEND / "evidence_span_anchor_v1_sha256").read_text().strip()):
        raise RuntimeError("FROZEN_SOURCE_CONTRACT_HASH_MISMATCH")
    if digest(ROOT / "scripts/search_plan_v24_alpha318a1_source_contracts.py") != (
        anchor_contract["implementation_sha256"]):
        raise RuntimeError("GROUNDING_VALIDATOR_IMPLEMENTATION_MISMATCH")
    prompt_v2 = read(BUILDER / "proposition_builder_protocol_v2.json")["system_prompt_utf8"]
    template_v2 = (AMEND / "proposition_builder_v2_1_user_prompt_template.txt").read_text()
    required = amendment["required_additional_instruction"]
    if required in prompt_v2 or required in template_v2:
        raise RuntimeError("PROMPT_DEFECT_NOT_PRESENT")
    return {"frozen": frozen, "raw_count": len(raw), "fields": fields,
        "schema_v2": schema_v2, "prompt_v2": prompt_v2,
        "template_v2": template_v2, "required": required,
        "amendment": amendment, "body_contract": body_contract,
        "document_contract": document_contract, "anchor_contract": anchor_contract}


def v3_schema(v2: dict[str, Any]) -> dict[str, Any]:
    schema = copy.deepcopy(v2)
    span = schema["properties"]["candidates"]["items"]["properties"]["construction_evidence_span"]
    span["properties"]["source_field"]["enum"] = ["body"]
    return schema


def synthetic_cases(v2: dict[str, Any], v3: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    token = "src_" + "a" * 64
    body = "Synthetic intervention decreases synthetic endpoint in cultured cells."
    paragraph = {"section_path": [1], "ordinal": 1, "text": body,
        "start_offset": 0, "end_offset": len(body),
        "span_id": "spanv1_" + checks.source.digest([
            checks.source.SPAN_VERSION, token, [1], 1, checks.source.sha_text(body)])}
    second = "Secondary synthetic paragraph."
    body_text = body + "\n\n" + second
    second_paragraph = {"section_path": [1], "ordinal": 2, "text": second,
        "start_offset": len(body) + 2, "end_offset": len(body_text),
        "span_id": "spanv1_" + checks.source.digest([
            checks.source.SPAN_VERSION, token, [1], 2, checks.source.sha_text(second)])}
    document = {"body_text": body_text, "paragraphs": [paragraph, second_paragraph]}
    base = {"actor_or_intervention": "synthetic intervention", "action": "treatment",
        "relation_direction": "DECREASES", "response_or_endpoint": "synthetic endpoint",
        "biological_unit": "cultured cells", "species": None,
        "intrinsic_conditioning": None, "intrinsic_therapy_context": None,
        "intrinsic_disease_or_genotype_context": None,
        "neutral_proposition": "Synthetic intervention decreases synthetic endpoint.",
        "construction_evidence_span": {"source_field": "body",
            "exact_text": body, "start_offset": 0, "end_offset": len(body)}}
    cases: list[dict[str, Any]] = []

    def schema_accept(candidates: list[dict[str, Any]], schema: dict[str, Any]) -> bool:
        try:
            checks.validate_builder_response(canonical({
                "source_record_token": token, "candidates": candidates}), token, schema)
            return True
        except ValueError:
            return False

    def add(name: str, expected: bool, actual: bool) -> None:
        cases.append({"case": name, "expected_pass": expected, "actual_pass": actual,
                      "pass": expected == actual})

    abstract = copy.deepcopy(base)
    abstract["construction_evidence_span"]["source_field"] = "abstract"
    add("A_abstract_rejected_by_v3", False, schema_accept([abstract], v3))
    add("B_body_schema_accepted", True, schema_accept([base], v3))
    add("C_body_reference_resolves", True,
        checks.source.resolve_candidate_span(document, "body", 0, len(body), body) == paragraph["span_id"])
    unknown = copy.deepcopy(base)
    unknown["construction_evidence_span"]["span_id"] = "spanv1_" + "0" * 64
    add("D_unknown_body_span_id_rejected_not_model_field", False, schema_accept([unknown], v3))
    try:
        cross_start, cross_end = len(body) - 5, len(body) + 5
        checks.source.resolve_candidate_span(document, "body", cross_start, cross_end,
            body_text[cross_start:cross_end])
        outside = True
    except ValueError:
        outside = False
    add("E_body_offset_outside_paragraph_rejected", False, outside)
    identity = copy.deepcopy(base)
    identity["construction_evidence_span"]["source_field"] = "PMC12345"
    add("F_source_identity_in_grounding_field_rejected", False, schema_accept([identity], v3))
    add("G_zero_candidates_valid", True, schema_accept([], v3))
    add("H_one_body_candidate_valid", True, schema_accept([base], v3))
    add("H_three_body_candidates_valid", True, schema_accept([base] * 3, v3))
    add("I_four_candidates_invalid", False, schema_accept([base] * 4, v3))
    add("J_v2_historical_abstract_parseable", True, schema_accept([abstract], v2))
    add("J_v2_historical_abstract_not_v3", False, schema_accept([abstract], v3))
    return cases, {"synthetic_case_count": len(cases),
        "passed": sum(row["pass"] for row in cases),
        "failed": sum(not row["pass"] for row in cases),
        "all_pass": all(row["pass"] for row in cases),
        "model_calls": 0}


def build() -> dict[str, Any]:
    audit = preflight()
    frozen = audit["frozen"]
    requests = frozen["requests"]
    sources = frozen["sources"]
    template = audit["template_v2"]
    amended_system = audit["prompt_v2"] + audit["required"] + "\n"
    schema = v3_schema(audit["schema_v2"])
    schema_json = json.dumps(schema, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    cases, case_results = synthetic_cases(audit["schema_v2"], schema)
    if not case_results["all_pass"]:
        raise RuntimeError("BUILDER_V3_SYNTHETIC_CONTRACT_TEST_FAILURE")
    results, deltas = [], []
    for ordinal, (source_row, original) in enumerate(zip(sources, requests), 1):
        token = source_row["source_token"]
        document_path = prior.a6.OUT / source_row["document_path"]
        if digest(document_path) != source_row["document_sha256"]:
            raise RuntimeError("V3_FROZEN_DOCUMENT_HASH_MISMATCH")
        doc = read(document_path)
        body = doc["body_text"]
        paragraphs = doc["paragraphs"]
        valid_paragraphs = [p for p in paragraphs
            if p["span_id"].startswith("spanv1_") and 0 <= p["start_offset"] < p["end_offset"] <= len(body)
            and body[p["start_offset"]:p["end_offset"]] == p["text"]]
        if not body or not valid_paragraphs:
            raise RuntimeError("V3_BUILDER_REQUEST_VISIBILITY_DEFECT")
        old = original["request"]
        old_user = old["messages"][1]["content"]
        if (old["messages"][0]["content"] != audit["prompt_v2"] or
            audit["required"] in old_user or
            "Abstract: " + doc["abstract_text"] not in old_user or
            "Body: " + body not in old_user or
            "spanv1_" in old_user):
            raise RuntimeError("V2_REQUEST_STRUCTURAL_AUDIT_MISMATCH")
        new_user = template.format(source_record_token=token,
            frozen_abstract=doc["abstract_text"], frozen_body=body,
            output_schema_json=schema_json)
        new = copy.deepcopy(old)
        new["messages"][0]["content"] = amended_system
        new["messages"][1]["content"] = new_user
        if (set(new) != set(old) or
            any(new[key] != old[key] for key in old if key != "messages") or
            not new_user.startswith(old_user.split("Output schema: ", 1)[0]) or
            new["messages"][0]["content"] != old["messages"][0]["content"] + audit["required"] + "\n"):
            raise RuntimeError("V3_REQUEST_DELTA_OUTSIDE_GROUNDING_INTERFACE")
        results.append({"ordinal": ordinal, "source_token": token,
            "document_sha256": source_row["document_sha256"],
            "request": new, "request_sha256": sha(canonical(new))})
        deltas.append({"ordinal": ordinal, "source_token": token,
            "v2_request_sha256": original["request_sha256"],
            "v3_request_sha256": results[-1]["request_sha256"],
            "document_sha256_unchanged": True, "scientific_task_text_unchanged": True,
            "candidate_cardinality_unchanged": True, "abstract_and_body_context_unchanged": True,
            "grounding_instruction_added_only": True,
            "schema_changed_only_source_field_enum_to_body": True,
            "provider_configuration_unchanged": True,
            "body_evidence_available": True, "body_paragraph_count": len(valid_paragraphs),
            "body_span_ids_visible_to_model": False})
    if (len(results) != 28 or len({row["source_token"] for row in results}) != 28 or
        [row["source_token"] for row in results] != [row["source_token"] for row in requests]):
        raise RuntimeError("V3_REQUEST_SET_MISMATCH")
    return {"audit": audit, "schema": schema, "requests": results,
        "deltas": deltas, "cases": cases, "case_results": case_results}


def main() -> None:
    built = build()
    audit = built["audit"]
    deltas = built["deltas"]
    schema_v3 = built["schema"]
    requests_v3 = built["requests"]
    original = audit["frozen"]["requests"]
    v2_schema = audit["schema_v2"]
    req_visibility = read(prior.a6.OUT / "builder_visibility_preflight_audit_v4.json")
    if req_visibility["failed_count"] != 0 or req_visibility["builder_request_count"] != 28:
        raise RuntimeError("V2_BUILDER_VISIBILITY_PREFLIGHT_NOT_CLEAR")
    identity_rows = rows(HISTORY / "builder_candidate_identity_manifest.jsonl")
    if len(identity_rows) != 70 or len({row["candidate_id"] for row in identity_rows}) != 70:
        raise RuntimeError("V2_CANDIDATE_QUARANTINE_IDENTITY_MISMATCH")
    OUT.mkdir()
    write("alpha3_18b_execution_verification.json", {
        "history_root_sha256": HISTORY_SHA, "history_root_verified": True,
        "prereg_root_sha256": PREREG_SHA, "prereg_root_verified": True,
        "execution_manifest_sha256": MANIFEST_SHA, "execution_manifest_verified": True,
        "construction_source_manifest_sha256": prior.SOURCE_SHA,
        "builder_request_manifest_sha256": prior.REQUEST_SHA,
        "builder_protocol_v2_sha256": prior.BUILDER_SHA,
        "builder_output_schema_v2_sha256": prior.SCHEMA_SHA,
        "historical_builder_inference_events": 28,
        "historical_quality_manifest_empty_and_unchanged": True})
    write("candidate_structural_failure_summary.json", {
        "raw_candidate_count": 70, "schema_valid_nonzero_responses": 28,
        "source_field_abstract_count": 70, "source_field_body_count": 0,
        "grounding_reference_failures": 70,
        "grounding_rejection_reason": "BODY_ONLY_POST_VALIDATION_REJECTS_ABSTRACT",
        "scientific_candidate_content_inspected": False})
    timeline = [
        {"stage": "alpha3.17_source_pool", "authority": "baseline source span schema",
         "frozen_source": ref(OLD_POOL / "proposition_builder_schema.json"),
         "abstract_allowed": True, "body_allowed": True,
         "note": "generic source_field plus exact_text and character offsets"},
        {"stage": "alpha3.17c_builder_v2", "authority": "BuilderProtocolV2 and BuilderOutputSchemaV2",
         "frozen_source": ref(BUILDER / "proposition_builder_protocol_v2.json"),
         "schema_source": ref(BUILDER / "proposition_builder_output_schema_v2.json"),
         "abstract_allowed": True, "body_allowed": True,
         "note": "cardinality amended to 0..3; scientific span enum unchanged"},
        {"stage": "alpha3.17d_quality_v2", "authority": "quality evidence input after deterministic reference precheck",
         "frozen_source": ref(QUALITY / "builder_output_freeze_barrier.json"),
         "abstract_allowed": "not independently decided here",
         "body_allowed": "not independently decided here",
         "note": "requires frozen source-local evidence reference before quality"},
        {"stage": "alpha3.18A.1_pre_builder_source_amendment",
         "authority": "prospective BODY-only scientific grounding requirement before any Builder calls",
         "frozen_source": ref(AMEND / "builder_grounding_reference_contract.json"),
         "document_source": ref(AMEND / "construction_evidence_document_v1_contract.json"),
         "anchor_source": ref(AMEND / "evidence_span_anchor_v1_contract.json"),
         "abstract_allowed": False, "body_allowed": True,
         "note": "abstract remains visible for context; valid candidate evidence must be BODY"},
        {"stage": "alpha3.18B_preregistration", "authority": "executor binding before 28 calls",
         "frozen_source": ref(prior.OUT / "builder_grounding_precheck_contract.json"),
         "abstract_allowed": False, "body_allowed": True,
         "note": "BODY reference required; invalid references excluded without repair"},
        {"stage": "alpha3.18B_execution", "authority": "historical execution",
         "frozen_source": ref(HISTORY / "builder_grounding_reference_audit.jsonl"),
         "abstract_allowed": False, "body_allowed": True,
         "note": "70 abstract references mechanically rejected; historical output preserved"}]
    write("grounding_authority_timeline.json", {
        "chronology": timeline,
        "authoritative_grounding_requirement_before_calls": "BODY_ONLY_AUTHORITATIVE",
        "authority_not_inferred_from_candidate_yield": True})
    write("builder_protocol_v2_grounding_audit.json", {
        "protocol_source": ref(BUILDER / "proposition_builder_protocol_v2.json"),
        "request_template_source": ref(AMEND / "proposition_builder_v2_1_user_prompt_template.txt"),
        "a1_required_instruction_source": ref(AMEND / "builder_request_visibility_amendment.json"),
        "system_prompt_explicit_body_only": False,
        "actual_template_explicit_body_only": False,
        "a1_required_body_only_instruction_missing_from_template": True,
        "actual_28_requests_with_required_instruction": 0,
        "abstract_visible_as_context": True,
        "body_visible": True,
        "abstract_grounding_not_prohibited_in_model_facing_prompt": True,
        "body_grounding_not_prohibited_in_model_facing_prompt": True})
    write("builder_output_schema_v2_grounding_audit.json", {
        "schema_source": ref(BUILDER / "proposition_builder_output_schema_v2.json"),
        "source_field_required": True,
        "allowed_source_field_enum": ["abstract", "body"],
        "abstract_schema_valid": True, "body_schema_valid": True,
        "span_reference_fields": ["source_field", "exact_text", "start_offset", "end_offset"],
        "model_generated_span_id_allowed": False,
        "span_id_attached_later_by_controller": True})
    write("builder_request_visibility_audit.json", {
        "source": ref(prior.a6.OUT / "proposition_builder_v2_request_manifest_v4.jsonl"),
        "source_visibility_preflight": ref(prior.a6.OUT / "builder_visibility_preflight_audit_v4.json"),
        "request_count": 28, "abstract_content_visible_count": 28,
        "body_content_visible_count": 28, "abstract_and_body_labels_visible_count": 28,
        "body_span_ids_visible_count": 0,
        "body_reference_mechanism": "source_field + exact_text + zero-based character offsets",
        "scientific_proposition_content_inspected": False})
    write("body_evidence_availability_audit.json", {
        "requests_with_body_evidence_available": 28,
        "requests_without_body_evidence_available": 0,
        "minimum_valid_body_paragraph_count": min(row["body_paragraph_count"] for row in deltas),
        "maximum_valid_body_paragraph_count": max(row["body_paragraph_count"] for row in deltas),
        "per_source": [{"source_token": row["source_token"],
            "valid_body_paragraph_count": row["body_paragraph_count"],
            "body_visible_in_request": True, "body_span_ids_visible_in_request": False}
            for row in deltas]})
    write("grounding_validator_audit.json", {
        "frozen_contract": ref(AMEND / "builder_grounding_reference_contract.json"),
        "frozen_anchor_contract": ref(AMEND / "evidence_span_anchor_v1_contract.json"),
        "implementation": ref(ROOT / "scripts/search_plan_v24_alpha318a1_source_contracts.py"),
        "actual_precheck": ref(ROOT / "scripts/search_plan_v24_alpha318b_post_builder_prechecks.py"),
        "body_only_enforced_first": True, "abstract_rejected": True,
        "offset_and_exact_text_verified_second": True,
        "exactly_one_canonical_body_paragraph_required_third": True,
        "controller_attaches_paragraph_span_id": True,
        "failed_candidate_state": "GROUNDING_REFERENCE_FAILED",
        "matches_pre_builder_frozen_contract": True})
    write("grounding_four_way_consistency_matrix.json", {
        "columns": ["component", "abstract_allowed", "body_allowed", "authority_level",
                    "frozen_before_builder", "notes"],
        "rows": [
            {"component": "scientific_authority", "abstract_allowed": False, "body_allowed": True,
             "authority_level": "alpha3.18A.1 prospective scientific source contract",
             "frozen_before_builder": True, "notes": "abstract may remain context-visible"},
            {"component": "builder_prompt_v2_1", "abstract_allowed": True, "body_allowed": True,
             "authority_level": "model-facing request wording",
             "frozen_before_builder": True, "notes": "required BODY-only sentence absent"},
            {"component": "builder_output_schema_v2", "abstract_allowed": True, "body_allowed": True,
             "authority_level": "provider output syntax", "frozen_before_builder": True,
             "notes": "source_field required, enum abstract/body"},
            {"component": "grounding_validator", "abstract_allowed": False, "body_allowed": True,
             "authority_level": "deterministic post-validation", "frozen_before_builder": True,
             "notes": "matches alpha3.18A.1 scientific authority"}]})
    write("grounding_defect_classification.json", {
        "authoritative_grounding_requirement": "BODY_ONLY_AUTHORITATIVE",
        "primary_classification": "MULTIPLE_GROUNDING_CONTRACT_DEFECTS",
        "defects": ["BUILDER_PROMPT_GROUNDING_CONTRACT_DEFECT",
                    "BUILDER_SCHEMA_GROUNDING_CONTRACT_DEFECT"],
        "request_visibility_defect": False, "grounding_validator_defect": False,
        "genuine_builder_scientific_failure_not_established": True,
        "classification_basis": "frozen pre-call contracts and structural source_field counts only"})
    write("zero_quality_budget_interpretation.json", {
        "historical_actual_quality_adjudication_call_count": 0,
        "historical_status": "HISTORICALLY_CORRECT_UNDER_EXECUTED_V2_CONTRACT",
        "scientific_interpretation": "NOT_INTERPRETABLE_AS_SCIENTIFIC_BUILDER_YIELD",
        "historical_manifest_rewritten": False,
        "future_v3_quality_budget": None,
        "no_quality_execution_on_v2_candidates": True})
    write("v2_candidate_quarantine.json", {
        "historical_candidate_identity_manifest": ref(HISTORY /
            "builder_candidate_identity_manifest.jsonl"),
        "quarantine_state": "INVALID_FOR_PROSPECTIVE_POOL_DUE_TO_GROUNDING_CONTRACT_DEFECT",
        "candidate_count": 70,
        "records": [{"candidate_id": row["candidate_id"],
            "state": "INVALID_FOR_PROSPECTIVE_POOL_DUE_TO_GROUNDING_CONTRACT_DEFECT"}
            for row in identity_rows],
        "may_be_pooled_with_v3": False, "may_be_reanchored_or_repaired": False,
        "best_of_two_selection": False})
    write("candidate_content_nonuse_audit.json", {
        "candidate_scientific_content_inspected": False,
        "candidate_fields_accessed": ["construction_evidence_span.source_field",
            "candidate_id", "terminal_state", "grounding_reference_state"],
        "candidate_wording_used_for_v3_prompt_or_schema": False,
        "scientific_candidate_comparison_or_ranking": False})

    write("builder_grounding_contract_v3.json", {
        "schema_version": V3_VERSION,
        "prospective_interface_correction_not_historical_repair": True,
        "scientific_authority": ref(AMEND / "builder_grounding_reference_contract.json"),
        "unchanged_builder_protocol_v2": ref(BUILDER / "proposition_builder_protocol_v2.json"),
        "unchanged_construction_source_manifest_v4": ref(prior.a6.OUT /
            "construction_source_manifest_v4.jsonl"),
        "model_grounding_reference": "source_field=body + exact_text + zero-based offsets",
        "model_generated_span_id": False,
        "controller_anchor_attachment": "unchanged EvidenceSpanAnchorV1 paragraph-level resolver",
        "abstract_visible_for_context_only": True,
        "abstract_admissible_as_candidate_evidence": False,
        "body_admissible_as_candidate_evidence": True,
        "candidate_cardinality": {"minimum": 0, "maximum": 3},
        "scientific_task_and_quality_criteria_unchanged": True,
        "postchecks_and_quality_protocol_unchanged": True,
        "v2_historical_outputs_quarantined": True})
    marker("builder_grounding_contract_v3_sha256",
           digest(OUT / "builder_grounding_contract_v3.json"))
    write("builder_output_schema_v3.json", {
        "artifact_schema_version": "PropositionBuilderOutputV3",
        "protocol_version": V3_VERSION,
        "schema": schema_v3,
        "v2_schema_source": ref(BUILDER / "proposition_builder_output_schema_v2.json"),
        "only_schema_delta": "candidates[*].construction_evidence_span.source_field enum abstract/body -> body",
        "model_generated_candidate_id_allowed": False,
        "candidate_array_order_semantically_meaningless": True})
    marker("builder_output_schema_v3_sha256", digest(OUT / "builder_output_schema_v3.json"))
    write("builder_prompt_v3_delta.json", {
        "v2_protocol": ref(BUILDER / "proposition_builder_protocol_v2.json"),
        "v2_1_template": ref(AMEND / "proposition_builder_v2_1_user_prompt_template.txt"),
        "added_system_instruction_utf8": audit["required"] + "\n",
        "added_instruction_authority": ref(AMEND / "builder_request_visibility_amendment.json"),
        "scientific_task_text_prefix_unchanged": True,
        "user_template_unchanged_except_output_schema_rendering": True,
        "abstract_retained_for_context": True,
        "source_content_or_scientific_candidate_wording_used_to_tune_prompt": False})
    write_rows("builder_v2_v3_request_delta.jsonl", deltas)
    write_rows("builder_v3_request_manifest.jsonl", requests_v3)
    v3_sha = digest(OUT / "builder_v3_request_manifest.jsonl")
    marker("builder_v3_request_manifest_sha256", v3_sha)
    write("builder_v3_visibility_audit.json", {
        "source_v2_visibility_audit": ref(prior.a6.OUT / "builder_visibility_preflight_audit_v4.json"),
        "v2_firewall_pass_count": 28,
        "v3_request_count": 28, "title_or_bibliography_newly_exposed": False,
        "private_pmid_pmcid_doi_author_journal_added": False,
        "private_source_token_added_to_grounding_field": False,
        "opaque_source_record_token_request_echo_unchanged": True,
        "abstract_and_body_context_unchanged": True,
        "body_span_ids_not_exposed": True,
        "only_new_text_is_frozen_a1_grounding_instruction_and_v3_schema": True})
    write("builder_v3_structural_validation.json", {
        "status": "PASS", "request_count": 28,
        "source_count": 28, "source_set_and_order_unchanged": True,
        "source_document_hashes_unchanged": True,
        "requests_with_body_evidence_available": 28,
        "v3_schema_bound_to_every_request": True,
        "v3_schema_abstract_reference_rejected": True,
        "candidate_cardinality_unchanged_0_to_3": True,
        "provider_configuration_unchanged": True,
        "material_runtime_policy_unresolved_count": 0})
    write_rows("builder_v3_synthetic_cases.jsonl", built["cases"])
    write("builder_v3_synthetic_test_results.json", built["case_results"])
    write("alpha3_18b2_builder_v3_execution_manifest.json", {
        "schema_version": "Alpha318B2BuilderV3ExecutionManifestV1",
        "status": "PROSPECTIVE_OFFLINE_PREREGISTRATION",
        "historical_v2_execution_root_sha256": HISTORY_SHA,
        "historical_v2_candidate_quarantine": ref(OUT / "v2_candidate_quarantine.json"),
        "source_manifest_v4": ref(prior.a6.OUT / "construction_source_manifest_v4.jsonl"),
        "builder_v3_request_manifest": ref(OUT / "builder_v3_request_manifest.jsonl"),
        "builder_v3_request_count": 28,
        "builder_v3_request_order": [{"ordinal": row["ordinal"],
            "source_token": row["source_token"], "request_sha256": row["request_sha256"]}
            for row in requests_v3],
        "builder_grounding_contract_v3": ref(OUT / "builder_grounding_contract_v3.json"),
        "builder_output_schema_v3": ref(OUT / "builder_output_schema_v3.json"),
        "builder_prompt_v3_delta": ref(OUT / "builder_prompt_v3_delta.json"),
        "provider_configuration": audit["frozen"]["provider"],
        "initial_scientific_inferences_per_source": 1,
        "scientific_repair": False,
        "automatic_retry": False,
        "ambiguous_execution_stops_stage": True,
        "schema_invalid_completed_response_reinferred": False,
        "zero_candidates_valid": True,
        "frozen_postchecks": {
            "candidate_identity_and_exact_dedup": ref(prior.OUT /
                "builder_candidate_identity_contract.json"),
            "body_grounding_reference": ref(prior.OUT /
                "builder_grounding_precheck_contract.json"),
            "leakage": ref(prior.OUT / "builder_leakage_execution_contract.json"),
            "quality_grouping_and_manifest": ref(prior.OUT /
                "quality_request_construction_contract.json")},
        "phase_barriers": ["all 28 V3 raw outputs frozen before Quality request construction",
            "all future Quality requests frozen before any Quality call"],
        "quality_protocol_v2_root_sha256": prior.QUALITY_SHA,
        "future_quality_call_budget": None,
        "network_calls_in_this_audit": 0,
        "provider_calls_in_this_audit": 0,
        "future_execution_requires_separate_exact_28_call_authorization": True,
        "historical_v2_inference_events_preserved": 28,
        "prospective_v3_inference_events_if_authorized": 28,
        "cumulative_project_builder_inference_events_after_full_v3_run": 56,
        "material_runtime_policy_unresolved_count": 0})
    manifest_sha = digest(OUT / "alpha3_18b2_builder_v3_execution_manifest.json")
    marker("alpha3_18b2_builder_v3_execution_manifest_sha256", manifest_sha)
    write("historical_preservation_audit.json", {
        "historical_alpha3_18b_root_sha256": HISTORY_SHA,
        "historical_alpha3_18b_preserved": True,
        "historical_prereg_root_sha256": PREREG_SHA,
        "historical_builder_v2_scientific_inference_events": 28,
        "prospective_builder_v3_calls_executed_here": 0,
        "historical_quality_budget_zero_preserved": True,
        "historical_quality_manifest_empty_preserved": True,
        "historical_assets_modified": False})
    write("scientific_state_safety_audit.json", {
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "quality_calls": 0, "builder_reruns": 0,
        "candidate_repair": False, "source_topup": False,
        "candidate_scientific_content_inspected": False,
        "historical_assets_modified": False})
    write("validation.json", {
        "status": "PASS", "authoritative_grounding_requirement": "BODY_ONLY_AUTHORITATIVE",
        "grounding_contract_defect_classification": "MULTIPLE_GROUNDING_CONTRACT_DEFECTS",
        "builder_v3_created": True, "builder_v3_request_count": 28,
        "builder_v3_source_count": 28,
        "material_runtime_policy_unresolved_count": 0,
        "synthetic_tests_passed": built["case_results"]["passed"],
        "historical_alpha3_18b_preserved": True,
        "historical_quality_budget_zero_scientifically_interpretable": False,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0})
    write("summary.json", {
        "status": "completed", "raw_candidate_count": 70,
        "abstract_grounding_candidate_count": 70, "body_grounding_candidate_count": 0,
        "requests_with_body_evidence_available": 28,
        "authoritative_grounding_requirement": "BODY_ONLY_AUTHORITATIVE",
        "primary_defect": "MULTIPLE_GROUNDING_CONTRACT_DEFECTS",
        "historical_quality_budget_zero_preserved": True,
        "historical_quality_budget_zero_scientifically_interpretable": False,
        "v2_candidates_quarantined": True,
        "builder_v3_request_count": 28,
        "future_v3_quality_call_count": None,
        "builder_grounding_contract_v3_sha256": digest(OUT / "builder_grounding_contract_v3.json"),
        "builder_output_schema_v3_sha256": digest(OUT / "builder_output_schema_v3.json"),
        "builder_v3_request_manifest_sha256": v3_sha,
        "alpha3_18b2_builder_v3_execution_manifest_sha256": manifest_sha,
        "next_stage_recommendation": "AUTHORIZE_EXACT_28_ALPHA3_18B2_BUILDER_V3_CALLS"})
    if prior.a6.base.prior.all_file_root(HISTORY,
        "search_plan_v24_dev_alpha3_18b_sha256") != HISTORY_SHA:
        raise RuntimeError("HISTORICAL_ALPHA3_18B_MUTATED_DURING_AUDIT")
    root = prior.a6.base.prior.all_file_root(OUT, ROOT_MARKER)
    marker(ROOT_MARKER, root)
    print(json.dumps({"status": "completed", "root_sha256": root,
        "builder_v3_request_manifest_sha256": v3_sha,
        "v3_execution_manifest_sha256": manifest_sha,
        "provider_calls": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
