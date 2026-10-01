#!/usr/bin/env python3
"""Prospectively freeze alpha3.18A.1 source contracts without network or model calls."""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

try:
    from scripts.search_plan_v24_alpha318a1_source_contracts import (
        ACCEPTED_PUBLICATION_TYPES, EXCLUDED_PUBLICATION_TYPES, LOCAL_PUBLICATION_TYPES,
        METHODS_HEADINGS, NEUTRAL_PUBLICATION_TYPES, OTHER_EXCLUDED_HEADINGS,
        RESULTS_HEADINGS,
    )
except ModuleNotFoundError:  # direct `python scripts/…py` execution
    from search_plan_v24_alpha318a1_source_contracts import (
        ACCEPTED_PUBLICATION_TYPES, EXCLUDED_PUBLICATION_TYPES, LOCAL_PUBLICATION_TYPES,
        METHODS_HEADINGS, NEUTRAL_PUBLICATION_TYPES, OTHER_EXCLUDED_HEADINGS,
        RESULTS_HEADINGS,
    )


ROOT = Path(__file__).resolve().parents[1]
FAILED = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_18a_source_acquisition_execution_preregistration_offline"
UP17A = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17a_new_pool_execution_preflight_offline"
UP17D = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17d_independent_quality_adjudication_v2_preregistration_offline"
ARCH = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_16_architecture_freeze_fresh_heldout_v3_preregistration_offline"
OUT = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_18a1_source_contract_resolution_offline"
FAILED_ROOT = "ea3a7f9ac0ec58a5babe8acacf19290e5aa699e09849e39370fd5d9b96d08113"
UP17D_ROOT = "1f96a0f276ba8ab58f4ad0959c1140fab0d0949c03eb75a3e10dd2af3cad42e9"
ARCH_ROOT = "ba82369f45c8a4fcee373fb36011e7bd5817af1e9568765ce0be7801518ff5d1"
SOURCE_ROOT = "755702713972012bc062f7cba43eea95708c9a5e75ca5c93e49ef5396f0c00c0"
MODULE_PATH = ROOT / "scripts/search_plan_v24_alpha318a1_source_contracts.py"


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def aggregate(directory: Path, names: list[str]) -> str:
    return sha(canonical([[name, sha((directory / name).read_bytes())] for name in sorted(names)]))


def all_file_root(directory: Path, excluded: str) -> str:
    return aggregate(directory, [p.name for p in directory.iterdir() if p.is_file() and p.name != excluded])


def write(name: str, value: Any) -> None:
    path = OUT / name
    if path.exists():
        raise RuntimeError(f"refusing overwrite: {path}")
    path.write_bytes(canonical(value) + b"\n")


def write_text(name: str, value: str) -> None:
    path = OUT / name
    if path.exists():
        raise RuntimeError(f"refusing overwrite: {path}")
    path.write_bytes(value.encode("utf-8"))


def local_pubmed_vocabulary() -> tuple[list[str], list[list[str]]]:
    files = sorted((ROOT / "runs").glob("202609*/retrieval_assets/pubmed_efetch/*.xml"))
    terms: set[str] = set()
    provenance: list[list[str]] = []
    for path in files:
        root = ET.parse(path).getroot()
        terms.update(" ".join((node.text or "").split()) for node in root.iter("PublicationType") if (node.text or "").strip())
        provenance.append([str(path.relative_to(ROOT)), sha(path.read_bytes())])
    return sorted(terms), provenance


def verify() -> tuple[list[dict], list[str], list[list[str]]]:
    for directory, marker, expected in ((FAILED, "search_plan_v24_dev_alpha3_18a_prereg_sha256", FAILED_ROOT),
                                         (UP17D, "search_plan_v24_dev_alpha3_17d_sha256", UP17D_ROOT)):
        if all_file_root(directory, marker) != expected or (directory / marker).read_text().strip() != expected:
            raise RuntimeError(f"upstream root drift: {directory.name}")
    failed = load(FAILED / "validation.json")
    if failed["status"] != "FAILED_CLOSED" or any(failed[key] for key in (
        "construction_oa_rule_resolved", "source_type_mechanical_rule_resolved",
        "construction_evidence_document_contract_frozen", "evidence_span_anchor_contract_frozen"
    )):
        raise RuntimeError("failed alpha3.18A state changed")
    arch = load(ARCH / "architecture_freeze_manifest.json")
    if arch["architecture_freeze_sha256"] != ARCH_ROOT or not all(
        sha((ROOT / relative).read_bytes()) == expected for relative, expected in arch["components"]
    ):
        raise RuntimeError("architecture freeze changed")
    if (UP17A / "new_pool_source_acquisition_manifest_sha256").read_text().strip() != SOURCE_ROOT:
        raise RuntimeError("source acquisition manifest changed")
    queries_bytes = (UP17A / "exact_source_queries.jsonl").read_bytes()
    if sha(queries_bytes) != (UP17A / "exact_source_queries_sha256").read_text().strip():
        raise RuntimeError("source-query hash changed")
    queries = [json.loads(line) for line in queries_bytes.splitlines()]
    if len(queries) != 6 or any(sha(row["query_utf8"].encode()) != row["query_sha256"] for row in queries):
        raise RuntimeError("six source queries changed")
    terms, provenance = local_pubmed_vocabulary()
    if set(terms) != LOCAL_PUBLICATION_TYPES:
        raise RuntimeError("local publication-type vocabulary differs from frozen source-policy module")
    return queries, terms, provenance


def main() -> None:
    if OUT.exists():
        raise RuntimeError("alpha3.18A.1 already exists; never regenerate frozen amendment")
    queries, publication_types, publication_provenance = verify()
    module_sha = sha(MODULE_PATH.read_bytes())
    OUT.mkdir()
    write("alpha3_18a_failed_prereg_verification.json", {
        "status": "PASS", "expected_failed_root_sha256": FAILED_ROOT,
        "actual_failed_root_sha256": all_file_root(FAILED, "search_plan_v24_dev_alpha3_18a_prereg_sha256"),
        "prior_flags_preserved": {key: False for key in (
            "construction_oa_rule_resolved", "source_type_mechanical_rule_resolved",
            "construction_evidence_document_contract_frozen", "evidence_span_anchor_contract_frozen")},
        "alpha3_17d_root_sha256": UP17D_ROOT, "architecture_freeze_sha256": ARCH_ROOT})
    facts = [
        "The historical PMC OA Web Service API is unavailable as of August 2026 and must not be used.",
        "Current PMC-supported automated article-dataset access includes PMC Cloud Service, PMC OAI-PMH, NCBI E-Utilities, and PMC BioC API.",
        "PMC Open Access Subset membership is separate from generic PMC presence and reflects reuse availability under CC-like terms or publisher permission.",
        "Article-specific license terms vary; the article's own license statement controls the local classification input.",
        "PMC search supports an Open Access Subset filter distinct from generic PMC presence.",
        "PMC article full text is available in JATS-compatible XML through supported NCBI/PMC services.",
        "PubMed Publication Type is structured indexing metadata, not proof that an article reports primary experiments.",
    ]
    write("external_ncbi_pmc_authority_snapshot.json", {
        "authority_kind": "CURRENT_EXTERNAL_FACTS_SUPPLIED_IN_TASK",
        "independently_network_verified_in_this_offline_run": False,
        "facts": facts,
        "implementation_caveat": "No network call was permitted; supported route syntax is frozen prospectively and must fail closed on provider rejection.",
        "historical_repository_fact_claimed": False})
    write("oa_web_service_deprecation_note.json", {"historical_oa_web_service_used": False,
        "task_supplied_deprecation_date": "2026-08", "old_repo_client_path": "src/code_engine/fulltext/pmc_oa_client.py",
        "old_client_not_reused_for_future_alpha3_18a": True,
        "future_route": "NCBI E-Utilities ESearch db=pmc plus PMC OA Subset filter"})
    write("oa_subset_verification_contract.json", {"route": "NCBI E-Utilities ESearch",
        "endpoint": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        "method": "GET", "fixed_parameters": {"db": "pmc", "retmode": "json", "retmax": "1"},
        "term_template": "{numeric_pmc_uid}[UID] AND open access[filter]",
        "pmcid_normalization": "require uppercase PMC followed by nonzero decimal digits; numeric_pmc_uid is exact suffix",
        "term_function": "scripts/search_plan_v24_alpha318a1_source_contracts.py:oa_subset_esearch_term",
        "positive_response": "valid ESearch JSON with exactly one returned IdList value equal to requested numeric PMC UID",
        "negative_response": "valid ESearch JSON with Count=0 and empty IdList",
        "other_response_or_transport_failure": "CONSTRUCTION_OA_UNRESOLVED",
        "raw_response_and_request_hash_required": True,
        "deprecated_oa_web_service_used": False,
        "query_changes": 0, "provider_syntax_not_network_tested_in_this_offline_stage": True})
    write("construction_license_policy.json", {
        "local_policy_purpose": "Conservative transfer of source evidence to an external model provider; not a determination of ultimate legal rights.",
        "accepted_machine_readable_classes": ["CC0", "CC_BY", "CC_BY_SA"],
        "accepted_cc_versions": ["CC0 1.0", "CC BY 2.0/2.5/3.0/4.0", "CC BY-SA 2.0/2.5/3.0/4.0"],
        "explicit_nonwhitelist_examples": ["CC BY-NC", "CC BY-ND", "CC BY-NC-SA", "CC BY-NC-ND"],
        "unknown_or_unparseable_license": "CONSTRUCTION_OA_UNRESOLVED",
        "explicit_nonwhitelist_license": "CONSTRUCTION_OA_INELIGIBLE",
        "journal_or_pmc_presence_inference_allowed": False})
    write("license_extraction_contract.json", {
        "input": "canonical NCBI PMC JATS article XML",
        "nodes": "article/front/article-meta/permissions/license (namespace-insensitive local names)",
        "url_field": "license/@xlink:href or license/@href, exactly one",
        "text_field": "normalized license subtree text, required nonempty",
        "normalization": "URL scheme/host lowercase; exact Creative Commons path; no query or fragment; text Unicode NFKC and whitespace collapse",
        "preserve": ["raw license text", "raw license URL", "normalized class", "classification provenance"],
        "conflicting_multiple_licenses_or_url_text": "CONSTRUCTION_OA_UNRESOLVED",
        "implementation": "scripts/search_plan_v24_alpha318a1_source_contracts.py:extract_license",
        "implementation_sha256": module_sha})
    write("oa_three_state_decision_table.json", {
        "CONSTRUCTION_OA_ELIGIBLE": "resolved PMCID, positive PMC OA Subset ESearch, valid canonical JATS, and whitelisted article-specific license statement",
        "CONSTRUCTION_OA_INELIGIBLE": "valid negative OA Subset result or explicit nonwhitelist CC license",
        "CONSTRUCTION_OA_UNRESOLVED": "missing PMCID, transport/parser/identity ambiguity, missing or conflicting or unknown license, or missing JATS",
        "no_manual_override_or_source_replacement": True,
        "implementation": "scripts/search_plan_v24_alpha318a1_source_contracts.py:construction_oa_state",
        "implementation_sha256": module_sha})
    write("construction_oa_eligibility_v1_contract.json", {
        "schema_version": "ConstructionOAEligibilityV1",
        "pmc_filter_is_discovery_only": True,
        "requires": ["resolved PMCID", "positive PMC OA Subset ESearch", "successful NCBI PMC JATS acquisition",
                     "classified article-specific license within local whitelist"],
        "subset_route": "oa_subset_verification_contract.json",
        "license_policy": "construction_license_policy.json",
        "three_state_table": "oa_three_state_decision_table.json",
        "OA_Web_Service_used": False, "publisher_or_general_web_fallback": False,
        "raw_subset_and_JATS_responses_frozen_before_classification": True,
        "only_ELIGIBLE_reaches_builder": True})
    write("source_metadata_contract_v2.json", {
        "route": "NCBI E-Utilities EFetch db=pubmed retmode=xml after sampling only",
        "fields": [
            {"name": "PMID", "xml_path": "PubmedArticle/MedlineCitation/PMID"},
            {"name": "PMCID", "xml_path": "PubmedArticle/PubmedData/ArticleIdList/ArticleId[@IdType='pmc']"},
            {"name": "DOI", "xml_path": "PubmedArticle/PubmedData/ArticleIdList/ArticleId[@IdType='doi']"},
            {"name": "publication_date", "xml_path": "MedlineCitation/Article/Journal/JournalIssue/PubDate and Article/ArticleDate"},
            {"name": "publication_types", "xml_path": "MedlineCitation/Article/PublicationTypeList/PublicationType"},
            {"name": "correction_retraction_refs", "xml_path": "MedlineCitation/CommentsCorrectionsList/CommentsCorrections/@RefType"},
        ],
        "date_rule": "stable parsed publication date/year must lie in 2018-01-01 through 2023-12-31; ambiguous dates UNRESOLVED",
        "identifier_rule": "PMID must equal sampled PMID; zero or multiple distinct PMCIDs UNRESOLVED",
        "not_fetched_for_preference": ["citation counts", "scientific keywords", "MeSH terms", "abstract", "title"],
        "raw_xml_and_identifier_provenance_frozen": True})
    write("pubmed_publication_type_authority.json", {
        "authority": "exact PublicationType element strings observed in locally preserved PubMed EFetch XML; not an exhaustive current NLM vocabulary",
        "local_raw_xml_file_count": len(publication_provenance),
        "local_raw_xml_files_sha256": sha(canonical(publication_provenance)),
        "observed_exact_strings": publication_types,
        "publication_type_alone_proves_primary_experimental": False,
        "unknown_future_type": "SOURCE_TYPE_UNRESOLVED"})
    write("publication_type_exclusion_set.json", {"exact_strings": sorted(EXCLUDED_PUBLICATION_TYPES),
        "source": "locally observed PubMed PublicationType strings only",
        "unobserved_task_examples_not_claimed_as_verified_vocabulary": True,
        "any_match": "SOURCE_TYPE_INELIGIBLE"})
    write("publication_type_acceptance_set.json", {"exact_strings": sorted(ACCEPTED_PUBLICATION_TYPES),
        "neutral_exact_strings": sorted(NEUTRAL_PUBLICATION_TYPES),
        "at_least_one_accepted_required": True,
        "accepted_type_alone_sufficient": False,
        "unknown_type": "SOURCE_TYPE_UNRESOLVED"})
    write("methods_heading_whitelist.json", {"exact_normalized_headings": sorted(METHODS_HEADINGS),
        "normalization": "Unicode NFKC casefold; strip leading decimal/Roman section numbering with punctuation; replace nonword runs with spaces; collapse spaces",
        "nested_sec_recursive": True,
        "implementation_sha256": module_sha})
    write("results_heading_whitelist.json", {"exact_normalized_headings": sorted(RESULTS_HEADINGS),
        "combined_results_discussion_allowed": True,
        "nested_sec_recursive": True,
        "implementation_sha256": module_sha})
    write("jats_primary_experimental_structure_contract.json", {
        "input": "canonical PMC JATS article XML with body",
        "required": ["one Methods-like heading", "one Results-like heading"],
        "nonprimary_article_type_values": ["review-article", "editorial", "letter", "case-report", "correction", "retraction"],
        "section_traversal": "body/sec recursively; preserve ordinal path and normalized heading",
        "missing_structure": "SOURCE_TYPE_UNRESOLVED",
        "free_semantic_heading_similarity": False,
        "implementation": "scripts/search_plan_v24_alpha318a1_source_contracts.py:body_headings",
        "implementation_sha256": module_sha})
    write("source_type_three_state_decision_table.json", {
        "SOURCE_TYPE_INELIGIBLE": "any exact excluded PubMed type or explicit nonprimary JATS article-type",
        "SOURCE_TYPE_ELIGIBLE": "at least one accepted PubMed type, no excluded or unknown type, valid JATS body with Methods-like and Results-like headings",
        "SOURCE_TYPE_UNRESOLVED": "missing/unknown type, absent positive type, unavailable/invalid JATS, or missing required structure without positive ineligibility",
        "manual_promotion_of_unresolved": False,
        "implementation": "scripts/search_plan_v24_alpha318a1_source_contracts.py:source_type_state",
        "implementation_sha256": module_sha})
    write("source_type_mechanical_eligibility_v1.json", {
        "schema_version": "SourceTypeMechanicalEligibilityV1",
        "publication_type_exclusions": "publication_type_exclusion_set.json",
        "publication_type_acceptance": "publication_type_acceptance_set.json",
        "JATS_structural_predicate": "jats_primary_experimental_structure_contract.json",
        "three_state_table": "source_type_three_state_decision_table.json",
        "mechanical_proxy_not_gold_scientific_label": True,
        "no_model_or_manual_scientific_judgment": True})
    write("construction_document_front_matter_policy.json", {
        "builder_visible_title": False, "builder_visible_authors": False,
        "builder_visible_affiliations": False, "builder_visible_journal": False,
        "builder_visible_PMiD_PMCID_DOI": False,
        "private_anchor_retains_available_identity": True})
    write("construction_document_abstract_policy.json", {
        "builder_visible": True, "separately_labeled": True,
        "first_unicode_codepoints_max": 10000,
        "abstract_only_candidate_grounding_allowed": False,
        "candidate_source_field_must_be_BODY": True})
    write("construction_document_body_policy.json", {
        "builder_visible": True, "JATS_source": "article/body only; never rendered HTML",
        "preserve": ["nested section paths and normalized headings", "paragraph order and text",
                     "figure captions", "table captions"],
        "first_unicode_codepoints_max": 60000,
        "truncation": "first 60000 code points of canonical body text; final paragraph may be truncated; anchors generated after truncation",
        "no_summarization_or_paraphrase": True})
    write("construction_document_reference_policy.json", {
        "exclude_back_element_entirely": True,
        "exclude_body_sec_when_normalized_heading_is_references_or_bibliography": True,
        "remove_xref_ref_type_bibr_marker_text_keep_tail_prose": True,
        "model_visible_bibliography": False})
    write("construction_document_other_section_policy.json", {
        "excluded_normalized_headings": sorted(OTHER_EXCLUDED_HEADINGS),
        "excluded_sec_types": ["supplementary-material", "references", "acknowledgments", "funding"],
        "excluded_front_matter": ["title", "authors", "affiliations", "journal", "identifiers", "publisher metadata"],
        "unrecognized_body_section": "retain under its source-local heading; no semantic deletion"})
    write("construction_document_canonicalization_contract.json", {
        "encoding": "UTF-8", "text_normalization": "Unicode NFKC then collapse all whitespace runs within each paragraph",
        "body_paragraph_separator": "two LF characters", "section_path": "nested 1-based sec ordinals",
        "heading_normalization": "same frozen heading-normalization function used for source-type checks",
        "caption_handling": "fig/caption and table-wrap/caption in body traversal, each as one paragraph-kind item",
        "offset_semantics": "zero-based Unicode code-point offsets in canonical body_text; exact_text must equal body_text[start:end]",
        "canonical_json": "UTF-8 JSON with sorted keys, ensure_ascii=false, compact separators, one trailing LF",
        "implementation": "scripts/search_plan_v24_alpha318a1_source_contracts.py:build_construction_document",
        "implementation_sha256": module_sha})
    write("construction_evidence_document_v1_contract.json", {
        "schema_version": "ConstructionEvidenceDocumentV1",
        "input": "frozen NCBI PMC JATS article XML",
        "model_visible_fields": ["schema_version", "abstract_text", "body_text", "paragraphs", "normalization"],
        "article_title_visible": False, "bibliography_visible": False,
        "body_only_candidate_grounding": True,
        "document_states": ["CONSTRUCTION_DOCUMENT_VALID", "CONSTRUCTION_DOCUMENT_INVALID", "CONSTRUCTION_DOCUMENT_UNRESOLVED"],
        "invalid_or_unresolved_builder_call": False,
        "fulltext_raw_and_document_hash_required": True,
        "implementation_sha256": module_sha})
    write("evidence_span_granularity_contract.json", {
        "granularity": "one canonical body paragraph or figure/table caption after deterministic 60000-character cutoff",
        "optional_candidate_subspan": "exact start/end offsets within one paragraph anchor",
        "cross_paragraph_candidate_span": "INVALID",
        "dynamic_scientific_granularity_choice": False})
    write("evidence_span_anchor_v1_contract.json", {
        "schema_version": "EvidenceSpanAnchorV1",
        "model_visible_id": "spanv1_ + SHA256(canonical JSON [EvidenceSpanAnchorV1, private opaque source token, section path, paragraph ordinal, SHA256(paragraph UTF-8 text)])",
        "private_token_encoded_in_clear": False,
        "forbidden_clear_identifiers": ["PMID", "PMCID", "DOI", "article title", "journal", "source rank"],
        "anchor_generation": "after canonical body truncation; paragraph-level",
        "candidate_mapping": "after BuilderProtocolV2 schema validation, require BODY exact_text and offsets within exactly one anchor, then attach span ID deterministically; builder output schema unchanged",
        "implementation": "scripts/search_plan_v24_alpha318a1_source_contracts.py:resolve_candidate_span",
        "implementation_sha256": module_sha})
    write("builder_grounding_reference_contract.json", {
        "builder_protocol_v2_sha256": "8a50314aac4e5f8017109a047905981a91aa91ffb784e1ebde0f92256917ba33",
        "builder_output_schema_v2_sha256": "5309d3edc9b8a40b64f6fc79e5f7a8e19ac4738808827b33cfe2eb3047db7849",
        "builder_schema_source_field_enum_unchanged": ["abstract", "body"],
        "prospective_post_validation_body_only_rule": True,
        "span_id_attached_by_deterministic_controller_not_model": True,
        "semantic_support_judged_by_independent_quality_stage": True})
    old_template = (UP17A / "proposition_builder_user_prompt_template.txt").read_text(encoding="utf-8")
    if "Title: {source_title}\n" not in old_template:
        raise RuntimeError("builder prompt title contract changed")
    new_template = old_template.replace("Title: {source_title}\n", "")
    if "{source_title}" in new_template:
        raise RuntimeError("builder title still visible")
    write_text("proposition_builder_v2_1_user_prompt_template.txt", new_template)
    write("builder_request_visibility_amendment.json", {
        "type": "PROSPECTIVE_PRE_BUILDER_SOURCE_PRESENTATION_AMENDMENT",
        "old_template_sha256": sha(old_template.encode()),
        "new_template_file": "proposition_builder_v2_1_user_prompt_template.txt",
        "new_template_sha256": sha(new_template.encode()),
        "title_removed": True,
        "required_additional_instruction": "Candidate evidence must use source_field=body and exact offsets into frozen canonical body_text; do not use abstract-only grounding.",
        "builder_core_scientific_fields_or_cardinality_changed": False,
        "builder_calls_before_amendment": 0})
    write("future_alpha3_18a_execution_order.json", {
        "ordered_stages": ["six unchanged PubMed source-query frames", "freeze all six frames",
            "cross-stratum deduplication", "deterministic sampling", "sampled PubMed metadata and frozen seen-source check",
            "preliminary publication-type screen", "PMC OA Subset ESearch check",
            "provisional NCBI PMC JATS fetch", "article-specific license classification",
            "JATS structural source-type check", "ConstructionEvidenceDocumentV1",
            "EvidenceSpanAnchorV1", "construction-source manifest", "builder V2 request-manifest freeze"],
        "reason_license_after_JATS": "article-specific license statement is read from JATS; provisional fetch must precede final construction OA classification",
        "no_model_or_scientific_selection_in_alpha3_18a": True,
        "no_source_replacement": True})
    write("source_query_immutability_audit.json", {
        "query_count": 6, "query_changes": 0,
        "source_query_file_sha256": sha((UP17A / "exact_source_queries.jsonl").read_bytes()),
        "per_query_sha256": [[row["stratum_id"], row["query_sha256"]] for row in queries],
        "new_post_sampling_OA_verification_is_not_discovery_query_modification": True,
        "architecture_changes": 0})
    write("historical_preservation_audit.json", {
        "failed_alpha3_18a_prereg_root_unchanged": FAILED_ROOT,
        "alpha3_17d_root_unchanged": UP17D_ROOT,
        "architecture_root_unchanged": ARCH_ROOT,
        "source_query_manifest_root_unchanged": SOURCE_ROOT,
        "new_rules_prospective_pre_network": True,
        "historical_assets_modified": False})
    write("scientific_state_safety_audit.json", {
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0, "retrieval_calls": 0,
        "builder_calls": 0, "quality_calls": 0, "source_acquisition_calls": 0,
        "propositions_generated": 0, "historical_assets_modified": False})
    root_groups = {
        "construction_oa_eligibility_v1_sha256": ["external_ncbi_pmc_authority_snapshot.json", "oa_web_service_deprecation_note.json",
            "construction_oa_eligibility_v1_contract.json", "oa_subset_verification_contract.json",
            "construction_license_policy.json", "license_extraction_contract.json", "oa_three_state_decision_table.json"],
        "source_type_mechanical_eligibility_v1_sha256": ["pubmed_publication_type_authority.json",
            "publication_type_exclusion_set.json", "publication_type_acceptance_set.json",
            "jats_primary_experimental_structure_contract.json", "methods_heading_whitelist.json",
            "results_heading_whitelist.json", "source_type_mechanical_eligibility_v1.json",
            "source_type_three_state_decision_table.json"],
        "construction_evidence_document_v1_sha256": ["source_metadata_contract_v2.json",
            "construction_evidence_document_v1_contract.json", "construction_document_front_matter_policy.json",
            "construction_document_abstract_policy.json", "construction_document_body_policy.json",
            "construction_document_reference_policy.json", "construction_document_other_section_policy.json",
            "construction_document_canonicalization_contract.json", "builder_request_visibility_amendment.json",
            "proposition_builder_v2_1_user_prompt_template.txt"],
        "evidence_span_anchor_v1_sha256": ["evidence_span_anchor_v1_contract.json",
            "evidence_span_granularity_contract.json", "builder_grounding_reference_contract.json"],
    }
    roots = {name: aggregate(OUT, names) for name, names in root_groups.items()}
    for name, value in roots.items():
        write_text(name, value + "\n")
    write("validation.json", {
        "status": "PASS", "pmc_oa_web_service_used": False,
        "pmc_filter_treated_as_final_oa_proof": False,
        "oa_subset_verification_route_frozen": True,
        "article_specific_license_policy_frozen": True,
        "construction_oa_rule_resolved": True,
        "publication_type_exclusion_set_frozen": True,
        "publication_type_acceptance_set_frozen": True,
        "methods_heading_whitelist_frozen": True,
        "results_heading_whitelist_frozen": True,
        "source_type_mechanical_rule_resolved": True,
        "construction_document_uses_jats_xml": True,
        "article_title_visible_to_builder": False,
        "bibliography_visible_to_builder": False,
        "construction_document_contract_frozen": True,
        "evidence_span_anchor_contract_frozen": True,
        "source_query_changes": 0, "architecture_changes": 0,
        "builder_calls": 0, "quality_calls": 0,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0, "retrieval_calls": 0,
        "external_fact_verification_network_calls": 0,
        "authority_facts_provided_by_task_not_independently_rechecked": True})
    write("summary.json", {"status": "completed", **roots,
        "next_stage_recommendation": "REBUILD_ALPHA3_18A_EXECUTION_PREREGISTRATION",
        "execution_authorized_now": False,
        "authority_facts_provided_by_task_not_independently_rechecked": True,
        "historical_assets_modified": False})
    run_root = all_file_root(OUT, "search_plan_v24_dev_alpha3_18a1_sha256")
    write_text("search_plan_v24_dev_alpha3_18a1_sha256", run_root + "\n")
    assert all_file_root(OUT, "search_plan_v24_dev_alpha3_18a1_sha256") == run_root
    print(json.dumps({"status": "completed", "run_root": run_root, **roots,
                      "network_calls": 0, "provider_calls": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
