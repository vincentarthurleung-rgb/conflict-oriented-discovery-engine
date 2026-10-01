#!/usr/bin/env python3
"""Freeze alpha3.18A.3 correction-reference rule and source execution manifest offline."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

try:
    from scripts import search_plan_v24_alpha318a2_rebuild_source_prereg_offline as prior
    from scripts import search_plan_v24_alpha318a3_correction_reference as rule
except ModuleNotFoundError:  # direct script execution
    import search_plan_v24_alpha318a2_rebuild_source_prereg_offline as prior
    import search_plan_v24_alpha318a3_correction_reference as rule


ROOT = prior.ROOT
RUNS = prior.RUNS
OLD = prior.OUT
AMEND = prior.AMEND
SOURCE = prior.SOURCE
BUILDER = prior.BUILDER
QUALITY = prior.QUALITY
ARCH = prior.ARCH
OUT = RUNS / "20260927_search_plan_v24_dev_alpha3_18a3_correction_reference_resolution_final_prereg_offline"
RULE_FILE = ROOT / "scripts/search_plan_v24_alpha318a3_correction_reference.py"
OLD_ROOT = "74a0f88f7f172843f5541d304777693826cf941c1a07ac191335dd5f75448da1"
AMEND_ROOT = "836fb4df24850b32720cb130c65329cac2a828ef257184683cd5a3e391a4e8fe"


def write(name: str, value: Any) -> None:
    path = OUT / name
    if path.exists():
        raise RuntimeError(f"refusing overwrite: {path}")
    path.write_bytes(prior.canonical(value) + b"\n")


def write_lines(name: str, rows: list[dict[str, Any]]) -> None:
    path = OUT / name
    if path.exists():
        raise RuntimeError(f"refusing overwrite: {path}")
    path.write_bytes(b"".join(prior.canonical(row) + b"\n" for row in rows))


def marker(name: str, value: str) -> None:
    path = OUT / name
    if path.exists():
        raise RuntimeError(f"refusing overwrite: {path}")
    path.write_text(value + "\n", encoding="utf-8")


def verify() -> list[dict[str, Any]]:
    queries = prior.verify()
    if prior.all_file_root(OLD, "search_plan_v24_dev_alpha3_18a2_prereg_sha256") != OLD_ROOT:
        raise RuntimeError("failed alpha3.18A.2 root drift")
    if (OLD / "search_plan_v24_dev_alpha3_18a2_prereg_sha256").read_text().strip() != OLD_ROOT:
        raise RuntimeError("failed alpha3.18A.2 marker drift")
    old = prior.load(OLD, "validation.json")
    if old["status"] != "FAILED_CLOSED" or old["unresolved_runtime_policy"] != prior.BLOCKER:
        raise RuntimeError("failed alpha3.18A.2 state drift")
    if (AMEND / "search_plan_v24_dev_alpha3_18a1_sha256").read_text().strip() != AMEND_ROOT:
        raise RuntimeError("alpha3.18A.1 root drift")
    frozen_excluded = set(prior.load(AMEND, "publication_type_exclusion_set.json")["exact_strings"])
    if not rule.EXPLICIT_PUBLICATION_TYPE_EXCLUSIONS <= frozen_excluded:
        raise RuntimeError("correction rule introduces an unfrozen Publication Type exclusion")
    if (rule.HARD_INELIGIBLE | rule.UNRESOLVED | rule.CONDITIONAL_UPDATE | rule.ORDINARY) != rule.RECOGNIZED:
        raise RuntimeError("RefType partition incomplete")
    if any(a & b for i, a in enumerate((rule.HARD_INELIGIBLE, rule.UNRESOLVED,
                                        rule.CONDITIONAL_UPDATE, rule.ORDINARY))
           for b in (rule.HARD_INELIGIBLE, rule.UNRESOLVED,
                     rule.CONDITIONAL_UPDATE, rule.ORDINARY)[i + 1:]):
        raise RuntimeError("RefType partition overlaps")
    return queries


def local_ref_type_authority() -> tuple[list[str], list[list[str]]]:
    paths = sorted(RUNS.glob("202609*/retrieval_assets/pubmed_efetch/*.xml"))
    observed: set[str] = set()
    evidence: list[list[str]] = []
    for path in paths:
        root = ET.parse(path).getroot()
        observed.update(node.attrib["RefType"] for node in root.iter("CommentsCorrections")
                        if "RefType" in node.attrib)
        evidence.append([str(path.relative_to(ROOT)), prior.sha(path.read_bytes())])
    if not observed or not observed <= rule.RECOGNIZED:
        raise RuntimeError("local linked-citation vocabulary differs from frozen parser")
    return sorted(observed), evidence


def cases() -> list[dict[str, Any]]:
    def row(case_id: str, refs: list[str], expected: str,
            publication_types: list[str] | None = None,
            primary_state: str | None = None,
            missing_linked_pmid: bool = False) -> dict[str, Any]:
        return {"case_id": case_id, "publication_types": publication_types or ["Journal Article"],
                "relationships": [{"ref_type": value,
                                   "linked_pmid": None if missing_linked_pmid else "12345678",
                                   "ref_source": None} for value in refs],
                "independent_primary_state": primary_state, "expected_state": expected}
    clear = "CORRECTION_REFERENCE_CLEAR"
    bad = "CORRECTION_REFERENCE_INELIGIBLE"
    unresolved = "CORRECTION_REFERENCE_UNRESOLVED"
    return [
        row("no_links", [], clear),
        row("retraction_in", ["RetractionIn"], bad),
        row("concern_in", ["ExpressionOfConcernIn"], bad),
        row("erratum_in", ["ErratumIn"], unresolved),
        row("corrected_republished_in", ["CorrectedandRepublishedIn"], bad),
        row("retracted_republished_in", ["RetractedandRepublishedIn"], bad),
        row("retraction_of", ["RetractionOf"], bad),
        row("concern_for", ["ExpressionOfConcernFor"], bad),
        row("erratum_for", ["ErratumFor"], bad),
        row("update_in", ["UpdateIn"], unresolved),
        row("corrected_republished_from", ["CorrectedandRepublishedFrom"], unresolved),
        row("retracted_republished_from", ["RetractedandRepublishedFrom"], unresolved),
        row("update_of_pre_jats", ["UpdateOf"], unresolved),
        row("update_of_primary_eligible", ["UpdateOf"], clear, primary_state="SOURCE_TYPE_ELIGIBLE"),
        row("update_of_primary_ineligible", ["UpdateOf"], bad, primary_state="SOURCE_TYPE_INELIGIBLE"),
        row("multiple_precedence", ["ErratumIn", "RetractionIn"], bad),
        row("unknown_ref_type", ["FutureIntegrityRef"], unresolved),
        row("missing_ref_type", [""], unresolved),
        row("missing_linked_pmid", ["RetractionIn"], bad, missing_linked_pmid=True),
        row("retracted_publication_type", [], bad, publication_types=["Journal Article", "Retracted Publication"]),
        row("multiple_reasons", ["RetractionIn", "ErratumIn"], bad,
            publication_types=["Journal Article", "Retracted Publication"]),
        row("ordinary_comment", ["CommentIn"], clear),
    ]


def binding(directory: Path, name: str) -> dict[str, str]:
    return prior.ref(directory, name)


def main() -> None:
    if OUT.exists():
        raise RuntimeError("alpha3.18A.3 output already exists; refusing overwrite")
    queries = verify()
    observed, provenance = local_ref_type_authority()
    synthetic = cases()
    results = []
    for item in synthetic:
        actual = rule.classify(item["publication_types"], item["relationships"],
                               item["independent_primary_state"])
        results.append({"case_id": item["case_id"], "expected_state": item["expected_state"],
                        "actual_state": actual["state"], "pass": actual["state"] == item["expected_state"],
                        "reasons": {"ineligible": actual["ineligible_reasons"],
                                    "unresolved": actual["unresolved_reasons"]}})
    if not all(row["pass"] for row in results):
        raise RuntimeError("synthetic correction-reference validation failed")
    OUT.mkdir()
    write("alpha3_18a2_failure_verification.json", {"status": "PASS", "failed_root_sha256": OLD_ROOT,
        "original_status": "FAILED_CLOSED", "original_blocker": prior.BLOCKER,
        "failure_preserved": True, "validation": binding(OLD, "validation.json")})
    write("nlm_correction_reference_authority_snapshot.json", {
        "authority_kind": "LOCAL_PUBMED_XML_PLUS_EXPLICIT_TASK_RELATIONSHIPS",
        "external_network_verification_in_this_run": False,
        "local_raw_xml_count": len(provenance), "local_raw_xml_provenance_sha256": prior.sha(prior.canonical(provenance)),
        "locally_observed_exact_ref_types": observed,
        "task_supplied_supported_ref_types_not_locally_observed": sorted(rule.RECOGNIZED - set(observed)),
        "direction_preserved": True, "unknown_future_type": "CORRECTION_REFERENCE_UNRESOLVED"})
    write("correction_reference_ref_type_matrix.json", {
        "exact_case_sensitive_strings": True,
        "ineligible": sorted(rule.HARD_INELIGIBLE), "unresolved": sorted(rule.UNRESOLVED),
        "conditional_update_of": sorted(rule.CONDITIONAL_UPDATE), "ordinary_nonblocking": sorted(rule.ORDINARY),
        "in_direction_means_original_has_linked_notice_or_republication": True,
        "of_or_from_direction_not_collapsed": True})
    write("correction_reference_eligibility_v1.json", {
        "schema_version": rule.SCHEMA_VERSION, "implementation": binding(ROOT / "scripts", RULE_FILE.name),
        "states": list(rule.STATES), "publication_type_exclusions": sorted(rule.EXPLICIT_PUBLICATION_TYPE_EXCLUSIONS),
        "recognized_ref_types": sorted(rule.RECOGNIZED), "precedence": ["INELIGIBLE", "UNRESOLVED", "CLEAR"],
        "only_clear_admitted": True, "no_source_replacement": True,
        "UpdateOf_finalization": "provisional UNRESOLVED before JATS; final CLEAR only when frozen independent SourceTypeMechanicalEligibilityV1 is ELIGIBLE; INELIGIBLE if it is INELIGIBLE; otherwise UNRESOLVED",
        "no_manual_or_model_severity_interpretation": True})
    write("correction_reference_decision_table.json", {
        "hard_integrity_or_notice_ref_types": sorted(rule.HARD_INELIGIBLE),
        "conservative_unresolved_ref_types": sorted(rule.UNRESOLVED),
        "conditional_UpdateOf": {"SOURCE_TYPE_ELIGIBLE": "CORRECTION_REFERENCE_CLEAR",
                                 "SOURCE_TYPE_INELIGIBLE": "CORRECTION_REFERENCE_INELIGIBLE",
                                 "SOURCE_TYPE_UNRESOLVED_or_not_yet_run": "CORRECTION_REFERENCE_UNRESOLVED"},
        "ordinary_relations": sorted(rule.ORDINARY),
        "explicit_publication_type_reasons": sorted(rule.EXPLICIT_PUBLICATION_TYPE_EXCLUSIONS),
        "unknown_or_missing_ref_type": "CORRECTION_REFERENCE_UNRESOLVED"})
    write("correction_reference_precedence_policy.json", {"order": ["CORRECTION_REFERENCE_INELIGIBLE",
        "CORRECTION_REFERENCE_UNRESOLVED", "CORRECTION_REFERENCE_CLEAR"],
        "all_applicable_reasons_preserved": True,
        "one_terminal_state_and_one_exclusion_count_per_source": True})
    write("correction_reference_unknown_type_policy.json", {
        "unrecognized_CommentsCorrections_RefType": "CORRECTION_REFERENCE_UNRESOLVED",
        "missing_RefType_on_CommentsCorrections": "CORRECTION_REFERENCE_UNRESOLVED",
        "recognized_blocking_type_with_missing_linked_PMID": "PRESERVE_BLOCKING_STATE",
        "no_silent_ignore": True})
    write("correction_reference_claim_boundary.json", {
        "CLEAR_means": "no blocking or unresolved structured relationship in the frozen sampled PubMed metadata response",
        "CLEAR_does_not_mean": "globally unretracted or permanently publication-integrity-clean",
        "no_notice_prose_or_scientific_severity_interpretation": True,
        "no_later_dynamic_refresh_without_separate_preregistration": True})
    write("correction_reference_metadata_extraction_contract.json", {
        "route": binding(AMEND, "source_metadata_contract_v2.json"),
        "implementation": binding(ROOT / "scripts", RULE_FILE.name),
        "fields": ["PublicationTypeList/PublicationType exact text",
                   "CommentsCorrectionsList/CommentsCorrections/@RefType exact string",
                   "CommentsCorrections/PMID if present", "CommentsCorrections/RefSource if present"],
        "linked_PMID_and_RefSource_private_provenance_only": True,
        "raw_PubMed_XML_frozen": True, "missing_linked_PMID_not_state_downgrade": True})
    write_lines("correction_reference_synthetic_cases.jsonl", synthetic)
    write("correction_reference_synthetic_test_results.json", {
        "status": "PASS", "case_count": len(results), "passed": sum(row["pass"] for row in results),
        "failed": sum(not row["pass"] for row in results), "results": results})
    write("source_eligibility_pipeline_v3.json", {"ordered_stages": [
        "six unchanged PubMed source-query frames", "freeze all six frames",
        "cross-stratum deduplication", "deterministic sampling",
        "sampled PubMed metadata and frozen seen-source check",
        "preliminary Publication Type screen", "preliminary CorrectionReferenceEligibilityV1",
        "PMC OA Subset ESearch check", "provisional NCBI PMC JATS fetch",
        "article-specific license classification", "JATS structural SourceTypeMechanicalEligibilityV1",
        "finalize conditional UpdateOf state using independent source-type state",
        "ConstructionEvidenceDocumentV1", "EvidenceSpanAnchorV1",
        "construction-source manifest", "builder V2 request-manifest freeze"],
        "UpdateOf_provisional_state_not_final_source_admission": True,
        "only_final_CORRECTION_REFERENCE_CLEAR_admitted": True,
        "all_other_prior_source_stages_unchanged": True,
        "no_replacement": True})
    write("multi_reason_exclusion_policy.json", {
        "preserve_all_applicable_publication_type_and_relationship_reasons": True,
        "terminal_state_precedence": ["INELIGIBLE", "UNRESOLVED", "CLEAR"],
        "source_exclusion_denominator_counts_unique_sampled_source_once": True,
        "no_refill": True})
    write("source_state_snapshot_policy.json", {"raw_PubMed_metadata_snapshot_frozen": True,
        "relationship_state_derived_from_that_snapshot": True,
        "builder_quality_heldout_or_Search_Plan_status_refresh": False,
        "future_update_requires_separate_preregistered_audit": True})
    correction_files = ["nlm_correction_reference_authority_snapshot.json", "correction_reference_ref_type_matrix.json",
        "correction_reference_eligibility_v1.json", "correction_reference_decision_table.json",
        "correction_reference_precedence_policy.json", "correction_reference_unknown_type_policy.json",
        "correction_reference_claim_boundary.json", "correction_reference_metadata_extraction_contract.json",
        "correction_reference_synthetic_cases.jsonl", "correction_reference_synthetic_test_results.json",
        "source_eligibility_pipeline_v3.json", "multi_reason_exclusion_policy.json",
        "source_state_snapshot_policy.json"]
    correction_root = prior.sha(prior.canonical(
        [[name, prior.sha((OUT / name).read_bytes())] for name in sorted(correction_files)] +
        [[str(RULE_FILE.relative_to(ROOT)), prior.sha(RULE_FILE.read_bytes())]]))
    marker("correction_reference_eligibility_v1_sha256", correction_root)
    source_bindings = {name: binding(SOURCE, name) for name in prior.SOURCE_FILES}
    amend_bindings = {name: binding(AMEND, name) for name in (
        "source_metadata_contract_v2.json", "oa_subset_verification_contract.json",
        "construction_license_policy.json", "license_extraction_contract.json",
        "construction_oa_eligibility_v1_contract.json", "oa_three_state_decision_table.json",
        "publication_type_exclusion_set.json", "publication_type_acceptance_set.json",
        "source_type_mechanical_eligibility_v1.json", "source_type_three_state_decision_table.json",
        "methods_heading_whitelist.json", "results_heading_whitelist.json",
        "construction_evidence_document_v1_contract.json", "construction_document_canonicalization_contract.json",
        "construction_document_front_matter_policy.json", "construction_document_abstract_policy.json",
        "construction_document_body_policy.json", "construction_document_reference_policy.json",
        "construction_document_other_section_policy.json", "evidence_span_anchor_v1_contract.json",
        "evidence_span_granularity_contract.json", "builder_request_visibility_amendment.json",
        "proposition_builder_v2_1_user_prompt_template.txt")}
    manifest = {
        "status": "EXECUTABLE_PREREGISTRATION_FROZEN", "schema_version": "Alpha318A3SourceAcquisitionExecutionManifest",
        "authoritative_roots": {"failed_alpha3_18a2": OLD_ROOT, "alpha3_18a1": AMEND_ROOT,
            "architecture_freeze": "ba82369f45c8a4fcee373fb36011e7bd5817af1e9568765ce0be7801518ff5d1",
            "builder_protocol_v2": "8a50314aac4e5f8017109a047905981a91aa91ffb784e1ebde0f92256917ba33",
            "builder_output_schema_v2": "5309d3edc9b8a40b64f6fc79e5f7a8e19ac4738808827b33cfe2eb3047db7849",
            "quality_protocol_v2": "89009283963c1db3dd00d57917d932b4d0a542dcb27863ad071dc30f8c0cd751",
            "correction_reference_eligibility_v1": correction_root},
        "queries": [{"stratum_id": row["stratum_id"], "stratum_order": row["stratum_order"],
                     "query_utf8": row["query_utf8"], "query_sha256": row["query_sha256"]} for row in queries],
        "query_file": binding(SOURCE, "exact_source_queries.jsonl"), "query_changes": 0,
        "network_scope": {"allowed_host": "eutils.ncbi.nlm.nih.gov",
            "allowed_services": ["NCBI PubMed E-Utilities", "NCBI PMC E-Utilities"],
            "all_other_network_services": "FORBIDDEN", "model_provider_calls": 0},
        "network_routes": {
            "source_frames": {"endpoint": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                "method": "GET", "db": "pubmed", "retmode": "json", "sort": "relevance",
                "page_size": 50, "retstart_sequence": [0, 50, 100, 150],
                "frame_cap_per_stratum": 200,
                "technical_policy": binding(SOURCE, "source_execution_policy.json")},
            "sampled_metadata": {"endpoint": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
                "method": "GET", "db": "pubmed", "retmode": "xml", "id": "sampled canonical PMID",
                "field_and_date_policy": binding(AMEND, "source_metadata_contract_v2.json")},
            "pmc_oa_subset": binding(AMEND, "oa_subset_verification_contract.json"),
            "pmc_jats": {"endpoint": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
                "method": "GET", "db": "pmc", "retmode": "xml", "id": "verified numeric PMCID suffix",
                "acquisition_policy": binding(SOURCE, "construction_fulltext_acquisition_policy.json"),
                "failure_policy": binding(SOURCE, "construction_fulltext_failure_policy.json")},
            "raw_requests_and_responses_frozen": True,
        },
        "frozen_source_bindings": source_bindings, "frozen_amendment_bindings": amend_bindings,
        "correction_gate": binding(OUT, "correction_reference_eligibility_v1.json"),
        "correction_gate_code": binding(ROOT / "scripts", RULE_FILE.name),
        "correction_gate_root_sha256": correction_root,
        "pipeline": binding(OUT, "source_eligibility_pipeline_v3.json"),
        "frame_barrier": "all six relevance-ordered frames freeze before dedup/sampling; terminal failure stops all network; no partial sampling",
        "sampling": "earliest-stratum PMID ownership; SHA-256 keyed ordering; at most 12 per stratum; no refill or replacement",
        "source_admission": "all prior frozen gates plus final CORRECTION_REFERENCE_CLEAR; no manual promotion",
        "builder_protocol": binding(BUILDER, "proposition_builder_protocol_v2.json"),
        "builder_output_schema": binding(BUILDER, "proposition_builder_output_schema_v2.json"),
        "builder_request": binding(SOURCE, "proposition_builder_request_contract.json"),
        "builder_visibility": {"original": binding(SOURCE, "proposition_builder_visibility_contract.json"),
            "prospective_amendment": binding(AMEND, "builder_request_visibility_amendment.json"),
            "title_free_template": binding(AMEND, "proposition_builder_v2_1_user_prompt_template.txt")},
        "opaque_source_token": "generate 32 CSPRNG bytes once per final source; prefix src_; freeze token-to-identity mapping in ANCHOR_RESTRICTED private vault before document/anchor generation; never regenerate after freeze",
        "builder_request_freeze": "all requests and aggregate hash before first future builder call; one request per final source",
        "failure": {"terminal_source_frame_failure": "STOP_ALL_NETWORK_AND_FAIL_CLOSED",
            "unresolved_metadata_or_eligibility": "EXCLUDE_SOURCE_WITHOUT_REPLACEMENT",
            "terminal_JATS_failure": "EXCLUDE_SOURCE_WITHOUT_REPLACEMENT",
            "invalid_document_or_anchor": "EXCLUDE_SOURCE_WITHOUT_REPLACEMENT",
            "unknown_RefType": "CORRECTION_REFERENCE_UNRESOLVED"},
        "future_required_freezes": ["six source frames and raw request/response provenance", "canonical deduplicated frame",
            "sample selection", "sampled metadata and linked-citation snapshot", "OA and license responses",
            "raw JATS", "construction documents and spans", "private anchor mapping",
            "construction-source manifest", "builder-request manifest", "actual future builder call budget"],
        "material_runtime_policy_unresolved_count": 0,
        "future_network_execution_requires_separate_authorization": True,
        "network_calls_in_this_preregistration": 0,
    }
    write("alpha3_18a3_source_acquisition_execution_manifest.json", manifest)
    manifest_sha = prior.sha((OUT / "alpha3_18a3_source_acquisition_execution_manifest.json").read_bytes())
    marker("alpha3_18a3_source_acquisition_execution_manifest_sha256", manifest_sha)
    write("final_execution_manifest_completeness_audit.json", {"status": "PASS",
        "material_runtime_policy_unresolved_count": 0, "only_new_eligibility_dimension": rule.SCHEMA_VERSION,
        "all_prior_source_contracts_unchanged": True, "query_changes": 0,
        "UpdateOf_deferred_resolution_explicit": True, "unknown_ref_type_fails_closed": True,
        "network_scope_ncbi_only": True, "manifest_sha256": manifest_sha})
    write("network_authorization_readiness.json", {"status": "READY_FOR_NCBI_ONLY_SOURCE_ACQUISITION_AUTHORIZATION",
        "network_execution_authorized_in_this_offline_stage": False,
        "future_allowed": ["NCBI PubMed source frames", "NCBI PubMed sampled metadata",
                           "NCBI PMC OA Subset verification", "NCBI PMC canonical JATS"],
        "future_model_calls": 0, "future_other_network_services": 0})
    write("historical_preservation_audit.json", {"failed_alpha3_18a2_root_sha256": OLD_ROOT,
        "alpha3_18a1_root_sha256": AMEND_ROOT, "source_queries_modified": False,
        "other_prior_source_contracts_modified": False, "historical_assets_modified": False})
    write("scientific_state_safety_audit.json", {"provider_calls": 0, "llm_calls": 0,
        "network_calls": 0, "retrieval_calls": 0, "builder_calls": 0, "quality_calls": 0,
        "heldout_cases_selected": 0, "source_results_observed": 0,
        "scientific_severity_interpretations": 0, "historical_assets_modified": False})
    write("validation.json", {"status": "PASS", "historical_alpha3_18a2_failure_preserved": True,
        "correction_reference_rule_resolved": True, "correction_reference_states_exactly_three": True,
        "retraction_in_is_ineligible": True, "expression_of_concern_in_is_ineligible": True,
        "erratum_in_is_unresolved": True, "corrected_and_republished_in_is_ineligible": True,
        "retracted_and_republished_in_is_ineligible": True,
        "unknown_correction_ref_type_is_unresolved": True,
        "manual_severity_interpretation_used": False, "model_severity_interpretation_used": False,
        "dynamic_source_replacement_allowed": False, "source_status_snapshot_frozen": True,
        "all_prior_source_contracts_unchanged": True, "material_runtime_policy_unresolved_count": 0,
        "final_execution_manifest_executable": True, "network_authorization_ready": True,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0, "retrieval_calls": 0})
    write("summary.json", {"status": "completed", "correction_reference_eligibility_v1_sha256": correction_root,
        "alpha3_18a3_source_acquisition_execution_manifest_sha256": manifest_sha,
        "next_stage_recommendation": "AUTHORIZE_ALPHA3_18A_NCBI_ONLY_SOURCE_ACQUISITION",
        "network_execution_authorized_now": False, "historical_assets_modified": False})
    root = prior.all_file_root(OUT, "search_plan_v24_dev_alpha3_18a3_prereg_sha256")
    marker("search_plan_v24_dev_alpha3_18a3_prereg_sha256", root)
    assert prior.all_file_root(OUT, "search_plan_v24_dev_alpha3_18a3_prereg_sha256") == root
    print(json.dumps({"status": "completed", "run_root": root,
        "correction_root": correction_root, "manifest_sha256": manifest_sha,
        "network_calls": 0, "provider_calls": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
