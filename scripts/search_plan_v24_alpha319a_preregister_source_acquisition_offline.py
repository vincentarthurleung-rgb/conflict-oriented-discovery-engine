#!/usr/bin/env python3
"""Preregister alpha3.19A NCBI acquisition, without making network calls."""
from __future__ import annotations

import json
from pathlib import Path

from scripts import search_plan_v24_alpha319_master_preregister_offline as master
from scripts.search_plan_v24_alpha318c_preregister_quality_offline import root as frozen_root


ROOT = master.ROOT
RUNS = master.RUNS
OUT = RUNS / "20261001_search_plan_v24_dev_alpha3_19a_new_source_acquisition_preregistration_offline"
A17 = RUNS / "20260927_search_plan_v24_dev_alpha3_17a_new_pool_execution_preflight_offline"
MASTER_SHA = "1cf1d29d67474996a6ee87b518af0f09456e3572a3969b5a5f1b6021009ed73b"
PLAN_SHA = "bd11d1e058a4123cfec1cdff68b6f26664d5a6256ef15e3ec8469338621126e2"
ENVELOPE_SHA = "25ad0b448a6d7fd9f6598841824c19cab33ba4b40eb92e2c2260d871d06e4a1d"
NEXT = "AUTHORIZE_ALPHA3_19A_NCBI_ONLY_SOURCE_ACQUISITION"
ES = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EF = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def require(ok: bool, code: str):
    if not ok:
        raise RuntimeError(code)


def load(path: Path):
    return json.loads(path.read_bytes())


def write(name: str, value):
    (OUT / name).write_bytes(master.canonical(value) + b"\n")


def writelines(name: str, values: list[dict]):
    (OUT / name).write_bytes(b"".join(master.canonical(value) + b"\n" for value in values))


def marker(name: str, value: str):
    (OUT / name).write_text(value + "\n")


def root_hash() -> str:
    return master.sha(master.canonical([[p.name, master.digest(p)] for p in sorted(OUT.iterdir())
        if p.is_file() and p.name != "search_plan_v24_dev_alpha3_19a_prereg_sha256"]))


def ref(path: Path):
    return master.ref(path)


def check_ref(binding: dict):
    path = ROOT / binding["path"]
    require(path.is_file() and master.digest(path) == binding["sha256"],
            "FROZEN_BINDING_MISMATCH:" + binding["path"])


def main():
    require(not OUT.exists(), "ALPHA3_19A_PREREG_OUTPUT_EXISTS")
    require(frozen_root(master.OUT, "search_plan_v24_dev_alpha3_19_master_prereg_sha256") == MASTER_SHA and
            (master.OUT / "search_plan_v24_dev_alpha3_19_master_prereg_sha256").read_text().strip() == MASTER_SHA,
            "ALPHA3_19_MASTER_ROOT_MISMATCH")
    for name, value in (("alpha3_19_master_execution_plan", PLAN_SHA),
                        ("quality_response_envelope_v3", ENVELOPE_SHA)):
        require(master.digest(master.OUT / (name + ".json")) == value and
                (master.OUT / (name + "_sha256")).read_text().strip() == value,
                "ALPHA3_19_MASTER_BINDING_MISMATCH:" + name)
    require(frozen_root(master.C2, "search_plan_v24_dev_alpha3_18c2_sha256") == master.EXPECTED_C2,
            "ALPHA3_18_CLOSURE_MISMATCH")
    summary = load(master.OUT / "summary.json")
    require(summary["status"] == "completed" and summary["alpha3_19_new_attempt"] and
            not summary["alpha3_18_scientific_assets_reused"] and
            summary["source_cohort_start"] == "2024-01-01" and
            summary["source_cohort_end"] == "2025-12-31",
            "ALPHA3_19_MASTER_SUMMARY_MISMATCH")

    master_queries_path = master.OUT / "alpha3_19_source_query_templates.jsonl"
    old_query_path = master.A18 / "source_query_request_manifest.jsonl"
    master_queries = master.rows(master_queries_path)
    old_queries = [x for x in master.rows(old_query_path) if x["page_retstart"] == 0]
    strata = load(master.OUT / "alpha3_19_source_cohort_contract.json")["strata"]
    require(len(master_queries) == len(old_queries) == len(strata) == 6 and
            [x["stratum_id"] for x in master_queries] == strata,
            "ALPHA3_19A_SOURCE_QUERY_DRIFT")
    old_date = '"2018/01/01"[Date - Publication] : "2023/12/31"[Date - Publication]'
    new_date = '"2024/01/01"[Date - Publication] : "2025/12/31"[Date - Publication]'
    query_set: list[dict] = []
    deltas: list[dict] = []
    for ordinal, (before, after) in enumerate(zip(old_queries, master_queries), 1):
        old_term = before["parameters"]["term"]
        term = after["term"]
        require(before["stratum_id"] == after["stratum_id"] and
                term.replace(new_date, old_date) == old_term and
                old_term.count(old_date) == term.count(new_date) == 1 and
                term.count('"pubmed pmc"[sb]') == 1 and
                'pmc[filter]' not in term and 'open access[filter]' not in term and
                master.sha(term.encode()) == after["query_sha256"] and
                master.sha(old_term.encode()) == before["query_sha256"],
                "ALPHA3_19A_SOURCE_QUERY_DRIFT")
        query_set.append({"ordinal": ordinal, "stratum_id": after["stratum_id"],
                          "query_utf8": term, "query_sha256": after["query_sha256"],
                          "endpoint": ES, "db": "pubmed", "sort": "relevance",
                          "retmode": "json", "page_size": 50,
                          "retstart_sequence": [0, 50, 100, 150]})
        deltas.append({"stratum_id": after["stratum_id"],
                       "alpha3_18_comparison_query_utf8": old_term,
                       "alpha3_19_query_utf8": term,
                       "old_sha256": before["query_sha256"],
                       "new_sha256": after["query_sha256"],
                       "old_date_window": ["2018-01-01", "2023-12-31"],
                       "new_date_window": ["2024-01-01", "2025-12-31"],
                       "scientific_token_delta": [],
                       "biological_boolean_structure_changed": False,
                       "pmc_subset_clause_changed": False})

    seed_path = master.OUT / "alpha3_19_sampling_seed_contract.json"
    seed = load(seed_path)
    require(seed["frozen_before_network"] and
            seed["seed"] == master.sha(seed["seed_input"].encode()) and
            not seed["depends_on_pmid_frame_findings_or_yield"],
            "SAMPLING_SEED_MISMATCH")
    seen_path = master.OUT / "alpha3_18_seen_source_registry.jsonl"
    seen = master.rows(seen_path)
    seen_ids = [x["pmid"] for x in seen]
    require(len(seen_ids) == len(set(seen_ids)) == 1041 and
            master.digest(seen_path) == load(master.OUT / "alpha3_19_master_execution_plan.json")[
                "historical_source_registry_sha256"],
            "HISTORICAL_SEEN_SOURCE_REGISTRY_MISMATCH")

    bindings = {
        "esearch_validator": master.A4 / "pubmed_esearch_response_validity_v2.json",
        "esearch_errorlist": master.A4 / "esearch_errorlist_policy.json",
        "esearch_warninglist": master.A4 / "esearch_warninglist_policy.json",
        "esearch_schema": master.A4 / "esearch_schema_validation_policy.json",
        "query_semantic_retry": master.A4 / "query_semantic_retry_policy.json",
        "hardened_search_execution": master.A4 / "alpha3_18a4_source_acquisition_execution_manifest_v2.json",
        "technical_transport": A17 / "source_execution_policy.json",
        "historical_transport_implementation": ROOT / "scripts/search_plan_v24_alpha318a_execute_ncbi_source_acquisition.py",
        "sampling_algorithm": A17 / "source_sampling_algorithm.json",
        "dedup": A17 / "cross_stratum_duplicate_policy.json",
        "metadata": master.A1 / "source_metadata_contract_v2.json",
        "primary_citation": master.A5 / "pubmed_primary_citation_identity_binding_v1.json",
        "primary_reference_exclusion": master.A5 / "reference_article_id_exclusion_contract.json",
        "primary_article_id_scope": master.A5 / "primary_article_id_scope_contract.json",
        "primary_identity_regressions": master.A5 / "primary_identity_parser_regression_tests.json",
        "publication_type_accept": master.A1 / "publication_type_acceptance_set.json",
        "publication_type_exclude": master.A1 / "publication_type_exclusion_set.json",
        "correction": master.A3 / "correction_reference_eligibility_v1.json",
        "correction_pipeline": master.A3 / "source_eligibility_pipeline_v3.json",
        "pmc_oa_subset": master.A1 / "oa_subset_verification_contract.json",
        "jats_acquisition": A17 / "construction_fulltext_acquisition_policy.json",
        "jats_failure": A17 / "construction_fulltext_failure_policy.json",
        "future_license_extraction": master.A6 / "construction_license_extraction_v2.json",
        "future_source_type": master.A1 / "source_type_mechanical_eligibility_v1.json",
        "future_construction_document": master.A1 / "construction_evidence_document_v1_contract.json",
        "future_evidence_anchor": master.A1 / "evidence_span_anchor_v1_contract.json",
    }
    bound = {key: ref(path) for key, path in bindings.items()}
    for value in bound.values():
        check_ref(value)
    search_policy = load(bindings["hardened_search_execution"])["active_source_frame_policy_v2"]
    require(search_policy["page_size"] == 50 and
            search_policy["frame_cap_per_stratum"] == 200 and
            search_policy["retstart_sequence"] == [0, 50, 100, 150] and
            search_policy["sort"] == "relevance" and
            search_policy["timeout_seconds"] == 60 and
            search_policy["maximum_attempts_per_request"] == 4 and
            search_policy["backoff_seconds"] == [2, 4, 8] and
            search_policy["stratum_order"] == strata,
            "HARDENED_TRANSPORT_POLICY_MISMATCH")
    metadata_policy = load(bindings["metadata"])
    require(metadata_policy["route"].startswith("NCBI E-Utilities EFetch") and
            len(metadata_policy["fields"]) >= 6,
            "METADATA_POLICY_MISMATCH")
    primary = load(bindings["primary_citation"])
    require(primary["article_id_list_must_be_direct_child_of_pubmed_data"] and
            not primary["reference_list_identity_contribution"] and
            primary["exactly_one_matching_pubmed_article_required"],
            "PRIMARY_CITATION_IDENTITY_REGRESSION")
    oa = load(bindings["pmc_oa_subset"])
    require(oa["endpoint"] == ES and oa["term_template"] ==
            "{numeric_pmc_uid}[UID] AND open access[filter]" and
            oa["fixed_parameters"] == {"db": "pmc", "retmax": "1", "retmode": "json"},
            "PMC_OA_ROUTE_MISMATCH")

    OUT.mkdir()
    write("master_preregistration_verification.json", {
        "alpha3_19_master_prereg_verified": True,
        "root_sha256": MASTER_SHA,
        "master_execution_plan": {"path": str((master.OUT / "alpha3_19_master_execution_plan.json").relative_to(ROOT)),
                                  "sha256": PLAN_SHA},
        "quality_response_envelope_v3": {"path": str((master.OUT / "quality_response_envelope_v3.json").relative_to(ROOT)),
                                         "sha256": ENVELOPE_SHA},
        "historical_alpha3_18_closure_sha256": master.EXPECTED_C2})
    write("alpha3_19_attempt_boundary_verification.json", {
        "attempt": "alpha3.19", "new_primary_fresh_heldout_attempt": True,
        "alpha3_18_history_state": "SEEN_DEVELOPMENT_HISTORY",
        "historical_scientific_source_preference": False,
        "historical_source_candidates_reused": False,
        "stage": "19A_EXECUTION_PREREGISTRATION_OFFLINE_ONLY"})
    write("alpha3_19_source_cohort_verification.json", {
        "start": "2024-01-01", "end": "2025-12-31", "inclusive": True,
        "strata": strata, "strata_changed": False,
        "2018_2023_included": False, "partial_2026_included": False,
        "date_decision_rule": "single stable parsed publication year from frozen PubDate/ArticleDate paths; 2024 or 2025 only; ambiguous/mixed/out-of-window UNRESOLVED",
        "online_ahead_of_print_special_override": False})
    writelines("alpha3_19_source_query_set.jsonl", query_set)
    marker("alpha3_19_source_query_set_sha256", master.digest(OUT / "alpha3_19_source_query_set.jsonl"))
    writelines("alpha3_19_source_query_delta_audit.jsonl", deltas)
    write("pubmed_esearch_validator_binding.json", {
        "contract": bound["esearch_validator"], "error_policy": bound["esearch_errorlist"],
        "warning_policy": bound["esearch_warninglist"],
        "schema_policy": bound["esearch_schema"],
        "validation_order": ["transport", "payload/schema", "ErrorList", "WarningList", "Count/IdList"],
        "http_200_alone_success": False,
        "nonempty_errorlist": "QUERY_SEMANTIC_ERROR_NO_RETRY",
        "unknown_semantic_warning": "FAIL_CLOSED",
        "valid_zero_only_after_prior_checks": True,
        "querytranslation": "PRESERVE_NOT_QUERY_REWRITE"})
    write("source_frame_execution_contract.json", {
        "query_set": ref(OUT / "alpha3_19_source_query_set.jsonl"),
        "query_delta_audit": ref(OUT / "alpha3_19_source_query_delta_audit.jsonl"),
        "source_cohort": ref(OUT / "alpha3_19_source_cohort_verification.json"),
        "stratum_order": strata, "sort": "relevance", "page_size": 50,
        "max_records_per_stratum": 200, "retstart_sequence": [0, 50, 100, 150],
        "request_parameters": ["db", "term", "sort", "retmode", "retmax", "retstart"],
        "transport": bound["technical_transport"],
        "transport_implementation_only": bound["historical_transport_implementation"],
        "hardened_execution": bound["hardened_search_execution"],
        "timeout_seconds": 60, "max_attempts_per_request": 4,
        "retryable_http_status": [408, 429, 500, 502, 503, 504],
        "backoff_seconds": [2, 4, 8],
        "minimum_inter_request_interval_seconds": 0.38,
        "http_redirects": "FAIL_CLOSED",
        "technical_retry_only": True, "semantic_error_retry": False,
        "per_page_freeze": ["exact parameters", "query", "page offset", "request ordinal",
                            "raw response bytes and SHA256", "transport and retry state",
                            "ESearch validity state", "querytranslation if returned"],
        "science_content_inspection_before_sampling": False})
    write("source_frame_completion_barrier.json", {
        "required_valid_frames": 6,
        "valid_terminal_conditions": ["NATURAL_EXHAUSTION", "200_RECORD_CAP"],
        "all_frames_frozen_before_dedup_or_sampling": True,
        "terminal_failure": "ALPHA3_19A_SOURCE_FRAME_FAILED_CLOSED",
        "partial_sampling_allowed": False,
        "no_subsequent_network_after_terminal_frame_failure": True})
    write("cross_stratum_dedup_contract.json", {
        "policy": bound["dedup"], "identity": "exact canonical PMID",
        "owner": "earliest frozen stratum in six-stratum order",
        "all_memberships_preserved_privately": True,
        "before_sampling": True,
        "sampling_universe_sha256_freeze_required": True,
        "content_based_reordering": False})
    write("sampling_seed_verification.json", {
        "seed_contract": ref(seed_path), "seed": seed["seed"],
        "derivation_verified": True, "frozen_before_network": True,
        "depends_on_frame_or_yield": False})
    write("sampling_execution_contract.json", {
        "algorithm_authority": bound["sampling_algorithm"],
        "algorithm": "SHA256(seed || ':' || stratum || ':' || canonical PMID), ascending; first 12",
        "seed": seed["seed"], "sample_cap_per_stratum": 12,
        "raw_sample_cap": 72, "sampling_after_complete_universe_freeze": True,
        "sampling_before_historical_contamination_exclusion": True,
        "seen_source_pre_filter": False,
        "refill_allowed": False, "replacement_allowed": False,
        "topup_allowed": False})
    write("alpha3_18_seen_source_registry_verification.json", {
        "registry": ref(seen_path), "count": 1041,
        "unique_pmid_count": 1041, "master_manifest_hash_match": True,
        "comparison_key": "exact canonical PMID"})
    write("historical_source_contamination_gate.json", {
        "applies_after_sample_identity_freeze": True,
        "states": ["NO_ALPHA3_18_SOURCE_MATCH", "ALPHA3_18_SEEN_SOURCE_MATCH"],
        "match_disposition": "INELIGIBLE_FOR_ALPHA3_19_PRIMARY_POOL",
        "unexpected_cohort_overlap_recorded_separately": True,
        "overlap_assumed_impossible": False,
        "date_policy_runtime_change": False,
        "replacement": False})
    write("primary_citation_identity_binding_contract.json", {
        "contract": bound["primary_citation"],
        "reference_exclusion": bound["primary_reference_exclusion"],
        "article_id_scope": bound["primary_article_id_scope"],
        "regression_suite": bound["primary_identity_regressions"],
        "expected_identity": "frozen sampled PMID",
        "canonical_path": "PubmedArticle/MedlineCitation/PMID",
        "matching_records_required": 1,
        "zero_or_multiple_match": "SOURCE_FAIL_CLOSED",
        "external_id_path": "PubmedArticle/PubmedData/ArticleIdList/ArticleId direct child",
        "ReferenceList_identity_contribution": False,
        "runtime_assertions": ["no ReferenceList PMID as current PMID",
                               "no ReferenceList PMCID as current PMCID",
                               "no ReferenceList DOI as current DOI",
                               "exact current PMID binding"]})
    write("sampled_metadata_contract.json", {
        "route": {"endpoint": EF, "method": "GET", "db": "pubmed",
                  "retmode": "xml", "id": "frozen sampled canonical PMID"},
        "metadata_policy": bound["metadata"],
        "only_frozen_sampled_identities": True,
        "all_frozen_sampled_identities_including_seen_matches": True,
        "seen_source_status_does_not_change_metadata_request_set": True,
        "fields": [x["name"] for x in metadata_policy["fields"]],
        "scientific_preference_field_retrieval": False,
        "raw_xml_and_provenance_freeze": True,
        "transport_policy": bound["technical_transport"]})
    write("publication_date_execution_contract.json", {
        "source_fields": ["JournalIssue/PubDate", "Article/ArticleDate"],
        "date_rule_source": bound["metadata"],
        "cohort_change_reason": "new prospective publication cohort, not observed-yield optimization",
        "accepted_single_stable_years": [2024, 2025],
        "ambiguous_or_conflicting_years": "UNRESOLVED",
        "out_of_window_year": "INELIGIBLE",
        "online_ahead_of_print_manual_override": False,
        "no_source_replacement": True})
    write("publication_type_execution_contract.json", {
        "accepted_vocabulary": bound["publication_type_accept"],
        "excluded_vocabulary": bound["publication_type_exclude"],
        "states": ["PRELIMINARY_TYPE_ACCEPTED", "SOURCE_TYPE_INELIGIBLE",
                   "SOURCE_TYPE_UNRESOLVED"],
        "accepted_type_alone_sufficient": False,
        "any_excluded_type": "SOURCE_TYPE_INELIGIBLE",
        "unknown_unsupported_type": "SOURCE_TYPE_UNRESOLVED",
        "vocabulary_update_after_records": False})
    write("correction_reference_execution_contract.json", {
        "contract": bound["correction"], "pipeline": bound["correction_pipeline"],
        "states": ["CORRECTION_REFERENCE_CLEAR", "CORRECTION_REFERENCE_INELIGIBLE",
                   "CORRECTION_REFERENCE_UNRESOLVED"],
        "direction_sensitive": True,
        "RetractionIn": "INELIGIBLE", "ExpressionOfConcernIn": "INELIGIBLE",
        "ErratumIn": "UNRESOLVED",
        "UpdateIn_and_republication_rules": "EXACT_FROZEN_CONTRACT",
        "UpdateOf": "CONDITIONAL_PRELIMINARY_UNRESOLVED; defer finalization to 19B structural source-type result",
        "unknown_relevant_RefType": "UNRESOLVED",
        "rules_changed": False})
    write("metadata_completion_barrier.json", {
        "all_sampled_sources_require_terminal_preliminary_states": True,
        "required": ["seen source", "publication date", "Publication Type",
                     "correction/retraction", "primary citation identity"],
        "OA_request_before_complete_freeze": False,
        "conditional_UpdateOf_can_advance_to_oa_jats": True,
        "conditional_UpdateOf_final_admission_in_19A": False})
    write("post_metadata_pre_oa_manifest_contract.json", {
        "future_path": "alpha3_19_post_metadata_pre_oa_source_manifest.jsonl",
        "only_metadata_stage_admissible": True,
        "clear_or_conditional_UpdateOf_only": True,
        "conditional_UpdateOf_final_source_admission": False,
        "all_other_unresolved_sources_excluded_without_replacement": True,
        "no_manual_injection": True,
        "freeze_before_first_oa_request": True})
    write("pmc_oa_subset_execution_contract.json", {
        "source_contract": bound["pmc_oa_subset"],
        "endpoint": ES, "method": "GET", "db": "pmc",
        "term_template": oa["term_template"],
        "retmax": 1, "retmode": "json",
        "requires_pre_oa_manifest": True,
        "PMCID_alone_sufficient": False,
        "pubmed_pmc_subset_alone_sufficient": False,
        "journal_inference_allowed": False,
        "states": ["OA_SUBSET_ELIGIBLE", "OA_SUBSET_INELIGIBLE",
                   "OA_SUBSET_UNRESOLVED"],
        "positive": "valid ESearch JSON with sole returned numeric PMC UID equal to requested UID, per frozen OA contract",
        "negative": "valid Count=0 and empty IdList",
        "other_or_transport_failure": "OA_SUBSET_UNRESOLVED",
        "raw_request_response_hash_freeze": True,
        "replacement": False})
    write("pmc_jats_acquisition_contract.json", {
        "route": {"endpoint": EF, "method": "GET", "db": "pmc",
                  "retmode": "xml", "id": "verified numeric PMCID suffix"},
        "requires_oa_subset_state": "OA_SUBSET_ELIGIBLE",
        "acquisition_policy": bound["jats_acquisition"],
        "failure_policy": bound["jats_failure"],
        "canonical_pmc_xml_jats_only": True,
        "publisher_pdf_html_europe_pmc_fallback": False,
        "technical_max_attempts": 4, "timeout_seconds": 60,
        "backoff_seconds": [2, 4, 8],
        "terminal_failure": "RECORD_NO_REPLACEMENT",
        "freeze": ["raw response bytes", "canonical XML bytes",
                   "content SHA256", "request/transport provenance",
                   "opaque source identity"],
        "license_interpretation": False,
        "construction_oa_finalization": False})
    write("jats_handoff_manifest_contract.json", {
        "future_path": "alpha3_19a_jats_handoff_manifest.jsonl",
        "for_stage": "alpha3.19B",
        "records": "successfully acquired and canonicalized JATS only",
        "required_private_bindings": ["opaque source token", "canonical sampled PMID",
                                      "direct current-article PMCID", "metadata gate states",
                                      "OA subset state", "raw JATS path and SHA256",
                                      "canonical JATS path and SHA256",
                                      "request/transport provenance"],
        "opaque_token_rule": "32 CSPRNG bytes, src_ prefix, freeze once per JATS-successful source",
        "handoff_contracts": {k: bound[k] for k in (
            "future_license_extraction", "future_source_type",
            "future_construction_document", "future_evidence_anchor")},
        "license_state_derived": False,
        "source_type_state_derived": False,
        "construction_document_generated": False,
        "additional_network_required_for_19B": False})
    write("scientific_content_nonuse_contract.json", {
        "title_abstract_fulltext_meaning_used_for_order_sample_replace_or_prefer": False,
        "structural_eligibility_rules_only": True,
        "source_frame_uses_only_ids_and_provenance": True,
        "metadata_fetched_for_scientific_preference": False,
        "no_source_topup": True})
    write("search_plan_firewall_audit.json", {
        "forbidden_to_source_selection": ["Search Plan queries or outcomes",
            "alpha3.18 retrieval results", "historical candidate labels",
            "known-paper labels", "P0/P1/P2 states"],
        "used_for_source_selection": False})
    write("alpha3_19a_completion_barrier.json", {
        "future_execution_complete_only_after": [
            "six valid frames frozen", "deduplicated universe and SHA256 frozen",
            "sampled identities frozen", "seen-source states frozen",
            "sampled PubMed metadata and preliminary gates frozen",
            "pre-OA manifest frozen", "OA subset states frozen",
            "all authorized JATS terminal states frozen",
            "all raw and canonical JATS artifacts frozen",
            "alpha3.19B handoff manifest frozen"],
        "license_or_source_type_finalization": False,
        "builder_call_budget": None})

    required_future_outputs = [
        "source_frame_request_manifest.jsonl", "source_frame_raw_responses/",
        "source_frame_validity_states.jsonl", "six_frame_completion_barrier.json",
        "deduplicated_sampling_universe.jsonl", "deduplicated_sampling_universe_sha256",
        "deterministic_sampled_identities.jsonl", "sampled_identities_sha256",
        "historical_contamination_states.jsonl", "sampled_metadata_requests.jsonl",
        "sampled_metadata_raw_responses/", "sampled_metadata_identity_states.jsonl",
        "sampled_metadata_eligibility_states.jsonl",
        "alpha3_19_post_metadata_pre_oa_source_manifest.jsonl",
        "oa_subset_requests.jsonl", "oa_subset_raw_responses/",
        "oa_subset_terminal_states.jsonl", "pmc_jats_requests.jsonl",
        "pmc_jats_raw_responses/", "pmc_jats_canonical_xml/",
        "pmc_jats_terminal_states.jsonl", "alpha3_19a_jats_handoff_manifest.jsonl",
        "transport_provenance.jsonl", "completion_barrier.json", "summary.json"]
    manifest = {
        "schema_version": "Alpha319ASourceAcquisitionExecutionManifestV1",
        "status": "EXECUTABLE_PROSPECTIVE_OFFLINE_PREREGISTRATION_FROZEN",
        "attempt": "alpha3.19", "phase": "19A",
        "authoritative_master_root_sha256": MASTER_SHA,
        "query_set": ref(OUT / "alpha3_19_source_query_set.jsonl"),
        "query_hashes": [q["query_sha256"] for q in query_set],
        "query_count": 6,
        "network_scope": {"allowed_host": "eutils.ncbi.nlm.nih.gov",
                          "allowed_endpoints": [ES, EF],
                          "allowed_services": ["NCBI PubMed", "NCBI PMC"],
                          "all_other_network": "FORBIDDEN"},
        "esearch_validator": bound["esearch_validator"],
        "esearch_error_warning_schema": {k: bound[k] for k in (
            "esearch_errorlist", "esearch_warninglist", "esearch_schema")},
        "frame_policy": ref(OUT / "source_frame_execution_contract.json"),
        "frame_completion": ref(OUT / "source_frame_completion_barrier.json"),
        "dedup": ref(OUT / "cross_stratum_dedup_contract.json"),
        "sampling_seed": ref(seed_path),
        "sampling_seed_verification": ref(OUT / "sampling_seed_verification.json"),
        "sampling_algorithm": ref(OUT / "sampling_execution_contract.json"),
        "historical_contamination_registry": ref(seen_path),
        "historical_contamination_registry_verification": ref(OUT / "alpha3_18_seen_source_registry_verification.json"),
        "historical_contamination_gate": ref(OUT / "historical_source_contamination_gate.json"),
        "metadata_parser_and_fields": bound["metadata"],
        "sampled_metadata_execution": ref(OUT / "sampled_metadata_contract.json"),
        "primary_citation_parser": bound["primary_citation"],
        "primary_citation_execution": ref(OUT / "primary_citation_identity_binding_contract.json"),
        "reference_identity_exclusion": bound["primary_reference_exclusion"],
        "date_rule": ref(OUT / "publication_date_execution_contract.json"),
        "publication_type_rule": ref(OUT / "publication_type_execution_contract.json"),
        "correction_rule": ref(OUT / "correction_reference_execution_contract.json"),
        "metadata_barrier": ref(OUT / "metadata_completion_barrier.json"),
        "pre_oa_manifest": ref(OUT / "post_metadata_pre_oa_manifest_contract.json"),
        "oa_subset_route": ref(OUT / "pmc_oa_subset_execution_contract.json"),
        "jats_route": ref(OUT / "pmc_jats_acquisition_contract.json"),
        "jats_handoff": ref(OUT / "jats_handoff_manifest_contract.json"),
        "technical_retry_failure": {
            "search": bound["technical_transport"],
            "query_semantic": bound["query_semantic_retry"],
            "jats": bound["jats_failure"],
            "terminal_frame": "STOP_ALL_NETWORK_AND_FAIL_CLOSED",
            "terminal_metadata_or_jats_source": "RECORD_EXCLUDE_NO_REPLACEMENT"},
        "phase_barriers": [ref(OUT / "source_frame_completion_barrier.json"),
                           ref(OUT / "metadata_completion_barrier.json"),
                           ref(OUT / "alpha3_19a_completion_barrier.json")],
        "required_future_output_paths": required_future_outputs,
        "scientific_content_nonuse": ref(OUT / "scientific_content_nonuse_contract.json"),
        "search_plan_firewall": ref(OUT / "search_plan_firewall_audit.json"),
        "material_runtime_policy_unresolved_count": 0,
        "future_network_execution_requires_separate_authorization": True,
        "model_calls": 0,
        "no_license_source_type_construction_or_builder_execution": True,
    }
    # All local and historical manifest bindings must resolve before signing.
    def walk(node):
        if isinstance(node, dict):
            if "path" in node and "sha256" in node:
                check_ref(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(manifest)
    require(manifest["material_runtime_policy_unresolved_count"] == 0 and
            manifest["query_count"] == 6 and len(manifest["required_future_output_paths"]) >= 20,
            "ALPHA3_19A_EXECUTION_MANIFEST_INCOMPLETE")
    write("alpha3_19a_source_acquisition_execution_manifest.json", manifest)
    write("historical_preservation_audit.json", {
        "historical_assets_modified": False,
        "verified_read_only": [ref(p) for p in (
            master.C2 / "summary.json", master_queries_path, old_query_path,
            seen_path, seed_path, bindings["esearch_validator"],
            bindings["primary_citation"], bindings["correction"])],
        "historical_scientific_outcomes_used_for_selection": False})
    write("scientific_state_safety_audit.json", {
        "license_interpretation_deferred_to_19b": True,
        "source_type_execution_deferred_to_19b": True,
        "construction_document_generation_deferred_to_19b": True,
        "evidence_span_generation_deferred_to_19b": True,
        "builder_request_generation_deferred_to_19b": True,
        "builder_call_budget_not_yet_known": True,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0})
    required = ["master_preregistration_verification.json", "alpha3_19_attempt_boundary_verification.json",
        "alpha3_19_source_cohort_verification.json", "alpha3_19_source_query_set.jsonl",
        "alpha3_19_source_query_set_sha256", "alpha3_19_source_query_delta_audit.jsonl",
        "pubmed_esearch_validator_binding.json", "source_frame_execution_contract.json",
        "source_frame_completion_barrier.json", "cross_stratum_dedup_contract.json",
        "sampling_seed_verification.json", "sampling_execution_contract.json",
        "alpha3_18_seen_source_registry_verification.json", "historical_source_contamination_gate.json",
        "primary_citation_identity_binding_contract.json", "sampled_metadata_contract.json",
        "publication_date_execution_contract.json", "publication_type_execution_contract.json",
        "correction_reference_execution_contract.json", "metadata_completion_barrier.json",
        "post_metadata_pre_oa_manifest_contract.json", "pmc_oa_subset_execution_contract.json",
        "pmc_jats_acquisition_contract.json", "jats_handoff_manifest_contract.json",
        "scientific_content_nonuse_contract.json", "search_plan_firewall_audit.json",
        "alpha3_19a_completion_barrier.json", "alpha3_19a_source_acquisition_execution_manifest.json",
        "historical_preservation_audit.json", "scientific_state_safety_audit.json"]
    require(all((OUT / name).is_file() for name in required),
            "ALPHA3_19A_REQUIRED_OUTPUT_MISSING")
    write("validation.json", {"status": "completed", "required_outputs_present": True,
        "master_root_verified": True, "master_execution_plan_verified": True,
        "quality_envelope_verified": True, "query_count": 6,
        "query_scientific_term_changes": 0,
        "source_query_set_sha256": master.digest(OUT / "alpha3_19_source_query_set.jsonl"),
        "historical_source_registry_count": 1041,
        "manifest_bindings_verified": True,
        "material_runtime_policy_unresolved_count": 0})
    write("summary.json", {"status": "completed",
        "alpha3_19_master_prereg_verified": True,
        "alpha3_19_new_attempt": True,
        "source_cohort_start": "2024-01-01", "source_cohort_end": "2025-12-31",
        "source_query_count": 6, "source_query_scientific_term_changes": 0,
        "source_query_pmc_clause": '"pubmed pmc"[sb]',
        "pubmed_esearch_validator_v2_bound": True,
        "source_frame_cap_per_stratum": 200, "source_page_size": 50,
        "six_frame_completion_barrier": True,
        "new_sampling_seed_verified": True, "sample_cap_per_stratum": 12,
        "sample_before_seen_source_exclusion": True,
        "dynamic_source_replacement_allowed": False,
        "alpha3_18_seen_source_registry_count": 1041,
        "alpha3_18_seen_source_registry_bound": True,
        "primary_citation_identity_v1_bound": True,
        "reference_article_ids_excluded": True,
        "publication_integrity_rules_changed": False,
        "pmc_oa_subset_route_bound": True,
        "license_interpretation_deferred_to_19b": True,
        "source_type_execution_deferred_to_19b": True,
        "construction_document_generation_deferred_to_19b": True,
        "builder_call_budget_not_yet_known": True,
        "network_scope_ncbi_only": True,
        "material_runtime_policy_unresolved_count": 0,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "next_stage_recommendation": NEXT,
        "historical_assets_modified": False})
    marker("alpha3_19a_source_acquisition_execution_manifest_sha256",
           master.digest(OUT / "alpha3_19a_source_acquisition_execution_manifest.json"))
    marker("search_plan_v24_dev_alpha3_19a_prereg_sha256", root_hash())
    print(master.canonical({"status": "completed", "out": str(OUT),
        "query_set_sha256": master.digest(OUT / "alpha3_19_source_query_set.jsonl"),
        "manifest_sha256": master.digest(OUT / "alpha3_19a_source_acquisition_execution_manifest.json"),
        "root_sha256": root_hash()}).decode())


if __name__ == "__main__":
    main()
