#!/usr/bin/env python3
"""Freeze a prospective source-query syntax and ESearch response-validity amendment."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

try:
    from scripts import search_plan_v24_alpha318a2_rebuild_source_prereg_offline as prior
    from scripts import search_plan_v24_alpha318a3_finalize_source_prereg_offline as freeze
    from scripts import search_plan_v24_alpha318a_execute_ncbi_source_acquisition as execution
    from scripts import search_plan_v24_alpha318a_audit_source_frame_response_offline as audit
    from scripts import search_plan_v24_alpha318a4_esearch_response_validity as validity
except ModuleNotFoundError:
    import search_plan_v24_alpha318a2_rebuild_source_prereg_offline as prior
    import search_plan_v24_alpha318a3_finalize_source_prereg_offline as freeze
    import search_plan_v24_alpha318a_execute_ncbi_source_acquisition as execution
    import search_plan_v24_alpha318a_audit_source_frame_response_offline as audit
    import search_plan_v24_alpha318a4_esearch_response_validity as validity


ROOT = prior.ROOT
OUT = ROOT / "runs/20260928_search_plan_v24_dev_alpha3_18a4_pubmed_query_runtime_validation_amendment_offline"
CODE = ROOT / "scripts/search_plan_v24_alpha318a4_esearch_response_validity.py"
INVALID = "pmc[filter]"
REPLACEMENT = '"pubmed pmc"[sb]'
SOURCE_ROOT = execution.MANIFEST_SHA
FAILED_RUN_ROOT = audit.EXPECTED_SOURCE_ROOT
FAILURE_AUDIT_ROOT = "f06c6bad9d84673e784f758f90c620f4f18fde35639ec3cda0d7dfa5aa860e1c"
ROOT_MARKER = "search_plan_v24_dev_alpha3_18a4_sha256"


def write(name: str, value: Any) -> None:
    path = OUT / name
    if path.exists():
        raise RuntimeError(f"refusing overwrite: {path}")
    path.write_bytes(prior.canonical(value) + b"\n")


def write_jsonl(name: str, rows: list[Any]) -> None:
    path = OUT / name
    if path.exists():
        raise RuntimeError(f"refusing overwrite: {path}")
    path.write_bytes(b"".join(prior.canonical(row) + b"\n" for row in rows))


def marker(name: str, value: str) -> None:
    path = OUT / name
    if path.exists():
        raise RuntimeError(f"refusing overwrite: {path}")
    path.write_text(value + "\n", encoding="utf-8")


def ref(directory: Path, name: str) -> dict[str, str]:
    return prior.ref(directory, name)


def verify() -> list[dict[str, Any]]:
    if execution.root_hash() != FAILED_RUN_ROOT or (execution.OUT / execution.ROOT_MARKER).read_text().strip() != FAILED_RUN_ROOT:
        raise RuntimeError("original network run drift")
    if prior.all_file_root(audit.OUT, audit.MARKER) != FAILURE_AUDIT_ROOT:
        raise RuntimeError("independent failure audit drift")
    if (audit.OUT / audit.MARKER).read_text().strip() != FAILURE_AUDIT_ROOT:
        raise RuntimeError("independent failure audit marker drift")
    if prior.all_file_root(freeze.OUT, "search_plan_v24_dev_alpha3_18a3_prereg_sha256") != execution.PREREG_SHA:
        raise RuntimeError("alpha3.18A.3 preregistration drift")
    source_manifest = freeze.OUT / "alpha3_18a3_source_acquisition_execution_manifest.json"
    if prior.sha(source_manifest.read_bytes()) != SOURCE_ROOT:
        raise RuntimeError("original executable manifest drift")
    rows = freeze.verify()
    findings = prior.load(audit.OUT, "ncbi_esearch_error_findings.json")
    if len(findings["findings"]) != 6 or not all(row["unresolved_pmc_phrase"] for row in findings["findings"]):
        raise RuntimeError("runtime failure signature drift")
    return rows


def amended_queries(original: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    changed = []
    delta = []
    for row in original:
        old = row["query_utf8"]
        if old.count(INVALID) != 1:
            raise RuntimeError("PMC_SUBSET_QUERY_REDESIGN_REQUIRED")
        updated = old.replace(INVALID, REPLACEMENT)
        if updated.replace(REPLACEMENT, INVALID) != old:
            raise RuntimeError("SOURCE_QUERY_SCIENTIFIC_SEMANTICS_CHANGED")
        next_row = copy.deepcopy(row)
        next_row["query_utf8"] = updated
        next_row["query_sha256"] = prior.sha(updated.encode("utf-8"))
        next_row["pmc_accessibility_proxy"] = REPLACEMENT
        changed.append(next_row)
        delta.append({"stratum_id": row["stratum_id"], "stratum_order": row["stratum_order"],
            "original_query": old, "original_query_sha256": row["query_sha256"],
            "invalid_clause": INVALID, "replacement_clause": REPLACEMENT,
            "amended_query": updated, "amended_query_sha256": next_row["query_sha256"],
            "changed_scientific_terms": 0, "changed_date_constraints": 0,
            "changed_strata": 0, "changed_boolean_structure_outside_pmc_clause": 0})
    if len(changed) != 6 or any(a["stratum_id"] != b["stratum_id"] for a, b in zip(original, changed)):
        raise RuntimeError("SOURCE_QUERY_SCIENTIFIC_SEMANTICS_CHANGED")
    return changed, delta


def cases() -> list[dict[str, Any]]:
    def payload(count: str, ids: list[str], *, errorlist=None, warninglist=None,
                include_count=True, retmax: str | None = None) -> bytes:
        result: dict[str, Any] = {"retstart": "0", "retmax": retmax if retmax is not None else ("0" if count == "0" else "50"),
                                  "idlist": ids, "querytranslation": REPLACEMENT}
        if include_count:
            result["count"] = count
        if errorlist is not None:
            result["errorlist"] = errorlist
        if warninglist is not None:
            result["warninglist"] = warninglist
        return prior.canonical({"esearchresult": result})
    valid_zero = {"phrasesignored": [], "quotedphrasesnotfound": [], "outputmessages": ["No items found."]}
    original_results = [json.loads(line) for line in (execution.OUT / "source_query_execution_results.jsonl").read_text().splitlines()]
    first_raw = (execution.OUT / original_results[0]["attempts"][-1]["raw_path"]).read_bytes()
    return [
        {"case_id": "positive_no_error", "status": 200, "raw": payload("2", ["123", "456"]), "expected": "QUERY_SEMANTIC_SUCCESS"},
        {"case_id": "legitimate_zero", "status": 200, "raw": payload("0", [], warninglist=valid_zero), "expected": "VALID_ZERO_RESULT"},
        {"case_id": "phrasesnotfound", "status": 200, "raw": payload("0", [], errorlist={"phrasesnotfound": ["pmc"]}), "expected": "QUERY_SEMANTIC_ERROR"},
        {"case_id": "unknown_error", "status": 200, "raw": payload("0", [], errorlist={"new_error": ["bad query"]}), "expected": "QUERY_SEMANTIC_ERROR"},
        {"case_id": "semantic_warning", "status": 200, "raw": payload("1", ["123"], warninglist={"phrasesignored": ["biology"]}), "expected": "QUERY_WARNING_UNRESOLVED"},
        {"case_id": "unknown_warning", "status": 200, "raw": payload("1", ["123"], warninglist={"future_warning": ["changed"]}), "expected": "QUERY_WARNING_UNRESOLVED"},
        {"case_id": "http_non_success", "status": 503, "raw": payload("0", []), "expected": "TRANSPORT_FAILURE"},
        {"case_id": "missing_count", "status": 200, "raw": payload("0", [], include_count=False), "expected": "RESPONSE_SCHEMA_INVALID"},
        {"case_id": "malformed_idlist", "status": 200, "raw": payload("1", ["00123"]), "expected": "RESPONSE_SCHEMA_INVALID"},
        {"case_id": "original_failed_payload", "status": 200, "raw": first_raw, "expected": "QUERY_SEMANTIC_ERROR"},
        {"case_id": "xml_errorlist", "status": 200, "raw": b"<eSearchResult><ErrorList><PhraseNotFound>pmc</PhraseNotFound></ErrorList></eSearchResult>", "expected": "QUERY_SEMANTIC_ERROR"},
    ]


def main() -> None:
    if OUT.exists():
        raise RuntimeError("alpha3.18A.4 output already exists; refusing overwrite")
    original = verify()
    amended, delta = amended_queries(original)
    test_cases = cases()
    test_results = []
    for case in test_cases:
        verdict = validity.validate_response(case["status"], case["raw"], 0, 50)
        test_results.append({"case_id": case["case_id"], "expected": case["expected"],
                             "actual": verdict["state"], "pass": verdict["state"] == case["expected"],
                             "raw_sha256": prior.sha(case["raw"])})
    if not all(result["pass"] for result in test_results):
        raise RuntimeError("ESearch validity synthetic validation failed")
    OUT.mkdir()
    write("original_runtime_failure_verification.json", {
        "status": "PASS", "original_run_root_sha256": FAILED_RUN_ROOT,
        "independent_failed_audit_root_sha256": FAILURE_AUDIT_ROOT,
        "original_nine_NCBI_attempts_preserved": True,
        "original_self_reported_PASS_preserved_but_invalid": True,
        "six_frame_classification": "INVALID_QUERY_RESPONSE_FRAMES",
        "root_causes": ["PUBMED_PMC_SUBSET_QUERY_SYNTAX_DEFECT", "ESEARCH_RESPONSE_ERROR_VALIDATION_DEFECT"],
        "not_scientific_source_scarcity_or_zero_hit_biology": True})
    write("query_syntax_authority_snapshot.json", {
        "assertion_source": "USER_SUPPLIED_CURRENT_PUBMED_DOCUMENTATION_CLAIM",
        "independently_network_verified_in_this_offline_stage": False,
        "PubMed_PMC_subset_clause": REPLACEMENT,
        "meaning": "PubMed citations with free full text available in PMC; discovery accessibility proxy only",
        "not_equivalent_to_PMC_OA_Subset_or_accepted_article_license": True,
        "forbidden_replacements": ["open access[filter]", "pubmed pmc open access[filter]"],
        "prospective_status": ["POST_RUNTIME_FAILURE", "PROSPECTIVE_BEFORE_RERUN"]})
    write_jsonl("source_query_v1_v2_delta.jsonl", delta)
    write_jsonl("source_query_set_v2.jsonl", amended)
    query_sha = prior.sha((OUT / "source_query_set_v2.jsonl").read_bytes())
    marker("source_query_set_v2_sha256", query_sha)
    write("pubmed_esearch_response_validity_v2.json", {
        "schema_version": validity.SCHEMA_VERSION, "implementation": ref(ROOT / "scripts", CODE.name),
        "active_transport": "NCBI PubMed ESearch GET retmode=json",
        "transport_success_required": True, "HTTP_200_alone_sufficient": False,
        "ErrorList_checked_before_count_or_idlist": True,
        "valid_states": sorted(validity.VALID_STATES),
        "failure_states": sorted(validity.STATES - validity.VALID_STATES),
        "valid_zero_requires_no_query_semantic_error_or_unresolved_warning": True,
        "querytranslation_preserved_not_used_to_rewrite_query": True})
    write("esearch_errorlist_policy.json", {
        "nonempty_JSON_errorlist_or_XML_ErrorList": "QUERY_SEMANTIC_ERROR",
        "phrasesnotfound_pmc": "QUERY_SEMANTIC_ERROR",
        "unknown_nonempty_errorlist": "QUERY_SEMANTIC_ERROR",
        "check_order": "after valid HTTP and parse, before count/idlist interpretation",
        "deterministic_query_error_technical_retry": False})
    write("esearch_warninglist_policy.json", {
        "all_nonempty_unallowlisted_warnings": "QUERY_WARNING_UNRESOLVED",
        "semantic_ignored_notfound_altered_term_warning": "QUERY_WARNING_UNRESOLVED",
        "only_allowed_nonsemantic_display_warning": {
            "conditions": "count=0 and idlist=[] and exact warninglist object",
            "warninglist": {"phrasesignored": [], "quotedphrasesnotfound": [], "outputmessages": ["No items found."]}},
        "unknown_warning_silently_ignored": False})
    write("esearch_schema_validation_policy.json", {
        "required_JSON_structure": ["esearchresult object", "count nonnegative decimal string",
            "retstart nonnegative decimal string", "retmax nonnegative decimal string",
            "idlist array of canonical positive decimal PMID strings"],
        "requested_retstart_must_match": True, "returned_retmax_at_most_requested": True,
        "count_zero_requires_empty_idlist_and_returned_retmax_zero": True,
        "nonzero_count_with_expected_page_but_empty_idlist": "RESPONSE_SCHEMA_INVALID",
        "missing_or_malformed": "RESPONSE_SCHEMA_INVALID",
        "optional_querytranslation_if_present": "string, preserve verbatim",
        "JSON_expected_XML_ErrorList_exception": "QUERY_SEMANTIC_ERROR"})
    write("query_semantic_retry_policy.json", {
        "transport_failures": ref(prior.SOURCE, "source_execution_policy.json"),
        "QUERY_SEMANTIC_ERROR": "STOP_CURRENT_EXECUTION_FAIL_CLOSED_NO_RETRY",
        "QUERY_WARNING_UNRESOLVED": "STOP_CURRENT_EXECUTION_FAIL_CLOSED_NO_RETRY",
        "RESPONSE_SCHEMA_INVALID": "STOP_CURRENT_EXECUTION_FAIL_CLOSED_NO_QUERY_REPAIR",
        "all_six_valid_frames_before_sampling": True})
    write("invalid_original_downstream_artifact_quarantine.json", {
        "source_run_root_sha256": FAILED_RUN_ROOT,
        "classification": "INVALID_DOWNSTREAM_DERIVATIVES_OF_INVALID_SOURCE_FRAMES",
        "paths": [str((execution.OUT / name).relative_to(ROOT)) for name in (
            "cross_stratum_duplicate_audit.json", "new_pool_source_sampling_frame.jsonl",
            "deterministic_source_sampling_results.jsonl", "construction_source_manifest.jsonl",
            "proposition_builder_v2_request_manifest.jsonl", "actual_builder_call_budget.json")],
        "may_be_consumed_by_future_builder_or_heldout_stage": False,
        "historical_files_modified_or_deleted": False})
    write("builder_budget_reset_audit.json", {
        "original_self_reported_zero_is_invalid": True,
        "actual_builder_scientific_call_count": "UNKNOWN",
        "derive_only_from_future_valid_construction_source_manifest": True})
    original_manifest = prior.load(freeze.OUT, "alpha3_18a3_source_acquisition_execution_manifest.json")
    old_bindings = original_manifest["frozen_source_bindings"]
    write("unchanged_downstream_contract_audit.json", {
        "original_manifest_sha256": SOURCE_ROOT,
        "unchanged_source_bindings_except_active_query_file": {
            key: value for key, value in old_bindings.items() if key != "exact_source_queries.jsonl"},
        "unchanged_amendment_bindings": original_manifest["frozen_amendment_bindings"],
        "unchanged_correction_gate_root_sha256": original_manifest["correction_gate_root_sha256"],
        "unchanged_builder_protocol_sha256": original_manifest["authoritative_roots"]["builder_protocol_v2"],
        "unchanged_builder_output_schema_sha256": original_manifest["authoritative_roots"]["builder_output_schema_v2"],
        "sampling_seed_modified": False, "frame_cap_or_page_size_modified": False,
        "OA_license_type_document_anchor_policy_modified": False})
    write_jsonl("esearch_synthetic_cases.jsonl", [{"case_id": case["case_id"],
        "http_status": case["status"], "raw_utf8": case["raw"].decode("utf-8"),
        "expected_state": case["expected"]} for case in test_cases])
    write("esearch_synthetic_test_results.json", {"status": "PASS", "case_count": len(test_results),
        "passed": len(test_results), "failed": 0, "results": test_results})
    validity_files = ["pubmed_esearch_response_validity_v2.json", "esearch_errorlist_policy.json",
        "esearch_warninglist_policy.json", "esearch_schema_validation_policy.json",
        "query_semantic_retry_policy.json", "esearch_synthetic_cases.jsonl",
        "esearch_synthetic_test_results.json"]
    validity_sha = prior.sha(prior.canonical(
        [[name, prior.sha((OUT / name).read_bytes())] for name in sorted(validity_files)] +
        [[str(CODE.relative_to(ROOT)), prior.sha(CODE.read_bytes())]]))
    marker("pubmed_esearch_response_validity_v2_sha256", validity_sha)
    new_manifest = copy.deepcopy(original_manifest)
    new_manifest["status"] = "EXECUTABLE_PROSPECTIVE_V2_PREREGISTRATION_FROZEN"
    new_manifest["schema_version"] = "Alpha318A4SourceAcquisitionExecutionManifestV2"
    new_manifest["amendment_class"] = "SOURCE_DISCOVERY_QUERY_TECHNICAL_AMENDMENT"
    new_manifest["amendment_temporality"] = ["POST_RUNTIME_FAILURE", "PROSPECTIVE_BEFORE_RERUN"]
    new_manifest["original_manifest_sha256"] = SOURCE_ROOT
    new_manifest["source_query_set_v2_sha256"] = query_sha
    new_manifest["pubmed_esearch_response_validity_v2_sha256"] = validity_sha
    new_manifest["queries"] = [{"stratum_id": row["stratum_id"], "stratum_order": row["stratum_order"],
        "query_utf8": row["query_utf8"], "query_sha256": row["query_sha256"]} for row in amended]
    new_manifest["query_file"] = ref(OUT, "source_query_set_v2.jsonl")
    new_manifest["query_changes"] = 6
    new_manifest["changed_scientific_terms"] = 0
    new_manifest["changed_date_constraints"] = 0
    new_manifest["changed_strata"] = 0
    new_manifest["historical_original_query_file"] = original_manifest["query_file"]
    new_manifest["frozen_source_bindings"] = {key: value for key, value in old_bindings.items()
        if key != "exact_source_queries.jsonl"}
    source_policy_v2 = prior.load(prior.SOURCE, "source_execution_policy.json")
    source_policy_v2["query_bytes_source"] = "source_query_set_v2.jsonl"
    source_policy_v2["response_validity_contract"] = "PubMedESearchResponseValidityV2"
    new_manifest["active_source_frame_policy_v2"] = source_policy_v2
    new_manifest["network_routes"]["source_frames"]["active_query_bytes_source"] = ref(OUT, "source_query_set_v2.jsonl")
    new_manifest["network_routes"]["source_frames"]["active_response_validity_contract"] = ref(OUT, "pubmed_esearch_response_validity_v2.json")
    new_manifest["response_validity"] = ref(OUT, "pubmed_esearch_response_validity_v2.json")
    new_manifest["response_validity_implementation"] = ref(ROOT / "scripts", CODE.name)
    new_manifest["query_semantic_retry_policy"] = ref(OUT, "query_semantic_retry_policy.json")
    new_manifest["six_frame_success_requires"] = ["TRANSPORT_SUCCESS", "QUERY_SEMANTIC_SUCCESS_OR_VALID_ZERO_RESULT",
        "RESPONSE_SCHEMA_VALID", "NO_ERRORLIST", "NO_UNRESOLVED_WARNING"]
    new_manifest["original_downstream_artifacts_quarantined"] = True
    new_manifest["actual_builder_scientific_call_count_before_valid_rerun"] = "UNKNOWN"
    new_manifest["rerun_from"] = "SOURCE_QUERY_1_PAGE_1"
    new_manifest["future_network_execution_requires_separate_authorization"] = True
    new_manifest["network_calls_in_this_preregistration"] = 0
    new_manifest["material_runtime_policy_unresolved_count"] = 0
    write("alpha3_18a4_source_acquisition_execution_manifest_v2.json", new_manifest)
    manifest_sha = prior.sha((OUT / "alpha3_18a4_source_acquisition_execution_manifest_v2.json").read_bytes())
    marker("alpha3_18a4_source_acquisition_execution_manifest_v2_sha256", manifest_sha)
    write("final_execution_manifest_completeness_audit.json", {
        "status": "PASS", "material_runtime_policy_unresolved_count": 0,
        "manifest_v2_sha256": manifest_sha, "active_query_file_sha256": query_sha,
        "response_validity_v2_sha256": validity_sha, "six_frozen_query_literals_bound": True,
        "prior_downstream_contracts_unchanged": True,
        "transport_and_semantic_success_distinguished": True,
        "valid_zero_separate_from_query_semantic_error": True,
        "full_rerun_required": True})
    write("historical_preservation_audit.json", {
        "original_failed_network_run_sha256": FAILED_RUN_ROOT,
        "independent_failure_audit_sha256": FAILURE_AUDIT_ROOT,
        "alpha3_18a3_prereg_sha256": execution.PREREG_SHA,
        "alpha3_18a3_manifest_sha256": SOURCE_ROOT,
        "historical_artifacts_modified": False, "original_queries_overwritten": False,
        "new_queries_are_prospective_V2": True})
    write("scientific_state_safety_audit.json", {
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0, "retrieval_calls": 0,
        "builder_calls": 0, "quality_calls": 0, "source_acquisition_calls": 0,
        "historical_artifacts_modified": False, "scientific_terms_changed": 0})
    write("validation.json", {
        "status": "PASS", "original_failed_run_preserved": True,
        "runtime_failure_root_cause_resolved": True,
        "query_amendment_limited_to_pmc_subset_clause": True,
        "source_discovery_pmc_clause": REPLACEMENT,
        "changed_scientific_terms": 0, "changed_date_constraints": 0, "changed_strata": 0,
        "esearch_errorlist_checked_before_count": True,
        "phrasesnotfound_invalidates_response": True,
        "esearch_warninglist_policy_frozen": True,
        "http_200_alone_not_query_success": True,
        "valid_zero_requires_no_query_semantic_error": True,
        "original_empty_downstream_artifacts_quarantined": True,
        "actual_builder_call_count_reset_to_unknown": True,
        "all_downstream_scientific_contracts_unchanged": True,
        "material_runtime_policy_unresolved_count": 0,
        "final_execution_manifest_executable": True,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0, "retrieval_calls": 0})
    write("summary.json", {"status": "completed", "source_query_set_v2_sha256": query_sha,
        "pubmed_esearch_response_validity_v2_sha256": validity_sha,
        "alpha3_18a4_source_acquisition_execution_manifest_v2_sha256": manifest_sha,
        "next_stage_recommendation": "AUTHORIZE_ALPHA3_18A_V2_NCBI_ONLY_RERUN",
        "network_execution_authorized_now": False, "historical_artifacts_modified": False})
    run_root = prior.all_file_root(OUT, ROOT_MARKER)
    marker(ROOT_MARKER, run_root)
    assert prior.all_file_root(OUT, ROOT_MARKER) == run_root
    print(json.dumps({"status": "completed", "run_root": run_root,
        "source_query_set_v2_sha256": query_sha,
        "response_validity_v2_sha256": validity_sha,
        "manifest_v2_sha256": manifest_sha, "network_calls": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
