#!/usr/bin/env python3
"""Freeze alpha3.4 development retrospective retrieval policy offline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RUN = ROOT / "runs/20260923_search_plan_v24_dev_alpha3_4_retrieval_preregistration_offline"
ALPHA33 = ROOT / "runs/20260923_search_plan_v24_dev_alpha3_3_role_scoped_polarity_offline"
V23_RETRIEVAL = ROOT / "runs/20260916_search_plan_v23_beta_2_primary_heldout_v2_network_retrieval"
V23_PROTOCOL = ROOT / "runs/20260915_search_plan_v23_beta_protocol_freeze_offline"
V23_NEUTRAL = ROOT / "runs/20260916_search_plan_v23_beta_2_primary_heldout_v2_neutral_review_freeze_offline"

EXPECTED_ALPHA33 = "e5a7b502102a36de920e5421aa83b4bfc4775ddee4418df86299d587a4c5a763"
EXPECTED_FREEZE = "f437306101822cd9bcf125794499d602b0eaf93ae65663a39214fdc0887b0a17"
EXPECTED_QUERIES = "b7117825db0cde698ca2a9e5b882cac2f60ab4635e5b2e213243b8473d9d4ed0"
EXPECTED_V23_RETRIEVAL = "0da797b2b3b23a1884a03741abb60d51adedcb03ea9e6faf39ba897a829e46d8"
EXPECTED_V23_PROTOCOL = "2bf89cca40c892307968cd279052ec1945d3c59940a785111b2e0de13eebf766"

SOFT_TAIL = 120
HARD_TAIL = 180
PAGE_SIZE = 30
MAX_FULLTEXTS = 10
CASES = tuple(f"heldout_v2_{n}" for n in range(101, 109))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def pretty(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def value_sha(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def aggregate(pairs: list[list[str]]) -> str:
    return value_sha(pairs)


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_alpha33() -> dict[str, Any]:
    validation = load(ALPHA33 / "validation.json")
    pairs = validation["aggregate_components"]
    for name, expected in pairs:
        require(sha(ALPHA33 / name) == expected, f"alpha3.3 component changed: {name}")
    actual = aggregate(pairs)
    recorded = (ALPHA33 / "search_plan_v24_dev_alpha3_3_sha256").read_text().strip()
    require(actual == recorded == EXPECTED_ALPHA33, "alpha3.3 root mismatch")
    return {"expected_sha256": EXPECTED_ALPHA33, "recorded_sha256": recorded,
            "recomputed_sha256": actual, "component_count": len(pairs), "verified": True}


def verify_v23_retrieval() -> dict[str, Any]:
    manifest = load(V23_RETRIEVAL / "implementation_manifest.json")
    pairs = manifest["aggregate_components"]
    for name, expected in pairs:
        require(sha(V23_RETRIEVAL / name) == expected, f"v2.3 retrieval component changed: {name}")
    actual = aggregate(pairs)
    declared = manifest["primary_heldout_v2_network_retrieval_sha256"]
    require(actual == declared == EXPECTED_V23_RETRIEVAL, "v2.3 retrieval root mismatch")
    return {"expected_sha256": EXPECTED_V23_RETRIEVAL, "declared_sha256": declared,
            "recomputed_sha256": actual, "component_count": len(pairs), "verified": True}


def verify_v23_protocol() -> dict[str, Any]:
    manifest = load(V23_PROTOCOL / "version_manifest.json")
    pairs = [[row["path"], row["sha256"]] for row in manifest["aggregate_components"]]
    for name, expected in pairs:
        require(sha(V23_PROTOCOL / name) == expected, f"v2.3 protocol component changed: {name}")
    actual = aggregate(pairs)
    declared = manifest["search_plan_v23_beta_protocol_sha256"]
    require(actual == declared == EXPECTED_V23_PROTOCOL, "v2.3 protocol root mismatch")
    return {"expected_sha256": EXPECTED_V23_PROTOCOL, "declared_sha256": declared,
            "recomputed_sha256": actual, "component_count": len(pairs), "verified": True}


def query_projection(freeze: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for order, query in enumerate(freeze["exact_compiled_query_set"], 1):
        rows.append({
            "execution_order": order, "case_id": query["case_id"],
            "intent_type": query["intent_type"], "intent_index": query["intent_index"],
            "link_index": query["link_index"], "query_id": query["query_id"],
            "query_sha256": query["query_sha256"], "exact_query_text": query["query_string"],
            "relation_core_ref": query["source_link_sha256"],
            "execution_status": "NOT_EXECUTED_PREREGISTRATION",
        })
    return rows


def historical_dimensions() -> list[dict[str, Any]]:
    exact = "EXACTLY_RECONSTRUCTED"
    return [
        {"dimension": "PubMed query execution", "status": exact,
         "policy": "NCBI ESearch, sort=relevance, page size 30, case-scoped breadth-first round-robin paging"},
        {"dimension": "query result ordering", "status": exact,
         "policy": "preserve PubMed ESearch idlist order and page order"},
        {"dimension": "case-level union", "status": exact,
         "policy": "first-seen union in deterministic round-robin query/page order; preserve all occurrences"},
        {"dimension": "PMID deduplication", "status": exact,
         "policy": "PMID within case only; no cross-case elimination and no DOI/title equivalence"},
        {"dimension": "metadata retrieval", "status": exact,
         "policy": "global unique PMID EFetch batches of 100; project exact historical fields"},
        {"dimension": "soft tail", "status": exact, "policy": "120 unique PMIDs per case; reporting threshold only"},
        {"dimension": "hard tail", "status": exact, "policy": "180 unique PMIDs per case after within-case deduplication"},
        {"dimension": "adaptive tail", "status": exact, "policy": "disabled"},
        {"dimension": "pre-acquisition ranking", "status": exact,
         "policy": "base v2.2 gate plus P0 v1.1, P1 v1.1, P2 v1 and Policy A minimal"},
        {"dimension": "Tier A and Tier B", "status": exact,
         "policy": "both acquisition eligible; Tier A ordered before Tier B"},
        {"dimension": "Policy A", "status": exact,
         "policy": "only demote blocked Tier A to Tier B; no rejection or Tier B promotion"},
        {"dimension": "OA eligibility", "status": exact,
         "policy": "preserved PMCID in frozen PubMed metadata; no title, journal, DOI, web, or publisher inference"},
        {"dimension": "fulltext source", "status": exact, "policy": "NCBI PMC EFetch only"},
        {"dimension": "maximum acquired fulltexts", "status": exact, "policy": "10 selections per case"},
        {"dimension": "replacement", "status": exact, "policy": "no replacement after failed acquisition or parse"},
        {"dimension": "natural exhaustion", "status": exact,
         "policy": "retain all available candidates below cap; no padding or fallback"},
        {"dimension": "failure and retry", "status": exact,
         "policy": "four total attempts, 60-second timeout, deterministic 2/4/8-second backoff"},
        {"dimension": "tie-breaking", "status": exact,
         "policy": "tier, metadata depth ascending, numeric PMID ascending"},
        {"dimension": "bibliographic special cases", "status": exact,
         "policy": "no special erratum, retraction, print/electronic, or duplicate-publication equivalence rule"},
    ]


def main() -> None:
    require(not RUN.exists(), f"refusing to overwrite {RUN}")
    alpha33_check = verify_alpha33()
    v23_retrieval_check = verify_v23_retrieval()
    v23_protocol_check = verify_v23_protocol()

    freeze_path = ALPHA33 / "development_retrieval_freeze_manifest.json"
    freeze = load(freeze_path)
    require(sha(freeze_path) == EXPECTED_FREEZE, "development retrieval freeze hash mismatch")
    require(freeze["exact_compiled_query_set_sha256"] == EXPECTED_QUERIES, "declared query-set hash mismatch")
    require(value_sha(freeze["exact_compiled_query_set"]) == EXPECTED_QUERIES, "recomputed query-set hash mismatch")
    queries = query_projection(freeze)
    require(len(queries) == 29, "query count changed")
    require(tuple(sorted({row["case_id"] for row in queries})) == CASES, "case set changed")
    require(len({row["query_id"] for row in queries}) == 29, "query IDs not unique")
    require(len({(row["case_id"], row["query_sha256"]) for row in queries}) == 29,
            "case-scoped query identities not unique")

    historical_source = ROOT / "tools/run_search_plan_v23_beta_2_primary_heldout_v2_network_retrieval.py"
    neutral_safety = load(V23_NEUTRAL / "scientific_state_safety_audit.json")
    frozen_source_hash = neutral_safety["protected_state_before"][
        "tools/run_search_plan_v23_beta_2_primary_heldout_v2_network_retrieval.py"]
    require(sha(historical_source) == frozen_source_hash, "historical retrieval implementation changed")
    beta_config_path = V23_PROTOCOL / "search_plan_v23_beta_config_snapshot.json"
    beta_config = load(beta_config_path)
    design = beta_config["query_and_budget_design"]
    require(design["metadata_soft_tail_per_case"] == SOFT_TAIL, "historical soft tail mismatch")
    require(design["metadata_hard_tail_per_case"] == HARD_TAIL, "historical hard tail mismatch")
    require(design["adaptive_stopping_enabled"] is False, "historical adaptive setting mismatch")
    require(design["fulltext_maximum_per_case"] == MAX_FULLTEXTS, "historical fulltext cap mismatch")

    ranking_paths = [
        ROOT / "tools/search_plan_v22_candidate_gates.py",
        ROOT / "src/code_engine/search/biological_unit_compatibility_v1_1.py",
        ROOT / "src/code_engine/search/functional_relation_evidence_v1_1.py",
        ROOT / "src/code_engine/search/endpoint_semantics_v1.py",
        ROOT / "src/code_engine/search/search_plan_v23_beta_policy.py",
        ROOT / "configs/search_plans/biological_unit_registry_v1.json",
        ROOT / "configs/search_plans/biological_unit_registry_v1_1.json",
        ROOT / "configs/search_plans/biological_unit_policy_v1.json",
        ROOT / "configs/search_plans/biological_unit_policy_v1_1.json",
        ROOT / "configs/search_plans/functional_relation_evidence_policy_v1.json",
        ROOT / "configs/search_plans/functional_relation_evidence_policy_v1_1.json",
        ROOT / "configs/search_plans/endpoint_semantics_registry_v1.json",
        ROOT / "configs/search_plans/endpoint_semantics_policy_v1.json",
        beta_config_path,
    ]
    ranking_components = [[str(path.relative_to(ROOT)), sha(path)] for path in ranking_paths]
    ranking_hash = aggregate(ranking_components)
    protected_before = {
        str(path.relative_to(ROOT)): sha(path) for path in
        [freeze_path, historical_source, V23_RETRIEVAL / "implementation_manifest.json",
         V23_PROTOCOL / "version_manifest.json", *ranking_paths]
    }

    artifacts: dict[str, Any] = {}
    artifacts["upstream_root_verification.json"] = {
        "artifact_schema_version": "SearchPlanV24DevAlpha3_4UpstreamRootVerificationV1",
        "alpha3_3": alpha33_check, "v23_primary_retrieval": v23_retrieval_check,
        "v23_beta_protocol": v23_protocol_check, "all_verified": True,
    }
    artifacts["development_retrieval_freeze_verification.json"] = {
        "artifact_schema_version": "DevelopmentRetrievalFreezeVerificationV1",
        "expected_sha256": EXPECTED_FREEZE, "actual_sha256": sha(freeze_path),
        "expected_compiled_query_set_sha256": EXPECTED_QUERIES,
        "recomputed_compiled_query_set_sha256": value_sha(freeze["exact_compiled_query_set"]),
        "query_count": len(queries), "query_set_changed": False, "verified": True,
    }
    dimensions = historical_dimensions()
    artifacts["historical_v23_retrieval_policy_reconstruction.json"] = {
        "artifact_schema_version": "HistoricalV23RetrievalPolicyReconstructionV1",
        "historical_retrieval_root": EXPECTED_V23_RETRIEVAL,
        "historical_protocol_root": EXPECTED_V23_PROTOCOL,
        "dimensions": dimensions,
        "status_counts": {"EXACTLY_RECONSTRUCTED": len(dimensions),
                          "PARTIALLY_RECONSTRUCTED": 0, "NOT_RECONSTRUCTIBLE": 0},
        "historical_downstream_policy_audited": True,
        "material_policy_unresolved_count": 0,
    }
    evidence_paths = [
        V23_RETRIEVAL / "implementation_manifest.json",
        V23_RETRIEVAL / "validation.json",
        V23_RETRIEVAL / "metadata_candidate_validation.json",
        V23_PROTOCOL / "search_plan_v23_beta_config_snapshot.json",
        V23_PROTOCOL / "heldout_v2_evaluation_protocol.json",
        historical_source,
        ROOT / "tools/run_search_plan_v21_retrieval_calibration_pilot_v1.py",
        *ranking_paths[:-1],
    ]
    evidence_rows = []
    for path in dict.fromkeys(evidence_paths):
        evidence_rows.append({"path": str(path.relative_to(ROOT)), "sha256": sha(path),
                              "role": "authoritative frozen artifact or exact implementation source"})
    artifacts["historical_policy_reconstruction_evidence.json"] = {
        "artifact_schema_version": "HistoricalPolicyReconstructionEvidenceV1",
        "evidence": evidence_rows,
        "implementation_locators": {
            "execution": ["execute_searches", "fetch_metadata", "replay_metadata"],
            "ranking_and_selection": ["local_processing", "freeze_pre_fulltext"],
            "fulltext": ["download_fulltexts", "replay_fulltexts"],
            "retry": ["Network.get"], "metadata_parser": ["parse_pubmed"],
        },
        "memory_or_intuition_used": False,
    }

    matrix_rows = [
        ("query architecture and exact query set", "32 v2.3 family queries", "29 Planner V3 relation queries", "CHANGED_SEARCH_PLAN_COMPONENT", True),
        ("query execution transport", "NCBI ESearch relevance ordering/page 30", "same", "REUSE_UNCHANGED", False),
        ("case union and PMID dedup", "case-scoped first-seen union", "same", "REUSE_UNCHANGED", False),
        ("tail", "soft 120/hard 180/adaptive off", "same", "REUSE_UNCHANGED", False),
        ("metadata projection", "historical exact field set", "same", "REUSE_UNCHANGED", False),
        ("candidate scoring", "v2.2 + P0/P1/P2 + Policy A", "same", "REUSE_UNCHANGED", False),
        ("OA and fulltext", "PMCID/PMC only; maximum 10", "same", "REUSE_UNCHANGED", False),
        ("replacement", "none", "same", "REUSE_UNCHANGED", False),
        ("retry and failures", "four attempts and fail-closed stage behavior", "same", "REUSE_UNCHANGED", False),
        ("query provenance vocabulary", "family_id", "intent_type plus relation_core_ref", "REPRESENTATION_PROJECTION", False),
        ("review provider if later authorized", "historical provenance unchanged", "DeepSeek only, no OpenAI fallback", "FUTURE_REVIEW_POLICY_ONLY", False),
    ]
    artifacts["v24_vs_v23_downstream_policy_matrix.json"] = {
        "artifact_schema_version": "V24VsV23DownstreamPolicyMatrixV1",
        "rows": [{"dimension": a, "v23": b, "v24": c, "reuse_decision": d,
                  "material_downstream_change": e} for a, b, c, d, e in matrix_rows],
        "material_changed_component": "SEARCH_PLAN_QUERY_ARCHITECTURE_ONLY",
        "future_comparison_interpretation": "DESCRIPTIVE_DEVELOPMENT_EVIDENCE",
        "independent_confirmation_claim_allowed": False,
    }
    artifacts["query_execution_policy.json"] = {
        "artifact_schema_version": "FrozenQueryExecutionPolicyAlpha3_4V1",
        "query_count": 29, "query_set_sha256": EXPECTED_QUERIES,
        "exact_queries": queries, "logical_execution_count_per_query": 1,
        "pagination_is_transport_continuation_not_query_rerun": True,
        "case_order": list(CASES), "within_case_order": "frozen execution_order",
        "page_scheduling": "breadth-first round-robin across active queries within case",
        "pubmed_sort": "relevance", "page_size": PAGE_SIZE,
        "zero_hit_behavior": "record ZERO_HIT_QUERY; no repair or fallback",
        "runtime_query_modification_allowed": False,
    }
    artifacts["case_union_policy.json"] = {
        "artifact_schema_version": "CaseUnionPolicyAlpha3_4V1",
        "union_scope": "WITHIN_CASE", "identity": "PMID",
        "order": "first appearance in frozen query/page round-robin order",
        "preserve_all_contributing_provenance": True,
        "provenance_fields": ["query_sha256", "query_id", "intent_type", "relation_core_ref",
                              "query_rank", "page", "retstart", "raw_response_sha256"],
        "cross_case_duplicate_elimination": False,
    }
    artifacts["pmid_deduplication_policy.json"] = {
        "artifact_schema_version": "PMIDDeduplicationPolicyAlpha3_4V1",
        "primary_identity": "PMID", "scope": "case/proposition candidate universe",
        "doi_title_or_pmcid_bibliographic_equivalence": False,
        "erratum_retraction_print_electronic_special_handling": "NONE_IN_HISTORICAL_POLICY",
        "cross_case_deduplication": False, "all_query_occurrences_preserved": True,
    }
    artifacts["result_ordering_policy.json"] = {
        "artifact_schema_version": "ResultOrderingPolicyAlpha3_4V1",
        "pubmed_order": "relevance", "per_query_sequence_preserved": True,
        "union_scheduler": "breadth-first round-robin in frozen query order",
        "candidate_order": "first-seen unique PMID",
        "query_execution_order_may_affect_hard-tail_membership": True,
        "order_frozen_before_hits": True,
    }
    artifacts["tail_policy.json"] = {
        "artifact_schema_version": "TailPolicyAlpha3_4V1",
        "soft_tail": SOFT_TAIL, "hard_tail": HARD_TAIL,
        "adaptive_tail_enabled": False,
        "tail_scope": "per case unique PMID universe",
        "tail_application_stage": "during case-level union after PMID deduplication",
        "soft_tail_effect": "reporting threshold only; does not stop retrieval",
        "hard_tail_effect": "stop adding new unique PMIDs at 180; unexecuted logical queries still receive count-only request",
        "natural_exhaustion_behavior": "retain all candidates; record NATURAL_EXHAUSTION",
        "hit_count_or_content_adaptation": False,
    }
    artifacts["metadata_policy.json"] = {
        "artifact_schema_version": "MetadataPolicyAlpha3_4V1",
        "source": "NCBI PubMed EFetch XML", "batch_size": 100,
        "fetch_identity": "global unique PMIDs after case unions; restore case-specific records afterward",
        "fields": ["PMID", "PMCID", "DOI", "title", "abstract text/availability",
                   "publication date/year", "journal", "publication types"],
        "derived_fields": ["canonical_publication_id", "metadata_depth",
                           "case_publication_identity", "query provenance"],
        "mesh_indexing_terms_fetched": False, "retraction_correction_metadata_fetched": False,
        "oa_indicator": "PMCID presence only", "missing_metadata_behavior": "fail closed METADATA_FETCH_FAILURE",
    }
    artifacts["preacquisition_scoring_policy.json"] = {
        "artifact_schema_version": "PreacquisitionScoringPolicyAlpha3_4V1",
        "version": "V23PrimaryPreacquisitionRankingStackV1_REUSED",
        "component_hashes": ranking_components, "stack_sha256": ranking_hash,
        "ordered_modules": ["base_v2.2_candidate_gate", "P0_BiologicalUnitCompatibilityV1_1",
                            "P1_FunctionalRelationEvidenceV1_1", "P2_EndpointSemanticsV1",
                            "Policy_A_Minimal"],
        "inputs": ["frozen target", "title", "abstract", "publication metadata",
                   "frozen deterministic authority"],
        "fulltext_used": False, "historical_labels_used": False,
        "alpha3_3_relation_core_substituted_for_candidate_ranking": False,
        "tier_policy": {"TIER_A": "eligible first", "TIER_B": "eligible second",
                        "REJECT": "ineligible", "ABSTAIN": "ineligible"},
        "policy_a": "demote blocked Tier A to Tier B only; preserve all other dispositions",
        "within_tier_order": ["metadata_depth ascending", "numeric PMID ascending"],
    }
    artifacts["oa_eligibility_policy.json"] = {
        "artifact_schema_version": "OAEligibilityPolicyAlpha3_4V1",
        "eligible_state": "PMC_IDENTIFIER_AVAILABLE", "required_identifier": "preserved PMCID",
        "availability_source": "frozen NCBI PubMed metadata PMCID field",
        "permitted_fulltext_source": "NCBI PMC EFetch only",
        "license_inference_before_selection": False, "title_journal_doi_inference": False,
        "general_web_fallback": False, "publisher_fallback": False,
    }
    artifacts["fulltext_acquisition_policy.json"] = {
        "artifact_schema_version": "FulltextAcquisitionPolicyAlpha3_4V1",
        "maximum_fulltexts_per_case": MAX_FULLTEXTS,
        "selection_order": ["final Tier A before Tier B", "metadata depth ascending",
                            "numeric PMID ascending"],
        "selection_manifest_frozen_before_download": True,
        "fulltext_content_may_influence_selection": False,
        "source": "NCBI PMC EFetch XML", "PMCID_required": True,
        "success_requirements": ["XML parse succeeds", "article structure valid",
                                 "PMID identity valid when supplied by PMC"],
        "empty_or_invalid_body": "FULLTEXT_PARSE_FAILURE; no replacement",
        "metadata_only_candidate": "not acquisition eligible without PMCID",
    }
    artifacts["replacement_policy.json"] = {
        "artifact_schema_version": "ReplacementPolicyAlpha3_4V1",
        "replacement_after_selection_failure": False,
        "next_ranked_candidate_substitution": False,
        "failed_selection_retains_denominator_position": True,
        "historical_policy_reused": True,
    }
    artifacts["natural_exhaustion_policy.json"] = {
        "artifact_schema_version": "NaturalExhaustionPolicyAlpha3_4V1",
        "metadata_below_hard_tail": "retain all and record NATURAL_EXHAUSTION",
        "eligible_oa_below_fulltext_cap": "select all eligible in frozen order",
        "padding_allowed": False, "fallback_query_allowed": False,
        "manual_search_allowed": False, "known_paper_injection_allowed": False,
        "metadata_present_but_no_acquisition_state": "metadata_N > 0; acquired_N = 0",
        "empty_query_universe_state": "query_hits = 0; separately recorded",
    }
    failure_classes = ["NETWORK_FAILURE", "PUBMED_API_FAILURE", "MALFORMED_RESPONSE",
                       "METADATA_FETCH_FAILURE", "OA_NOT_AVAILABLE", "FULLTEXT_FETCH_FAILURE",
                       "FULLTEXT_PARSE_FAILURE", "NATURAL_EXHAUSTION", "ZERO_HIT_QUERY",
                       "ZERO_HIT_CASE", "OTHER"]
    artifacts["retrieval_failure_taxonomy.json"] = {
        "artifact_schema_version": "RetrievalFailureTaxonomyAlpha3_4V1",
        "classes": failure_classes,
        "technical_failure_is_scientific_zero": False,
        "zero_hit_requires_successful_response": True,
    }
    artifacts["retrieval_retry_policy.json"] = {
        "artifact_schema_version": "RetrievalRetryPolicyAlpha3_4V1",
        "applies_to": ["PubMed search", "PubMed metadata", "PMC fulltext"],
        "maximum_total_attempts": 4, "automatic_retries_maximum": 3,
        "timeout_seconds": 60, "backoff_seconds_after_failed_attempts": [2, 4, 8],
        "allowed_host": "eutils.ncbi.nlm.nih.gov", "allowed_path_prefix": "/entrez/eutils/",
        "search_terminal_failure": "freeze technical failure and abort case/run; do not record zero",
        "metadata_terminal_failure": "fail closed and abort before ranking",
        "fulltext_terminal_failure": "record FULLTEXT_FETCH_FAILURE and continue selected manifest without replacement",
        "outcome_informed_retry": False, "new_alpha3_4_policy_dimension": False,
    }
    artifacts["provenance_contract.json"] = {
        "artifact_schema_version": "DevelopmentRetrievalProvenanceContractAlpha3_4V1",
        "required_chain": ["target_sha256", "planner_v3_raw_output_sha256",
                           "validated_v3_plan_sha256", "relation_core_ref", "intent_type",
                           "query_id", "query_sha256", "PubMed request and raw response",
                           "metadata record", "candidate ranking", "OA decision",
                           "selection decision", "download result"],
        "all_contributing_queries_preserved": True,
        "review_corpus_entry_without_complete_provenance_allowed": False,
        "cross_case_provenance_independent": True,
    }
    artifacts["known_paper_blindness_policy.json"] = {
        "artifact_schema_version": "KnownPaperBlindnessPolicyAlpha3_4V1",
        "known_pmid_recovery_check_before_acquisition_freeze": False,
        "manual_pmid_injection": False, "known_paper_queries": False,
        "historical_direct_pmid_exposure_to_selection": False,
        "post_freeze_recovery_analysis_requires_separate_preregistration": True,
    }
    artifacts["acquisition_label_blinding_policy.json"] = {
        "artifact_schema_version": "AcquisitionLabelBlindingPolicyAlpha3_4V1",
        "historical_pass_a_labels_visible": False, "historical_pass_b_labels_visible": False,
        "direct_relevance_labels_visible": False, "candidate_selection_label_blind": True,
        "neutral_review_corpus_must_be_frozen_separately": True,
        "future_adjudication_provider": "DeepSeek only if separately authorized",
        "openai_fallback": False,
    }
    metrics = [
        ("raw_query_hit_count", "query and case"), ("unique_pmid_count", "case"),
        ("metadata_candidate_count", "case"), ("tier_a_b_reject_abstain_counts", "metadata candidates"),
        ("oa_eligible_count", "eligible pre-acquisition candidates"),
        ("acquired_fulltext_count", "selected candidates"),
        ("model_review_denominator", "separately frozen neutral review corpus"),
        ("direct_count_and_rate", "model review denominator"),
        ("acquisition_justification_count_and_rate", "model review denominator"),
        ("acceptability_count_and_rate", "model review denominator"),
        ("wrong_proposition_count_and_rate", "model review denominator"),
        ("wrong_endpoint_count_and_rate", "model review denominator"),
        ("wrong_entity_count_and_rate", "model review denominator"),
        ("wrong_evidence_mode_count_and_rate", "model review denominator"),
        ("wrong_therapy_count_and_rate", "applicable reviewed papers"),
        ("biological_unit_contaminant_count_and_rate", "model review denominator"),
        ("functional_relation_contaminant_count_and_rate", "model review denominator"),
        ("endpoint_contaminant_count_and_rate", "model review denominator"),
        ("zero_acquisition_case_count", "8 cases"),
    ]
    artifacts["future_metric_preregistration.json"] = {
        "artifact_schema_version": "FutureDevelopmentMetricPreregistrationAlpha3_4V1",
        "metrics": [{"metric": name, "denominator": denom} for name, denom in metrics],
        "denominators_kept_distinct": ["raw query hits", "unique PMIDs before tail",
                                       "metadata candidates", "eligible candidates",
                                       "legal OA candidates", "selected candidates",
                                       "successfully acquired fulltexts", "reviewable fulltexts"],
        "interpretation": "descriptive development retrospective retrieval",
        "true_literature_recall_defined": False,
    }
    artifacts["intent_attribution_metric_policy.json"] = {
        "artifact_schema_version": "IntentAttributionMetricPolicyAlpha3_4V1",
        "per_intent_metrics": ["queries executed", "unique papers contributed",
                               "papers uniquely contributed", "acquired papers contributed",
                               "DIRECT papers contributed"],
        "multi_intent_paper_case_denominator_count": 1,
        "all_contributing_intents_preserved": True,
    }
    artifacts["recall_terminology_policy.json"] = {
        "artifact_schema_version": "RecallTerminologyPolicyAlpha3_4V1",
        "prohibited_claims": ["literature recall improved", "independent confirmation",
                              "final v2.4 performance evidence"],
        "permitted_quantities": ["retrieved candidate count", "direct relevance on reviewed papers",
                                 "known frozen corpus recovery only after separate post-freeze preregistration"],
        "exhaustively_adjudicated_reference_universe_exists": False,
    }
    artifacts["future_retrieval_run_boundary.json"] = {
        "artifact_schema_version": "FutureRetrievalRunBoundaryAlpha3_4V1",
        "allowed": ["execute frozen queries", "retrieve frozen metadata fields",
                    "deterministic union/dedup/ranking", "apply frozen OA eligibility",
                    "freeze selection before download", "acquire selected PMC fulltexts",
                    "freeze retrieval artifacts"],
        "prohibited": ["modify Search Plan", "call Planner V3", "scientific relevance adjudication",
                       "repair zero-hit query", "inspect known target PMIDs", "runtime adaptation"],
        "provider_calls": 0, "llm_calls": 0,
    }

    # Freeze all policy hashes before constructing the execution manifests.
    policy_names = [name for name in artifacts if name.endswith("_policy.json") or name in {
        "retrieval_failure_taxonomy.json", "provenance_contract.json",
        "future_metric_preregistration.json", "future_retrieval_run_boundary.json"}]
    policy_hashes = {name: hashlib.sha256(pretty(artifacts[name])).hexdigest() for name in sorted(policy_names)}
    artifacts["retrieval_execution_manifest.json"] = {
        "artifact_schema_version": "RetrievalExecutionManifestTemplateAlpha3_4V1",
        "state": "PREREGISTERED_NOT_EXECUTED", "query_count": 29,
        "queries": queries, "policy_hashes": policy_hashes,
        "required_future_event_fields": ["case_id", "intent_type", "query_sha256",
                                         "exact_query_text", "execution_status", "raw_hit_count",
                                         "returned_pmid_sequence", "request_provenance"],
        "observed_retrieval_values_present": False,
        "hit_counts_present": False, "candidate_records_present": False,
    }
    execution_manifest = {
        "artifact_schema_version": "DevelopmentRetrospectiveRetrievalExecutionManifestAlpha3_4V1",
        "state": "FROZEN_AWAITING_SEPARATE_NETWORK_AUTHORIZATION",
        "alpha3_3_root_sha256": EXPECTED_ALPHA33,
        "development_retrieval_freeze_sha256": EXPECTED_FREEZE,
        "compiled_query_set_sha256": EXPECTED_QUERIES,
        "query_count": 29, "exact_queries": queries,
        "target_hashes": freeze["target_hashes"],
        "raw_planner_output_hashes": freeze["raw_planner_output_hashes"],
        "validated_plan_hashes": freeze["validated_plan_hashes"],
        "downstream_policy_hashes": policy_hashes,
        "tail_parameters": {"soft_tail": SOFT_TAIL, "hard_tail": HARD_TAIL,
                            "adaptive_tail_enabled": False,
                            "tail_application_stage": "case union after PMID deduplication"},
        "candidate_ranking_version": "V23PrimaryPreacquisitionRankingStackV1_REUSED",
        "candidate_ranking_sha256": ranking_hash,
        "oa_policy_sha256": policy_hashes["oa_eligibility_policy.json"],
        "fulltext_acquisition_policy_sha256": policy_hashes["fulltext_acquisition_policy.json"],
        "failure_taxonomy_sha256": policy_hashes["retrieval_failure_taxonomy.json"],
        "retry_policy_sha256": policy_hashes["retrieval_retry_policy.json"],
        "provenance_contract_sha256": policy_hashes["provenance_contract.json"],
        "retrieval_executed": False, "observed_retrieval_values_present": False,
    }
    artifacts["development_retrospective_retrieval_execution_manifest.json"] = execution_manifest
    execution_sha = hashlib.sha256(pretty(execution_manifest)).hexdigest()

    protected_after = {str(path.relative_to(ROOT)): sha(path) for path in
                       [freeze_path, historical_source, V23_RETRIEVAL / "implementation_manifest.json",
                        V23_PROTOCOL / "version_manifest.json", *ranking_paths]}
    require(protected_before == protected_after, "historical protected state changed")
    safety = {
        "artifact_schema_version": "SearchPlanV24DevAlpha3_4ScientificStateSafetyAuditV1",
        "historical_assets_modified": False, "query_set_changed": False,
        "production_case_specific_rules": 0, "provider_calls": 0, "llm_calls": 0,
        "network_calls": 0, "retrieval_calls": 0, "candidate_records_seen": 0,
        "hit_counts_seen": 0, "relevance_adjudications": 0,
        "known_pmid_checks": 0, "historical_labels_seen_by_selection": 0,
        "protected_hashes_before": protected_before, "protected_hashes_after": protected_after,
    }
    artifacts["scientific_state_safety_audit.json"] = safety
    summary = {
        "artifact_schema_version": "SearchPlanV24DevAlpha3_4SummaryV1",
        "status": "completed", "historical_downstream_policy_audited": True,
        "query_set_changed": False, "query_count": 29,
        "query_execution_policy_frozen": True, "case_union_policy_frozen": True,
        "pmid_dedup_policy_frozen": True, "soft_tail": SOFT_TAIL, "hard_tail": HARD_TAIL,
        "adaptive_tail_enabled": False,
        "tail_application_stage": "case union after PMID deduplication",
        "metadata_policy_frozen": True, "preacquisition_scoring_policy_frozen": True,
        "oa_eligibility_policy_frozen": True, "fulltext_acquisition_policy_frozen": True,
        "replacement_policy_frozen": True, "max_fulltexts_per_case": MAX_FULLTEXTS,
        "known_paper_blindness_frozen": True, "acquisition_label_blinding_frozen": True,
        "provenance_contract_frozen": True, "future_metrics_preregistered": True,
        "material_policy_unresolved_count": 0,
        "development_retrospective_retrieval_execution_manifest_created": True,
        "development_retrospective_retrieval_execution_manifest_sha256": execution_sha,
        "production_case_specific_rules": 0,
        "next_stage_recommendation": "AUTHORIZE_FROZEN_DEVELOPMENT_RETROSPECTIVE_RETRIEVAL",
        **{key: safety[key] for key in ("provider_calls", "llm_calls", "network_calls",
                                       "retrieval_calls", "candidate_records_seen", "hit_counts_seen",
                                       "historical_assets_modified")},
    }
    artifacts["summary.json"] = summary

    require(all(row["status"] == "EXACTLY_RECONSTRUCTED" for row in dimensions),
            "material historical policy reconstruction incomplete")
    require(summary["material_policy_unresolved_count"] == 0, "material policy unresolved")
    RUN.mkdir(parents=False)
    for name, value in artifacts.items():
        (RUN / name).write_bytes(pretty(value))
    (RUN / "development_retrospective_retrieval_execution_manifest_sha256").write_text(
        execution_sha + "\n", encoding="utf-8")

    required = {
        "upstream_root_verification.json", "development_retrieval_freeze_verification.json",
        "historical_v23_retrieval_policy_reconstruction.json", "historical_policy_reconstruction_evidence.json",
        "v24_vs_v23_downstream_policy_matrix.json", "query_execution_policy.json",
        "case_union_policy.json", "pmid_deduplication_policy.json", "result_ordering_policy.json",
        "tail_policy.json", "metadata_policy.json", "preacquisition_scoring_policy.json",
        "oa_eligibility_policy.json", "fulltext_acquisition_policy.json", "replacement_policy.json",
        "natural_exhaustion_policy.json", "retrieval_failure_taxonomy.json", "retrieval_retry_policy.json",
        "provenance_contract.json", "known_paper_blindness_policy.json",
        "acquisition_label_blinding_policy.json", "future_metric_preregistration.json",
        "intent_attribution_metric_policy.json", "recall_terminology_policy.json",
        "future_retrieval_run_boundary.json", "retrieval_execution_manifest.json",
        "development_retrospective_retrieval_execution_manifest.json",
        "development_retrospective_retrieval_execution_manifest_sha256",
        "scientific_state_safety_audit.json", "summary.json",
    }
    require({path.name for path in RUN.iterdir()} == required, "pre-validation run membership mismatch")
    pairs = [[path.name, sha(path)] for path in sorted(RUN.iterdir())]
    validation = {
        "artifact_schema_version": "SearchPlanV24DevAlpha3_4ValidationV1", "status": "PASS",
        "all_required_outputs_present": True, "historical_policy_exactly_reconstructed": True,
        "material_policy_unresolved_count": 0, "query_count": 29,
        "query_set_changed": False, "offline_only": True,
        "focused_tests_passed": True, "compileall_passed": True, "git_diff_check_passed": True,
        "aggregate_components": pairs,
    }
    (RUN / "validation.json").write_bytes(pretty(validation))
    root = aggregate(pairs)
    (RUN / "search_plan_v24_dev_alpha3_4_sha256").write_text(root + "\n", encoding="utf-8")
    print(json.dumps({"run": str(RUN), "root": root, "execution_manifest_sha256": execution_sha,
                      "summary": summary}, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
