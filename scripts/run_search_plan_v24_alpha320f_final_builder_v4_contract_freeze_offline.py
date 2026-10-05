#!/usr/bin/env python3
"""Freeze the selected Builder V4 development contract without inference."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from scripts import run_search_plan_v24_alpha320e2_replication_unblind_aggregate_select_offline as e2


ROOT = e2.ROOT
RUNS = ROOT / "runs"
MASTER = RUNS / "20261002_search_plan_v24_dev_alpha3_20_post_alpha3_19_development_master_preregistration_offline"
A = RUNS / "20261002_search_plan_v24_dev_alpha3_20a_evidence_reference_v4_offline_validation"
B = RUNS / "20261002_search_plan_v24_dev_alpha3_20b_proposition_abstraction_prompt_freeze_offline"
D = RUNS / "20261003_search_plan_v24_dev_alpha3_20d_deterministic_variant_evaluation_offline"
E2 = e2.OUT
OUT = RUNS / "20261004_search_plan_v24_dev_alpha3_20f_final_builder_v4_contract_freeze_offline"
ROOT_MARKER = "search_plan_v24_dev_alpha3_20f_sha256"
ROOTS = (
    (MASTER, "search_plan_v24_dev_alpha3_20_master_prereg_sha256",
     "8a8edb619c2ad2a31e4b0f6398ae43e3d05de74ae31baddeb611b0cd3e0cd3e6"),
    (A, "search_plan_v24_dev_alpha3_20a_sha256",
     "ecc4549aca4329ac3a910fc933f070333175ec2aa2c0fc728cd1279d9e274364"),
    (B, "search_plan_v24_dev_alpha3_20b_sha256",
     "0c5e11b5e53acda51250fca80a544e39fda06c40e9ac2bff138d96ae7cf42e2d"),
    (D, "search_plan_v24_dev_alpha3_20d_sha256",
     "d6d9b66627fe193d7925333c0c7dd32553465611c11b095075fb84cc75c95e84"),
    (E2, e2.ROOT_MARKER,
     "bf8401301bf21ccfe0c23eee26cb7814a222773907ea83e6b31deacfc602729d"),
)
PROMPT_SHA = "6af5b7f3cd8b23cc65e4ee9c3e85eb955d760f7f06e88a48722be213454d7592"
SCHEMA_SHA = "e6b65571708d196b9fb7a4b8c4af71f46e8680b4b078a6ebedd9ece28658f1c1"
GROUNDING_SHA = "429a11294f1df2c40564f4249ea9f54ce637824cbca13d3450b7afef83c4717b"
EVIDENCE_SHA = "156424459bd499272f6dba5a466216ffbe72fe96039045ae8bc44dd7b40b5612"
ABSTRACTION_SHA = "5ab84eebd9fb8b6a4d7d7600869c5860aa19fbd815ad6dc4c139a6332550fc99"
CLASSIFICATION = "FINAL_BUILDER_V4_CONTRACT_FROZEN_WITH_V1_RELATION_SENTENCE"
NEXT = "PREREGISTER_NEXT_FRESH_PRIMARY_ATTEMPT_WITH_FROZEN_BUILDER_V4"


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RuntimeError(reason)


def canonical(value: object) -> bytes:
    return e2.r.canonical(value)


def digest(path: Path) -> str:
    return e2.r.digest(path)


def obj(path: Path) -> dict:
    return e2.r.obj(path)


def ref(path: Path, role: str, stage: str) -> dict:
    return {"artifact_role": role,
            "artifact_path": str(path.relative_to(ROOT)),
            "sha256": digest(path),
            "authority_source_stage": stage,
            "immutable_frozen": True}


def put(name: str, value: object) -> str:
    raw = canonical(value) + b"\n"
    path = OUT / name
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return e2.r.sha(raw)


def marker(name: str, value: str) -> None:
    with (OUT / name).open("xb") as handle:
        handle.write((value + "\n").encode("ascii"))
        handle.flush()
        os.fsync(handle.fileno())


def preflight() -> dict:
    require(not OUT.exists(), "ALPHA320F_OUTPUT_ALREADY_EXISTS")
    for directory, marker_name, expected in ROOTS:
        require((directory / marker_name).read_text().strip() == expected
                and e2.r.e.d.c.root_hash(directory, marker_name) == expected,
                "UPSTREAM_ROOT_MISMATCH:" + marker_name)
    e2_validation = obj(E2 / "validation.json")
    require(e2_validation["alpha3_20e2_classification"] ==
                "SEMANTIC_SELECTION_COMPLETE_TIE_LEXICAL_BREAKS_TO_V1"
            and e2_validation["semantic_comparison_state"] == "SEMANTIC_TIE"
            and e2_validation["deterministic_selection_recommendation"] == "V1"
            and e2_validation["v1_semantic_pass_count"] == 41
            and e2_validation["v1_semantic_fail_count"] == 1
            and e2_validation["v1_semantic_unresolved_count"] == 0
            and e2_validation["v2_semantic_pass_count"] == 41
            and e2_validation["v2_semantic_fail_count"] == 1
            and e2_validation["v2_semantic_unresolved_count"] == 0
            and e2_validation["v1_frozen_lexical_survivors"] == 39
            and e2_validation["v2_frozen_lexical_survivors"] == 37
            and e2_validation["lexical_result_used_for_selection"] is True
            and e2_validation["e1_judgments_used_for_selection"] is False
            and e2_validation["v3_used_for_selection"] is False,
            "E2_SELECTION_AUTHORITY_MISMATCH")
    expected_files = (
        (B / "prompt_variant_1_full_template.txt", PROMPT_SHA,
         B / "prompt_variant_1_sha256"),
        (B / "builder_output_schema_v4.json", SCHEMA_SHA,
         B / "builder_output_schema_v4_sha256"),
        (B / "builder_grounding_contract_v4.json", GROUNDING_SHA,
         B / "builder_grounding_contract_v4_sha256"),
        (MASTER / "evidence_reference_contract_v4.json", EVIDENCE_SHA,
         MASTER / "evidence_reference_contract_v4_sha256"),
        (MASTER / "proposition_abstraction_contract_v1.json", ABSTRACTION_SHA,
         MASTER / "proposition_abstraction_contract_v1_sha256"),
    )
    require(all(digest(path) == expected
                and marker_path.read_text().strip() == expected
                for path, expected, marker_path in expected_files),
            "AUTHORITATIVE_COMPONENT_HASH_MISMATCH")
    selected_prompt = (B / "prompt_variant_1_full_template.txt").read_bytes()
    require(not any(term in selected_prompt.lower() for term in
                    (b"8-token", b"jaccard", b"0.80", b"detector avoidance",
                     b"leakage survivor")),
            "SELECTED_PROMPT_EXPOSES_LEAKAGE_RULE")
    schema = obj(B / "builder_output_schema_v4.json")
    grounding = obj(B / "builder_grounding_contract_v4.json")
    evidence = obj(MASTER / "evidence_reference_contract_v4.json")
    abstraction = obj(MASTER / "proposition_abstraction_contract_v1.json")
    ownership = obj(B / "builder_v4_model_controller_ownership_matrix.json")
    firewall = obj(B / "builder_v4_source_identity_firewall.json")
    leakage = obj(B / "leakage_policy_preservation.json")
    runtime = obj(B / "alpha3_20c_runtime_policy.json")
    design = obj(MASTER / "builder_v4_design_constraints.json")
    require(schema["candidate_cardinality"] == {"minimum": 0, "maximum": 3}
            and schema["schema"]["properties"]["candidates"]["minItems"] == 0
            and schema["schema"]["properties"]["candidates"]["maxItems"] == 3
            and grounding["fuzzy_or_semantic_rescue_allowed"] is False
            and grounding["model_owned_evidence"] ==
                "exact verbatim canonical BODY quote"
            and evidence["model_supplied_offsets_or_paragraph_or_anchor_ids"]
                is False
            and evidence["semantic_or_fuzzy_localization"] is False
            and abstraction["scientific_fidelity_precedence_over_lexical_novelty"]
                is True
            and ownership["model_generated_offsets_required"] is False
            and ownership["candidate_evidence_and_proposition_separate"] is True
            and firewall["variant_id_controller_only"] is True
            and firewall["private_filesystem_path_or_source_mapping_exposed"]
                is False
            and leakage["candidate_side"] == "neutral_proposition only"
            and leakage["eight_consecutive_shared_token_failure_threshold"]
                == 8
            and leakage["qualifying_token_jaccard_failure_threshold"] == 0.8
            and leakage["thresholds_changed"] is False
            and leakage["comparison_policy_changed"] is False
            and leakage["thresholds_exposed_to_model"] is False
            and runtime["provider"] == "DeepSeek"
            and runtime["model"] == "deepseek-flash"
            and runtime["thinking"] == {"type": "enabled"}
            and runtime["reasoning_effort"] == "high"
            and runtime["automatic_retry"] is False
            and runtime["known_no_inference_transport_retry_enabled"] is False
            and runtime["completed_schema_invalid_action"] ==
                "COUNT_INFERENCE_RECORD_INVALID_NO_SCIENTIFIC_RETRY"
            and design["candidate_cardinality_per_request"] ==
                {"minimum": 0, "maximum": 3},
            "FROZEN_BUILDER_V4_POLICY_MISMATCH")
    d_validation = obj(D / "validation.json")
    require(d_validation["raw_candidate_count"] == 126
            and [d_validation["per_variant"][v]["grounding_success_count"]
                 for v in ("V1", "V2", "V3")] == [42, 42, 41]
            and [d_validation["per_variant"][v]["nonleakage_eligible"]
                 for v in ("V1", "V2", "V3")] == [True, True, False]
            and [d_validation["per_variant"][v]["leakage_survivor_count"]
                 for v in ("V1", "V2")] == [39, 37],
            "ALPHA320D_DETERMINISTIC_FACT_MISMATCH")
    a_validation = obj(A / "validation.json")
    require(a_validation["v4_unique_exact_localization_success"] == 35
            and a_validation["development_candidate_count"] == 35
            and a_validation["historical_candidate_states_modified"] is False,
            "ALPHA320A_GROUNDING_REPLAY_FACT_MISMATCH")
    return {"e2_validation": e2_validation,
            "d_validation": d_validation,
            "a_validation": a_validation,
            "runtime": runtime,
            "leakage": leakage,
            "ownership": ownership,
            "firewall": firewall}


def freeze(state: dict) -> dict:
    OUT.mkdir()
    root_names = {"alpha3_20e2_root_verification.json": ROOTS[4],
                  "alpha3_20d_root_verification.json": ROOTS[3],
                  "alpha3_20b_root_verification.json": ROOTS[2],
                  "alpha3_20a_root_verification.json": ROOTS[1],
                  "alpha3_20_master_root_verification.json": ROOTS[0]}
    for output, (_, marker_name, value) in root_names.items():
        put(output, {"verified": True,
                     "root_marker": marker_name, "sha256": value})
    put("final_variant_selection_authority.json", {
        "selected_abstraction_variant": "V1",
        "selected_abstraction_mode": "relation_sentence",
        "selection_authority": ref(E2 /
            "development_variant_selection_recommendation.json",
            "development_variant_selection", "alpha3.20E2"),
        "e2_root_sha256": ROOTS[4][2],
        "classification": state["e2_validation"]["alpha3_20e2_classification"],
        "not_scientific_superiority_claim": True})
    put("final_variant_selection_provenance.json", {
        "semantic_v1": {"pass": 41, "fail": 1, "unresolved": 0,
                        "denominator": 42, "vector_fail_unresolved": [1, 0]},
        "semantic_v2": {"pass": 41, "fail": 1, "unresolved": 0,
                        "denominator": 42, "vector_fail_unresolved": [1, 0]},
        "semantic_comparison": "SEMANTIC_TIE",
        "lexical_tie_breaker": {"v1_survivors": 39,
                                "v2_survivors": 37, "denominator_each": 42},
        "selected_development_variant": "V1",
        "selection_basis": "preregistered lexical tie breaker after semantic tie",
        "v1_scientifically_superior_claim": False})
    put("e1_quarantine_final_binding.json", {
        "state": "SEEN_DEVELOPMENT_INCOMPLETE_EXPERIMENT_NOT_SELECTION_ELIGIBLE",
        "e1_judgments_used_for_final_selection": False,
        "selection_scientific_authority": "complete E1R1 replication only",
        "incomplete_e1_branch_preserved": True})
    put("v3_exclusion_final_binding.json", {
        "v3_used_for_final_selection": False,
        "v3_nonleakage_eligible": False,
        "authority": ref(D / "variant_nonleakage_eligibility.json",
                         "v3_exclusion", "alpha3.20D"),
        "v3_prompt_preserved_as_development_history": True})
    source_prompt = B / "prompt_variant_1_full_template.txt"
    final_prompt = OUT / "final_selected_builder_v4_prompt.txt"
    require(digest(source_prompt) == PROMPT_SHA,
            "SELECTED_PROMPT_CHANGED_BEFORE_COPY")
    with source_prompt.open("rb") as src, final_prompt.open("xb") as dst:
        shutil.copyfileobj(src, dst)
        dst.flush()
        os.fsync(dst.fileno())
    final_prompt_sha = digest(final_prompt)
    require(final_prompt_sha == PROMPT_SHA
            and final_prompt.read_bytes() == source_prompt.read_bytes(),
            "SELECTED_PROMPT_BYTE_IDENTITY_FAILURE")
    marker("final_selected_builder_v4_prompt_sha256", final_prompt_sha)
    put("final_selected_prompt_byte_identity_audit.json", {
        "alpha3_20b_v1_prompt": ref(source_prompt, "selected_v1_prompt_source",
                                   "alpha3.20B"),
        "final_prompt": ref(final_prompt, "final_selected_prompt",
                            "alpha3.20F"),
        "byte_identical": True,
        "scientific_wording_modified": False,
        "line_endings_modified": False})
    bindings = (
        ("final_builder_output_schema_v4_binding.json",
         B / "builder_output_schema_v4.json", SCHEMA_SHA,
         "builder_output_schema_v4", "alpha3.20B"),
        ("final_evidence_reference_contract_v4_binding.json",
         MASTER / "evidence_reference_contract_v4.json", EVIDENCE_SHA,
         "evidence_reference_contract_v4", "alpha3.20 master"),
        ("final_builder_grounding_contract_v4_binding.json",
         B / "builder_grounding_contract_v4.json", GROUNDING_SHA,
         "builder_grounding_contract_v4", "alpha3.20B"),
        ("final_proposition_abstraction_contract_binding.json",
         MASTER / "proposition_abstraction_contract_v1.json", ABSTRACTION_SHA,
         "proposition_abstraction_contract_v1", "alpha3.20 master"),
    )
    for output, path, expected, role, stage in bindings:
        require(digest(path) == expected,
                "CONTRACT_COMPONENT_CHANGED:" + role)
        put(output, {"component": ref(path, role, stage),
                     "unchanged": True})
    put("final_builder_v4_model_controller_ownership.json", {
        "frozen_authority": ref(B /
            "builder_v4_model_controller_ownership_matrix.json",
            "model_controller_ownership", "alpha3.20B"),
        "controller_owned_coordinates": True,
        "model_generated_offsets_required": False,
        "exact_body_quote_model_owned": True,
        "candidate_evidence_and_proposition_separate": True})
    put("final_builder_v4_candidate_cardinality.json", {
        "frozen_authority": ref(MASTER / "builder_v4_design_constraints.json",
            "candidate_cardinality", "alpha3.20 master"),
        "minimum": 0, "maximum": 3,
        "zero_candidates_valid": True})
    put("final_builder_v4_source_identity_firewall.json", {
        "frozen_authority": ref(B / "builder_v4_source_identity_firewall.json",
            "source_identity_firewall", "alpha3.20B"),
        "opaque_response_binding_handle": "source_record_token",
        "pmid_pmcid_doi_authors_journal_paths_added_by_controller": False,
        "private_source_mapping_exposed_to_model": False})
    leakage_ref = ref(B / "leakage_policy_preservation.json",
                      "lexical_leakage_policy", "alpha3.20B")
    put("final_builder_v4_leakage_policy_binding.json", {
        "frozen_authority": leakage_ref,
        "master_policy": ref(MASTER / "leakage_policy_preservation.json",
            "lexical_leakage_master_policy", "alpha3.20 master"),
        "thresholds_changed": False,
        "comparison_policy_changed": False,
        "thresholds_exposed_to_model": False,
        "candidate_side": "neutral_proposition only",
        "evidence_quote_concatenated_candidate_side": False})
    runtime_ref = ref(B / "alpha3_20c_runtime_policy.json",
                      "builder_v4_runtime_policy", "alpha3.20B")
    put("final_builder_v4_runtime_policy_binding.json", {
        "frozen_authority": runtime_ref,
        "provider": "DeepSeek", "model": "deepseek-flash",
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
        "other_parameters_from_frozen_authority": True,
        "provider_calls_in_alpha3_20f": 0})
    retry_ref = state["runtime"]["historical_transport_retry_contract"]
    require(digest(ROOT / retry_ref["path"]) == retry_ref["sha256"],
            "FROZEN_TRANSPORT_RETRY_AUTHORITY_CHANGED")
    put("final_builder_v4_retry_policy.json", {
        "runtime_policy": runtime_ref,
        "historical_transport_retry_contract": retry_ref,
        "one_scientific_inference_per_frozen_request": True,
        "technical_retry_only_if_no_inference_deterministically_known": True,
        "completed_invalid_response_counts_inference": True,
        "completed_invalid_response_scientific_retry": False})
    postprocessing = {
        "stage_order": [
            "response_and_schema_validation",
            "opaque_source_token_response_binding",
            "candidate_extraction",
            "v4_exact_body_evidence_localization",
            "structural_completeness_check",
            "lexical_leakage_evaluation"],
        "builder_response_implementation": ref(ROOT /
            "scripts/run_search_plan_v24_alpha320c_builder_v4_execution.py",
            "builder_response_processing_implementation", "alpha3.20C"),
        "structural_completeness_contract": ref(B /
            "structural_completeness_contract.json",
            "structural_completeness_contract", "alpha3.20B"),
        "lexical_leakage_execution_contract": ref(RUNS /
            "20261001_search_plan_v24_dev_alpha3_18b_builder_execution_preregistration_offline/builder_leakage_execution_contract.json",
            "frozen_lexical_leakage_execution_contract", "alpha3.18B"),
        "localizer_implementation": state["runtime"].get(
            "localizer_implementation") or obj(B /
                "builder_grounding_contract_v4.json")["localizer_implementation"],
        "deterministic_evaluation_implementation": ref(ROOT /
            "scripts/run_search_plan_v24_alpha320d_deterministic_variant_evaluation_offline.py",
            "deterministic_postprocessing_implementation", "alpha3.20D"),
        "gate_order_changed": False,
        "no_fuzzy_rescue": True}
    localizer_ref = postprocessing["localizer_implementation"]
    require(digest(ROOT / localizer_ref["path"]) == localizer_ref["sha256"],
            "FROZEN_LOCALIZER_IMPLEMENTATION_CHANGED")
    put("final_builder_v4_postprocessing_order.json", postprocessing)
    components = [
        ref(final_prompt, "selected_v1_full_prompt", "alpha3.20B physical copy in F"),
        ref(B / "builder_output_schema_v4.json", "builder_output_schema_v4",
            "alpha3.20B"),
        ref(MASTER / "evidence_reference_contract_v4.json",
            "evidence_reference_contract_v4", "alpha3.20 master"),
        ref(B / "builder_grounding_contract_v4.json",
            "builder_grounding_contract_v4", "alpha3.20B"),
        ref(MASTER / "proposition_abstraction_contract_v1.json",
            "proposition_abstraction_contract_v1", "alpha3.20 master"),
        ref(B / "builder_v4_model_controller_ownership_matrix.json",
            "model_controller_ownership", "alpha3.20B"),
        ref(MASTER / "builder_v4_design_constraints.json",
            "candidate_cardinality", "alpha3.20 master"),
        ref(B / "builder_v4_source_identity_firewall.json",
            "source_identity_firewall", "alpha3.20B"),
        leakage_ref,
        runtime_ref,
        ref(OUT / "final_builder_v4_retry_policy.json",
            "retry_policy_binding", "alpha3.20F"),
        ref(OUT / "final_builder_v4_postprocessing_order.json",
            "deterministic_postprocessing_order", "alpha3.20F"),
    ]
    require(len({item["artifact_role"] for item in components}) ==
            len(components), "AMBIGUOUS_DUPLICATE_COMPONENT_AUTHORITY")
    put("final_contract_integrity_manifest.json", {
        "schema_version": "BuilderV4FinalContractIntegrityManifest",
        "components": components,
        "ambiguous_duplicate_authorities": False})
    contract = {
        "schema_version": "SearchPlanBuilderV4FinalContract",
        "selected_abstraction_variant": "V1",
        "selected_abstraction_mode": "relation_sentence",
        "builder_v4_contract_status": "FROZEN_FOR_NEXT_FRESH_PRIMARY_ATTEMPT",
        "builder_v4_contract_origin": "SEEN_DATA_DEVELOPMENT_SELECTION",
        "components": components,
        "model_visible_request_must_not_include_development_results": True,
        "source_identity_firewall_preserved": True,
        "scientific_fidelity_precedes_lexical_novelty": True,
        "fresh_primary_attempt_started": False}
    contract_sha = put("search_plan_builder_v4_final_contract.json", contract)
    marker("search_plan_builder_v4_final_contract_sha256", contract_sha)
    bundle = {
        "schema_version": "BuilderV4ProspectiveReproducibilityBundle",
        "final_contract": ref(OUT / "search_plan_builder_v4_final_contract.json",
            "final_composite_contract", "alpha3.20F"),
        "selected_prompt": components[0],
        "component_sha256_by_role": {item["artifact_role"]: item["sha256"]
                                      for item in components},
        "runtime_provider": "DeepSeek",
        "runtime_model": "deepseek-flash",
        "model_visible_development_results": False,
        "new_requests_generated_here": False}
    bundle_sha = put("builder_v4_reproducibility_bundle.json", bundle)
    marker("builder_v4_reproducibility_bundle_sha256", bundle_sha)
    put("development_selection_rationale.json", {
        "source": ref(E2 / "variant_selection_rule_execution.json",
            "development_selection_provenance", "alpha3.20E2"),
        "semantic_comparison": "SEMANTIC_TIE",
        "v1_vector_fail_unresolved": [1, 0],
        "v2_vector_fail_unresolved": [1, 0],
        "lexical_tie_breaker": {"v1": [39, 42], "v2": [37, 42]},
        "selected_development_variant": "V1",
        "scientific_superiority_claim": False})
    put("development_runtime_separation_audit.json", {
        "development_rationale_path": str((OUT /
            "development_selection_rationale.json").relative_to(ROOT)),
        "rationale_not_in_model_visible_prompt": True,
        "rationale_not_in_reproducibility_bundle": True,
        "semantic_and_lexical_outcomes_not_in_runtime_request_specification": True})
    put("historical_variant_preservation_audit.json", {
        "v2_prompt": ref(B / "prompt_variant_2_full_template.txt",
            "unselected_development_prompt_v2", "alpha3.20B"),
        "v3_prompt": ref(B / "prompt_variant_3_full_template.txt",
            "unselected_development_prompt_v3", "alpha3.20B"),
        "v2_or_v3_prompt_modified": False,
        "v2_or_v3_wording_in_selected_prompt": False,
        "historical_variants_invalid_science_labelled": False})
    put("historical_builder_v3_preservation_audit.json", {
        "alpha3_19_builder_v3_history_modified": False,
        "historical_v3_schema_or_prompt_overwritten": False,
        "alpha3_19g_root": ref(RUNS /
            "20261002_search_plan_v24_dev_alpha3_19g_primary_attempt_closure_offline/search_plan_v24_dev_alpha3_19g_sha256",
            "historical_builder_v3_closure_root_marker", "alpha3.19G")})
    put("alpha3_20_complete_inference_accounting.json", {
        "alpha3_18_builder": 56, "alpha3_18_quality": 1,
        "alpha3_19_builder": 14, "alpha3_19_quality": 0,
        "alpha3_20c_builder": 42,
        "alpha3_20e1_semantic_adjudication": 28,
        "alpha3_20e1r1_replication_semantic_adjudication": 28,
        "alpha3_20f_new_inference_events": 0,
        "provider_calls": 0, "deepseek_calls": 0,
        "llm_calls": 0, "network_calls": 0,
        "builder_calls": 0, "quality_calls": 0})
    closure = {
        "schema_version": "Alpha3_20DevelopmentClosureManifest",
        "classification":
            "POST_ALPHA3_19_SEEN_DATA_DEVELOPMENT_FINAL_BUILDER_V4_CONTRACT_FREEZE",
        "grounding_v4_development": {"historical_35_exact_quotes_localized": 35,
            "historical_alpha3_19_outcomes_mutated": False,
            "alpha3_20a_root_sha256": ROOTS[1][2]},
        "three_variant_builder_development": {"builder_inferences": 42,
            "raw_candidates": 126,
            "grounding_by_variant": {"V1": [42, 42], "V2": [42, 42],
                                     "V3": [41, 42]},
            "v1_v2_nonleakage_eligible": True,
            "v3_nonleakage_eligible": False,
            "alpha3_20b_root_sha256": ROOTS[2][2],
            "alpha3_20d_root_sha256": ROOTS[3][2]},
        "first_semantic_experiment": {"inference_events": 28,
            "valid_groups": 27, "malformed_completed_groups": 1,
            "selection_eligible": False,
            "quarantine_state":
                "SEEN_DEVELOPMENT_INCOMPLETE_EXPERIMENT_NOT_SELECTION_ELIGIBLE"},
        "full_blinded_replication": {"inference_events": 28,
            "valid_groups": 28, "candidate_judgment_sets": 84,
            "selection_eligible": True},
        "replication_selection": {"v1_semantic": [41, 1, 0],
            "v2_semantic": [41, 1, 0],
            "semantic_comparison": "SEMANTIC_TIE",
            "lexical_tie_breaker": {"v1": [39, 42], "v2": [37, 42]},
            "selected_development_variant": "V1",
            "e2_root_sha256": ROOTS[4][2]},
        "final_builder_v4_contract_sha256": contract_sha,
        "final_reproducibility_bundle_sha256": bundle_sha,
        "fresh_primary_attempt_started": False,
        "fresh_performance_claim": False}
    closure_sha = put("alpha3_20_development_closure_manifest.json", closure)
    marker("alpha3_20_development_closure_manifest_sha256", closure_sha)
    put("fresh_primary_attempt_not_started_audit.json", {
        "fresh_primary_attempt_started": False,
        "fresh_literature_queries_generated": False,
        "fresh_source_cohort_generated": False,
        "fresh_builder_requests_generated": False,
        "fresh_quality_requests_generated": False})
    put("development_contamination_boundary.json", {
        "final_contract_origin": "SEEN_DATA_DEVELOPMENT_SELECTION",
        "alpha3_20f_new_scientific_sources_used": False,
        "alpha3_20f_new_candidate_contamination": False,
        "future_primary_requires_new_fresh_cohort": True})
    require(all(e2.r.e.d.c.root_hash(directory, name) == expected
                for directory, name, expected in ROOTS),
            "HISTORICAL_ROOT_CHANGED_DURING_FREEZE")
    put("scientific_state_safety_audit.json", {
        "prompt_scientific_wording_changed": False,
        "schema_changed": False,
        "grounding_or_leakage_policy_changed": False,
        "semantic_fail_cases_used_for_tuning": False,
        "e1_judgments_used_for_selection": False,
        "v3_used_for_selection": False,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "builder_calls": 0, "quality_calls": 0})
    put("protocol_compliance_audit.json", {
        "all_required_upstream_roots_verified_before_freeze": True,
        "selected_prompt_byte_identical_to_alpha3_20b_v1": True,
        "authoritative_components_bound_by_hash": True,
        "development_rationale_separate_from_runtime_bundle": True,
        "historical_assets_modified": False,
        "fresh_primary_attempt_started": False,
        "runtime_calls": 0})
    validation = {"status": "completed",
        "alpha3_20f_classification": CLASSIFICATION,
        "alpha3_20e2_root_verified": True,
        "alpha3_20d_root_verified": True,
        "alpha3_20b_root_verified": True,
        "alpha3_20a_root_verified": True,
        "semantic_comparison_state": "SEMANTIC_TIE",
        "development_selection_recommendation": "V1",
        "selected_abstraction_variant": "V1",
        "selected_abstraction_mode": "relation_sentence",
        "final_selected_builder_v4_prompt_sha256": final_prompt_sha,
        "expected_selected_prompt_sha256": PROMPT_SHA,
        "selected_prompt_byte_identical_to_alpha3_20b_v1": True,
        "builder_output_schema_v4_sha256": SCHEMA_SHA,
        "builder_grounding_contract_v4_sha256": GROUNDING_SHA,
        "evidence_reference_contract_v4_sha256": EVIDENCE_SHA,
        "proposition_abstraction_contract_v1_sha256": ABSTRACTION_SHA,
        "candidate_cardinality_min": 0,
        "candidate_cardinality_max": 3,
        "controller_owned_coordinates": True,
        "model_generated_offsets_required": False,
        "exact_body_quote_required": True,
        "fuzzy_grounding_allowed": False,
        "leakage_thresholds_changed": False,
        "leakage_comparison_policy_changed": False,
        "leakage_thresholds_exposed_to_model": False,
        "provider": "DeepSeek", "model": "deepseek-flash",
        "builder_v4_contract_frozen": True,
        "builder_v4_contract_status": "FROZEN_FOR_NEXT_FRESH_PRIMARY_ATTEMPT",
        "builder_v4_contract_origin": "SEEN_DATA_DEVELOPMENT_SELECTION",
        "search_plan_builder_v4_final_contract_sha256": contract_sha,
        "builder_v4_reproducibility_bundle_sha256": bundle_sha,
        "alpha3_20_development_closure_manifest_sha256": closure_sha,
        "e1_judgments_used_for_final_selection": False,
        "v3_used_for_final_selection": False,
        "fresh_primary_attempt_started": False,
        "new_scientific_sources_used": False,
        "provider_calls": 0, "deepseek_calls": 0,
        "llm_calls": 0, "network_calls": 0,
        "builder_calls": 0, "quality_calls": 0,
        "next_stage_recommendation": NEXT,
        "historical_assets_modified": False}
    put("validation.json", validation)
    put("summary.json", {"status": "completed",
        "classification": CLASSIFICATION,
        "selected_abstraction_variant": "V1",
        "builder_v4_contract_status":
            "FROZEN_FOR_NEXT_FRESH_PRIMARY_ATTEMPT",
        "next_stage_recommendation": NEXT})
    root = e2.r.e.d.c.root_hash(OUT, ROOT_MARKER)
    marker(ROOT_MARKER, root)
    return {**validation, "search_plan_v24_dev_alpha3_20f_sha256": root}


def run() -> dict:
    state = preflight()
    return freeze(state)


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
