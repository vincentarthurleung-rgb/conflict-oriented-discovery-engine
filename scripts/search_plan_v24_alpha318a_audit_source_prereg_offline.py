#!/usr/bin/env python3
"""Fail-closed audit of alpha3.18A source-acquisition execution authority."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
UP17 = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17_new_blinded_proposition_pool_preregistration_offline"
UP17A = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17a_new_pool_execution_preflight_offline"
UP17C = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17c_builder_cardinality_reconciliation_offline"
UP17D = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17d_independent_quality_adjudication_v2_preregistration_offline"
ARCH = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_16_architecture_freeze_fresh_heldout_v3_preregistration_offline"
RUN = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_18a_source_acquisition_execution_preregistration_offline"
ROOTS = [
    ("alpha3_17", UP17, "search_plan_v24_dev_alpha3_17_sha256", "10bc7cc1f03b0cdf38b4409f624b10697ffef3939053601cfba2dc4ea74cece6"),
    ("alpha3_17a", UP17A, "search_plan_v24_dev_alpha3_17a_sha256", "a23e549cf9d83714782d4283c823ee94ce569f5f00f820fc2c4e0b9d3ee7248e"),
    ("alpha3_17c", UP17C, "search_plan_v24_dev_alpha3_17c_sha256", "01145d324a9bcf6d3d926afe1e4a1135c8b35d8b4404d473f32cb50e9608703d"),
    ("alpha3_17d", UP17D, "search_plan_v24_dev_alpha3_17d_sha256", "1f96a0f276ba8ab58f4ad0959c1140fab0d0949c03eb75a3e10dd2af3cad42e9"),
]
ARCH_ROOT = "ba82369f45c8a4fcee373fb36011e7bd5817af1e9568765ce0be7801518ff5d1"
SOURCE_ROOT = "755702713972012bc062f7cba43eea95708c9a5e75ca5c93e49ef5396f0c00c0"
BUILDER_ROOT = "8a50314aac4e5f8017109a047905981a91aa91ffb784e1ebde0f92256917ba33"
BUILDER_SCHEMA_ROOT = "5309d3edc9b8a40b64f6fc79e5f7a8e19ac4738808827b33cfe2eb3047db7849"
QUALITY_ROOT = "89009283963c1db3dd00d57917d932b4d0a542dcb27863ad071dc30f8c0cd751"
SOURCE_FILES = ["exact_source_queries.jsonl", "source_execution_policy.json", "source_frame_freeze_policy.json",
                "cross_stratum_duplicate_policy.json", "source_sampling_algorithm.json", "mechanical_source_exclusion_order.json",
                "seen_source_local_registry.json", "construction_fulltext_acquisition_policy.json",
                "construction_fulltext_failure_policy.json"]
STRATA = ["basic_cell_signaling", "immunology", "metabolism", "neuroscience",
          "cancer_biology", "therapy_response_biology"]


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
    path = RUN / name
    if path.exists():
        raise RuntimeError(f"refusing overwrite: {path}")
    path.write_bytes(canonical(value) + b"\n")


def verify() -> tuple[list[dict], dict, dict, dict, dict]:
    for _, directory, marker, expected in ROOTS:
        if all_file_root(directory, marker) != expected or (directory / marker).read_text().strip() != expected:
            raise RuntimeError(f"upstream root mismatch: {directory.name}")
    arch = load(ARCH / "architecture_freeze_manifest.json")
    if arch["architecture_freeze_sha256"] != ARCH_ROOT or (ARCH / "architecture_freeze_sha256").read_text().strip() != ARCH_ROOT:
        raise RuntimeError("architecture freeze mismatch")
    if not all(sha((ROOT / relative).read_bytes()) == digest for relative, digest in arch["components"]):
        raise RuntimeError("architecture component drift")
    if aggregate(UP17A, SOURCE_FILES) != SOURCE_ROOT or (UP17A / "new_pool_source_acquisition_manifest_sha256").read_text().strip() != SOURCE_ROOT:
        raise RuntimeError("source acquisition manifest changed")
    for directory, filename, expected in (
        (UP17C, "proposition_builder_protocol_v2.json", BUILDER_ROOT),
        (UP17C, "proposition_builder_output_schema_v2.json", BUILDER_SCHEMA_ROOT),
    ):
        if sha((directory / filename).read_bytes()) != expected:
            raise RuntimeError(f"V2 builder artifact mismatch: {filename}")
    if (UP17D / "proposition_quality_adjudication_v2_protocol_sha256").read_text().strip() != QUALITY_ROOT:
        raise RuntimeError("quality protocol root mismatch")
    rows = [json.loads(line) for line in (UP17A / "exact_source_queries.jsonl").read_bytes().splitlines()]
    if len(rows) != 6 or [row["stratum_id"] for row in rows] != STRATA:
        raise RuntimeError("SOURCE_QUERY_FREEZE_MISMATCH")
    if any(sha(row["query_utf8"].encode("utf-8")) != row["query_sha256"] for row in rows):
        raise RuntimeError("SOURCE_QUERY_FREEZE_MISMATCH")
    if sha((UP17A / "exact_source_queries.jsonl").read_bytes()) != (UP17A / "exact_source_queries_sha256").read_text().strip():
        raise RuntimeError("SOURCE_QUERY_FREEZE_MISMATCH")
    return (rows, load(UP17A / "source_execution_policy.json"),
            load(UP17A / "construction_fulltext_acquisition_policy.json"),
            load(UP17A / "mechanical_source_exclusion_order.json"),
            load(UP17A / "proposition_builder_visibility_contract.json"))


def main() -> None:
    if RUN.exists():
        raise RuntimeError("alpha3.18A prereg audit already exists; refusing regeneration")
    rows, execution, oa, exclusions, visibility = verify()
    if execution["page_size"] != 50 or execution["frame_cap_per_stratum"] != 200:
        raise RuntimeError("source execution policy drift")
    if load(UP17A / "source_sampling_algorithm.json")["sample_cap_per_stratum"] != 12:
        raise RuntimeError("sampling policy drift")
    # Inspect only frozen policy artifacts; do not infer a new legal or scientific rule.
    has_oa_authority = all(key in oa for key in ("oa_verification_route", "accepted_oa_statuses", "license_decision_rule"))
    has_type_authority = all(key in exclusions for key in ("accepted_publication_types", "excluded_publication_types", "article_type_mapping", "results_section_rule"))
    title_private = oa["source_title_private"]
    title_model_visible = "one frozen title/abstract/body representation" in visibility["allow"]
    prompt_title_visible = "Title: {source_title}" in (UP17A / "proposition_builder_user_prompt_template.txt").read_text()
    references_rule_frozen = "reference_section_policy" in oa
    if has_oa_authority or has_type_authority or references_rule_frozen:
        raise RuntimeError("unexpected policy expansion; re-audit required")
    RUN.mkdir()
    write("root_verification.json", {
        "upstreams": {name: {"expected_sha256": expected, "actual_sha256": all_file_root(directory, marker),
                            "status": "PASS"} for name, directory, marker, expected in ROOTS},
        "architecture_freeze_sha256": ARCH_ROOT, "architecture_component_hashes_match": True,
        "source_acquisition_manifest_sha256": SOURCE_ROOT,
        "builder_protocol_v2_sha256": BUILDER_ROOT,
        "builder_output_schema_v2_sha256": BUILDER_SCHEMA_ROOT,
        "quality_protocol_sha256": QUALITY_ROOT})
    write("source_query_freeze_verification.json", {
        "status": "PASS", "query_count": 6, "query_byte_changes": 0, "query_hash_changes": 0,
        "source_query_file_sha256": sha((UP17A / "exact_source_queries.jsonl").read_bytes()),
        "ordered_strata": STRATA,
        "per_query_sha256": [[row["stratum_id"], row["query_sha256"]] for row in rows],
        "development_derived_term_additions": 0,
        "no_query_reconstruction_or_edit": True})
    write("source_execution_contract.json", {
        "status": "VERIFIED_UPSTREAM_POLICY_NOT_NETWORK_AUTHORIZATION",
        "source_policy_sha256": sha((UP17A / "source_execution_policy.json").read_bytes()),
        "sort": execution["sort"], "page_size": 50, "frame_cap_per_stratum": 200,
        "stratum_order": execution["stratum_order"],
        "timeout_seconds": execution["timeout_seconds"],
        "maximum_attempts_per_request": execution["maximum_attempts_per_request"],
        "backoff_seconds": execution["backoff_seconds"],
        "six_frame_completion_barrier_from_upstream": True,
        "no_network_request_this_stage": True})
    write("sampling_contract_verification.json", {
        "status": "PASS", "sampling_algorithm_sha256": sha((UP17A / "source_sampling_algorithm.json").read_bytes()),
        "sampling_seed_sha256": load(UP17 / "sampling_seed_contract.json")["seed_sha256"],
        "cross_stratum_duplicate_policy_sha256": sha((UP17A / "cross_stratum_duplicate_policy.json").read_bytes()),
        "sample_cap_per_stratum": 12, "dynamic_source_replacement_allowed": False})
    write("construction_oa_eligibility_contract.json", {
        "status": "UNRESOLVED", "failure_code": "CONSTRUCTION_OA_ELIGIBILITY_RULE_UNRESOLVED",
        "upstream_policy_sha256": sha((UP17A / "construction_fulltext_acquisition_policy.json").read_bytes()),
        "upstream_literal": oa["legal_oa_evidence"],
        "pmc_filter_is_final_oa_proof": False,
        "missing_frozen_decisions": ["authoritative NCBI OA verification route and response field",
                                     "accepted versus rejected OA/license/status mapping",
                                     "precise ELIGIBLE/INELIGIBLE/UNRESOLVED mapping and technical failure handling"],
        "new_oa_policy_invented": False, "fulltext_acquisition_authorized": False})
    write("source_type_mechanical_eligibility_contract.json", {
        "status": "UNRESOLVED", "failure_code": "SOURCE_TYPE_ELIGIBILITY_RULE_UNRESOLVED",
        "upstream_policy_sha256": sha((UP17A / "mechanical_source_exclusion_order.json").read_bytes()),
        "upstream_literal": exclusions["classification"],
        "missing_frozen_decisions": ["exact accepted and excluded PubMed publication types",
                                     "PMC article-type mapping", "Results-section detection rule",
                                     "precise no-usable-experimental-result mechanical predicate"],
        "new_source_type_policy_invented": False})
    write("construction_evidence_document_v1_contract.json", {
        "status": "UNRESOLVED", "failure_code": "CONSTRUCTION_EVIDENCE_DOCUMENT_CONTRACT_UNRESOLVED",
        "upstream_fulltext_policy_sha256": sha((UP17A / "construction_fulltext_acquisition_policy.json").read_bytes()),
        "upstream_visibility_policy_sha256": sha((UP17A / "proposition_builder_visibility_contract.json").read_bytes()),
        "title_private_in_acquisition_policy": title_private,
        "title_allowed_in_builder_visibility": title_model_visible,
        "title_present_in_frozen_builder_prompt": prompt_title_visible,
        "reference_section_policy_frozen": references_rule_frozen,
        "missing_frozen_decisions": ["resolve model-visible title versus private-title boundary",
                                     "deterministic bibliography/reference exclusion or retention",
                                     "structure-preserving source-text extraction and stable span-ID generation"],
        "new_document_transformation_invented": False})
    write("reference_section_handling_contract.json", {
        "status": "UNRESOLVED", "reference_section_rule_frozen_upstream": False,
        "reason": "The upstream XML body itertext instruction does not say whether bibliography is included; excluding or retaining it here would be a new policy choice.",
        "citation_identifier_leak_risk_acknowledged": True})
    write("source_metadata_contract.json", {
        "status": "UNRESOLVED", "reason": "Upstream specifies purposes but not an exact PubMed metadata field allowlist or identifier-resolution route; no new fields selected here.",
        "metadata_fetched": 0})
    write("scientific_state_safety_audit.json", {
        "network_calls": 0, "retrieval_calls": 0, "provider_calls": 0, "llm_calls": 0,
        "builder_calls": 0, "quality_calls": 0, "propositions_generated": 0,
        "heldout_cases_selected": 0, "query_compilation_calls": 0,
        "historical_assets_modified": False})
    write("validation.json", {
        "status": "FAILED_CLOSED", "failure_code": "CONSTRUCTION_OA_ELIGIBILITY_RULE_UNRESOLVED",
        "additional_unresolved": ["SOURCE_TYPE_ELIGIBILITY_RULE_UNRESOLVED",
                                  "CONSTRUCTION_EVIDENCE_DOCUMENT_CONTRACT_UNRESOLVED",
                                  "REFERENCE_SECTION_HANDLING_UNRESOLVED", "SOURCE_METADATA_FIELDS_UNRESOLVED"],
        "six_source_queries_verified": True, "source_query_byte_changes": 0,
        "source_frame_cap_per_stratum": 200, "source_page_size": 50,
        "six_frame_completion_barrier_defined_upstream": True,
        "sample_cap_per_stratum": 12, "dynamic_source_replacement_allowed": False,
        "pmc_filter_treated_as_final_oa_proof": False,
        "construction_oa_rule_resolved": False,
        "source_type_mechanical_rule_resolved": False,
        "construction_evidence_document_contract_frozen": False,
        "evidence_span_anchor_contract_frozen": False,
        "builder_protocol_v2_bound": True,
        "builder_output_schema_v2_bound": True,
        "actual_builder_call_count_not_yet_known": True,
        "maximum_builder_calls": 72,
        "builder_calls": 0, "quality_calls": 0, "propositions_generated": 0,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0, "retrieval_calls": 0})
    write("summary.json", {
        "status": "failed", "reason": "CONSTRUCTION_OA_ELIGIBILITY_RULE_UNRESOLVED",
        "additional_unresolved_count": 4,
        "alpha3_18a_source_acquisition_execution_manifest_sha256": None,
        "next_stage_recommendation": "RESOLVE_SOURCE_OA_TYPE_AND_CONSTRUCTION_DOCUMENT_CONTRACTS_OFFLINE",
        "network_execution_authorized": False,
        "historical_assets_modified": False})
    run_root = all_file_root(RUN, "search_plan_v24_dev_alpha3_18a_prereg_sha256")
    (RUN / "search_plan_v24_dev_alpha3_18a_prereg_sha256").write_text(run_root + "\n", encoding="utf-8")
    assert all_file_root(RUN, "search_plan_v24_dev_alpha3_18a_prereg_sha256") == run_root
    print(json.dumps({"status": "failed_closed", "failure_code": "CONSTRUCTION_OA_ELIGIBILITY_RULE_UNRESOLVED",
                      "run_root": run_root, "execution_manifest_sha256": None,
                      "network_calls": 0, "provider_calls": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
