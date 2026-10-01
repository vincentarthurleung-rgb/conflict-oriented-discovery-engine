#!/usr/bin/env python3
"""Bind 28 frozen V4 Builder requests to prospective alpha3.18B execution."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

try:
    from scripts import search_plan_v24_alpha318a6_replay_license_offline as a6
    from scripts import search_plan_v24_alpha318b_post_builder_prechecks as prechecks
    from scripts import search_plan_v24_alpha317d_preregister_quality_v2_offline as quality
except ModuleNotFoundError:
    import search_plan_v24_alpha318a6_replay_license_offline as a6
    import search_plan_v24_alpha318b_post_builder_prechecks as prechecks
    import search_plan_v24_alpha317d_preregister_quality_v2_offline as quality


ROOT = a6.ROOT
OUT = ROOT / "runs/20261001_search_plan_v24_dev_alpha3_18b_builder_execution_preregistration_offline"
ROOT_MARKER = "search_plan_v24_dev_alpha3_18b_prereg_sha256"
A6_ROOT = "204bcc949b3f8b86fd03cc1dfd4cbab371ceceab7e44824df9c71e58e3f26b40"
SOURCE_SHA = "1ac2a03e80441903b25c6ee8ecef344bd22c1460ecff6e8af6fe469050d84bd4"
REQUEST_SHA = "8bd9a35d80902e086b1b6621bdd220cf519a200b7e1788125470a14cfe172365"
BUILDER_SHA = "8a50314aac4e5f8017109a047905981a91aa91ffb784e1ebde0f92256917ba33"
SCHEMA_SHA = "5309d3edc9b8a40b64f6fc79e5f7a8e19ac4738808827b33cfe2eb3047db7849"
QUALITY_SHA = "89009283963c1db3dd00d57917d932b4d0a542dcb27863ad071dc30f8c0cd751"
BUILDER_DIR = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17c_builder_cardinality_reconciliation_offline"
QUALITY_DIR = quality.RUN
LEAKAGE_DIR = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17a_new_pool_execution_preflight_offline"
REQUIRED_EXECUTION_OUTPUTS = [
    "builder_execution_preflight.json", "builder_request_manifest_verification.json",
    "builder_call_order.json", "builder_raw_responses.jsonl", "builder_transport_provenance.jsonl",
    "builder_response_validation.jsonl", "builder_source_terminal_states.jsonl",
    "builder_candidate_raw_manifest.jsonl", "builder_candidate_identity_manifest.jsonl",
    "builder_exact_duplicate_audit.json", "builder_grounding_reference_audit.jsonl",
    "builder_leakage_audit.jsonl", "builder_prechecked_candidate_manifest.jsonl",
    "builder_candidate_summary.json", "builder_execution_accounting.json",
    "all_builder_outputs_freeze_barrier.json", "quality_source_group_manifest.jsonl",
    "actual_quality_call_budget.json", "quality_visibility_preflight_audit.json",
    "proposition_quality_v2_request_manifest.jsonl",
    "proposition_quality_v2_request_manifest_sha256", "quality_manifest_freeze_barrier.json",
    "anchor_firewall_audit.json", "development_nonuse_audit.json",
    "search_plan_firewall_audit.json", "protocol_compliance_audit.json",
    "scientific_state_safety_audit.json", "validation.json", "summary.json",
]
QUALITY_PROTOCOL_FILES = [
    "builder_protocol_v2_verification.json", "quality_criterion_authority_matrix.json",
    "proposition_quality_adjudicator_role.json", "quality_provider_config.json",
    "quality_visibility_contract.json", "quality_source_context_contract.json",
    "semantic_grounding_criterion.json", "quality_criteria_contract.json",
    "criterion_state_contract.json", "overall_quality_eligibility_rule.json",
    "proposition_quality_adjudication_v2_schema.json",
    "quality_adjudicator_system_prompt.txt", "quality_adjudicator_user_prompt_template.txt",
    "quality_machine_output_contract.json", "quality_response_identity_binding_contract.json",
    "quality_invalid_response_policy.json", "provider_execution_ambiguity_policy.json",
    "one_source_per_quality_call_contract.json", "candidate_independence_contract.json",
    "quality_ranking_prohibition.json", "deterministic_one_per_source_selector.json",
    "duplicate_selection_order_authority_audit.json", "builder_output_freeze_barrier.json",
    "quality_request_manifest_freeze_barrier.json", "quality_call_budget_formula.json",
    "anchor_firewall_quality_stage_contract.json", "quality_payload_blinding_audit_contract.json",
    "future_stage_separation.json",
]


def sha(raw: bytes) -> str:
    return a6.sha(raw)


def digest(path: Path) -> str:
    return sha(path.read_bytes())


def ref(path: Path) -> dict[str, str]:
    return {"path": str(path.relative_to(ROOT)), "sha256": digest(path)}


def write(name: str, value: Any) -> None:
    a6.base.write_json(OUT / name, value)


def marker(name: str, value: str) -> None:
    a6.base.write_bytes(OUT / name, (value + "\n").encode("ascii"))


def _assert_file_marker(directory: Path, marker_name: str, expected: str, file_name: str) -> None:
    if (directory / marker_name).read_text().strip() != expected or digest(directory / file_name) != expected:
        raise RuntimeError("FROZEN_CONTRACT_HASH_MISMATCH:" + file_name)


def preflight() -> dict[str, Any]:
    if a6.sha(a6.base.canonical([[str(path.relative_to(a6.OUT)), digest(path)]
        for path in sorted(a6.OUT.rglob("*")) if path.is_file() and path.name != a6.ROOT_MARKER])) != A6_ROOT or (
        a6.OUT / a6.ROOT_MARKER).read_text().strip() != A6_ROOT:
        raise RuntimeError("ALPHA3_18A6_ROOT_MISMATCH")
    _assert_file_marker(a6.OUT, "construction_source_manifest_v4_sha256", SOURCE_SHA,
                        "construction_source_manifest_v4.jsonl")
    _assert_file_marker(a6.OUT, "proposition_builder_v2_request_manifest_v4_sha256", REQUEST_SHA,
                        "proposition_builder_v2_request_manifest_v4.jsonl")
    _assert_file_marker(BUILDER_DIR, "proposition_builder_protocol_v2_sha256", BUILDER_SHA,
                        "proposition_builder_protocol_v2.json")
    _assert_file_marker(BUILDER_DIR, "proposition_builder_output_schema_v2_sha256", SCHEMA_SHA,
                        "proposition_builder_output_schema_v2.json")
    qroot = sha(a6.base.canonical([[name, digest(QUALITY_DIR / name)]
        for name in sorted(QUALITY_PROTOCOL_FILES)]))
    if qroot != QUALITY_SHA or (
        QUALITY_DIR / "proposition_quality_adjudication_v2_protocol_sha256").read_text().strip() != QUALITY_SHA:
        raise RuntimeError("QUALITY_V2_PROTOCOL_ROOT_MISMATCH")
    sources = a6.v3.replay.rows(a6.OUT / "construction_source_manifest_v4.jsonl")
    requests = a6.v3.replay.rows(a6.OUT / "proposition_builder_v2_request_manifest_v4.jsonl")
    vault = a6.v3.replay.rows(a6.OUT / "private_anchor_vault_source_manifest_v4.jsonl")
    budget = json.loads((a6.OUT / "actual_builder_call_budget_v4.json").read_text())
    if not (len(sources) == len(requests) == len(vault)):
        raise RuntimeError("BUILDER_REQUEST_FREEZE_MISMATCH:cardinality")
    if len(sources) != 28 or len(requests) != 28 or len(vault) != 28 or (
        budget["actual_builder_scientific_call_count_v4"] != 28):
        raise RuntimeError("BUILDER_REQUEST_FREEZE_MISMATCH:budget")
    if [row["source_token"] for row in sources] != [row["source_token"] for row in requests] or (
        len({row["source_token"] for row in sources}) != 28):
        raise RuntimeError("BUILDER_REQUEST_FREEZE_MISMATCH:source order")
    protocol = json.loads((BUILDER_DIR / "proposition_builder_protocol_v2.json").read_text())
    schema = json.loads((BUILDER_DIR / "proposition_builder_output_schema_v2.json").read_text())["schema"]
    provider = protocol["provider_configuration"]
    if provider["provider"] != "DeepSeek" or provider["model"] != "deepseek-v4-pro" or (
        provider["reasoning_effort"] != "high" or provider["thinking"] != {"type": "enabled"} or
        provider["automatic_retry"] is not False or provider["fallback"] is not None or
        provider["temperature"] != "omitted" or provider["top_p"] != "omitted"):
        raise RuntimeError("BUILDER_PROVIDER_CONFIG_UNRESOLVED")
    if schema["properties"]["candidates"]["minItems"] != 0 or (
        schema["properties"]["candidates"]["maxItems"] != 3 or
        schema["properties"]["candidates"]["items"]["additionalProperties"] is not False):
        raise RuntimeError("BUILDER_SCHEMA_CARDINALITY_MISMATCH")
    template = (a6.base.prior.AMEND / "proposition_builder_v2_1_user_prompt_template.txt").read_text()
    output_schema_json = json.dumps(schema, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    vault_by_token = {row["source_token"]: row for row in vault}
    jats_records = a6.v3.replay.rows(a6.V3 / "pmc_jats_acquisition_results_v3.jsonl")
    jats_by_pmcid = {row["pmcid"]: row for row in jats_records}
    for source, item in zip(sources, requests):
        token = source["source_token"]
        if not re.fullmatch(r"src_[0-9a-f]{64}", token) or token not in vault_by_token:
            raise RuntimeError("BUILDER_REQUEST_FREEZE_MISMATCH:opaque token")
        path = a6.OUT / source["document_path"]
        if not path.resolve().is_relative_to((a6.OUT / "construction_evidence_documents_v4").resolve()) or (
            not path.is_file() or path.is_symlink() or digest(path) != source["document_sha256"] or
            item["document_sha256"] != source["document_sha256"]):
            raise RuntimeError("BUILDER_REQUEST_FREEZE_MISMATCH:document")
        document = json.loads(path.read_text())
        if document["schema_version"] != "ConstructionEvidenceDocumentV1" or (
            document["article_title_visible"] is not False or document["bibliography_visible"] is not False):
            raise RuntimeError("BUILDER_REQUEST_FREEZE_MISMATCH:visibility flags")
        request = item["request"]
        if sha(a6.base.canonical(request)) != item["request_sha256"] or set(request) != {
            "model", "thinking", "reasoning_effort", "response_format", "messages"} or (
            request["model"] != provider["model"] or request["thinking"] != provider["thinking"] or
            request["reasoning_effort"] != provider["reasoning_effort"] or
            request["response_format"] != provider["response_format"] or
            request["messages"][0] != {"role": "system", "content": protocol["system_prompt_utf8"]}):
            raise RuntimeError("BUILDER_REQUEST_FREEZE_MISMATCH:payload/config")
        expected_user = template.format(source_record_token=token,
            frozen_abstract=document["abstract_text"], frozen_body=document["body_text"],
            output_schema_json=output_schema_json)
        if request["messages"][1] != {"role": "user", "content": expected_user}:
            raise RuntimeError("BUILDER_REQUEST_FREEZE_MISMATCH:user wording")
        private = vault_by_token[token]
        if private["pmcid"] not in jats_by_pmcid:
            raise RuntimeError("QUALITY_PAYLOAD_FIREWALL_INCOMPLETE:JATS identity")
        jats = a6.V3 / jats_by_pmcid[private["pmcid"]]["canonical_jats_path"]
        if digest(jats) != private["canonical_jats_sha256"]:
            raise RuntimeError("QUALITY_PAYLOAD_FIREWALL_INCOMPLETE:JATS hash")
        # Future pre-call quality firewall can inspect private title, journal,
        # authors, PMID, PMCID and DOI without exposing them in the payload.
        prechecks.private_identity_from_jats(jats.read_bytes(), private["pmid"],
            private["pmcid"], private["doi"])
    leak_contract = json.loads((LEAKAGE_DIR / "leakage_audit_implementation_contract.json").read_text())
    if digest(ROOT / "scripts/search_plan_v24_alpha317a_safety_audits.py") != leak_contract["implementation_sha256"]:
        raise RuntimeError("BUILDER_LEAKAGE_IMPLEMENTATION_MISMATCH")
    quality_audit = json.loads((QUALITY_DIR / "quality_payload_blinding_audit_contract.json").read_text())
    if digest(ROOT / "scripts/search_plan_v24_alpha317d_preregister_quality_v2_offline.py") != (
        quality_audit["implementation_sha256"]):
        raise RuntimeError("QUALITY_PAYLOAD_FIREWALL_IMPLEMENTATION_MISMATCH")
    return {"sources": sources, "requests": requests, "vault": vault,
        "protocol": protocol, "schema": schema, "provider": provider,
        "quality_protocol_root": qroot}


def main() -> None:
    if OUT.exists():
        raise RuntimeError("alpha3.18B preregistration already exists; refusing overwrite")
    frozen = preflight()
    sources, requests = frozen["sources"], frozen["requests"]
    OUT.mkdir()
    write("root_verification.json", {"alpha3_18a6_root_sha256": A6_ROOT,
        "quality_protocol_v2_sha256": QUALITY_SHA,
        "builder_protocol_v2_sha256": BUILDER_SHA,
        "builder_output_schema_v2_sha256": SCHEMA_SHA,
        "all_verified_before_preregistration_write": True,
        "historical_assets_modified": False})
    write("construction_source_manifest_v4_verification.json", {"source_manifest": ref(a6.OUT /
        "construction_source_manifest_v4.jsonl"), "source_count": 28,
        "source_order": [row["source_token"] for row in sources],
        "no_replacement_or_topup": True})
    write("builder_request_manifest_v4_verification.json", {"request_manifest": ref(a6.OUT /
        "proposition_builder_v2_request_manifest_v4.jsonl"), "request_count": 28,
        "all_28_request_hashes_verified": True, "all_28_documents_hash_verified": True,
        "all_28_user_prompts_byte_identical_to_frozen_template_rendering": True,
        "source_request_order_identical": True})
    provider = frozen["provider"]
    write("builder_provider_config_verification.json", {"provider_configuration": provider,
        "request_config_28_of_28_equal": True, "temperature_override": False,
        "top_p_override": False, "openai_fallback": False,
        "builder_role": "proposition_pool_builder"})
    write("builder_execution_order_contract.json", {"source": ref(a6.OUT /
        "proposition_builder_v2_request_manifest_v4.jsonl"),
        "exact_order": [{"ordinal": index, "source_token": row["source_token"],
            "request_sha256": row["request_sha256"]} for index, row in enumerate(requests, 1)],
        "reorder_from_output_or_expected_yield": False,
        "fresh_isolated_context_per_source": True})
    write("builder_transport_retry_contract.json", {"provider_policy": ref(BUILDER_DIR /
        "proposition_builder_protocol_v2.json"), "automatic_retry": False,
        "maximum_initial_scientific_inferences_per_source": 1,
        "known_no_inference_transport_retry_enabled": False,
        "retry_after_ambiguous_execution": False,
        "scientific_repair_or_second_opinion": False})
    write("builder_ambiguity_policy.json", {"ambiguous_provider_execution":
        "BUILDER_PROVIDER_EXECUTION_AMBIGUOUS", "action": "STOP_STAGE_IMMEDIATELY",
        "preserve_completed_previous_responses": True,
        "replacement_inference": False, "quality_manifest_derivation": False})
    write("builder_response_validation_contract.json", {"schema": ref(BUILDER_DIR /
        "proposition_builder_output_schema_v2.json"),
        "validator": ref(ROOT / "scripts/search_plan_v24_alpha318b_post_builder_prechecks.py"),
        "order": ["freeze raw provider response", "parse JSON", "closed-shape schema",
            "source_record_token equality", "0..3 cardinality"],
        "zero_candidates_valid": True,
        "schema_invalid_terminal": "BUILDER_RESPONSE_INVALID",
        "schema_invalid_source_reinferred": False,
        "later_sources_continue_if_completed_inference_unambiguous": True})
    write("builder_candidate_identity_contract.json", {"source": ref(BUILDER_DIR /
        "candidate_identity_contract.json"),
        "implementation": ref(ROOT / "scripts/search_plan_v24_alpha317c_reconcile_builder_offline.py"),
        "candidate_id": "pcv2_ + SHA256(canonical JSON [PropositionBuilderProtocolV2, opaque source token, SHA256(canonical candidate JSON)])",
        "candidate_array_position_is_not_identity": True,
        "hash_collision": "FAIL_CLOSED"})
    write("builder_exact_dedup_contract.json", {"source": ref(BUILDER_DIR /
        "within_source_exact_dedup_policy.json"),
        "implementation": ref(ROOT / "scripts/search_plan_v24_alpha317c_reconcile_builder_offline.py"),
        "same_source_exact_canonical_candidate_payload_only": True,
        "original_positions_private_provenance": True,
        "canonical_storage_order": "candidate payload SHA-256 then candidate ID",
        "semantic_near_duplicate_elimination_here": False})
    write("builder_grounding_precheck_contract.json", {"source": ref(BUILDER_DIR /
        "candidate_evidence_grounding_contract.json"),
        "body_only_amendment": ref(a6.base.prior.AMEND / "builder_grounding_reference_contract.json"),
        "implementation": ref(ROOT / "scripts/search_plan_v24_alpha318a1_source_contracts.py"),
        "precheck_helper": ref(ROOT / "scripts/search_plan_v24_alpha318b_post_builder_prechecks.py"),
        "candidate_specific_body_offsets_exact_text": True,
        "private_anchor_id_attached_by_controller": True,
        "invalid_reference_excluded_without_repair": True,
        "semantic_support_judgment_deferred_to_quality": True})
    write("builder_leakage_execution_contract.json", {"source": ref(LEAKAGE_DIR /
        "leakage_audit_implementation_contract.json"),
        "implementation": ref(ROOT / "scripts/search_plan_v24_alpha317a_safety_audits.py"),
        "sentence_and_stage_helper": ref(ROOT / "scripts/search_plan_v24_alpha318b_post_builder_prechecks.py"),
        "shared_consecutive_tokens_failure_threshold": 8,
        "qualifying_token_jaccard_failure_threshold": 0.80,
        "private_title_and_containing_evidence_sentence": True,
        "ambiguous_sentence_boundary_uses_entire_field": True,
        "failure_state": "LEXICAL_LEAKAGE_FAILED", "no_repair": True})
    write("builder_terminal_state_contract.json", {"terminal_states": [
        "BUILDER_VALID_ZERO", "BUILDER_VALID_NONZERO", "BUILDER_RESPONSE_INVALID",
        "BUILDER_TRANSPORT_KNOWN_NO_INFERENCE_FAILURE"],
        "provider_ambiguous_execution": "STAGE_STOP_NOT_SOURCE_TERMINAL",
        "schema_invalid_does_not_stop_later_sources": True,
        "exactly_one_source_terminal_state_if_nonambiguous": True})
    write("builder_output_freeze_barrier.json", {"source": ref(QUALITY_DIR /
        "builder_output_freeze_barrier.json"),
        "before_any_quality_manifest": ["all 28 builder identities terminal unless ambiguous stage stop",
            "all raw outputs immutable", "all schemas validated", "candidate IDs frozen",
            "exact within-source duplicates collapsed", "BODY grounding references checked",
            "lexical leakage states frozen"],
        "builder_calls_after_barrier": False})
    write("quality_source_grouping_contract.json", {"source": ref(QUALITY_DIR /
        "one_source_per_quality_call_contract.json"),
        "grouping": "one original source with one to three surviving prechecked candidates",
        "cross_source_mixing": False,
        "zero_survivor_source_quality_call": False,
        "source_group_id_function": ref(ROOT /
            "scripts/search_plan_v24_alpha317d_preregister_quality_v2_offline.py")})
    write("quality_call_budget_contract.json", {"source": ref(QUALITY_DIR /
        "quality_call_budget_formula.json"),
        "formula": "count sources with >=1 quality-adjudication-input candidate after deterministic prechecks",
        "maximum_future_quality_calls": 28,
        "actual_quality_call_count_not_yet_known": True,
        "candidate_count_does_not_multiply_calls": True})
    quality_refs = {name: ref(QUALITY_DIR / name) for name in (
        "quality_provider_config.json", "proposition_quality_adjudication_v2_schema.json",
        "quality_adjudicator_system_prompt.txt", "quality_adjudicator_user_prompt_template.txt",
        "quality_machine_output_contract.json", "quality_source_context_contract.json")}
    write("quality_request_construction_contract.json", {"quality_protocol_root_sha256": QUALITY_SHA,
        "frozen_files": quality_refs,
        "builder_to_quality_helper": ref(ROOT / "scripts/search_plan_v24_alpha318b_post_builder_prechecks.py"),
        "candidate_evidence": "exact BODY span plus up to 240 code points each side in same frozen body",
        "candidate_packets_canonical_payload_sha256_then_candidate_id_order": True,
        "quality_model_calls_in_this_stage": 0})
    write("quality_payload_firewall_contract.json", {"source": ref(QUALITY_DIR /
        "quality_payload_blinding_audit_contract.json"),
        "frozen_audit": ref(ROOT /
            "scripts/search_plan_v24_alpha317d_preregister_quality_v2_offline.py"),
        "private_jats_identity_extraction": ref(ROOT /
            "scripts/search_plan_v24_alpha318b_post_builder_prechecks.py"),
        "all_28_private_front_matter_identities_locally_extractable": True,
        "private_source_token_and_anchor_id_exposed": False,
        "on_identity_match": "STOP_BEFORE_QUALITY_MODEL_CALL_NO_REDACTION"})
    write("quality_manifest_freeze_barrier.json", {"source": ref(QUALITY_DIR /
        "quality_request_manifest_freeze_barrier.json"),
        "all_builder_outputs_frozen_first": True,
        "all_quality_payloads_and_hashes_frozen_before_first_quality_call": True,
        "quality_calls_this_stage": 0,
        "dynamic_quality_request_after_first_call": False})
    write("pool_size_claim_boundary.json", {"construction_sources": 28,
        "theoretical_final_at_most_one_per_source_pool_maximum": 28,
        "preferred_historical_36_to_48_not_a_topup_quota": True,
        "builder_outputs_are_not_quality_eligible_pool": True,
        "final_quality_and_duplicate_selection_deferred": True,
        "source_topup_allowed": False})
    manifest = {"schema_version": "Alpha318BBuilderExecutionManifestV1",
        "status": "EXECUTABLE_OFFLINE_PREREGISTRATION_FROZEN",
        "authoritative_root_alpha3_18a6_sha256": A6_ROOT,
        "construction_source_manifest_v4": ref(a6.OUT / "construction_source_manifest_v4.jsonl"),
        "builder_request_manifest_v4": ref(a6.OUT / "proposition_builder_v2_request_manifest_v4.jsonl"),
        "builder_protocol_v2": ref(BUILDER_DIR / "proposition_builder_protocol_v2.json"),
        "builder_output_schema_v2": ref(BUILDER_DIR / "proposition_builder_output_schema_v2.json"),
        "quality_protocol_v2_root_sha256": QUALITY_SHA,
        "quality_protocol_files": [ref(QUALITY_DIR / name) for name in QUALITY_PROTOCOL_FILES],
        "provider_configuration": provider,
        "planned_builder_source_identities": 28,
        "planned_builder_request_count": 28,
        "execution_order": [{"ordinal": index, "source_token": row["source_token"],
            "request_sha256": row["request_sha256"]} for index, row in enumerate(requests, 1)],
        "frozen_execution_contracts": {name: ref(OUT / name) for name in (
            "builder_execution_order_contract.json", "builder_transport_retry_contract.json",
            "builder_ambiguity_policy.json", "builder_response_validation_contract.json",
            "builder_candidate_identity_contract.json", "builder_exact_dedup_contract.json",
            "builder_grounding_precheck_contract.json", "builder_leakage_execution_contract.json",
            "builder_terminal_state_contract.json", "builder_output_freeze_barrier.json",
            "quality_source_grouping_contract.json", "quality_call_budget_contract.json",
            "quality_request_construction_contract.json", "quality_payload_firewall_contract.json",
            "quality_manifest_freeze_barrier.json", "pool_size_claim_boundary.json")},
        "deterministic_post_builder_implementation": ref(ROOT /
            "scripts/search_plan_v24_alpha318b_post_builder_prechecks.py"),
        "required_execution_outputs": REQUIRED_EXECUTION_OUTPUTS,
        "phase_barriers": ["all Builder raw outputs/schema/ID/dedup/grounding/leakage frozen",
            "quality source groups and request manifest frozen", "no Quality calls in alpha3.18B"],
        "future_network_scope": "DeepSeek BuilderProtocolV2 only; no NCBI or OpenAI",
        "material_runtime_policy_unresolved_count": 0,
        "future_execution_requires_separate_exact_28_call_authorization": True,
        "network_calls_in_this_preregistration": 0,
        "provider_calls_in_this_preregistration": 0}
    write("alpha3_18b_builder_execution_manifest.json", manifest)
    manifest_sha = digest(OUT / "alpha3_18b_builder_execution_manifest.json")
    marker("alpha3_18b_builder_execution_manifest_sha256", manifest_sha)
    write("scientific_state_safety_audit.json", {"provider_calls": 0, "llm_calls": 0,
        "network_calls": 0, "builder_calls": 0, "quality_calls": 0,
        "heldout_selection": False, "source_topup": False,
        "historical_assets_modified": False})
    write("validation.json", {"status": "PASS", "construction_source_manifest_v4_verified": True,
        "builder_request_manifest_v4_verified": True,
        "planned_builder_source_identities": 28, "planned_builder_request_count": 28,
        "one_source_per_builder_call": True, "builder_candidate_cardinality": "0_TO_3",
        "builder_ranking_allowed": False, "builder_preferred_candidate_allowed": False,
        "builder_execution_order_frozen": True,
        "builder_scientific_repair_calls_allowed": False,
        "ambiguous_provider_execution_stops_stage": True,
        "schema_invalid_response_reinferred": False,
        "candidate_identity_deterministic": True,
        "candidate_array_order_semantically_meaningless": True,
        "exact_within_source_dedup_frozen": True,
        "grounding_reference_precheck_frozen": True,
        "leakage_gate_frozen": True,
        "all_builder_outputs_before_quality_manifest": True,
        "quality_call_budget_derived_after_builder": True,
        "maximum_future_quality_calls": 28,
        "quality_manifest_before_quality_calls": True,
        "source_topup_allowed": False,
        "material_runtime_policy_unresolved_count": 0,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0})
    write("summary.json", {"status": "completed", "planned_builder_source_identities": 28,
        "planned_builder_request_count": 28,
        "provider": provider["provider"], "model": provider["model"],
        "maximum_future_quality_calls": 28,
        "actual_quality_call_count": None,
        "alpha3_18b_builder_execution_manifest_sha256": manifest_sha,
        "next_stage_recommendation": "AUTHORIZE_EXACT_28_ALPHA3_18B_BUILDER_CALLS"})
    root = a6.base.prior.all_file_root(OUT, ROOT_MARKER)
    marker(ROOT_MARKER, root)
    print(json.dumps({"status": "completed", "root_sha256": root,
        "manifest_sha256": manifest_sha, "planned_builder_calls": 28,
        "provider_calls": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
