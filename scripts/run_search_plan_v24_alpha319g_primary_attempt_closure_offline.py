#!/usr/bin/env python3
"""Freeze the alpha3.19 primary-attempt closure without scientific execution."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
OUT = RUNS / "20261002_search_plan_v24_dev_alpha3_19g_primary_attempt_closure_offline"
ROOT_MARKER = "search_plan_v24_dev_alpha3_19g_sha256"
TERMINAL = "TERMINATED_WITH_ZERO_QUALITY_INPUT_UNDER_CONSISTENT_FROZEN_GATES"
NEXT = "DESIGN_POST_ALPHA3_19_DEVELOPMENT_PROTOCOL_BEFORE_NEXT_FRESH_ATTEMPT"

# Historical roots are authority, not values inferred from current result files.
STAGES = {
    "master": ("20261001_search_plan_v24_dev_alpha3_19_fresh_heldout_attempt2_master_preregistration_offline", "search_plan_v24_dev_alpha3_19_master_prereg_sha256", "1cf1d29d67474996a6ee87b518af0f09456e3572a3969b5a5f1b6021009ed73b"),
    "a_failed": ("20261002_search_plan_v24_dev_alpha3_19a_ncbi_only_source_acquisition", "search_plan_v24_dev_alpha3_19a_sha256", "0fb0fb6dba2685a3441c3148e2148d1f65f3c2a95960a6aedb15d7e2b3db03b0"),
    "a1": ("20261002_search_plan_v24_dev_alpha3_19a1_ncbi_esearch_backend_failure_audit_offline", "search_plan_v24_dev_alpha3_19a1_sha256", "05d155650b10556ac173978f69d5f607ab18872676db8e2d9e0d7e1ee340d1a7"),
    "a2": ("20261002_search_plan_v24_dev_alpha3_19a2_full_six_frame_ncbi_restart", "search_plan_v24_dev_alpha3_19a2_sha256", "64b7db6eb803b6464a11876bec2b868eaade5fdcbc7e6eada69a5e675ad7480c"),
    "b": ("20261002_search_plan_v24_dev_alpha3_19b_dedup_seen_source_sampling_offline", "search_plan_v24_dev_alpha3_19b_sha256", "7b409cd2bf35b01f7d511717cafa7f030ca0a0b351ec41a6a7e75cd31f5aa1f8"),
    "c": ("20261002_search_plan_v24_dev_alpha3_19c_pubmed_metadata_eligibility", "search_plan_v24_dev_alpha3_19c_sha256", "922cc952e03bca7e8605971b9dcb6f4acfe3cfbe02e308ca26c9ab37c3a86689"),
    "d": ("20261002_search_plan_v24_dev_alpha3_19d_pmc_oa_jats_construction_eligibility", "search_plan_v24_dev_alpha3_19d_sha256", "422975cb0706f19a6ee2640bc126fc49892d2e220df34b3f6c25c5a57a5b9a33"),
    "d1": ("20261002_search_plan_v24_dev_alpha3_19d1_updateof_resolution_offline", "search_plan_v24_dev_alpha3_19d1_sha256", "2914e34c003aa8aa7a4949e4a276f68fb11b81b3f77f8796a7fb7469f5a0a545"),
    "e": ("20261002_search_plan_v24_dev_alpha3_19e_construction_document_anchor_builder_freeze_offline", "search_plan_v24_dev_alpha3_19e_sha256", "afcc320cc2e0e352d77fdc4370b87f146b63e7f089663b60dac80c570c87bb87"),
    "e1": ("20261002_search_plan_v24_dev_alpha3_19e1_source_token_authority_audit_offline", "search_plan_v24_dev_alpha3_19e1_sha256", "3a13c2d644f6b7ad48d36cb0f4663783d1780dd00341d9b4679262c0335da035"),
    "f": ("20261002_search_plan_v24_dev_alpha3_19f_builder_v3_execution", "search_plan_v24_dev_alpha3_19f_sha256", "e1aad29348c72d323221e799b0c9d897aeae336df753f2e761aa98ea4a993549"),
    "f1": ("20261002_search_plan_v24_dev_alpha3_19f1_zero_quality_input_gate_audit_offline", "search_plan_v24_dev_alpha3_19f1_sha256", "090dd53981166a3a64f46af34376a72fe926d6844dfe85f0d8bd52a7263cfeb3"),
}


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RuntimeError(reason)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_bytes())


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line]


def stage_path(stage: str) -> Path:
    return RUNS / STAGES[stage][0]


def directory_root(directory: Path, marker_name: str) -> str:
    entries = sorted(path for path in directory.rglob("*") if path.is_file()
                     and path.name != marker_name)
    require(not any(path.is_symlink() for path in directory.rglob("*")),
            "HISTORICAL_SYMLINK:" + directory.name)
    return digest(canonical([[str(path.relative_to(directory)), digest(path.read_bytes())]
                             for path in entries]))


def verify_roots() -> dict[str, dict]:
    result = {}
    for stage, (directory_name, marker_name, expected) in STAGES.items():
        directory = RUNS / directory_name
        actual = directory_root(directory, marker_name)
        require(actual == expected and (directory / marker_name).read_text().strip() == expected,
                "FROZEN_ROOT_MISMATCH:" + stage)
        result[stage] = {"path": str(directory.relative_to(ROOT)),
                         "root_marker": marker_name, "sha256": expected,
                         "verified": True}
    return result


def put(name: str, value: object) -> None:
    with (OUT / name).open("xb") as handle:
        handle.write(canonical(value) + b"\n")


def put_rows(name: str, values: list[dict]) -> None:
    with (OUT / name).open("xb") as handle:
        for value in values:
            handle.write(canonical(value) + b"\n")


def prepare() -> dict:
    require(not OUT.exists(), "ALPHA319G_OUTPUT_ALREADY_EXISTS_NO_REWRITE")
    historical_roots = verify_roots()
    failed_a = read_json(stage_path("a_failed") / "summary.json")
    a2 = read_json(stage_path("a2") / "alpha3_19a2_source_acquisition_execution_summary.json")
    b_dedup = read_json(stage_path("b") / "deduplication_summary.json")
    b_seen = read_json(stage_path("b") / "seen_source_audit.json")
    b_sample = read_json(stage_path("b") / "sampling_execution_audit.json")
    c = read_json(stage_path("c") / "summary.json")
    d1 = read_json(stage_path("d1") / "summary.json")
    e = read_json(stage_path("e") / "validation.json")
    f = read_json(stage_path("f") / "validation.json")
    f1 = read_json(stage_path("f1") / "validation.json")
    require(failed_a["status"] == "failed" and failed_a["raw_source_records"] == 800
            and failed_a["six_source_frames_frozen"] is False
            and a2["raw_source_records"] == 1200 and a2["source_frames_completed"] == 6
            and b_dedup["raw_record_count"] == 1200
            and b_dedup["unique_pmid_count"] == 1025
            and b_seen["naturally_overlapping_pmid_count"] == 0
            and b_sample["sampled_count"] == 72
            and c["pre_oa_source_count"] == 42
            and d1["final_construction_source_count"] == 15
            and e["construction_documents_valid"] == 14
            and e["construction_documents_invalid"] == 1
            and e["builder_request_count"] == 14,
            "UPSTREAM_FUNNEL_MISMATCH")
    expected_f = {"builder_requests_attempted": 14,
                  "builder_scientific_inference_events": 14,
                  "builder_valid_nonzero": 13, "builder_response_invalid": 1,
                  "builder_raw_candidate_count": 35,
                  "exact_duplicates_removed": 0,
                  "body_grounding_pass_count": 6,
                  "body_grounding_failure_count": 29,
                  "lexical_leakage_denominator": 6,
                  "lexical_leakage_failure_count": 6,
                  "quality_input_candidate_count": 0,
                  "quality_source_group_count": 0,
                  "quality_calls": 0}
    require(all(f.get(key) == value for key, value in expected_f.items())
            and f["historical_alpha3_18_builder_inference_events"] == 56
            and f["historical_alpha3_18_quality_inference_events"] == 1,
            "ALPHA319F_FUNNEL_OR_INFERENCE_MISMATCH")
    expected_f1 = {
        "status": "completed",
        "grounding_primary_classification": "GROUNDING_CONTRACT_CONSISTENT_MODEL_NONCONFORMANCE",
        "leakage_primary_classification": "LEAKAGE_CONTRACT_CONSISTENT_ZERO_SURVIVORS",
        "zero_quality_input_primary_classification":
            "ZERO_QUALITY_INPUT_GENUINE_UNDER_CONSISTENT_FROZEN_GATES",
        "exact_copy_requirement": "EXACT_COPY_REQUIREMENT_EXPLICIT_AND_ALIGNED",
        "offline_postcheck_replay_eligible": False,
        "eligible_proposition_pool": "NOT_DERIVED",
        "failed_by_8_token_rule_only": 4,
        "failed_by_jaccard_only": 0,
        "failed_by_both": 2,
        "passed_both": 0,
    }
    require(all(f1.get(key) == value for key, value in expected_f1.items()),
            "ALPHA319F1_INTERPRETATION_MISMATCH")
    require(rows(stage_path("f") / "quality_input_candidate_manifest.jsonl") == []
            and rows(stage_path("f") / "quality_source_group_manifest.jsonl") == []
            and not (stage_path("f1") /
                     "alpha3_19f2_deterministic_postcheck_replay_manifest.json").exists(),
            "QUALITY_OR_REPLAY_BOUNDARY_MISMATCH")

    universe = rows(stage_path("b") / "deduplicated_sampling_universe.jsonl")
    sampled = rows(stage_path("b") / "sampled_source_manifest.jsonl")
    pre_oa = rows(stage_path("c") / "post_metadata_pre_oa_source_manifest_v3.jsonl")
    construction = rows(stage_path("d1") / "final_construction_source_manifest.jsonl")
    requests = rows(stage_path("e") / "alpha3_19_builder_v3_request_manifest.jsonl")
    candidates = rows(stage_path("f") / "candidate_identity_manifest.jsonl")
    require(len(universe) == 1025 and len(sampled) == 72 and len(pre_oa) == 42
            and len(construction) == 15 and len(requests) == 14 and len(candidates) == 35,
            "MANIFEST_CARDINALITY_MISMATCH")
    canonical_pmids = {row["pmid"] for row in universe}
    sampled_pmids = {row["pmid"] for row in sampled}
    pre_oa_pmids = {row["pmid"] for row in pre_oa}
    construction_pmids = {row["pmid"] for row in construction}
    construction_by_token = {row["opaque_source_token"]: row for row in construction}
    request_tokens = {row["source_token"] for row in requests}
    require(len(canonical_pmids) == 1025 and len(sampled_pmids) == 72
            and len(pre_oa_pmids) == 42 and len(construction_pmids) == 15
            and len(construction_by_token) == 15 and len(request_tokens) == 14
            and sum(row["raw_occurrences"] for row in universe) == 1200
            and sampled_pmids <= canonical_pmids and pre_oa_pmids <= sampled_pmids
            and construction_pmids <= pre_oa_pmids
            and request_tokens <= set(construction_by_token)
            and len({row["candidate_id"] for row in candidates}) == 35
            and len({row["candidate_payload_sha256"] for row in candidates}) == 35
            and all(row["source_token"] in request_tokens for row in candidates),
            "IDENTITY_CHAIN_MISMATCH")

    # Failed A is an exposure-only lineage. It never enters A2 dedup or sampling.
    failed_frames = sorted((stage_path("a_failed") / "six_source_frame_manifests").glob("*.json"))
    require(len(failed_frames) == 4, "FAILED_A_FRAME_COUNT_MISMATCH")
    failed_a_raw_pmids = [pmid for path in failed_frames
                          for pmid in read_json(path)["raw_pmid_order"]]
    failed_a_pmids = set(failed_a_raw_pmids)
    require(len(failed_a_raw_pmids) == 800 and len(failed_a_pmids) == 657
            and len(failed_a_pmids & canonical_pmids) == 303
            and len(failed_a_pmids - canonical_pmids) == 354,
            "FAILED_A_EXPOSURE_ACCOUNTING_MISMATCH")
    require(all(pmid.isdecimal() for pmid in canonical_pmids | failed_a_pmids),
            "PMID_IDENTITY_INVALID")
    return locals()


def freeze(state: dict) -> None:
    OUT.mkdir()
    roots = state["historical_roots"]
    universe_by_pmid = {row["pmid"]: row for row in state["universe"]}
    pre_oa_by_pmid = {row["pmid"]: row for row in state["pre_oa"]}
    construction_by_pmid = {row["pmid"]: row for row in state["construction"]}
    construction_by_token = state["construction_by_token"]
    seen_pmids = state["canonical_pmids"] | state["failed_a_pmids"]
    source_registry = []
    for pmid in sorted(seen_pmids, key=lambda value: int(value)):
        canonical_source = universe_by_pmid.get(pmid)
        construction_source = construction_by_pmid.get(pmid)
        pre_oa_source = pre_oa_by_pmid.get(pmid)
        source_registry.append({
            "pmid": pmid,
            "exposure_lineages": (["ALPHA3_19A_FAILED_NONCANONICAL_FRAME"]
                                  if pmid in state["failed_a_pmids"] else [])
                                 + (["ALPHA3_19A2_CANONICAL_SOURCE_FRAME"]
                                     if canonical_source else []),
            "canonical_a2_deduplicated_source": canonical_source is not None,
            "sampled_source": pmid in state["sampled_pmids"],
            "post_metadata_pre_oa_source": pmid in state["pre_oa_pmids"],
            "construction_source": construction_source is not None,
            "builder_requested_source": bool(construction_source and
                                             construction_source["opaque_source_token"]
                                             in state["request_tokens"]),
            "opaque_source_token": (construction_source["opaque_source_token"]
                                    if construction_source else None),
            "pmcid": ((construction_source or pre_oa_source or {}).get("pmcid")),
            "doi": ((construction_source or pre_oa_source or {}).get("doi")),
            "historical_role": "SEEN_DEVELOPMENT_HISTORY",
            "future_primary_fresh_heldout_reuse_prohibited": True,
        })
    candidate_registry = []
    for row in sorted(state["candidates"], key=lambda value: value["candidate_id"]):
        source = construction_by_token[row["source_token"]]
        candidate_registry.append({
            "candidate_id": row["candidate_id"],
            "candidate_payload_sha256": row["candidate_payload_sha256"],
            "opaque_source_token": row["source_token"],
            "source_pmid": source["pmid"],
            "candidate_text_included": False,
            "historical_role": "SEEN_DEVELOPMENT_HISTORY",
            "future_primary_fresh_heldout_reuse_prohibited": True,
        })
    require(len(source_registry) == 1379 and len(candidate_registry) == 35,
            "CONTAMINATION_REGISTRY_CARDINALITY_MISMATCH")

    put("alpha3_19f1_root_verification.json", {
        "alpha3_19f1_sha256": roots["f1"]["sha256"],
        "alpha3_19f_sha256": roots["f"]["sha256"],
        "alpha3_19e1_sha256": roots["e1"]["sha256"],
        "all_three_authoritative_roots_verified": True})
    funnel = {
        "canonical_source_frame_raw_records": 1200,
        "deduplicated_pmids": 1025,
        "seen_source_overlaps": 0,
        "deterministically_sampled_sources": 72,
        "post_metadata_pre_oa_sources": 42,
        "final_construction_sources": 15,
        "valid_construction_documents": 14,
        "builder_requests": 14,
        "builder_scientific_inference_events": 14,
        "valid_nonzero_builder_responses": 13,
        "invalid_completed_builder_responses": 1,
        "raw_builder_v3_candidates": 35,
        "exact_duplicates_removed": 0,
        "body_grounding_passes": 6,
        "body_grounding_failures": 29,
        "lexical_leakage_denominator": 6,
        "lexical_leakage_failures": 6,
        "quality_input_candidates": 0,
        "quality_source_groups": 0,
        "quality_scientific_inference_events": 0,
        "failed_a_noncanonical_raw_records_exposure_only": 800,
        "failed_a_noncanonical_records_in_funnel": 0,
    }
    put("alpha3_19_complete_funnel.json", funnel)
    put("alpha3_19_terminal_classification.json", {
        "attempt": "ALPHA3_19_PRIMARY_FRESH_HELDOUT_ATTEMPT",
        "terminal_state": TERMINAL,
        "not_classified_as": ["QUALITY_FAILURE", "QUALITY_REJECTION",
                              "EMPTY_FINAL_POOL", "SEARCH_PLAN_FAILURE",
                              "SOURCE_ACQUISITION_FAILURE", "BUILDER_EXECUTION_FAILURE"]})
    put("builder_invalid_response_boundary.json", {
        "invalid_completed_response_count": 1,
        "finish_reason": "length",
        "terminal_state": "BUILDER_V3_RESPONSE_INVALID",
        "partial_candidates_salvaged": 0,
        "interpreted_as_valid_zero_response": False,
        "completed_scientific_inference_events_preserved": 1})
    put("grounding_outcome_interpretation.json", {
        "classification": "GROUNDING_CONTRACT_CONSISTENT_MODEL_NONCONFORMANCE",
        "exact_copy_requirement": "EXACT_COPY_REQUIREMENT_EXPLICIT_AND_ALIGNED",
        "failed_candidates": 29,
        "exact_unique_quote_present_elsewhere_in_canonical_body": 29,
        "model_supplied_offset_mismatch": 29,
        "historical_candidate_eligibility_changed": False})
    put("leakage_outcome_interpretation.json", {
        "classification": "LEAKAGE_CONTRACT_CONSISTENT_ZERO_SURVIVORS",
        "independent_reference_reproduced_all_six": True,
        "failed_by_8_token_rule_only": 4,
        "failed_by_jaccard_only": 0,
        "failed_by_both": 2,
        "passed_both": 0,
        "threshold_or_comparison_surface_changed": False})
    put("quality_nonexecution_boundary.json", {
        "quality_input_candidate_count": 0,
        "quality_source_group_count": 0,
        "quality_scientific_inference_events": 0,
        "quality_executed": False,
        "quality_rejected_candidates": None})
    put("quality_rate_nonclaim.json", {
        "quality_denominator_exists": False,
        "quality_pass_rate": None,
        "quality_fail_rate": None,
        "quality_unresolved_rate": None,
        "quality_source_success_rate": None,
        "quality_pass_count_claim_allowed": False,
        "quality_rates_computed": False})
    put("eligible_pool_state.json", {
        "eligible_proposition_pool_state": "NOT_DERIVED",
        "eligible_proposition_pool_derived": False,
        "final_pool_size": None,
        "empty_final_pool_claim_allowed": False})
    put("fresh_heldout_state.json", {
        "fresh_heldout_selected": False,
        "alpha3_19_heldout_case_count": 0,
        "alpha3_19_retrieval_evaluation_performed": False})
    put("search_plan_nonclaim_boundary.json", {
        "search_plan_evaluation_performed": False,
        "search_plan_precision_or_recall_claim_allowed": False,
        "retrieval_generalization_or_direct_rate_claim_allowed": False,
        "p0_p1_p2_performance_claim_allowed": False,
        "source_cohort_lacked_useful_biology_claim_allowed": False})
    put("upstream_validity_preservation.json", {
        "historical_stages_preserved_as_valid_outputs": [
            "NCBI_SOURCE_ACQUISITION", "DETERMINISTIC_SAMPLING",
            "METADATA_ELIGIBILITY", "OA_VERIFICATION", "JATS_ACQUISITION",
            "LICENSE_AND_SOURCE_CONSTRUCTION_ELIGIBILITY",
            "CONSTRUCTION_EVIDENCE_DOCUMENTS", "BODY_ANCHORS",
            "BUILDER_REQUEST_FREEZE", "BUILDER_EXECUTION_PROVENANCE"],
        "zero_quality_input_invalidates_upstream": False})
    put("posthoc_salvage_prohibition.json", {
        "builder_rerun": False, "offset_repair": False,
        "offsets_derived_from_quote_for_alpha3_19": False,
        "leakage_threshold_reduction": False,
        "leakage_comparison_surface_change": False,
        "candidate_paraphrase_repair": False,
        "excluded_source_reactivation": False,
        "source_topup": False, "quality_execution": False,
        "offline_postcheck_replay_eligible": False,
        "alpha3_19f2_replay_created": False})
    put_rows("alpha3_19_seen_source_registry.jsonl", source_registry)
    put_rows("alpha3_19_seen_candidate_registry.jsonl", candidate_registry)
    put("future_contamination_boundary.json", {
        "historical_role": "SEEN_DEVELOPMENT_HISTORY",
        "canonical_a2_deduplicated_pmid_count": 1025,
        "failed_a_noncanonical_unique_pmid_count": 657,
        "failed_a_overlap_with_a2_count": 303,
        "failed_a_only_pmid_count": 354,
        "total_unique_registered_pmid_count": 1379,
        "sampled_source_identity_count": 72,
        "construction_source_identity_count": 15,
        "builder_requested_source_identity_count": 14,
        "builder_candidate_identity_and_payload_hash_count": 35,
        "failed_a_exposure_used_as_scientific_funnel_input": False,
        "future_primary_fresh_heldout_reuse_prohibited": True,
        "identity_match_keys": ["exact PMID", "opaque source token where frozen",
                                "candidate ID", "candidate payload SHA-256"],
        "candidate_text_copied_into_registry": False})
    put("cumulative_inference_accounting.json", {
        "alpha3_18_builder_scientific_inference_events": 56,
        "alpha3_18_quality_scientific_inference_events": 1,
        "alpha3_19_builder_scientific_inference_events": 14,
        "alpha3_19_quality_scientific_inference_events": 0,
        "alpha3_19g_new_scientific_inference_events": 0})
    reporting = ("Alpha3.19 constructed a new 2024–2025 source cohort and generated "
                 "35 schema-valid Builder candidates from 14 frozen source requests. "
                 "Six candidates satisfied deterministic BODY-grounding validation, "
                 "but all six triggered the prospectively frozen lexical-leakage gate. "
                 "Therefore no candidate entered Quality adjudication and no final "
                 "heldout proposition pool was derived.")
    put("publication_reporting_language.json", {
        "recommended_exact_text": reporting,
        "quality_rejected_all_candidates_claim_prohibited": True})
    put("reviewer_grounding_disclosure.json", {
        "candidate_denominator": 35,
        "body_grounding_offset_failures": 29,
        "otherwise_exact_unique_body_quote_count": 29,
        "contract_explicit_and_aligned": True,
        "repair_permitted_or_performed": False,
        "scientific_candidate_failure_inferred": False})
    put("reviewer_leakage_disclosure.json", {
        "body_grounded_candidate_denominator": 6,
        "frozen_lexical_leakage_failures": 6,
        "independent_reference_reproduced": True,
        "post_result_threshold_or_surface_adaptation": False})
    put("future_grounding_ownership_recommendation.json", {
        "status": "FUTURE_PROTOCOL_RECOMMENDATION_ONLY",
        "observation": "Exact unique BODY quotes accompanied incorrect model-authored offsets in 29 frozen responses.",
        "prospective_option": "Separate scientific evidence selection from deterministic evidence localization by making the controller derive unique character offsets.",
        "requires_preregistration_before_new_scientific_cohort": True,
        "implies_alpha3_19_validator_defect": False,
        "authorizes_alpha3_19_candidate_replay": False})
    put("future_leakage_policy_boundary.json", {
        "eight_token_threshold_unchanged": True,
        "jaccard_threshold_unchanged": 0.80,
        "qualifying_token_rules_unchanged": True,
        "zero_survivors_alone_justify_policy_change": False,
        "future_change_requires_independent_methodological_justification": True,
        "future_change_requires_new_development_fresh_evaluation_separation": True})
    put("future_protocol_design_questions.json", {
        "status": "DEVELOPMENT_QUESTIONS_ONLY",
        "questions": [
            "Should the next prospectively registered interface transfer grounding-coordinate ownership to the controller?",
            "Can a Builder generate scientifically faithful propositions sufficiently abstracted from source wording to pass the existing leakage criterion?",
            "Should leakage methodology change for independently justified reasons, or remain unchanged?"],
        "new_primary_attempt_automatically_declared": False,
        "historical_candidate_repair_authorized": False,
        "prospective_model_identifier_unless_separately_changed": "deepseek-flash",
        "historical_model_provenance_modified": False})
    after = verify_roots()
    require(after == roots, "HISTORICAL_ASSETS_CHANGED_DURING_CLOSURE")
    put("historical_preservation_audit.json", {
        "all_historical_roots_before_and_after_verified": True,
        "historical_roots": roots,
        "historical_assets_modified": False,
        "canonical_a2_funnel_kept_separate_from_failed_a_exposure": True})
    put("scientific_state_safety_audit.json", {
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "builder_calls": 0, "quality_calls": 0,
        "candidate_replay_or_repair": False,
        "source_topup_or_resampling": False,
        "threshold_or_policy_change": False,
        "historical_assets_modified": False})
    validation = {
        "status": "completed", "alpha3_19f1_root_verified": True,
        "alpha3_19_primary_attempt_closed": True,
        "alpha3_19_terminal_state": TERMINAL,
        "raw_builder_candidate_count": 35,
        "body_grounding_pass_count": 6,
        "body_grounding_failure_count": 29,
        "leakage_denominator": 6,
        "leakage_failure_count": 6,
        "quality_input_candidate_count": 0,
        "quality_executed": False,
        "quality_pass_count_claim_allowed": False,
        "quality_rates_computed": False,
        "eligible_proposition_pool_derived": False,
        "final_pool_size": None,
        "fresh_heldout_selected": False,
        "search_plan_evaluation_performed": False,
        "posthoc_candidate_salvage_used": False,
        "historical_alpha3_19_builder_inference_events": 14,
        "historical_alpha3_19_quality_inference_events": 0,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "next_stage_recommendation": NEXT,
        "historical_assets_modified": False,
        "seen_source_registry_unique_pmid_count": 1379,
        "seen_candidate_registry_count": 35,
    }
    put("validation.json", validation)
    put("summary.json", {
        "status": "completed", "terminal_state": TERMINAL,
        "funnel": funnel, "quality_executed": False,
        "eligible_proposition_pool_state": "NOT_DERIVED",
        "fresh_heldout_selected": False,
        "seen_source_registry_unique_pmid_count": 1379,
        "seen_candidate_registry_count": 35,
        "next_stage_recommendation": NEXT})
    output_root = directory_root(OUT, ROOT_MARKER)
    with (OUT / ROOT_MARKER).open("xb") as handle:
        handle.write((output_root + "\n").encode("ascii"))
    require(directory_root(OUT, ROOT_MARKER) == output_root,
            "ALPHA319G_ROOT_VERIFY_FAILED")
    print(json.dumps({"status": "completed", "root_sha256": output_root,
                      "terminal_state": TERMINAL,
                      "seen_source_registry_unique_pmid_count": 1379,
                      "seen_candidate_registry_count": 35}, sort_keys=True))


def main() -> None:
    state = prepare()
    freeze(state)


if __name__ == "__main__":
    main()
