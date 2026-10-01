#!/usr/bin/env python3
"""Freeze a source-blinded new-proposition-pool protocol, without execution."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_16_architecture_freeze_fresh_heldout_v3_preregistration_offline"
RUN = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17_new_blinded_proposition_pool_preregistration_offline"
UPSTREAM_ROOT = "810f39e106d867042bb3ab692e4b1f04c3b39c7227993db63596b47dcdd93335"
ARCHITECTURE_ROOT = "ba82369f45c8a4fcee373fb36011e7bd5817af1e9568765ce0be7801518ff5d1"
PROTOCOL_VERSION = "SearchPlanV24DevAlpha3_17NewBlindedPropositionPoolProtocolV1"
STRATA = ["basic_cell_signaling", "immunology", "metabolism", "neuroscience",
          "cancer_biology", "therapy_response_biology"]


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(name: str, value: Any) -> None:
    path = RUN / name
    require(not path.exists(), f"refusing overwrite: {name}")
    path.write_bytes(canonical(value) + b"\n")


def verify_upstream() -> dict[str, Any]:
    require(not RUN.exists(), "alpha3.17 run exists; never regenerate a frozen protocol")
    pairs = [[path.name, sha(path)] for path in sorted(UPSTREAM.iterdir())
             if path.is_file() and path.name != "search_plan_v24_dev_alpha3_16_sha256"]
    require(digest(pairs) == UPSTREAM_ROOT ==
            (UPSTREAM / "search_plan_v24_dev_alpha3_16_sha256").read_text().strip(),
            "alpha3.16 root mismatch")
    architecture = load(UPSTREAM / "architecture_freeze_manifest.json")
    require(architecture["architecture_freeze_sha256"] == ARCHITECTURE_ROOT ==
            (UPSTREAM / "architecture_freeze_sha256").read_text().strip(),
            "architecture freeze root mismatch")
    require(all(sha(ROOT / relative) == checksum for relative, checksum in architecture["components"]),
            "architecture component changed")
    assert_again = digest({"component_hashes": architecture["components"],
                           "frozen_architecture_roots": architecture["frozen_architecture_roots"],
                           "alpha3_15_interpretation_root":
                           load(UPSTREAM / "alpha3_15_root_verification.json")["actual_sha256"]})
    require(assert_again == ARCHITECTURE_ROOT, "architecture aggregate mismatch")
    previous = load(UPSTREAM / "summary.json")
    require(previous["eligible_untouched_proposition_count"] == 0 and
            previous["fresh_heldout_v3_case_count"] == 0 and
            previous["next_stage_recommendation"] == "CONSTRUCT_NEW_PROPOSITION_POOL_UNDER_BLINDED_PROTOCOL",
            "alpha3.16 fail-closed state drift")
    require((UPSTREAM / "fresh_heldout_v3_target_manifest_sha256").read_text().strip() == "null",
            "unexpected target freeze")
    return {"alpha3_16_root_sha256": UPSTREAM_ROOT,
            "architecture_freeze_sha256": ARCHITECTURE_ROOT,
            "architecture_component_count": len(architecture["components"]),
            "upstream_failed_closed_as_expected": True,
            "old_eligible_untouched_proposition_count": 0,
            "old_fresh_heldout_v3_case_count": 0}


def main() -> None:
    upstream = verify_upstream()
    seed_preimage = ARCHITECTURE_ROOT + "|" + PROTOCOL_VERSION + "|source-sampling-v1"
    seed = hashlib.sha256(seed_preimage.encode("ascii")).hexdigest()
    RUN.mkdir()
    write("alpha3_16_root_verification.json", {
        "status": "PASS", "expected_sha256": UPSTREAM_ROOT,
        "actual_sha256": upstream["alpha3_16_root_sha256"],
        "eligible_untouched_proposition_count_preserved": 0,
        "fresh_heldout_v3_case_count_preserved": 0})
    write("architecture_freeze_verification.json", {
        "status": "PASS", "expected_sha256": ARCHITECTURE_ROOT,
        "actual_sha256": upstream["architecture_freeze_sha256"],
        "verified_component_count": upstream["architecture_component_count"],
        "all_component_hashes_match": True,
        "architecture_modified": False})
    write("new_pool_construction_contract.json", {
        "artifact_schema_version": PROTOCOL_VERSION,
        "stage": "OFFLINE_PREREGISTRATION_ONLY",
        "construction_chain": ["NEW_SOURCE_MATERIAL", "BLINDED_PROPOSITION_EXTRACTION",
                               "SOURCE_ANCHOR_SEALING", "GENERIC_QUALITY_CONTROL",
                               "POOL_FREEZE", "DETERMINISTIC_HELDOUT_SAMPLING"],
        "source_anchor_role": "CONSTRUCTION_ANCHOR_ONLY",
        "source_anchor_is_not_retrieval_hint_query_seed_relevance_label_or_gold": True,
        "existing_unresolved_propositions_promoted": 0,
        "propositions_generated_now": 0,
        "heldout_cases_selected_now": 0})
    write("source_universe_contract.json", {
        "source_interface": "NCBI_PUBMED_TO_PMC_OA",
        "source_article_universe": "Primary experimental journal articles with a legal PMC OA fulltext source and stable publication dates in the frozen window.",
        "source_purpose": "Sufficient source evidence for proposition construction, not downstream Search Plan acquisition ease.",
        "strata": STRATA,
        "source_frame_per_stratum_max_records": 200,
        "source_frame_complete_before_sampling": True,
        "exact_broad_source_query_literals_must_be_frozen_before_any_alpha3_18_network_request": True,
        "source_query_literature_retrieval_now": False,
        "no_proposition_specific_query": True,
        "source_oa_choice_frozen": "PMC_OA_ONLY"})
    write("source_date_policy.json", {
        "publication_date_start_inclusive": "2018-01-01",
        "publication_date_end_inclusive": "2023-12-31",
        "reason": "A closed historical publication window allows stable article and OA availability checks without using current retrieval performance.",
        "chosen_before_source_retrieval": True,
        "change_after_source_yield_inspection": False})
    write("generic_source_strata.json", {
        "ordered_strata": STRATA,
        "source_sampling_categories_only": True,
        "not_case_specific_search_rules": True,
        "not_weighted_by_alpha3_15_failure_frequencies": True,
        "overlapping_source_article_assignment": "Assign a repeated article to its earliest stratum in this frozen order before source sampling.",
        "stratum_identification": "Broad publication indexing/category only; no scientific-finding inspection before sampling."})
    write("source_query_restriction_policy.json", {
        "future_query_style": "Broad domain/indexing query plus frozen date and PMC OA constraints only.",
        "future_exact_query_freeze_required_before_network": True,
        "forbidden_source_query_inputs": ["cases 101-108 entities or proposition strings",
                                          "alpha3.15 wrong-entity or wrong-biological-unit examples",
                                          "current Search Plan relation strings",
                                          "known target propositions", "previous retrieved PMIDs",
                                          "development relevance labels"],
        "query_preflight": "A separate audit-only controller compares exact broad query literals against the frozen forbidden source classes before the first source request; the proposition builder never receives the seen-case materials.",
        "query_modification_after_source_yield": False,
        "current_search_plan_query_reuse": False})
    write("source_sampling_policy.json", {
        "frame_rule": "Within each stratum, freeze at most 200 source-paper IDs in the preregistered PubMed response order; deduplicate globally by the frozen stratum order; freeze the complete bounded frame before sampling.",
        "sample_rule": "Sort each stratum's opaque source IDs by SHA256(seed || ':' || stratum || ':' || source_id); preselect the first 12 per stratum, without inspecting findings.",
        "source_papers_preselected_per_stratum": 12,
        "maximum_source_papers_preselected_total": 72,
        "no_adaptive_resampling_from_scientific_results": True,
        "mechanical_exclusion_policy_separate": True,
        "sampling_independent_of_search_plan": True,
        "sampling_independent_of_development_labels": True,
        "no_sampling_executed_now": True})
    write("sampling_seed_contract.json", {
        "seed_source": "architecture_freeze_sha256",
        "literal_protocol_version": PROTOCOL_VERSION,
        "seed_preimage_format": "ASCII architecture_freeze_sha256 + '|' + protocol_version + '|source-sampling-v1'",
        "seed_sha256": seed,
        "derived_before_any_source_retrieval": True,
        "repository_deterministic_method": "SHA256-keyed ordering, as used by the frozen neutral-review ordering convention",
        "no_seed_choice_after_source_frame_inspection": True,
        "source_sampling_executed_now": False})
    write("source_exclusion_policy.json", {
        "allowed_post_sample_mechanical_exclusions": ["article_unavailable", "not_primary_experimental_research",
                                                       "no_usable_experimental_result", "duplicate_source_article",
                                                       "overlap_with_frozen_seen_development_source",
                                                       "source_provenance_failure"],
        "forbidden_exclusions": ["proposition_looks_difficult", "Search_Plan_likely_to_fail",
                                 "biologically_inconvenient", "unusual_relation",
                                 "known_answer_appears_absent"],
        "exclusion_decision_logged_with_source_token_and_reason": True,
        "no_scientific_result_informed_source_replacement": True})
    write("proposition_builder_isolation_contract.json", {
        "role": "proposition_pool_builder",
        "not_roles": ["Search_Planner", "retrieval_adjudicator"],
        "allowed_input": ["opaque_source_token", "frozen_source_evidence", "generic_builder_schema",
                          "generic_quality_instructions"],
        "forbidden_input": ["Search_Plan_queries", "cases_101_108", "alpha3_15_review_labels",
                            "P0_P1_P2_failure_distributions", "candidate_retrieval_outcomes",
                            "historical_known_paper_recovery_results"],
        "future_model_provider_if_used": "DeepSeek_only",
        "future_model_and_configuration_must_be_frozen_before_call": True,
        "openai_or_alternate_provider_fallback": False,
        "model_calls_now": 0})
    proposition_schema = {
        "type": "object", "additionalProperties": False,
        "required": ["source_record_token", "propositions"],
        "properties": {
            "source_record_token": {"type": "string", "minLength": 1},
            "propositions": {"type": "array", "minItems": 0, "maxItems": 3,
                             "items": {"type": "object", "additionalProperties": False,
                                       "required": ["actor_or_intervention", "action", "relation_direction",
                                                    "response_or_endpoint", "biological_unit", "species",
                                                    "intrinsic_conditioning", "intrinsic_therapy_context",
                                                    "intrinsic_disease_or_genotype_context", "neutral_proposition",
                                                    "construction_evidence_span"],
                                       "properties": {
                                           "actor_or_intervention": {"type": "string", "minLength": 1},
                                           "action": {"type": "string", "minLength": 1},
                                           "relation_direction": {"enum": ["INCREASES", "DECREASES", "ACTIVATES",
                                                                           "INHIBITS", "REQUIRES", "PROMOTES",
                                                                           "SUPPRESSES", "MODULATES_DIRECTION_UNSPECIFIED"]},
                                           "response_or_endpoint": {"type": "string", "minLength": 1},
                                           "biological_unit": {"type": "string", "minLength": 1},
                                           "species": {"type": ["string", "null"]},
                                           "intrinsic_conditioning": {"type": ["string", "null"]},
                                           "intrinsic_therapy_context": {"type": ["string", "null"]},
                                           "intrinsic_disease_or_genotype_context": {"type": ["string", "null"]},
                                           "neutral_proposition": {"type": "string", "minLength": 1},
                                           "construction_evidence_span": {"type": "object", "additionalProperties": False,
                                               "required": ["source_field", "exact_text", "start_offset", "end_offset"],
                                               "properties": {"source_field": {"enum": ["abstract", "body"]},
                                                              "exact_text": {"type": "string", "minLength": 1},
                                                              "start_offset": {"type": "integer", "minimum": 0},
                                                              "end_offset": {"type": "integer", "minimum": 1}}}}}}
        }
    }
    write("proposition_builder_schema.json", {
        "artifact_schema_version": "PropositionPoolBuilderOutputV1",
        "schema": proposition_schema,
        "provider_output_is_proposal_not_scientific_authority": True,
        "private_evidence_span_removed_from_public_pool": True})
    write("construction_grounding_contract.json", {
        "construction_evidence_span_present_required": True,
        "exact_span_must_match_frozen_source_bytes_after_documented_text_extraction": True,
        "span_and_source_hash_verified_deterministically": True,
        "background_knowledge_only_proposition_accepted": False,
        "grounding_failure_state": "GROUNDING_FAILED",
        "builder_output_never_gold_label": True})
    write("source_evidence_span_contract.json", {
        "source_evidence_private_fields": ["source_article_sha256", "source_field", "exact_text",
                                           "start_offset", "end_offset", "text_extraction_version"],
        "offset_semantics": "Zero-based UTF-8-decoded normalized source-text character offsets; exact_text must equal source_text[start_offset:end_offset].",
        "frozen_source_text_hash_required": True,
        "source_span_not_exported_to_search_plan_or_reviewer": True,
        "construction_evidence_span_present": True})
    write("paraphrase_leakage_policy.json", {
        "neutral_proposition_must_preserve_scientific_slots": True,
        "verbatim_title_or_long_sentence_copy_forbidden": True,
        "normalization": "Unicode NFKC, lowercase, tokenize contiguous alphanumeric spans, collapse whitespace; do not use Search Plan lexicons.",
        "automatic_repair_calls_allowed": False,
        "excess_overlap_outcome": "LEXICAL_LEAKAGE_FAILED; no rephrasing after observing Search Plan output",
        "scientific_meaning_checked_independently_of_search_architecture": True})
    write("lexical_overlap_audit_contract.json", {
        "compared_private_texts": ["source_title", "construction_evidence_sentence"],
        "compared_public_text": "neutral_proposition",
        "normalization": "Unicode NFKC lowercase alphanumeric tokens, punctuation discarded",
        "failure_if_max_contiguous_shared_tokens_at_least": 8,
        "failure_if_token_jaccard_at_least": 0.80,
        "jaccard_rule_applies_only_when_both_sides_have_at_least_tokens": 8,
        "failure_state": "LEXICAL_LEAKAGE_FAILED",
        "audit_goal": "near-verbatim leakage detection only",
        "wording_optimized_against_search_plan": False,
        "threshold_change_after_retrieval": False})
    write("proposition_quality_gate.json", {
        "generic_required_checks": ["scientifically_coherent", "experimentally_testable",
                                    "directionally_interpretable", "sufficiently_specific",
                                    "not_tautological", "not_purely_descriptive_if_functional_relation_required",
                                    "actor_and_response_identifiable", "biological_context_interpretable"],
        "quality_reviewer_input": "public scientific fields plus private grounding evidence, never Search Plan outputs",
        "failure_state": "QUALITY_GATE_FAILED",
        "all_checks_required": True,
        "search_architecture_success_prediction_forbidden": True})
    write("architecture_compatibility_nonuse_policy.json", {
        "quality_gate_may_ask_planner_v3_can_represent": False,
        "quality_gate_may_ask_pubmed_will_retrieve": False,
        "quality_gate_may_ask_p0_p1_p2_can_resolve": False,
        "quality_gate_may_ask_lexicon_contains_terms": False,
        "valid_proposition_compilation_failure_is_evaluation_outcome": True})
    write("pool_size_policy.json", {
        "target_heldout_case_count_if_sufficient_pool": "12-16",
        "preferred_certified_candidate_pool_count": "36-48",
        "preferred_pool_multiple_of_final_heldout": 3,
        "candidate_source_preselection_maximum": 72,
        "do_not_fabricate_to_reach_target": True,
        "undersized_pool_blocks_heldout_sampling_unless_separately_preregistered": True})
    write("one_proposition_per_source_policy.json", {
        "eligible_heldout_propositions_per_source_article_maximum": 1,
        "source_internal_choice_rule": "After generic grounding, leakage, quality, and duplicate gates, choose the eligible proposition with smallest SHA256(seed || ':' || opaque_source_token || ':' || canonical_scientific_slot_signature).",
        "choice_uses_retrieval_performance_or_review_labels": False,
        "no_outcome_informed_substitution": True})
    write("duplicate_control_policy.json", {
        "exact_normalized_identity": "Canonical actor/action/direction/endpoint/unit/species/intrinsic-conditioning/therapy/disease slot tuple after generic Unicode and whitespace normalization.",
        "semantic_near_duplicate_audit": "Independent source-blinded scientific reviewer examines deterministically blocked pairs sharing normalized actor and endpoint or biological unit; no Search Plan queries, outcomes, or development labels are visible.",
        "uncertain_near_duplicate_decision": "Stop pool freeze for the affected pair until the preregistered independent review is resolved; never silently mark eligible.",
        "duplicate_state": "DUPLICATE",
        "current_architecture_lexicons_used": False})
    eligibility_states = ["ELIGIBLE_NEW_BLINDED_POOL", "SOURCE_INELIGIBLE", "GROUNDING_FAILED",
                          "QUALITY_GATE_FAILED", "LEXICAL_LEAKAGE_FAILED", "DUPLICATE", "PROVENANCE_FAILED"]
    write("pool_eligibility_state_contract.json", {
        "exactly_one_final_state_per_candidate": True,
        "allowed_states": eligibility_states,
        "precedence_for_multiple_failures": ["SOURCE_INELIGIBLE", "PROVENANCE_FAILED",
                                             "GROUNDING_FAILED", "LEXICAL_LEAKAGE_FAILED",
                                             "QUALITY_GATE_FAILED", "DUPLICATE",
                                             "ELIGIBLE_NEW_BLINDED_POOL"],
        "unresolved_candidate_may_enter_eligible_pool": False,
        "full_eligible_pool_freeze_before_heldout_sampling": True})
    write("anchor_vault_contract.json", {
        "artifact_schema_version": "PropositionAnchorVaultV1",
        "vault_defined_not_created_now": True,
        "future_physical_location": "separate sealed anchor-vault directory outside public evaluation and Search Plan workspaces",
        "future_fields": ["opaque_proposition_id", "opaque_source_token", "PMID", "PMCID", "DOI",
                          "source_article_sha256", "source_evidence_span", "builder_provenance",
                          "source_exclusion_and_quality_audit"],
        "source_anchor_role": "CONSTRUCTION_ANCHOR_ONLY",
        "vault_access_before_post_evaluation_anchor_audit": "construction_controller_only",
        "vault_available_to_compiler_retrieval_selector_or_scientific_reviewer": False})
    write("public_pool_contract.json", {
        "artifact_schema_version": "PublicEvaluationPropositionPoolV1",
        "future_public_fields": ["opaque_proposition_id", "actor_or_intervention", "action",
                                 "relation_direction", "response_or_endpoint", "biological_unit",
                                 "species_if_intrinsic", "intrinsic_conditioning",
                                 "intrinsic_therapy_context", "intrinsic_disease_or_genotype_context",
                                 "neutral_proposition"],
        "forbidden_public_fields": ["PMID", "PMCID", "DOI", "source_article_hash",
                                    "source_title", "source_evidence_span", "source_record_token",
                                    "builder_source_provenance"],
        "public_pool_physically_separate_from_anchor_vault": True,
        "public_pool_frozen_before_heldout_selection": True})
    write("anchor_firewall_policy.json", {
        "construction_controller_may_access_vault": True,
        "Search_Plan_compiler_may_access_vault": False,
        "retrieval_runner_may_access_vault": False,
        "candidate_selector_may_access_vault": False,
        "scientific_reviewer_may_access_vault": False,
        "primary_evaluation_known_paper_recovery_checks": 0,
        "primary_evaluation_source_injection": False,
        "post_evaluation_anchor_audit_requires_separate_explicit_preregistration": True,
        "firewall_enforced_by_separate_paths_and_allowlisted_workspace_manifests": True})
    write("heldout_sampling_policy.json", {
        "sampling_precondition": "Entire certified eligible public pool frozen and hashed, vault sealed and access-audited.",
        "reuse_generic_alpha3_16_stratification": True,
        "target_case_count_if_pool_supports": "12-16",
        "selection_method": "Deterministic SHA256-keyed stratified ordering from a seed frozen before pool sampling; use no Search Plan output.",
        "source_article_cluster_constraint": "At most one selected proposition per source article, enforced by construction controller without exposing anchor to Search Plan.",
        "target_manifest_freeze_before_query_compilation": True,
        "no_case_replacement_for_difficulty_or_zero_hit": True,
        "heldout_cases_selected_now": 0})
    write("development_label_nonuse_policy.json", {
        "forbidden_construction_or_sampling_inputs": ["WRONG_ENTITY_frequency", "wrong_biological_unit_frequency",
                                                      "case_101_dominance", "0_of_11_DIRECT",
                                                      "historical_reviewer_disagreements",
                                                      "individual_P0_P1_P2_outcomes",
                                                      "known_PMID_recovery_results"],
        "allowed_upstream_input": "architecture freeze root and generic alpha3.16 stratification contract only",
        "old_unresolved_propositions_promoted_to_eligible": 0,
        "development_labels_used_now": False})
    write("future_stage_boundary.json", {
        "alpha3_17": "Offline protocol freeze only; zero source retrieval, builder calls, propositions, heldout selection or queries.",
        "alpha3_18": "After separate authorization, acquire new source pool and construct blinded propositions; seal source anchors.",
        "alpha3_19": "Freeze certified eligible public pool, then deterministically select Fresh Heldout V3 and freeze targets.",
        "alpha3_20": "Only after target freeze, preregister frozen-architecture query compilation and retrieval.",
        "do_not_collapse_if_anchor_exposure_could_occur": True,
        "next_authorization_required": "AUTHORIZE_NEW_SOURCE_POOL_ACQUISITION_AND_BLINDED_PROPOSITION_CONSTRUCTION"})
    write("scientific_state_safety_audit.json", {
        "architecture_modified": False,
        "old_unresolved_propositions_promoted_to_eligible": 0,
        "new_propositions_generated": 0,
        "heldout_cases_selected": 0,
        "query_compilation_calls": 0,
        "known_pmid_checks_for_search_evaluation": 0,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "retrieval_calls": 0, "scientific_adjudication_calls": 0,
        "historical_assets_modified": False})
    write("validation.json", {
        "status": "PASS",
        "architecture_freeze_verified": True,
        "new_source_pool_required": True,
        "source_sampling_independent_of_search_plan": True,
        "source_sampling_independent_of_development_labels": True,
        "anchor_vault_defined": True,
        "anchor_visible_to_search_plan": False,
        "construction_evidence_required": True,
        "architecture_compatibility_used_as_quality_gate": False,
        "pool_freeze_before_heldout_selection": True,
        "query_compilation_before_target_freeze": False,
        "old_unresolved_propositions_promoted_to_eligible": 0,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0, "retrieval_calls": 0})
    write("summary.json", {
        "status": "completed",
        "architecture_freeze_sha256": ARCHITECTURE_ROOT,
        "alpha3_16_root_sha256": UPSTREAM_ROOT,
        "old_eligible_untouched_proposition_count": 0,
        "fresh_heldout_v3_case_count": 0,
        "proposition_pool_constructed": False,
        "new_source_pool_required": True,
        "next_stage_recommendation": "AUTHORIZE_NEW_SOURCE_POOL_ACQUISITION_AND_BLINDED_PROPOSITION_CONSTRUCTION",
        "historical_assets_modified": False})
    protocol_names = [
        "new_pool_construction_contract.json", "source_universe_contract.json", "source_date_policy.json",
        "generic_source_strata.json", "source_query_restriction_policy.json", "source_sampling_policy.json",
        "sampling_seed_contract.json", "source_exclusion_policy.json", "proposition_builder_isolation_contract.json",
        "proposition_builder_schema.json", "construction_grounding_contract.json",
        "source_evidence_span_contract.json", "paraphrase_leakage_policy.json",
        "lexical_overlap_audit_contract.json", "proposition_quality_gate.json",
        "architecture_compatibility_nonuse_policy.json", "pool_size_policy.json",
        "one_proposition_per_source_policy.json", "duplicate_control_policy.json",
        "pool_eligibility_state_contract.json", "anchor_vault_contract.json", "public_pool_contract.json",
        "anchor_firewall_policy.json", "heldout_sampling_policy.json",
        "development_label_nonuse_policy.json", "future_stage_boundary.json",
    ]
    protocol_pairs = [[name, sha(RUN / name)] for name in sorted(protocol_names)]
    protocol_root = digest(protocol_pairs)
    (RUN / "new_blinded_proposition_pool_protocol_sha256").write_text(protocol_root + "\n", encoding="utf-8")
    paths = [path for path in sorted(RUN.iterdir()) if path.is_file() and
             path.name != "search_plan_v24_dev_alpha3_17_sha256"]
    run_pairs = [[path.name, sha(path)] for path in paths]
    run_root = digest(run_pairs)
    (RUN / "search_plan_v24_dev_alpha3_17_sha256").write_text(run_root + "\n", encoding="utf-8")
    require(all(sha(RUN / name) == checksum for name, checksum in run_pairs), "artifact drift after freeze")
    print(json.dumps({"status": "completed", "protocol_root": protocol_root,
                      "run_root": run_root, "provider_calls": 0, "network_calls": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
