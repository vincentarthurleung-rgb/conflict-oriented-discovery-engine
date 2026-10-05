#!/usr/bin/env python3
"""Freeze the alpha3.21C request universe and audit inherited execution authority.

No requests are sent. Unresolved eligibility or collision semantics block C1.
"""

from __future__ import annotations

import inspect
import json
import os
from collections import Counter
from pathlib import Path

from code_engine.extraction_assets import source_identity
from scripts import run_search_plan_v24_alpha321b_source_selection_offline as b
from scripts import run_search_plan_v24_alpha319c_pubmed_metadata_eligibility as historical
from scripts import run_search_plan_v24_alpha319a_ncbi_source_acquisition as rules
from scripts import search_plan_v24_alpha318a3_correction_reference as correction


ROOT, RUNS, MASTER, A1 = b.ROOT, b.RUNS, b.MASTER, b.A1
B = RUNS / "20261005_search_plan_v24_primary_alpha3_21b_offline_dedup_seen_exclusion_stratified_sampling"
C19 = RUNS / "20261002_search_plan_v24_dev_alpha3_19c_pubmed_metadata_eligibility"
A19 = RUNS / "20261001_search_plan_v24_dev_alpha3_19a_new_source_acquisition_preregistration_offline"
OUT = RUNS / "20261005_search_plan_v24_primary_alpha3_21c_metadata_source_type_preregistration_offline"
ROOT_MARKER = "search_plan_v24_primary_alpha3_21c_prereg_sha256"
B_SHA = "075192522a49d97fb650996b160b26b2cdec2631ebcdf052ea28fbc8f45f3bb3"
SAMPLE_SHA = "721ead72b454bb0cb8dee044e678c41f5e42393771726220a76cd7bee2e19a75"
C19_SHA = "922cc952e03bca7e8605971b9dcb6f4acfe3cfbe02e308ca26c9ab37c3a86689"
CLASS_BLOCKED = "FRESH_PRIMARY_METADATA_BLOCKED_BY_SOURCE_IDENTITY_COLLISION_AUTHORITY"
NEXT_BLOCKED = "AUDIT_ALPHA3_21C_SAME_ATTEMPT_SOURCE_IDENTITY_COLLISION_AUTHORITY_OFFLINE"
IDENTITY = "FRESH_PRIMARY_ALPHA3_21_METADATA_AND_SOURCE_TYPE_PREREGISTRATION"
NO_CALLS = {key: 0 for key in ("network_calls", "pubmed_metadata_calls", "pmc_calls",
                              "provider_calls", "llm_calls", "builder_calls", "quality_calls")}
canonical, digest, sha, root_hash, ref = b.canonical, b.digest, b.sha, b.root_hash, b.ref
obj, rows, require = b.obj, b.rows, b.require


def put_bytes(name: str, raw: bytes) -> str:
    with (OUT / name).open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return sha(raw)


def put(name: str, value: object) -> str:
    return put_bytes(name, canonical(value) + b"\n")


def freeze(stem: str, value: object, *, jsonl=False) -> str:
    raw = b"".join(canonical(row) + b"\n" for row in value) if jsonl else canonical(value) + b"\n"
    value_sha = put_bytes(stem + (".jsonl" if jsonl else ".json"), raw)
    put_bytes(stem + "_sha256", (value_sha + "\n").encode("ascii"))
    return value_sha


def implementation(function, role: str) -> dict:
    return {**ref(Path(inspect.getsourcefile(function)).resolve(), role),
            "entrypoint": function.__module__ + "." + function.__qualname__,
            "entrypoint_source_sha256": sha(inspect.getsource(function).encode("utf-8"))}


def verify_inputs() -> dict:
    for directory, marker, expected in (
        (B, "search_plan_v24_primary_alpha3_21b_sha256", B_SHA),
        (MASTER, "search_plan_v24_primary_alpha3_21_master_prereg_sha256", b.MASTER_SHA),
        (C19, "search_plan_v24_dev_alpha3_19c_sha256", C19_SHA),
        (A1, "search_plan_v24_primary_alpha3_21a1_sha256", b.A1_SHA),
    ):
        require((directory / marker).read_text().strip() == expected
                and root_hash(directory, marker) == expected,
                "UPSTREAM_ROOT_MISMATCH:" + marker)
    sample_path = B / "sampled_source_manifest.jsonl"
    require(digest(sample_path) == SAMPLE_SHA
            and (B / "sampled_source_manifest_sha256").read_text().strip() == SAMPLE_SHA,
            "SAMPLED_MANIFEST_HASH_MISMATCH")
    sample = rows(sample_path)
    require(len(sample) == len({r["pmid"] for r in sample}) == 72
            and all(b.PMID.fullmatch(r["pmid"]) for r in sample),
            "IMMUTABLE_72_SOURCE_IDENTITY_MISMATCH")
    strata = [r["stratum_id"] for r in rows(MASTER / "alpha3_21_source_query_set.jsonl")]
    require(Counter(r["owner_stratum"] for r in sample) == {s: 12 for s in strata},
            "SIX_STRATUM_SAMPLE_MISMATCH")
    barrier = obj(B / "sample_freeze_barrier.json")
    replacement = obj(B / "downstream_replacement_prohibition.json")
    require(barrier["immutable_sample"]["sha256"] == SAMPLE_SHA
            and barrier["frozen_before_any_metadata_or_downstream_execution"] is True
            and barrier["additions_allowed"] is False
            and barrier["replacement_allowed"] is False
            and barrier["topup_allowed"] is False
            and replacement["unsampled_source_addition_allowed"] is False
            and replacement["topup_allowed"] is False,
            "SAMPLE_FREEZE_OR_NO_REPLACEMENT_BARRIER_MISMATCH")
    require(digest(MASTER / "alpha3_21_seen_contamination_registry.json") == b.SEEN_SHA
            and digest(A1 / "alpha3_21_current_attempt_source_exposure_registry.json") == b.EXPOSURE_SHA,
            "CONTAMINATION_REGISTRY_HASH_MISMATCH")
    registry = obj(MASTER / "alpha3_21_seen_contamination_registry.json")
    historical_pmids = {r["pmid"] for r in registry["source_identities"]}
    require(len(historical_pmids) == 2545 and not historical_pmids & {r["pmid"] for r in sample},
            "SAMPLED_HISTORICAL_PMID_OVERLAP")
    canonical_aliases = {}
    for kind, expected in (("pmcid", 146), ("doi", 180)):
        originals = sorted({r[kind] for r in registry["source_identities"] if r.get(kind)})
        normalized = sorted({source_identity.normalize_identifier(value, kind) for value in originals})
        require(len(originals) == len(normalized) == expected
                and all(isinstance(value, str) and value for value in normalized),
                "HISTORICAL_ALIAS_CANONICAL_COUNT_MISMATCH:" + kind)
        canonical_aliases[kind] = {"canonical_values": normalized,
            "normalization_mapping": [{"original": v,
                "canonical": source_identity.normalize_identifier(v, kind)} for v in originals]}
    require(not source_identity.identifier_collision_rows(registry["source_identities"]),
            "HISTORICAL_CANONICAL_ALIAS_COLLISION")
    policy_binding = obj(MASTER / "alpha3_21_metadata_policy_binding.json")
    authority_paths = {key: b.checked_ref(policy_binding[key]) for key in
                       ("sampled_metadata", "publication_date", "publication_type", "correction_reference", "source_type")}
    metadata = obj(authority_paths["sampled_metadata"])
    metadata_path = b.checked_ref(metadata["metadata_policy"])
    transport_path = b.checked_ref(metadata["transport_policy"])
    transport = obj(transport_path)
    require(metadata["route"] == {"db": "pubmed", "endpoint": historical.EFETCH,
                "id": "frozen sampled canonical PMID", "method": "GET", "retmode": "xml"}
            and transport["maximum_attempts_per_request"] == 4
            and transport["timeout_seconds"] == 60 and transport["backoff_seconds"] == [2, 4, 8],
            "METADATA_CLIENT_OR_TECHNICAL_POLICY_MISMATCH")
    manifest = obj(A19 / "alpha3_19a_source_acquisition_execution_manifest.json")
    for key in ("sampled_metadata_execution", "primary_citation_execution", "pre_oa_manifest",
                "metadata_parser_and_fields", "date_rule", "publication_type_rule", "correction_rule"):
        b.checked_ref(manifest[key])
    require(manifest["technical_retry_failure"]["terminal_metadata_or_jats_source"] ==
            "RECORD_EXCLUDE_NO_REPLACEMENT", "PER_SOURCE_FAILURE_AUTHORITY_MISMATCH")
    identity_path = b.checked_ref(manifest["primary_citation_execution"])
    identity = obj(identity_path)
    for key in ("contract", "article_id_scope", "reference_exclusion"):
        b.checked_ref(identity[key])
    type_rule = obj(authority_paths["publication_type"])
    acceptance_path = b.checked_ref(type_rule["accepted_vocabulary"])
    exclusion_path = b.checked_ref(type_rule["excluded_vocabulary"])
    correction_rule = obj(authority_paths["correction_reference"])
    correction_contract = b.checked_ref(correction_rule["contract"])
    correction_pipeline = b.checked_ref(correction_rule["pipeline"])
    return {"sample": sample, "strata": strata, "canonical_aliases": canonical_aliases,
        "authority_paths": authority_paths, "metadata_path": metadata_path,
        "transport_path": transport_path, "transport": transport,
        "identity_path": identity_path, "identity": identity,
        "pre_oa_path": b.checked_ref(manifest["pre_oa_manifest"]),
        "acceptance_path": acceptance_path, "exclusion_path": exclusion_path,
        "correction_contract": correction_contract, "correction_pipeline": correction_pipeline}


def request_manifest(sample: list[dict]) -> list[dict]:
    requests = []
    for ordinal, source in enumerate(sample, 1):
        params = {"db": "pubmed", "retmode": "xml", "id": source["pmid"]}
        payload = {"method": "GET", "endpoint": historical.EFETCH, "parameters": params}
        request_sha = sha(canonical(payload))
        requests.append({"logical_request_id": "a321c_" + request_sha,
            "execution_ordinal": ordinal, "sampled_pmids": [source["pmid"]],
            **payload, "request_payload": payload, "request_payload_sha256": request_sha,
            "sampled_source_manifest_sha256": SAMPLE_SHA,
            "source_selection_provenance": source,
            "execution_requires_separate_C1_authorization_and_resolved_authority": True})
    return requests


def authority_audit() -> dict:
    # These are code/policy compatibility findings, not judgments about sampled articles.
    return {"execution_ready": False, "new_scientific_policy_created": False,
        "blockers": [
            {"code": "ALPHA3_21C_SAME_ATTEMPT_SOURCE_IDENTITY_COLLISION_AUTHORITY_UNRESOLVED",
             "existing_detector": implementation(source_identity.identifier_collision_rows, "canonical_exact_alias_collision_detector"),
             "existing_status": "identifier_conflict", "existing_resolution_status": "fail_closed",
             "master_registry_guard": ref(ROOT / "scripts/run_search_plan_v24_alpha321_master_prereg_offline.py", "historical_registry_cross_pmid_alias_conflict_guard"),
             "finding": "Detector emits collision audit rows; master guard aborts historical registry assembly. Neither specifies sampled-source terminal disposition, same-attempt cohort handling, or C1 handoff behavior.",
             "winner_rule_selected": None, "all_colliding_sources_excluded_by_new_rule": False,
             "stage_wide_vs_per_source_collision_failure_policy_invented": False},
            {"code": "ALPHA3_21C_PUBLICATION_WINDOW_PARSER_AUTHORITY_UNRESOLVED",
             "implementation": implementation(rules.frozen_date_year, "inherited_stable_year_parser"),
             "historical_accepted_years": [2024, 2025],
             "master_primary_window": {"start": "2026-01-01", "end": "2026-09-30", "inclusive": True},
             "finding": "Inherited parser reads Year/MedlineDate years, ignores Month/Day, and hardcodes 2024/2025 eligibility. Exact partial-year metadata verification and an authoritative 2026-compatible parser are not bound by the master.",
             "year_only_2026_rule_substituted": False, "new_date_precedence_selected": False}],
        "same_attempt_collision_detection_resolved": True,
        "same_attempt_collision_disposition_authority_resolved": False,
        "direct_citation_identity_parser_resolved": True,
        "complete_metadata_eligibility_parser_authority_resolved": False}


def run() -> dict:
    require(not OUT.exists(), "ALPHA321C_OUTPUT_ALREADY_EXISTS_NO_OVERWRITE")
    state = verify_inputs()
    audit = authority_audit()
    OUT.mkdir()
    for name, expected in (("alpha3_21b_root_verification.json", B_SHA),
                           ("alpha3_21_master_root_verification.json", b.MASTER_SHA)):
        put(name, {"verified_before_request_construction": True, "root_sha256": expected})
    put("sampled_source_manifest_verification.json", {
        "artifact": ref(B / "sampled_source_manifest.jsonl", "immutable_72_source_universe"),
        "sampled_source_count": 72, "six_strata": state["strata"], "sources_per_stratum": 12})
    put("sample_freeze_barrier_verification.json", {
        "barrier": ref(B / "sample_freeze_barrier.json", "immutable_sample_barrier"), "verified": True})
    put("preexisting_contamination_registry_binding.json", {
        "artifact": ref(MASTER / "alpha3_21_seen_contamination_registry.json", "only_current_historical_exclusion_registry"),
        "pmid_count": 2545, "pmcid_count": 146, "doi_count": 180,
        "canonical_aliases": state["canonical_aliases"], "sample_pmid_intersection_count": 0})
    put("current_attempt_exposure_registry_binding.json", {
        "artifact": ref(A1 / "alpha3_21_current_attempt_source_exposure_registry.json", "future_contamination_history"),
        "pmid_count": 1015, "current_exclusion_authority": False})
    put("historical_alpha3_19c_metadata_policy_binding.json", {
        "root_sha256": C19_SHA, "historical_root_verified": True,
        "master_binding": ref(MASTER / "alpha3_21_metadata_policy_binding.json", "inherited_policy_binding"),
        "policy_artifacts": {k: ref(p, k) for k, p in state["authority_paths"].items()},
        "historical_outcome_counts_used_as_targets": False,
        "historical_metadata_records_or_eligibility_labels_inspected": False})
    put("metadata_acquisition_client_authority.json", {
        "authority_resolved": True,
        "contract": ref(state["authority_paths"]["sampled_metadata"], "frozen_metadata_route"),
        "client": implementation(historical.PubMedTransport.fetch, "established_metadata_client"),
        "route": {"endpoint": historical.EFETCH, "method": "GET", "db": "pubmed", "retmode": "xml"},
        "one_logical_request_per_sampled_pmid": True, "client_instantiated": False})
    put("metadata_parser_authority.json", {
        "authority_resolved": False, "identity_paths_resolved": True,
        "parser": implementation(historical.parse_metadata, "historical_metadata_parser"),
        "date_dependency": implementation(rules.frozen_date_year, "historical_cohort_bound_date_dependency"),
        "field_contract": ref(state["metadata_path"], "metadata_fields_and_paths"),
        "future_parser_entrypoint_ready": False,
        "blocking_code": "ALPHA3_21C_PUBLICATION_WINDOW_PARSER_AUTHORITY_UNRESOLVED"})
    requests = request_manifest(state["sample"])
    require(len(requests) == len({r["logical_request_id"] for r in requests}) == 72,
            "REQUEST_UNIVERSE_IDENTITY_MISMATCH")
    requests_sha = freeze("metadata_request_manifest", requests, jsonl=True)
    put("metadata_execution_order.json", {"order_authority": "exact frozen 21B sampled-source manifest order",
        "logical_request_ids": [r["logical_request_id"] for r in requests], "sample_order_changed": False})
    validity_sha = freeze("metadata_response_validity_contract", {
        "execution_ready": False, "existing_transport_success": "HTTP 200 and no transport error",
        "parser": implementation(historical.parse_metadata, "existing_structural_identity_guards"),
        "existing_guards": ["XML parseability", "exactly one direct PubmedArticle",
            "exactly one direct MedlineCitation", "direct PMID equals requested PMID",
            "exactly one citation Article", "at most one PubmedData",
            "at most one direct ArticleIdList", "direct pubmed ArticleId cannot conflict"],
        "pure_error_envelope_without_required_article": "invalid under existing parser",
        "invalid_xml_or_identity_record": "SOURCE_FAILED_CLOSED; no parse-repair retry",
        "no_new_validator_behavior_added": True, "repair_allowed": False,
        "complete_execution_authority_blockers": [r["code"] for r in audit["blockers"]]})
    put("metadata_technical_retry_policy.json", {
        "transport_authority": ref(state["transport_path"], "metadata_client_explicitly_inherited_transport_values"),
        "client": implementation(historical.PubMedTransport.fetch, "metadata_retry_and_success_logic"),
        **{k: state["transport"][k] for k in ("maximum_attempts_per_request", "timeout_seconds", "backoff_seconds", "http_status_retryable")},
        "retryable_conditions": "missing HTTP status or frozen retryable HTTP status",
        "successful_http_response_ends_transport_retry": True,
        "parse_identity_or_scientific_failure_retry_allowed": False,
        "terminal_metadata_failure": "record source failure; continue other frozen sources; no replacement",
        "ESearch_stage_wide_terminal_scope_not_inherited_for_metadata": True})
    put("metadata_raw_response_preservation_contract.json", {
        "freeze_before_xml_parsing_extraction_eligibility_and_alias_checks": True,
        "every_attempt_fields": ["logical_request_id", "sampled_pmid", "attempt", "request_payload_sha256",
            "timestamp_utc", "transport_metadata", "raw_response_path", "raw_response_sha256"],
        "invalid_response_preserved": True, "invalid_response_identifiers_not_imported": True})
    put("publication_date_policy_binding.json", {
        "historical_policy": ref(state["authority_paths"]["publication_date"], "inherited_stable_year_date_policy"),
        "master_window": ref(MASTER / "alpha3_21_publication_window.json", "primary_inclusive_window"),
        "implementation": implementation(rules.frozen_date_year, "historical_date_parser"),
        "publication_date_policy_frozen": False, "execution_ready": False,
        "authority_conflict": audit["blockers"][1], "new_date_semantics_created": False})
    put("publication_type_policy_binding.json", {
        "policy": ref(state["authority_paths"]["publication_type"], "exact_publication_type_policy"),
        "accepted_vocabulary": ref(state["acceptance_path"], "unchanged_accepted_types"),
        "excluded_vocabulary": ref(state["exclusion_path"], "unchanged_excluded_types"),
        "implementation": implementation(rules.publication_type_state, "publication_type_classifier"),
        "states": obj(state["authority_paths"]["publication_type"])["states"], "rules_changed": False})
    put("correction_update_policy_binding.json", {
        "policy": ref(state["authority_paths"]["correction_reference"], "direction_sensitive_correction_policy"),
        "contract": ref(state["correction_contract"], "unchanged_correction_contract"),
        "pipeline": ref(state["correction_pipeline"], "inherited_deferred_progression_contract"),
        "implementation": implementation(correction.classify, "exact_correction_classifier"),
        "states": list(correction.STATES), "UpdateOf": "DEFERRED_TO_STRUCTURE_STAGE",
        "conditional_pre_oa_only_if_other_dimensions_clear": True, "forced_UpdateOf_CLEAR": False,
        "rules_changed": False})
    put("direct_article_identifier_binding_contract.json", {
        "policy": ref(state["identity_path"], "direct_citation_identity_contract"),
        "parser": implementation(historical.parse_metadata, "direct_article_identifier_extraction"),
        "pmid_path": "PubmedArticle/MedlineCitation/PMID",
        "pmcid_doi_path": "PubmedArticle/PubmedData/ArticleIdList/ArticleId direct child",
        "ReferenceList_or_related_target_identity_contribution": False,
        "missing_or_multiple_direct_pmcids": "metadata UNRESOLVED; no fabricated PMCID",
        "missing_direct_doi": "permitted by inherited identity rule",
        "multiple_distinct_direct_dois": "metadata UNRESOLVED"})
    for kind in ("pmcid", "doi"):
        put(kind + "_identity_normalization_binding.json", {
            "implementation": implementation(source_identity.normalize_identifier, "established_canonical_identifier_normalizer"),
            "kind_argument": kind, "historical_canonical_count": len(state["canonical_aliases"][kind]["canonical_values"]),
            "direct_extraction_zero_one_many_semantics_unchanged": True,
            "normalization_applies_after_direct_primary_identity_binding": True})
        put("preexisting_" + kind + "_contamination_gate.json", {
            "canonical_registry_artifact": ref(OUT / "preexisting_contamination_registry_binding.json", "preexisting_canonical_alias_snapshot"),
            "identifier_type": kind, "comparison": "exact canonical equality only",
            "contaminated_state": "POST_SAMPLE_EXACT_SOURCE_CONTAMINATION",
            "exclusion_without_replacement": True, "semantic_matching_allowed": False,
            "current_attempt_aliases_used_as_historical_exclusion": False})
    put("same_attempt_source_identity_collision_policy_binding.json", {
        **audit["blockers"][0], "policy_resolved": False,
        "primary_lifecycle_authority_candidates_examined": [
            ref(ROOT / "src/code_engine/extraction_assets/source_identity.py", "canonical_source_collision_audit"),
            ref(ROOT / "src/code_engine/corpus/paper_registry.py", "general_corpus_registry_not_inherited_primary_cohort_policy"),
            ref(ROOT / "scripts/run_search_plan_v24_alpha321_master_prereg_offline.py", "historical_registry_guard")],
        "default_winner_or_retain_both_policy_created": False})
    put("metadata_identity_exposure_registry_contract.json", {
        "future_artifact": "alpha3_21_current_attempt_metadata_identity_exposure_registry",
        "valid_response_only": True, "fields": ["sampled_pmid", "direct_pmcid_if_present", "direct_doi_if_present", "raw_response_sha256"],
        "ineligible_but_valid_source_identities_remain_future_exposure": True,
        "use": "future contamination history only", "original_master_and_A1_registries_mutated": False})
    put("metadata_no_self_contamination_contract.json", {
        "current_attempt_new_pmcids_used_as_current_historical_exclusion": False,
        "current_attempt_new_dois_used_as_current_historical_exclusion": False,
        "same_attempt_collision_is_historical_contamination": False})
    put("metadata_source_state_contract.json", {
        "existing_metadata_states": ["RESOLVED", "UNRESOLVED", "SOURCE_FAILED_CLOSED"],
        "existing_dimension_states": ["CLEAR", "INELIGIBLE", "UNRESOLVED"],
        "existing_deferred_UpdateOf_state": "DEFERRED_TO_STRUCTURE_STAGE",
        "existing_pre_oa_states": ["PRE_OA_CLEAR", "PRE_OA_CONDITIONAL_UPDATEOF", "BLOCKED"],
        "existing_exact_alias_contamination_state": "POST_SAMPLE_EXACT_SOURCE_CONTAMINATION",
        "existing_collision_audit_state": "identifier_conflict",
        "prospective_report_fields": ["metadata_response_state", "date_state", "publication_type_state",
            "correction_update_state", "direct_pmcid", "direct_doi", "historical_alias_contamination_state",
            "same_attempt_alias_collision_state", "pre_oa_handoff_state"],
        "complete_lifecycle_contract_ready": False, "unresolved_collision_disposition_not_invented": True})
    pre_oa_sha = freeze("metadata_pre_oa_handoff_contract", {
        "execution_ready": False,
        "inherited_contract": ref(state["pre_oa_path"], "clear_or_conditional_UpdateOf_pre_oa_gate"),
        "inherited_conditions": {"metadata_state": "RESOLVED", "date_state": "CLEAR",
            "publication_type_state": "CLEAR", "correction_state": "CLEAR or sole conditionally deferred UpdateOf reason"},
        "new_exact_historical_alias_gates_must_pass": True,
        "same_attempt_collision_disposition_authority_resolved": False,
        "date_parser_primary_window_authority_resolved": False,
        "handoff_must_preserve_conditional_deferred_state": True,
        "zero_eligible_handoff_is_valid_after_all_requests_have_terminal_states": True,
        "maximum_sources": 72, "additions_replacement_topup_allowed": False,
        "no_PMC_OA_license_JATS_or_BODY_eligibility_claim": True})
    put("metadata_source_funnel_contract.json", {
        "sampled_source_count": 72, "actual_metadata_counts_computed": False,
        "dimensions": ["metadata_valid", "metadata_terminal_failure", "date_eligible", "publication_type_eligible",
            "correction_update_direct_clear", "conditionally_deferred", "historical_pmid_contaminated",
            "historical_pmcid_contaminated", "historical_doi_contaminated", "same_attempt_identity_collision",
            "pre_oa_handoff_count"], "per_dimension_counts_may_overlap": True,
        "final_terminal_or_handoff_state_reported_separately": True,
        "ambiguous_sum_of_exclusion_counts_allowed": False})
    put("downstream_no_replacement_binding.json", {
        "artifact": ref(B / "downstream_replacement_prohibition.json", "frozen_no_replacement_contract"),
        "downstream_replacement_allowed": False, "sample_size_or_ownership_changes_allowed": False})
    put("alpha3_21c1_execution_handoff.json", {
        "execution_ready": False, "authorization_ready": False,
        "network_authorized": False, "planned_metadata_logical_requests": 72,
        "request_manifest": ref(OUT / "metadata_request_manifest.jsonl", "frozen_72_source_request_universe"),
        "required_authority_resolution_before_network_authorization": audit["blockers"],
        "maximum_potential_transport_attempts_if_authorized": 288})
    put("authority_resolution_audit.json", audit)
    put("builder_v4_nonuse_audit.json", {"builder_calls": 0, "builder_requests_constructed": False})
    put("quality_nonuse_audit.json", {"quality_calls": 0, "quality_requests_constructed": False})
    put("fresh_primary_policy_nonadaptation_audit.json", {
        "scientific_policy_changed": False, "sample_changed": False, "source_queries_changed": False,
        "publication_window_changed": False, "historical_date_rule_amended": False,
        "same_attempt_collision_disposition_policy_created": False,
        "historical_outcome_distributions_used_as_targets": False})
    verify_inputs()
    put("historical_preservation_audit.json", {
        "B_master_A1_C19_roots_reverified_unchanged": True,
        "sample_and_both_registries_unchanged": True, "historical_assets_modified": False})
    put("scientific_state_safety_audit.json", {**NO_CALLS,
        "metadata_execution_started": False, "pmc_execution_started": False,
        "builder_execution_started": False, "quality_execution_started": False,
        "retrieval_evaluation_started": False, "abstract_scientific_inspection_performed": False})
    put("execution_implementation_binding.json", ref(Path(__file__).resolve(), "offline_preregistration_authority_audit"))
    result = {"status": "failed", "stage_identity": IDENTITY, "alpha3_21c_classification": CLASS_BLOCKED,
        "alpha3_21b_root_verified": True, "alpha3_21_master_root_verified": True,
        "sampled_source_count": 72, "sampled_source_manifest_sha256": SAMPLE_SHA,
        "metadata_request_authority_resolved": True, "metadata_parser_authority_resolved": False,
        "planned_metadata_logical_requests": 72, "publication_date_policy_frozen": False,
        "publication_type_policy_frozen": True, "correction_update_policy_frozen": True,
        "direct_pmcid_binding_frozen": True, "direct_doi_binding_frozen": True,
        "preexisting_seen_pmid_count": 2545, "preexisting_seen_pmcid_count": 146, "preexisting_seen_doi_count": 180,
        "preexisting_pmcid_contamination_gate_frozen": True, "preexisting_doi_contamination_gate_frozen": True,
        "same_attempt_source_identity_collision_policy_resolved": False,
        "current_attempt_aliases_self_exclude": False, "downstream_replacement_allowed": False,
        "metadata_request_manifest_sha256": requests_sha,
        "metadata_response_validity_contract_sha256": validity_sha,
        "metadata_pre_oa_handoff_contract_sha256": pre_oa_sha,
        "metadata_execution_started": False, "pmc_execution_started": False,
        "builder_execution_started": False, "quality_execution_started": False,
        "retrieval_evaluation_started": False, **NO_CALLS,
        "next_stage_recommendation": NEXT_BLOCKED, "historical_assets_modified": False,
        "authority_blocking_codes": [r["code"] for r in audit["blockers"]]}
    put("validation.json", result)
    put("summary.json", result)
    root = root_hash(OUT, ROOT_MARKER)
    put_bytes(ROOT_MARKER, (root + "\n").encode("ascii"))
    return {**result, ROOT_MARKER: root}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
