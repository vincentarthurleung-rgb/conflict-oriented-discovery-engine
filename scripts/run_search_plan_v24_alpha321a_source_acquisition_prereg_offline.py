#!/usr/bin/env python3
"""Freeze alpha3.21A PubMed request universe without network execution."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
MASTER = RUNS / "20261005_search_plan_v24_primary_alpha3_21_fresh_primary_master_preregistration_offline"
A19 = RUNS / "20261001_search_plan_v24_dev_alpha3_19a_new_source_acquisition_preregistration_offline"
A19_VALIDITY = RUNS / "20261002_search_plan_v24_dev_alpha3_19a1_ncbi_esearch_backend_failure_audit_offline"
OUT = RUNS / "20261005_search_plan_v24_primary_alpha3_21a_fresh_source_acquisition_preregistration_offline"
ROOT_MARKER = "search_plan_v24_primary_alpha3_21a_prereg_sha256"
MASTER_ROOT = "47c0ba15f6acb4e1e581d148edbfa0674a7dc1e82261764876cef20f4184d935"
MASTER_PLAN_SHA = "7628bbfd8560a4c2b6c0bebbe4f650bda5b507cd7df3e0204a6e1b4389fbd582"
SEEN_SHA = "2c1a5b6cb46d4dace84f77068bc2ba3805760594927e1f5b7e8e11af2e08dab3"
SEED_SHA = "ad531a2b47d4a9ffdea7338c7f3fbabd8d39b404c623ae4777f8bdc4a43adae9"
CLASSIFICATION = "FRESH_SOURCE_ACQUISITION_REQUEST_UNIVERSE_FROZEN"
NEXT = "AUTHORIZE_ALPHA3_21A1_FRESH_SOURCE_ACQUISITION_NETWORK_EXECUTION"
PAGE_OFFSETS = (0, 50, 100, 150)
TERMINAL_STATES = ("NOT_YET_EXECUTED", "NOT_REQUIRED_BY_COUNT",
                   "VALID_SUCCESS", "TERMINAL_TECHNICAL_FAILURE",
                   "RESPONSE_VALIDITY_FAILURE", "RESULT_SET_COUNT_DRIFT",
                   "NOT_EXECUTED_AFTER_STAGE_STOP")


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RuntimeError(reason)


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def digest(path: Path) -> str:
    return sha(path.read_bytes())


def obj(path: Path) -> dict:
    return json.loads(path.read_bytes())


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line]


def root_hash(directory: Path, marker: str) -> str:
    require(not any(path.is_symlink() for path in directory.rglob("*")),
            "FROZEN_SYMLINK_FORBIDDEN")
    files = sorted(path for path in directory.rglob("*")
                   if path.is_file() and path.name != marker)
    return sha(canonical([[str(path.relative_to(directory)), digest(path)]
                          for path in files]))


def ref(path: Path, role: str) -> dict:
    return {"artifact_role": role, "artifact_path": str(path.relative_to(ROOT)),
            "sha256": digest(path), "immutable_frozen": True}


def put(name: str, value: object) -> str:
    raw = canonical(value) + b"\n"
    with (OUT / name).open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return sha(raw)


def put_rows(name: str, values: list[dict]) -> str:
    raw = b"".join(canonical(value) + b"\n" for value in values)
    with (OUT / name).open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return sha(raw)


def marker(name: str, value: str) -> None:
    with (OUT / name).open("xb") as handle:
        handle.write((value + "\n").encode("ascii"))
        handle.flush()
        os.fsync(handle.fileno())


def page_required(retstart: int, initial_count: int) -> bool:
    require(retstart in PAGE_OFFSETS and isinstance(initial_count, int)
            and not isinstance(initial_count, bool) and initial_count >= 0,
            "INVALID_PAGE_PREDICATE_INPUT")
    return retstart == 0 or retstart < min(initial_count, 200)


def preflight() -> dict:
    require(not OUT.exists(), "ALPHA321A_OUTPUT_ALREADY_EXISTS")
    marker_name = "search_plan_v24_primary_alpha3_21_master_prereg_sha256"
    require((MASTER / marker_name).read_text().strip() == MASTER_ROOT
            and root_hash(MASTER, marker_name) == MASTER_ROOT,
            "ALPHA321_MASTER_ROOT_MISMATCH")
    for name, expected in (
        ("alpha3_21_master_execution_plan", MASTER_PLAN_SHA),
        ("alpha3_21_seen_contamination_registry", SEEN_SHA),
    ):
        require(digest(MASTER / (name + ".json")) == expected
                and (MASTER / (name + "_sha256")).read_text().strip() == expected,
                "MASTER_COMPONENT_HASH_MISMATCH:" + name)
    validation = obj(MASTER / "validation.json")
    require(validation["status"] == "completed"
            and validation["publication_window_start"] == "2026-01-01"
            and validation["publication_window_end"] == "2026-09-30"
            and validation["source_stratum_count"] == 6
            and validation["max_records_per_stratum"] == 200
            and validation["seen_unique_pmids"] == 2545
            and validation["alpha3_21_seen_contamination_registry_sha256"] ==
                SEEN_SHA
            and validation["sampling_seed_sha256"] == SEED_SHA
            and validation["fresh_primary_source_acquisition_started"] is False,
            "MASTER_ACQUISITION_AUTHORITY_MISMATCH")
    master_query = MASTER / "alpha3_21_source_query_set.jsonl"
    master_query_sha = digest(master_query)
    query_authority = obj(MASTER / "alpha3_21_six_stratum_query_authority.json")
    master_plan = obj(MASTER / "alpha3_21_master_execution_plan.json")
    require(query_authority["derived_query_set_sha256"] == master_query_sha
            and master_plan["query_set"]["sha256"] == master_query_sha
            and master_plan["query_set"]["artifact_path"] ==
                str(master_query.relative_to(ROOT))
            and query_authority["source_stratum_count"] == 6
            and query_authority["pmc_subset_clause"] == '"pubmed pmc"[sb]',
            "MASTER_SIX_QUERY_HASH_AUTHORITY_MISMATCH")
    queries = rows(master_query)
    inherited_order = obj(A19 / "source_frame_execution_contract.json")[
        "stratum_order"]
    require(len(queries) == 6
            and [row["ordinal"] for row in queries] == list(range(1, 7))
            and [row["stratum_id"] for row in queries] == inherited_order
            and len(set(inherited_order)) == 6,
            "SIX_STRATUM_ORDER_AUTHORITY_MISMATCH")
    for row in queries:
        query = row["query_utf8"]
        require(sha(query.encode("utf-8")) == row["query_sha256"]
                and query.count('"2026/01/01"[Date - Publication]') == 1
                and query.count('"2026/09/30"[Date - Publication]') == 1
                and '"pubmed pmc"[sb]' in query
                and "pmc[filter]" not in query
                and row["page_size"] == 50
                and row["sort"] == "relevance"
                and row["retmode"] == "json"
                and row["retstart_sequence"] == list(PAGE_OFFSETS),
                "FROZEN_QUERY_CONTENT_OR_REQUEST_SHAPE_MISMATCH")
    frame_policy_path = A19 / "source_frame_execution_contract.json"
    frame = obj(frame_policy_path)
    require(frame["max_records_per_stratum"] == 200
            and frame["page_size"] == 50
            and frame["sort"] == "relevance"
            and frame["retstart_sequence"] == list(PAGE_OFFSETS)
            and frame["max_attempts_per_request"] == 4
            and frame["timeout_seconds"] == 60
            and frame["backoff_seconds"] == [2, 4, 8],
            "INHERITED_SOURCE_FRAME_RUNTIME_MISMATCH")
    esearch_path = A19_VALIDITY / "pubmed_esearch_response_validity_v2_1.json"
    esearch = obj(esearch_path)
    require(esearch["schema_version"] == "PubMedESearchResponseValidityV2_1"
            and esearch["backend_ERROR_valid_zero_allowed"] is False
            and esearch["implementation"]["sha256"] ==
                digest(ROOT / esearch["implementation"]["path"]),
            "HARDENED_ESEARCH_VALIDITY_AUTHORITY_MISMATCH")
    registry = obj(MASTER / "alpha3_21_seen_contamination_registry.json")
    require(registry["seen_unique_pmids"] == 2545
            and len(registry["source_identities"]) == 2545,
            "PREEXISTING_SEEN_REGISTRY_COUNT_MISMATCH")
    return {"queries": queries, "query_sha": master_query_sha,
            "stratum_order": inherited_order,
            "frame_policy": frame, "esearch": esearch}


def potential_requests(queries: list[dict]) -> list[dict]:
    result = []
    for row in queries:
        for offset in PAGE_OFFSETS:
            payload = {"db": "pubmed", "term": row["query_utf8"],
                       "sort": "relevance", "retmode": "json",
                       "retmax": 50, "retstart": offset}
            identity = "a321a_" + sha(canonical([
                "alpha3.21A", row["stratum_id"], offset,
                row["query_sha256"]]))
            result.append({"potential_ordinal": len(result) + 1,
                "stratum_ordinal": row["ordinal"],
                "stratum_id": row["stratum_id"],
                "query_sha256": row["query_sha256"],
                "retstart": offset, "retmax": 50,
                "sort": "relevance", "retmode": "json",
                "endpoint": row["endpoint"],
                "logical_request_id": identity,
                "request_payload": payload,
                "request_payload_sha256": sha(canonical(payload)),
                "execution_predicate": ("UNCONDITIONAL_FIRST_PAGE"
                    if offset == 0 else
                    "retstart < min(frozen_initial_result_count, 200)"),
                "future_execution_phase": ("FIRST_PAGE_BARRIER"
                    if offset == 0 else "FROZEN_REMAINING_PAGE_MANIFEST"),
                "initial_terminal_state": "NOT_YET_EXECUTED"})
    require(len(result) == 24
            and len({row["logical_request_id"] for row in result}) == 24,
            "POTENTIAL_PAGE_UNIVERSE_NOT_24_UNIQUE")
    return result


def freeze(state: dict) -> dict:
    OUT.mkdir()
    master_query = MASTER / "alpha3_21_source_query_set.jsonl"
    copied_query = OUT / "alpha3_21_source_query_set.jsonl"
    with master_query.open("rb") as src, copied_query.open("xb") as dst:
        shutil.copyfileobj(src, dst)
        dst.flush()
        os.fsync(dst.fileno())
    require(copied_query.read_bytes() == master_query.read_bytes()
            and digest(copied_query) == state["query_sha"],
            "FROZEN_QUERY_BYTE_COPY_MISMATCH")
    marker("alpha3_21_source_query_set_sha256", state["query_sha"])
    potential = potential_requests(state["queries"])
    first = [row for row in potential if row["retstart"] == 0]
    require(len(first) == 6
            and [row["stratum_id"] for row in first] == state["stratum_order"],
            "FIRST_PAGE_BARRIER_SET_MISMATCH")
    potential_sha = put_rows("alpha3_21_potential_page_request_manifest.jsonl",
                             potential)
    marker("alpha3_21_potential_page_request_manifest_sha256", potential_sha)
    first_sha = put_rows("alpha3_21_first_page_request_manifest.jsonl", first)
    marker("alpha3_21_first_page_request_manifest_sha256", first_sha)
    put("alpha3_21_master_root_verification.json", {
        "root_sha256": MASTER_ROOT, "stored_marker_verified": True,
        "root_recalculated": True})
    put("alpha3_21_master_plan_verification.json", {
        "master_execution_plan": ref(MASTER / "alpha3_21_master_execution_plan.json",
                                     "frozen_alpha3_21_master_execution_plan"),
        "expected_sha256": MASTER_PLAN_SHA,
        "verified": True})
    put("alpha3_21_preexisting_contamination_registry_binding.json", {
        "registry": ref(MASTER / "alpha3_21_seen_contamination_registry.json",
                        "immutable_preexisting_seen_registry"),
        "registry_sha256": SEEN_SHA,
        "historical_seen_pmid_count": 2545,
        "exclusion_occurs_in_alpha3_21b_not_alpha3_21a1": True})
    put("alpha3_21_source_query_authority_verification.json", {
        "master_query_artifact": ref(master_query, "frozen_master_six_query_set"),
        "local_byte_identical_copy": ref(copied_query,
                                         "alpha3_21a_six_query_set_copy"),
        "byte_identical": True, "stratum_count": 6,
        "publication_window": ["2026-01-01", "2026-09-30"],
        "query_modification": False})
    put("alpha3_21_stratum_order.json", {
        "stratum_ids_in_order": state["stratum_order"],
        "authority": ref(A19 / "source_frame_execution_contract.json",
                         "inherited_six_stratum_order"),
        "result_informed_reordering_allowed": False})
    put("alpha3_21_pubmed_request_parameter_contract.json", {
        "endpoint": state["queries"][0]["endpoint"],
        "client_configuration_authority": ref(A19 /
            "source_frame_execution_contract.json",
            "hardened_ncbi_source_acquisition_client_policy"),
        "db": "pubmed", "retmode": "json", "sort": "relevance",
        "retmax": 50, "retstart_coordinates": list(PAGE_OFFSETS),
        "term_source": "byte-frozen alpha3.21 master query string",
        "credentials_embedded": False,
        "network_executed_now": False})
    put("alpha3_21_page_expansion_contract.json", {
        "schema_version": "Alpha3_21ConditionalPageExpansionV1",
        "first_page_phase": {
            "request_count": 6, "retstart": 0,
            "order": "frozen stratum order",
            "all_six_valid_terminal_success_required_before_expansion": True},
        "remaining_page_coordinates": [50, 100, 150],
        "execute_if": "retstart < min(frozen_initial_result_count, 200)",
        "initial_result_count_source": "valid frozen retstart=0 ESearch Count",
        "remaining_manifest_filename":
            "alpha3_21a_remaining_page_execution_manifest.json",
        "freeze_remaining_manifest_before_any_retstart_gt_zero": True,
        "remaining_order": "frozen stratum order, then ascending retstart",
        "request_content_change_after_count": False,
        "count_examples": {"0": [0], "1_to_50": [0],
                           "51_to_100": [0, 50],
                           "101_to_150": [0, 50, 100],
                           "151_or_more": [0, 50, 100, 150]},
        "logical_request_minimum": 6,
        "logical_request_maximum": 24})
    put("alpha3_21_esearch_response_validity_binding.json", {
        "hardened_contract": ref(A19_VALIDITY /
            "pubmed_esearch_response_validity_v2_1.json",
            "frozen_esearch_response_validity_v2_1"),
        "implementation": ref(ROOT / state["esearch"]["implementation"]["path"],
                              "frozen_esearch_validity_implementation"),
        "http_200_backend_error_is_valid_page": False,
        "required_checks": ["transport", "HTTP_status", "JSON_parse",
                            "ESearch_structure", "backend_ERROR", "ErrorList",
                            "WarningList", "Count", "IdList"],
        "weaker_parser_allowed": False})
    put("alpha3_21_result_set_count_consistency_contract.json", {
        "first_valid_page_count_field": "initial_result_count",
        "subsequent_executed_page_count_must_equal_initial": True,
        "drift_state": "PUBMED_ESEARCH_RESULT_SET_COUNT_DRIFT",
        "drift_terminal_page_state": "RESULT_SET_COUNT_DRIFT",
        "on_drift": "preserve_raw_responses_stop_and_recommend_offline_audit",
        "dedup_or_sampling_after_drift_allowed": False,
        "idlist_cardinality_must_match_retstart_retmax_count": True,
        "missing_pmids_synthesized": False})
    put("alpha3_21_technical_retry_policy.json", {
        "inherited_frame_policy": ref(A19 /
            "source_frame_execution_contract.json",
            "frozen_technical_acquisition_policy"),
        "max_attempts_per_logical_page": 4,
        "timeout_seconds": 60,
        "backoff_seconds": [2, 4, 8],
        "retryable_http_status": state["frame_policy"]["retryable_http_status"],
        "backend_retry_eligibility": ref(A19_VALIDITY /
            "pubmed_esearch_response_validity_v2_1.json",
            "frozen_backend_failure_classification"),
        "scientific_low_yield_retry": False,
        "query_repair_allowed": False})
    put("alpha3_21_acquisition_terminal_state_contract.json", {
        "terminal_states": list(TERMINAL_STATES),
        "normal_completion_state": "VALID_SUCCESS",
        "required_page_failure_stops_stage": True,
        "partial_stratum_handoff_allowed": False,
        "replacement_scientific_query_allowed": False})
    put("alpha3_21_raw_response_preservation_contract.json", {
        "preserve_before_postprocessing": True,
        "per_attempt_required": ["logical_request_id", "attempt_ordinal",
            "exact_request_parameters", "transport_result", "HTTP_status",
            "raw_response_body", "raw_response_sha256", "timestamp_utc"],
        "per_valid_page_required": ["Count", "IdList", "querytranslation",
            "response_validity_state"],
        "no_metadata_fetch": True,
        "no_raw_response_overwrite": True})
    put("alpha3_21_raw_pmid_provenance_contract.json", {
        "preserve_every_returned_membership": True,
        "fields": ["PMID", "stratum_id", "logical_page_id", "retstart",
                   "within_page_position", "raw_acquisition_ordinal"],
        "within_page_dedup": False,
        "within_stratum_dedup": False,
        "cross_stratum_dedup": False,
        "later_dedup_stage": "alpha3.21B"})
    put("alpha3_21_current_attempt_exposure_registry_contract.json", {
        "registry_name": "ALPHA3_21_CURRENT_ATTEMPT_EXPOSURE_REGISTRY",
        "registry_created_in_preregistration": False,
        "successful_acquisition_finalization":
            "freeze every unique PMID from executed valid pages",
        "failed_or_stopped_acquisition_bookkeeping":
            "preserve every PMID already exposed by valid pages for future history",
        "partial_attempt_exposures_discarded": False,
        "use": "future_attempt_contamination_history",
        "not_current_attempt_historical_exclusion_input": True})
    put("alpha3_21_no_self_contamination_contract.json", {
        "preexisting_registry": ref(MASTER /
            "alpha3_21_seen_contamination_registry.json",
            "master_frozen_preexisting_seen_registry"),
        "preexisting_seen_pmid_count": 2545,
        "current_attempt_exposure_does_not_self_exclude": True,
        "alpha3_21b_excludes_only_master_frozen_preexisting_set": True,
        "append_current_acquired_pmids_to_same_attempt_exclusion": False})
    put("alpha3_21_database_snapshot_interpretation.json", {
        "corpus_meaning": "PubMed index state observed during frozen acquisition run",
        "coverage": "first up to 200 relevance-ranked IDs per stratum",
        "all_matching_2026_publications_claim": False,
        "record_execution_timestamps": True,
        "later_indexing_topup_allowed": False,
        "refresh_after_successful_corpus_freeze_allowed": False})
    put("alpha3_21_acquisition_completeness_contract.json", {
        "requires_six_valid_first_pages": True,
        "requires_remaining_page_manifest_frozen_before_additional_requests": True,
        "requires_all_count_predicate_pages_valid": True,
        "requires_no_count_drift": True,
        "normal_handoff":
            "PREREGISTER_ALPHA3_21B_OFFLINE_DEDUP_SEEN_EXCLUSION_AND_STRATIFIED_SAMPLING",
        "zero_count_valid_primary_outcome": True,
        "incomplete_prefix_handoff_allowed": False})
    put("alpha3_21_acquisition_call_budget.json", {
        "minimum_logical_page_requests": 6,
        "maximum_logical_page_requests": 24,
        "max_attempts_per_logical_page": 4,
        "maximum_transport_attempts": 96,
        "not_an_execution_target": True,
        "network_calls_in_preregistration": 0})
    put("alpha3_21a1_execution_handoff.json", {
        "requires_separate_network_authorization": True,
        "first_page_manifest": ref(OUT /
            "alpha3_21_first_page_request_manifest.jsonl",
            "six_unconditional_first_page_requests"),
        "potential_page_manifest": ref(OUT /
            "alpha3_21_potential_page_request_manifest.jsonl",
            "twenty_four_frozen_potential_pages"),
        "execute_first_pages_before_expansion": True,
        "freeze_remaining_manifest_before_additional_pages": True,
        "current_stage_network_execution": False})
    put("sampling_seed_nonuse_audit.json", {
        "master_sampling_seed_sha256": SEED_SHA,
        "master_seed_binding": ref(MASTER /
            "alpha3_21_sampling_seed_derivation.json",
            "frozen_future_sampling_seed"),
        "sampling_seed_used": False,
        "sampling_performed": False})
    put("builder_v4_nonuse_audit.json", {
        "builder_contract": ref(RUNS /
            "20261004_search_plan_v24_dev_alpha3_20f_final_builder_v4_contract_freeze_offline/search_plan_builder_v4_final_contract.json",
            "inactive_frozen_builder_v4_contract"),
        "builder_execution_started": False,
        "builder_calls": 0})
    put("quality_nonuse_audit.json", {
        "quality_execution_started": False,
        "quality_requests_constructed": 0,
        "quality_calls": 0})
    put("fresh_primary_policy_nonadaptation_audit.json", {
        "source_query_modification": False,
        "publication_window_change": False,
        "new_strata": 0,
        "additional_page_coordinates": 0,
        "sort_change": False,
        "builder_v4_change": False,
        "quality_change": False,
        "scientific_result_informed_retry": False})
    require(root_hash(MASTER,
        "search_plan_v24_primary_alpha3_21_master_prereg_sha256") == MASTER_ROOT,
        "MASTER_ROOT_CHANGED_DURING_PREREGISTRATION")
    put("historical_preservation_audit.json", {
        "master_root_unchanged": True,
        "historical_assets_modified": False,
        "preexisting_registry_modified": False})
    put("scientific_state_safety_audit.json", {
        "source_acquisition_executed": False,
        "deduplication_performed": False,
        "seen_exclusion_performed": False,
        "sampling_performed": False,
        "metadata_fetched": False,
        "builder_execution_started": False,
        "quality_execution_started": False,
        "retrieval_evaluation_started": False,
        "network_calls": 0, "pubmed_calls": 0, "pmc_calls": 0,
        "provider_calls": 0, "llm_calls": 0})
    validation = {"status": "completed",
        "alpha3_21a_classification": CLASSIFICATION,
        "alpha3_21_master_root_verified": True,
        "publication_window_start": "2026-01-01",
        "publication_window_end": "2026-09-30",
        "source_stratum_count": 6,
        "alpha3_21_source_query_set_sha256": state["query_sha"],
        "potential_logical_page_request_count": 24,
        "unconditional_first_page_request_count": 6,
        "retmax": 50, "max_records_per_stratum": 200,
        "sort": "relevance", "retmode": "json",
        "page_execution_rule_frozen": True,
        "result_set_count_consistency_rule_frozen": True,
        "max_attempts_per_logical_page": 4,
        "timeout_seconds": 60,
        "maximum_logical_page_requests": 24,
        "maximum_transport_attempts": 96,
        "historical_seen_pmid_count": 2545,
        "historical_seen_registry_sha256": SEEN_SHA,
        "preexisting_seen_exclusion_performed": False,
        "deduplication_performed": False,
        "sampling_performed": False,
        "current_attempt_exposure_registry_created": False,
        "current_attempt_exposure_does_not_self_exclude": True,
        "sampling_seed_used": False,
        "builder_execution_started": False,
        "quality_execution_started": False,
        "retrieval_evaluation_started": False,
        "network_calls": 0, "pubmed_calls": 0, "pmc_calls": 0,
        "provider_calls": 0, "llm_calls": 0,
        "alpha3_21_potential_page_request_manifest_sha256": potential_sha,
        "alpha3_21_first_page_request_manifest_sha256": first_sha,
        "next_stage_recommendation": NEXT,
        "historical_assets_modified": False}
    put("validation.json", validation)
    put("summary.json", {"status": "completed",
        "classification": CLASSIFICATION,
        "potential_logical_page_request_count": 24,
        "unconditional_first_page_request_count": 6,
        "next_stage_recommendation": NEXT})
    root = root_hash(OUT, ROOT_MARKER)
    marker(ROOT_MARKER, root)
    return {**validation, ROOT_MARKER: root}


def run() -> dict:
    return freeze(preflight())


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
