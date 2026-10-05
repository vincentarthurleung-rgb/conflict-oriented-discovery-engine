#!/usr/bin/env python3
"""Prospectively freeze only the two alpha3.21C execution-authority overlays."""

from __future__ import annotations

import json
import os
from pathlib import Path
from xml.sax.saxutils import escape

from scripts import run_search_plan_v24_alpha321c_metadata_prereg_offline as c
from scripts import search_plan_v24_alpha321_metadata_eligibility_v2 as v2


ROOT, RUNS, C, B, MASTER = c.ROOT, c.RUNS, c.OUT, c.B, c.MASTER
OUT = RUNS / "20261006_search_plan_v24_primary_alpha3_21c1_metadata_authority_resolution_offline"
ROOT_MARKER = "search_plan_v24_primary_alpha3_21c1_sha256"
C_SHA = "026ad401d9b158f44fdf7a19e47f3615c374ba5657275a8b4eae6b6952bbca85"
REQUEST_SHA = "dc5cedcb5e995e85f0b7e31b91baf962b38c7e80719d9e0982c554b905d66aef"
NO_CALLS = {name: 0 for name in ("network_calls", "pubmed_calls", "pubmed_metadata_calls",
                                "pmc_calls", "provider_calls", "llm_calls", "builder_calls", "quality_calls")}
canonical, digest, sha, root_hash, ref = c.canonical, c.digest, c.sha, c.root_hash, c.ref
obj, rows, require, implementation = c.obj, c.rows, c.require, c.implementation


def put_bytes(name: str, raw: bytes) -> str:
    with (OUT / name).open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return sha(raw)


def put(name: str, value: object) -> str:
    return put_bytes(name, canonical(value) + b"\n")


def freeze(stem: str, value: object) -> str:
    value_sha = put(stem + ".json", value)
    put_bytes(stem + "_sha256", (value_sha + "\n").encode("ascii"))
    return value_sha


def synthetic_xml(pmid="123", pubdate="<Year>2026</Year><Month>07</Month><Day>01</Day>",
                  article_dates="", pmcid="PMC123", doi="10.fixture/123", relationships="", extra_data="", types="Journal Article") -> bytes:
    pubdate_xml = f"<Journal><JournalIssue><PubDate>{pubdate}</PubDate></JournalIssue></Journal>" if pubdate else ""
    ids = '<ArticleId IdType="pubmed">' + escape(pmid) + '</ArticleId>'
    if pmcid is not None:
        ids += '<ArticleId IdType="pmc">' + escape(pmcid) + '</ArticleId>'
    if doi is not None:
        ids += '<ArticleId IdType="doi">' + escape(doi) + '</ArticleId>'
    return (f'<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>{escape(pmid)}</PMID>'
            f'<Article>{pubdate_xml}{article_dates}<PublicationTypeList><PublicationType>{escape(types)}</PublicationType>'
            f'</PublicationTypeList></Article>{relationships}</MedlineCitation><PubmedData><ArticleIdList>{ids}'
            f'</ArticleIdList>{extra_data}</PubmedData></PubmedArticle></PubmedArticleSet>').encode("utf-8")


def date_fixtures() -> list[dict]:
    cases = [
        ("exact_inside", "<Year>2026</Year><Month>07</Month><Day>01</Day>", "", v2.DATE_IN),
        ("start_boundary", "<Year>2026</Year><Month>01</Month><Day>01</Day>", "", v2.DATE_IN),
        ("end_boundary", "<Year>2026</Year><Month>09</Month><Day>30</Day>", "", v2.DATE_IN),
        ("before_window", "<Year>2025</Year><Month>12</Month><Day>31</Day>", "", v2.DATE_OUT),
        ("after_window", "<Year>2026</Year><Month>10</Month><Day>01</Day>", "", v2.DATE_OUT),
        ("2026_09", "<Year>2026</Year><Month>09</Month>", "", v2.DATE_IN),
        ("2026_10", "<Year>2026</Year><Month>10</Month>", "", v2.DATE_OUT),
        ("year_only_2026", "<Year>2026</Year>", "", v2.DATE_PARTIAL),
        ("known_year_named_month", "<Year>2026</Year><Month>Jul</Month>", "", v2.DATE_IN),
        ("leap_day_valid", "<Year>2024</Year><Month>02</Month><Day>29</Day>", "", v2.DATE_OUT),
        ("nonleap_day_invalid", "<Year>2026</Year><Month>02</Month><Day>29</Day>", "", v2.DATE_BAD),
        ("explicit_range", "<MedlineDate>2026-01-01/2026-09-30</MedlineDate>", "", v2.DATE_IN),
        ("partial_overlap_range", "<MedlineDate>2026-09-15/2026-10-15</MedlineDate>", "", v2.DATE_PARTIAL),
        ("named_month_range", "<MedlineDate>2026 Jan-Sep</MedlineDate>", "", v2.DATE_IN),
        ("named_partial_month_range", "<MedlineDate>2026 Sep-Oct</MedlineDate>", "", v2.DATE_PARTIAL),
        ("missing_date", "", "", v2.DATE_MISSING),
        ("unparseable_date", "<MedlineDate>publication pending</MedlineDate>", "", v2.DATE_BAD),
        ("unknown_season", "<Year>2026</Year><Season>Autumn</Season>", "", v2.DATE_BAD),
        ("multiple_agree", "<Year>2026</Year><Month>01</Month>",
         "<ArticleDate><Year>2026</Year><Month>09</Month></ArticleDate>", v2.DATE_IN),
        ("multiple_conflict", "<Year>2026</Year><Month>09</Month>",
         "<ArticleDate><Year>2026</Year><Month>10</Month></ArticleDate>", v2.DATE_CONFLICT),
        ("exact_plus_partial", "<Year>2026</Year><Month>07</Month><Day>01</Day>",
         "<ArticleDate><Year>2026</Year></ArticleDate>", v2.DATE_CONFLICT),
        ("parseable_plus_unparseable", "<Year>2026</Year><Month>07</Month>",
         "<ArticleDate><MedlineDate>unknown</MedlineDate></ArticleDate>", v2.DATE_BAD),
    ]
    return [{"fixture_id": name, "fixture_origin": "OFFLINE_SYNTHETIC_NOT_SAMPLED_METADATA",
             "expected_pmid": "123", "raw_xml": synthetic_xml(pubdate=pubdate, article_dates=dates).decode("utf-8"),
             "expected_date_state": expected} for name, pubdate, dates, expected in cases]


def verify_inputs() -> dict:
    require((C / c.ROOT_MARKER).read_text().strip() == C_SHA
            and root_hash(C, c.ROOT_MARKER) == C_SHA, "FAILED_C_ROOT_MISMATCH")
    state = c.verify_inputs()
    validation = obj(C / "validation.json")
    require(validation["status"] == "failed" and validation["alpha3_21c_classification"] == c.CLASS_BLOCKED
            and validation["metadata_parser_authority_resolved"] is False
            and validation["publication_date_policy_frozen"] is False
            and validation["same_attempt_source_identity_collision_policy_resolved"] is False
            and validation["metadata_execution_started"] is False,
            "FAILED_C_FACTUAL_STATE_CHANGED")
    request_path = C / "metadata_request_manifest.jsonl"
    require(digest(request_path) == REQUEST_SHA
            and (C / "metadata_request_manifest_sha256").read_text().strip() == REQUEST_SHA,
            "FROZEN_REQUEST_MANIFEST_MISMATCH")
    requests = rows(request_path)
    require(len(requests) == 72 and [r["sampled_pmids"][0] for r in requests] == [r["pmid"] for r in state["sample"]],
            "REQUEST_AND_SAMPLE_UNIVERSE_MISMATCH")
    window = obj(MASTER / "alpha3_21_publication_window.json")
    require(window["publication_window_start"] == v2.WINDOW_START.isoformat()
            and window["publication_window_end"] == v2.WINDOW_END.isoformat()
            and window["end_inclusive"] is True, "EXACT_WINDOW_AUTHORITY_MISMATCH")
    stable_names = ["metadata_acquisition_client_authority.json", "metadata_response_validity_contract.json",
        "metadata_technical_retry_policy.json", "metadata_raw_response_preservation_contract.json",
        "publication_type_policy_binding.json", "correction_update_policy_binding.json",
        "direct_article_identifier_binding_contract.json", "pmcid_identity_normalization_binding.json",
        "doi_identity_normalization_binding.json", "preexisting_pmcid_contamination_gate.json",
        "preexisting_doi_contamination_gate.json", "downstream_no_replacement_binding.json",
        "metadata_identity_exposure_registry_contract.json", "metadata_no_self_contamination_contract.json"]

    def check_references(value):
        if isinstance(value, dict):
            if "artifact_path" in value and "sha256" in value:
                c.b.checked_ref(value)
            for child in value.values():
                check_references(child)
        elif isinstance(value, list):
            for child in value:
                check_references(child)

    for name in stable_names:
        check_references(obj(C / name))
    state["stable_names"] = stable_names
    return state


def run() -> dict:
    require(not OUT.exists(), "ALPHA321C1_OUTPUT_ALREADY_EXISTS_NO_OVERWRITE")
    state = verify_inputs()
    fixtures = date_fixtures()
    # Only synthetic metadata is processed. No real source metadata is loaded.
    first = [v2.resolve_publication_dates(f["raw_xml"].encode(), f["expected_pmid"]) for f in fixtures]
    second = [v2.resolve_publication_dates(f["raw_xml"].encode(), f["expected_pmid"]) for f in fixtures]
    require(canonical(first) == canonical(second)
            and all(r["state"] == f["expected_date_state"] for r, f in zip(first, fixtures)),
            "DATE_FIXTURE_EXPECTATION_OR_DETERMINISM_FAILURE")
    OUT.mkdir()
    for name, expected in (("alpha3_21c_root_verification.json", C_SHA),
                           ("alpha3_21b_root_verification.json", c.B_SHA),
                           ("alpha3_21_master_root_verification.json", c.b.MASTER_SHA)):
        put(name, {"root_sha256": expected, "verified": True})
    put("metadata_request_manifest_preservation_audit.json", {
        "original_request_manifest": ref(C / "metadata_request_manifest.jsonl", "only_future_C2_request_universe"),
        "metadata_request_manifest_unchanged": True, "logical_request_count": 72,
        "request_regeneration_performed": False, "new_request_manifest_created": False,
        "sampled_manifest": ref(B / "sampled_source_manifest.jsonl", "unchanged_sample")})
    put("historical_date_parser_incompatibility_audit.json", {
        "classification": "DATE_PARSER_IMPLEMENTATION_INCOMPATIBLE_WITH_FROZEN_WINDOW",
        "historical_parser": implementation(c.rules.frozen_date_year, "unchanged_2024_2025_year_only_implementation"),
        "master_window": ref(MASTER / "alpha3_21_publication_window.json", "existing_scientific_date_policy"),
        "historical_parser_compatible_with_alpha3_21_window": False,
        "master_window_authority_conflict": False, "historical_parser_or_results_changed": False})
    put("direct_publication_date_field_authority_audit.json", {
        "field_contract": ref(state["metadata_path"], "established_direct_publication_date_paths"),
        "historical_implementation": implementation(c.rules.frozen_date_year, "historical_year_consistency_not_date_precedence"),
        "historical_fixture_suite": ref(ROOT / "tests/test_run_search_plan_v24_alpha319c_pubmed_metadata_eligibility.py", "existing_direct_record_date_fixture"),
        "paths": v2.DATE_PATHS, "structured_or_text_fields": v2.DATE_FIELDS,
        "existing_unique_governing_precedence_found": False,
        "adopted_user_authorized_procedure": "conservative multi-representation agreement",
        "History_ReferenceList_and_related_record_dates_used": False})
    put("publication_date_interval_normalization_spec.json", {
        "implementation": implementation(v2.resolve_publication_dates, "new_direct_date_interval_resolver"),
        "supported_direct_fields": v2.DATE_FIELDS, "supported_direct_paths": v2.DATE_PATHS,
        "month_vocabulary": {**v2.MONTHS, "numeric": "1..12; one or two decimal digits"},
        "structured_date_precision": {"Year": "Jan 1..Dec 31", "Year_Month": "first..last calendar day of month",
            "Year_Month_Day": "one calendar day"},
        "MedlineDate_grammar": ["YYYY", "YYYY-MM", "YYYY-MM-DD", "YYYY EnglishMonth", "YYYY EnglishMonth D[D]",
            "two supported endpoints separated by / or .. or ' to '", "YYYY Month-Month", "YYYY Month D[D]-D[D]",
            "YYYY Month-YYYY Month"],
        "gregorian_calendar_and_leap_year_validation": True,
        "reversed_range_or_invalid_calendar_date": "UNPARSEABLE_DIRECT_PUBLICATION_DATE",
        "unknown_Season_or_duplicate_fields_or_mixed_MedlineDate_and_structured_fields": "UNPARSEABLE_DIRECT_PUBLICATION_DATE",
        "precision_invented": False, "locale_independent_english_month_vocabulary": True})
    date_sha = freeze("publication_date_resolution_contract_v2", {
        "schema_version": "PublicationDateResolutionContractV2",
        "implementation": ref(ROOT / "scripts/search_plan_v24_alpha321_metadata_eligibility_v2.py", "versioned_offline_date_and_collision_helper"),
        "normalization_spec": ref(OUT / "publication_date_interval_normalization_spec.json", "frozen_interval_grammar"),
        "publication_window_start": "2026-01-01", "publication_window_end": "2026-09-30", "inclusive": True,
        "field_authority": ref(OUT / "direct_publication_date_field_authority_audit.json", "direct_record_paths_only"),
        "inside_rule": "entire possible interval inside window",
        "outside_rule": "entire possible interval disjoint from window",
        "partial_overlap_state": v2.DATE_PARTIAL, "year_only_2026_automatically_eligible": False,
        "multiple_representations": "all parseable direct representations must agree on IN or OUT; partial or conflicting conclusions unresolved",
        "any_unparseable_direct_representation": v2.DATE_BAD,
        "authoritative_precedence": None, "ESearch_inclusion_substitutes_for_metadata_verification": False,
        "fresh_metadata_observed_before_freeze": False})
    put("publication_date_terminal_state_contract.json", {
        "DATE_CLEAR_IN_WINDOW": "satisfies only date dimension",
        "DATE_CLEAR_OUTSIDE_WINDOW": "exclude without replacement",
        "DATE_UNRESOLVED_*": "exclude without replacement",
        "unparseable_representation_state": "UNPARSEABLE_DIRECT_PUBLICATION_DATE",
        "article_level_states": [v2.DATE_IN, v2.DATE_OUT, v2.DATE_PARTIAL, v2.DATE_CONFLICT, v2.DATE_MISSING, v2.DATE_BAD],
        "date_unresolved_sources_enter_pre_oa_handoff": False})
    fixture_sha = put_bytes("publication_date_synthetic_fixtures.jsonl", b"".join(canonical(f) + b"\n" for f in fixtures))
    put("publication_date_parser_fixture_manifest.json", {
        "fixture_artifact": ref(OUT / "publication_date_synthetic_fixtures.jsonl", "offline_synthetic_date_tests"),
        "fixture_count": len(fixtures), "fixture_sha256": fixture_sha,
        "cases": [{"fixture_id": f["fixture_id"], "expected_state": f["expected_date_state"],
                   "xml_sha256": sha(f["raw_xml"].encode())} for f in fixtures]})
    put("publication_date_parser_determinism_audit.json", {
        "fixture_count": len(fixtures), "runs": 2, "byte_identical": True,
        "first_results_sha256": sha(canonical(first)), "second_results_sha256": sha(canonical(second)),
        "all_expected_states_passed": True, "fresh_source_metadata_used": False})
    put("same_attempt_identity_collision_definition.json", {
        "distinct_sampled_pmids_share_exact_canonical_direct_PMCID_or_DOI": True,
        "canonical_normalization": ref(C / "doi_identity_normalization_binding.json", "unchanged_identifier_normalizer"),
        "direct_extraction": ref(C / "direct_article_identifier_binding_contract.json", "unchanged_identifier_zero_one_many_semantics"),
        "exact_source_identity_integrity_only": True, "scientific_invalidity_asserted": False,
        "titles_authors_abstracts_relations_or_semantic_similarity_used": False})
    put("same_attempt_identity_collision_graph_contract.json", {
        "implementation": implementation(v2.collision_components, "exact_alias_connected_components"),
        "nodes": "all immutable sampled PMID records; edges use singly bound aliases from structurally valid metadata",
        "edge": "same canonical direct PMCID or DOI; distinct PMID nodes",
        "transitive_multi_identifier_components": True,
        "historically_contaminated_or_otherwise_ineligible_valid_identities_participate_for_integrity_audit": True,
        "repeated_identifier_in_one_record_creates_component": False,
        "sort_order_is_serialization_only_not_winner_selection": True})
    put("same_attempt_identity_collision_terminal_state_contract.json", {
        "state": v2.COLLISION, "component_minimum_size": 2,
        "resolution": "FAIL_CLOSE_ALL_COMPONENT_MEMBERS",
        "every_member_excluded_from_downstream_handoff": True,
        "scientific_eligibility_claim": False, "winner_selection": False,
        "collapse_to_one_synthetic_record": False, "replacement_allowed": False,
        "historical_contamination_remains_primary_reporting_reason_where_present": True,
        "stronger_existing_source_identity_rule_conflict_found": False})
    put("same_attempt_collision_no_winner_audit.json", {
        "winner_selection_used": False, "collapse_used": False,
        "PMID_rank_order_metadata_completeness_or_content_used_to_retain_one_member": False,
        "existing_conflict_detector": implementation(c.source_identity.identifier_collision_rows, "unchanged_identifier_conflict_fail_closed_authority"),
        "new_terminal_semantics_instantiates_existing_fail_closed_integrity_boundary": True})
    put("same_attempt_collision_no_replacement_binding.json", {
        "binding": ref(C / "downstream_no_replacement_binding.json", "unchanged_no_replacement_authority"),
        "excluded_sample_units_are_not_replaced": True, "unsampled_943_sources_used": False})
    put("source_terminal_reason_precedence.json", {
        "primary_reporting_reason_precedence": v2.PRECEDENCE,
        "reporting_only": True, "all_exclusion_dimensions_preserved": True,
        "precedence_changes_progression": False,
        "metadata_unresolved_direct_identity_also_blocks_under_existing_metadata_contract": True})
    stable = {name.removesuffix(".json"): ref(C / name, "unchanged_C_component") for name in state["stable_names"]}
    put("metadata_parser_component_binding_manifest.json", {
        "stable_components": stable,
        "legacy_parser": implementation(c.historical.parse_metadata, "unchanged_direct_identity_extractor"),
        "new_date_component": ref(OUT / "publication_date_resolution_contract_v2.json", "prospective_exact_window_resolution"),
        "new_collision_component": ref(OUT / "same_attempt_identity_collision_terminal_state_contract.json", "prospective_all_members_terminal_rule"),
        "legacy_parser_date_state_only_overlaid": True,
        "historical_failed_C_readiness_flags_not_mutated": True})
    composite_sha = freeze("alpha321_metadata_eligibility_parser_contract_v2", {
        "schema_version": "Alpha321MetadataEligibilityParserContractV2",
        "implementation": implementation(v2.evaluate_batch, "offline_composite_metadata_eligibility"),
        "components": ref(OUT / "metadata_parser_component_binding_manifest.json", "immutable_component_bindings"),
        "processing_order": ["existing response and requested PMID validation", "existing direct IDs and canonical normalization",
            "historical exact alias contamination", "freeze all valid direct source identities", "complete collision graph and terminal dimensions",
            "new date and unchanged type/correction/update dimensions", "all-dimension pre-OA handoff"],
        "pre_oa_conditions": {"metadata_state": "RESOLVED", "historical_alias_contamination": "CLEAR",
            "same_attempt_alias_collision": "CLEAR", "date_resolution": v2.DATE_IN,
            "publication_type": "CLEAR", "correction_update": "CLEAR or sole inherited deferred UpdateOf reason"},
        "dimension_classification_before_graph_has_no_selection_side_effects": True,
        "order_equivalence": "Pure date/type/correction classification may occur during parsing; no record is filtered, admitted, or omitted from collision diagnosis by those results. Final progression is decided only after all identities and components are complete.",
        "UpdateOf_state_preserved": "DEFERRED_TO_STRUCTURE_STAGE",
        "final_pre_oa_states": ["PRE_OA_CLEAR", "PRE_OA_CONDITIONAL_UPDATEOF", "BLOCKED"],
        "per_source_metadata_terminal_failure_isolation": True,
        "input_sample_units_preserved": True, "no_replacement": True,
        "zero_handoff_is_valid": True, "actual_metadata_execution_authorized": False})
    put("metadata_execution_readiness_audit.json", {
        "publication_date_policy_frozen": True, "metadata_parser_authority_resolved": True,
        "same_attempt_source_identity_collision_policy_resolved": True,
        "metadata_request_manifest_unchanged": True, "all_stable_C_component_bindings_valid": True,
        "metadata_execution_ready": True, "network_authorization_present": False})
    put("alpha3_21c1_future_execution_handoff.json", {
        "next_execution_stage": "alpha3.21C2",
        "original_metadata_requests": ref(C / "metadata_request_manifest.jsonl", "only_72_logical_request_universe"),
        "logical_request_count": 72, "maximum_transport_attempts": 288,
        "transport_and_retry": ref(C / "metadata_technical_retry_policy.json", "unchanged_metadata_technical_policy"),
        "response_raw_preservation": ref(C / "metadata_raw_response_preservation_contract.json", "freeze_every_attempt_before_parse"),
        "composite_parser": ref(OUT / "alpha321_metadata_eligibility_parser_contract_v2.json", "new_execution_authority_overlay"),
        "future_alias_exposure": ref(C / "metadata_identity_exposure_registry_contract.json", "future_attempt_history_only"),
        "historical_alias_exclusion_registry": ref(C / "preexisting_contamination_registry_binding.json", "only_preexisting_alias_authority"),
        "metadata_execution_ready": True, "network_authorized": False,
        "future_separate_network_authorization_required": True})
    put("fresh_metadata_not_observed_audit.json", {
        "fresh_metadata_observed": False, "actual_72_source_metadata_inspected": False,
        "offline_synthetic_fixture_count": len(fixtures), "request_generation_or_execution_performed": False})
    nonadaptation = {key: False for key in ("publication_window_changed", "publication_type_policy_changed",
        "correction_update_policy_changed", "historical_alias_contamination_policy_changed",
        "sample_changed", "request_manifest_changed", "builder_policy_changed", "quality_policy_changed")}
    put("scientific_policy_nonadaptation_audit.json", {**nonadaptation,
        "new_execution_semantics": ["exact publication date interval resolution", "all-members exact source identity collision terminal state"],
        "outcome_informed_modification": False})
    verify_inputs()
    put("historical_preservation_audit.json", {
        "failed_C_classification_and_false_readiness_flags_preserved": True,
        "C_B_master_roots_unchanged": True, "request_and_sample_hashes_unchanged": True,
        "historical_2024_2025_parser_unchanged": True, "historical_assets_modified": False})
    put("scientific_state_safety_audit.json", {**NO_CALLS, "metadata_execution_started": False,
        "builder_execution_started": False, "quality_execution_started": False,
        "retrieval_evaluation_started": False, "PMC_OA_or_JATS_processing_started": False})
    put("execution_implementation_binding.json", ref(Path(__file__).resolve(), "offline_authority_overlay_freeze"))
    put("focused_test_implementation_binding.json", ref(ROOT / "tests/test_search_plan_v24_alpha321_metadata_eligibility_v2.py", "synthetic_date_collision_and_boundary_tests"))
    result = {"status": "completed",
        "stage_identity": "FRESH_PRIMARY_ALPHA3_21_METADATA_EXECUTION_AUTHORITY_RESOLUTION_OVERLAY",
        "alpha3_21c1_classification": "METADATA_EXECUTION_AUTHORITY_RESOLVED_BEFORE_FRESH_METADATA_OBSERVATION",
        "alpha3_21c_root_verified": True, "alpha3_21b_root_verified": True, "alpha3_21_master_root_verified": True,
        "sampled_source_count": 72, "metadata_request_manifest_sha256": REQUEST_SHA,
        "metadata_request_manifest_unchanged": True,
        "historical_date_parser_compatible_with_alpha3_21_window": False,
        "publication_window_start": "2026-01-01", "publication_window_end": "2026-09-30",
        "publication_date_resolution_contract_v2_frozen": True,
        "publication_date_resolution_contract_v2_sha256": date_sha,
        "year_only_2026_automatically_eligible": False, "partial_overlap_date_state": v2.DATE_PARTIAL,
        "date_unresolved_sources_enter_pre_oa_handoff": False,
        "same_attempt_collision_policy_resolved": True,
        "same_attempt_collision_resolution": "FAIL_CLOSE_ALL_COMPONENT_MEMBERS",
        "same_attempt_collision_winner_selection_used": False, "same_attempt_collision_collapse_used": False,
        "same_attempt_collision_replacement_allowed": False,
        "metadata_parser_authority_resolved": True,
        "alpha321_metadata_eligibility_parser_contract_v2_sha256": composite_sha,
        "publication_date_policy_frozen": True, **nonadaptation,
        "metadata_request_manifest_changed": False, "fresh_metadata_observed": False,
        "metadata_execution_ready": True, **NO_CALLS,
        "next_stage_recommendation": "AUTHORIZE_ALPHA3_21C2_METADATA_AND_SOURCE_TYPE_NETWORK_EXECUTION",
        "historical_assets_modified": False}
    put("validation.json", result)
    put("summary.json", result)
    root = root_hash(OUT, ROOT_MARKER)
    put_bytes(ROOT_MARKER, (root + "\n").encode("ascii"))
    return {**result, ROOT_MARKER: root}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
