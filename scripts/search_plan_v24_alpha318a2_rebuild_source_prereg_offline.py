#!/usr/bin/env python3
"""Audit alpha3.18A.2 bindings offline; fail closed on unfrozen runtime policy."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
OLD = RUNS / "20260927_search_plan_v24_dev_alpha3_18a_source_acquisition_execution_preregistration_offline"
AMEND = RUNS / "20260927_search_plan_v24_dev_alpha3_18a1_source_contract_resolution_offline"
SOURCE = RUNS / "20260927_search_plan_v24_dev_alpha3_17a_new_pool_execution_preflight_offline"
BUILDER = RUNS / "20260927_search_plan_v24_dev_alpha3_17c_builder_cardinality_reconciliation_offline"
QUALITY = RUNS / "20260927_search_plan_v24_dev_alpha3_17d_independent_quality_adjudication_v2_preregistration_offline"
ARCH = RUNS / "20260927_search_plan_v24_dev_alpha3_16_architecture_freeze_fresh_heldout_v3_preregistration_offline"
OUT = RUNS / "20260927_search_plan_v24_dev_alpha3_18a2_rebuilt_source_acquisition_preregistration_offline"

EXPECTED = {
    "failed_prereg": (OLD, "search_plan_v24_dev_alpha3_18a_prereg_sha256", "ea3a7f9ac0ec58a5babe8acacf19290e5aa699e09849e39370fd5d9b96d08113"),
    "amendment": (AMEND, "search_plan_v24_dev_alpha3_18a1_sha256", "836fb4df24850b32720cb130c65329cac2a828ef257184683cd5a3e391a4e8fe"),
    "builder": (BUILDER, "search_plan_v24_dev_alpha3_17c_sha256", "01145d324a9bcf6d3d926afe1e4a1135c8b35d8b4404d473f32cb50e9608703d"),
    "quality": (QUALITY, "search_plan_v24_dev_alpha3_17d_sha256", "1f96a0f276ba8ab58f4ad0959c1140fab0d0949c03eb75a3e10dd2af3cad42e9"),
}
AMEND_COMPONENTS = {
    "construction_oa_eligibility_v1_sha256": "c6104c806d46e324b604adaedccd47caf18cfe82f3a48b361bb425e121312c7b",
    "source_type_mechanical_eligibility_v1_sha256": "850ed1883860d3e83c5c071bb376112f157c6c3a0f7d9d9b78807cc26c3c714f",
    "construction_evidence_document_v1_sha256": "be3b6ca63c361a63430fffa3b2c99b6e57ec401eb287408715e9980dde030d70",
    "evidence_span_anchor_v1_sha256": "e29dfcbb6bd0d068d57d57799c29e590cc67d818cdfb1ebb26bebaec29de25f7",
}
SOURCE_FILES = ["exact_source_queries.jsonl", "source_execution_policy.json", "source_frame_freeze_policy.json",
                "cross_stratum_duplicate_policy.json", "source_sampling_algorithm.json", "mechanical_source_exclusion_order.json",
                "seen_source_local_registry.json", "construction_fulltext_acquisition_policy.json",
                "construction_fulltext_failure_policy.json"]
STRATA = ["basic_cell_signaling", "immunology", "metabolism", "neuroscience",
          "cancer_biology", "therapy_response_biology"]
BLOCKER = "CORRECTION_RETRACTION_REFERENCE_DECISION_UNFROZEN"


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def aggregate(directory: Path, names: list[str]) -> str:
    return sha(canonical([[name, sha((directory / name).read_bytes())] for name in sorted(names)]))


def all_file_root(directory: Path, marker: str) -> str:
    return aggregate(directory, [p.name for p in directory.iterdir() if p.is_file() and p.name != marker])


def load(directory: Path, name: str) -> Any:
    return json.loads((directory / name).read_text(encoding="utf-8"))


def ref(directory: Path, name: str) -> dict[str, str]:
    path = directory / name
    return {"path": str(path.relative_to(ROOT)), "sha256": sha(path.read_bytes())}


def verify() -> list[dict[str, Any]]:
    for name, (directory, marker, expected) in EXPECTED.items():
        if all_file_root(directory, marker) != expected or (directory / marker).read_text().strip() != expected:
            raise RuntimeError(f"frozen root mismatch: {name}")
    if load(OLD, "validation.json")["status"] != "FAILED_CLOSED":
        raise RuntimeError("historical failed preregistration was altered")
    for marker, expected in AMEND_COMPONENTS.items():
        if (AMEND / marker).read_text().strip() != expected:
            raise RuntimeError(f"amendment component mismatch: {marker}")
    if load(AMEND, "validation.json")["status"] != "PASS":
        raise RuntimeError("alpha3.18A.1 amendment is not frozen PASS")
    if aggregate(SOURCE, SOURCE_FILES) != "755702713972012bc062f7cba43eea95708c9a5e75ca5c93e49ef5396f0c00c0":
        raise RuntimeError("frozen source-acquisition manifest changed")
    query_bytes = (SOURCE / "exact_source_queries.jsonl").read_bytes()
    if sha(query_bytes) != "a583726dd65ef34c6b79493d6bafac8405c6c2e511e114cdc0c9f8339cc8c565":
        raise RuntimeError("SOURCE_QUERY_FREEZE_MISMATCH")
    rows = [json.loads(line) for line in query_bytes.splitlines()]
    if len(rows) != 6 or [r["stratum_id"] for r in rows] != STRATA:
        raise RuntimeError("SOURCE_QUERY_FREEZE_MISMATCH")
    if any(r["stratum_order"] != i or sha(r["query_utf8"].encode("utf-8")) != r["query_sha256"] for i, r in enumerate(rows)):
        raise RuntimeError("SOURCE_QUERY_FREEZE_MISMATCH")
    if sha((BUILDER / "proposition_builder_protocol_v2.json").read_bytes()) != "8a50314aac4e5f8017109a047905981a91aa91ffb784e1ebde0f92256917ba33":
        raise RuntimeError("builder protocol changed")
    if sha((BUILDER / "proposition_builder_output_schema_v2.json").read_bytes()) != "5309d3edc9b8a40b64f6fc79e5f7a8e19ac4738808827b33cfe2eb3047db7849":
        raise RuntimeError("builder output schema changed")
    if (QUALITY / "proposition_quality_adjudication_v2_protocol_sha256").read_text().strip() != "89009283963c1db3dd00d57917d932b4d0a542dcb27863ad071dc30f8c0cd751":
        raise RuntimeError("quality protocol changed")
    arch = load(ARCH, "architecture_freeze_manifest.json")
    if arch["architecture_freeze_sha256"] != "ba82369f45c8a4fcee373fb36011e7bd5817af1e9568765ce0be7801518ff5d1":
        raise RuntimeError("architecture freeze changed")
    if any(sha((ROOT / relative).read_bytes()) != expected for relative, expected in arch["components"]):
        raise RuntimeError("architecture component changed")
    return rows


def write(name: str, value: Any) -> None:
    path = OUT / name
    if path.exists():
        raise RuntimeError(f"refusing overwrite: {path}")
    path.write_bytes(canonical(value) + b"\n")


def text_file(name: str, value: str) -> None:
    path = OUT / name
    if path.exists():
        raise RuntimeError(f"refusing overwrite: {path}")
    path.write_text(value + "\n", encoding="utf-8")


def main() -> None:
    if OUT.exists():
        raise RuntimeError("alpha3.18A.2 output already exists; refusing overwrite")
    rows = verify()
    execution = load(SOURCE, "source_execution_policy.json")
    metadata = load(AMEND, "source_metadata_contract_v2.json")
    if "correction_retraction_refs" not in [f["name"] for f in metadata["fields"]]:
        raise RuntimeError("metadata field contract changed")
    if "correction_retraction_refs" in load(AMEND, "source_type_three_state_decision_table.json"):
        raise RuntimeError("new correction/retraction rule detected; re-audit")
    OUT.mkdir()
    write("root_verification.json", {"status": "PASS", "roots": {name: expected for name, (_, _, expected) in EXPECTED.items()},
                                     "architecture_freeze_sha256": "ba82369f45c8a4fcee373fb36011e7bd5817af1e9568765ce0be7801518ff5d1",
                                     "source_manifest_sha256": "755702713972012bc062f7cba43eea95708c9a5e75ca5c93e49ef5396f0c00c0",
                                     "builder_protocol_v2_sha256": "8a50314aac4e5f8017109a047905981a91aa91ffb784e1ebde0f92256917ba33",
                                     "builder_output_schema_v2_sha256": "5309d3edc9b8a40b64f6fc79e5f7a8e19ac4738808827b33cfe2eb3047db7849",
                                     "quality_protocol_v2_sha256": "89009283963c1db3dd00d57917d932b4d0a542dcb27863ad071dc30f8c0cd751"})
    write("failed_prereg_preservation.json", {"status": "PASS", "original_alpha3_18a_prereg_status": "failed",
                                                "reason": "unresolved OA/type/document contracts", "source": ref(OLD, "validation.json"),
                                                "original_root_sha256": EXPECTED["failed_prereg"][2], "historical_mutation": False})
    write("alpha3_18a1_contract_verification.json", {"status": "PASS", "prospective_amendment_before_network_execution": True,
                                                     "root_sha256": EXPECTED["amendment"][2], "components": AMEND_COMPONENTS,
                                                     "current_external_facts_network_verified_here": False})
    write("source_query_verification.json", {"status": "PASS", "query_count": 6, "query_changes": 0,
                                            "query_file": ref(SOURCE, "exact_source_queries.jsonl"),
                                            "ordered_queries": [{"stratum_id": r["stratum_id"], "query_sha256": r["query_sha256"]} for r in rows],
                                            "post_sampling_OA_and_type_gates_not_discovery_query_edits": True})
    write("network_scope_contract.json", {"future_allowed_hosts": ["eutils.ncbi.nlm.nih.gov", "www.ncbi.nlm.nih.gov"],
                                           "future_allowed_services": ["NCBI PubMed E-Utilities", "NCBI PMC E-Utilities"],
                                           "all_other_services_forbidden": True, "network_calls_now": 0,
                                           "deprecated_PMC_OA_Web_Service_allowed": False})
    write("source_frame_execution_contract.json", {"policy": ref(SOURCE, "source_execution_policy.json"),
                                                   "queries": ref(SOURCE, "exact_source_queries.jsonl"),
                                                   "sort": execution["sort"], "page_size": 50, "cap_per_stratum": 200,
                                                   "stratum_order": STRATA, "retry_policy": {k: execution[k] for k in
                                                   ("maximum_attempts_per_request", "timeout_seconds", "backoff_seconds", "http_status_retryable", "nonretryable_response")},
                                                   "raw_requests_responses_and_page_order_preserved": True})
    write("source_frame_completion_barrier.json", {"source": ref(SOURCE, "source_frame_freeze_policy.json"),
                                                   "all_six_frames_freeze_before_sampling": True,
                                                   "completion": "natural exhaustion or 200 records per stratum",
                                                   "terminal_failure": "SOURCE_FRAME_ACQUISITION_FAILED_CLOSED", "partial_sampling": False})
    write("cross_stratum_dedup_contract.json", {"source": ref(SOURCE, "cross_stratum_duplicate_policy.json"),
                                               "canonical_identity": "normalized decimal PMID", "owner": "earliest frozen stratum",
                                               "all_memberships_preserved": True, "freeze_before_sampling": True})
    write("sampling_execution_contract.json", {"source": ref(SOURCE, "source_sampling_algorithm.json"),
                                               "seed_sha256": load(SOURCE, "source_sampling_algorithm.json")["seed_sha256"],
                                               "key_preimage": "seed_sha256:stratum_id:canonical PMID", "sample_cap_per_stratum": 12,
                                               "no_refill_or_replacement_after_any_exclusion": True})
    write("sampled_metadata_execution_contract.json", {"source": ref(AMEND, "source_metadata_contract_v2.json"),
                                                       "sampled_only": True, "frozen_fields": metadata["fields"],
                                                       "correction_retraction_refs_extracted": True,
                                                       "correction_retraction_refs_decision_rule_frozen": False,
                                                       "failure_code": BLOCKER})
    write("seen_source_execution_contract.json", {"source": ref(SOURCE, "seen_source_local_registry.json"),
                                                  "only_states": ["MATCHED_FROZEN_SEEN_SOURCE", "NO_FROZEN_LOCAL_MATCH"],
                                                  "registry_expansion": False, "global_unseen_claim": False})
    write("publication_type_execution_contract.json", {"acceptance": ref(AMEND, "publication_type_acceptance_set.json"),
                                                       "exclusion": ref(AMEND, "publication_type_exclusion_set.json"),
                                                       "unknown_type": "SOURCE_TYPE_UNRESOLVED", "yield_based_changes": False})
    write("oa_subset_execution_contract.json", {"source": ref(AMEND, "oa_subset_verification_contract.json"),
                                                "PMC_OA_Web_Service_used": False, "pmc_filter_final_proof": False,
                                                "raw_request_and_response_frozen": True})
    write("license_execution_contract.json", {"extraction": ref(AMEND, "license_extraction_contract.json"),
                                              "whitelist": ref(AMEND, "construction_license_policy.json"),
                                              "accepted_classes": ["CC0", "CC_BY", "CC_BY_SA"], "manual_override": False})
    write("construction_oa_execution_contract.json", {"decision": ref(AMEND, "construction_oa_eligibility_v1_contract.json"),
                                                      "three_states": ref(AMEND, "oa_three_state_decision_table.json"),
                                                      "provisional_JATS_before_license_decision": True,
                                                      "only_CONSTRUCTION_OA_ELIGIBLE_proceeds": True})
    write("pmc_jats_acquisition_contract.json", {"source": ref(SOURCE, "construction_fulltext_acquisition_policy.json"),
                                                 "failure": ref(SOURCE, "construction_fulltext_failure_policy.json"),
                                                 "route": "NCBI PMC EFetch XML only", "raw_JATS_preserved": True,
                                                 "publisher_HTML_PDF_fallback": False, "failed_source_replacement": False})
    write("jats_source_type_execution_contract.json", {"decision": ref(AMEND, "source_type_mechanical_eligibility_v1.json"),
                                                        "decision_table": ref(AMEND, "source_type_three_state_decision_table.json"),
                                                        "methods": ref(AMEND, "methods_heading_whitelist.json"),
                                                        "results": ref(AMEND, "results_heading_whitelist.json"),
                                                        "only_SOURCE_TYPE_ELIGIBLE_proceeds": True,
                                                        "correction_retraction_ref_treatment": "UNFROZEN", "failure_code": BLOCKER})
    write("construction_document_execution_contract.json", {"decision": ref(AMEND, "construction_evidence_document_v1_contract.json"),
                                                           "canonicalization": ref(AMEND, "construction_document_canonicalization_contract.json"),
                                                           "front_matter": ref(AMEND, "construction_document_front_matter_policy.json"),
                                                           "abstract": ref(AMEND, "construction_document_abstract_policy.json"),
                                                           "body": ref(AMEND, "construction_document_body_policy.json"),
                                                           "references": ref(AMEND, "construction_document_reference_policy.json"),
                                                           "other_sections": ref(AMEND, "construction_document_other_section_policy.json"),
                                                           "article_title_visible_to_builder": False, "bibliography_visible_to_builder": False})
    write("evidence_span_execution_contract.json", {"anchor": ref(AMEND, "evidence_span_anchor_v1_contract.json"),
                                                    "granularity": ref(AMEND, "evidence_span_granularity_contract.json"),
                                                    "body_only_candidate_grounding": True, "anchor_integrity_required": True})
    write("construction_source_manifest_contract.json", {"source": ref(SOURCE, "alpha3_18_phase_barrier_contract.json"),
                                                        "one_included_source_per_fully_passed_sample": True,
                                                        "full_provenance_required": True,
                                                        "cannot_issue_until_runtime_blocker_resolved": BLOCKER})
    write("private_anchor_vault_execution_contract.json", {"source": ref(SOURCE, "anchor_vault_filesystem_contract.json"),
                                                           "source_identity_mapping_private": True,
                                                           "source_record_fields": ["opaque_source_token", "PMID", "PMCID", "DOI", "stratum_provenance", "source_frame_provenance", "metadata_sha256", "JATS_sha256", "construction_document_sha256"],
                                                           "access": "ANCHOR_RESTRICTED", "public_identity_leakage": False})
    write("builder_request_generation_contract.json", {"builder_protocol": ref(BUILDER, "proposition_builder_protocol_v2.json"),
                                                      "output_schema": ref(BUILDER, "proposition_builder_output_schema_v2.json"),
                                                      "request": ref(SOURCE, "proposition_builder_request_contract.json"),
                                                      "user_template": ref(AMEND, "proposition_builder_v2_1_user_prompt_template.txt"),
                                                      "one_request_per_final_source": True, "builder_calls_now": 0})
    write("builder_visibility_execution_contract.json", {"source": ref(AMEND, "builder_request_visibility_amendment.json"),
                                                        "article_title_visible": False, "bibliography_visible": False,
                                                        "private_identifiers_visible": False, "development_or_search_state_visible": False,
                                                        "audit_before_manifest_inclusion": True})
    write("alpha3_18a_completion_barrier.json", {"requires": ["six frozen source frames", "sampling results", "all mechanical eligibility records",
                                                               "construction JATS artifacts", "construction evidence documents", "span anchors",
                                                               "construction_source_manifest", "private source anchor manifest", "builder request manifest",
                                                               "actual builder call budget"], "builder_execution": False,
                                                   "preregistration_complete_now": False, "failure_code": BLOCKER})
    write("source_phase_metrics_plan.json", {"descriptive_only": ["per-stratum frame size", "deduplicated frame size", "sampled count",
                                                            "seen-source exclusions", "Publication Type states", "OA/license states",
                                                            "JATS acquisition success/failure", "source-type structural states",
                                                            "construction-document states", "final construction-source count", "actual future builder-call count"],
                                            "search_plan_relevance_metrics": False, "computed_now": False})
    write("alpha3_18a2_source_acquisition_execution_manifest.json", {
        "status": "NON_EXECUTABLE_FAIL_CLOSED", "failure_code": "ALPHA3_18A_EXECUTION_MANIFEST_INCOMPLETE",
        "unresolved_runtime_policy": BLOCKER,
        "evidence": {"metadata": ref(AMEND, "source_metadata_contract_v2.json"),
                     "type_decision": ref(AMEND, "source_type_three_state_decision_table.json"),
                     "type_implementation": ref(ROOT / "scripts", "search_plan_v24_alpha318a1_source_contracts.py")},
        "reason": "CommentsCorrections RefType is extracted but no frozen decision maps source-article correction/retraction/expression-of-concern references to inclusion states. Publication Type and JATS article-type exclusions do not cover every referenced source-article state.",
        "network_execution_authorized": False, "builder_execution_authorized": False,
        "contract_files": sorted(p.name for p in OUT.iterdir() if p.name.endswith("_contract.json")),
    })
    write("scientific_state_safety_audit.json", {"historical_assets_modified": False, "source_queries_modified": False,
                                                 "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
                                                 "retrieval_calls": 0, "builder_calls": 0, "quality_calls": 0,
                                                 "propositions_generated": 0, "scientific_metrics_computed": False})
    write("validation.json", {"status": "FAILED_CLOSED", "failure_code": "ALPHA3_18A_EXECUTION_MANIFEST_INCOMPLETE",
                              "unresolved_runtime_policy": BLOCKER, "historical_failed_prereg_preserved": True,
                              "alpha3_18a1_contracts_verified": True, "six_source_queries_verified": True,
                              "source_query_changes": 0, "network_scope_ncbi_only": True,
                              "six_frame_completion_barrier": True, "cross_stratum_dedup_frozen": True,
                              "sampling_algorithm_frozen": True, "dynamic_source_replacement_allowed": False,
                              "seen_source_registry_frozen": True, "publication_type_rule_bound": True,
                              "oa_subset_verification_bound": True, "construction_license_policy_bound": True,
                              "construction_oa_rule_bound": True, "pmc_oa_web_service_used": False,
                              "pmc_filter_treated_as_final_oa_proof": False, "jats_acquisition_bound": True,
                              "source_type_mechanical_rule_bound": True, "construction_document_contract_bound": True,
                              "evidence_span_contract_bound": True, "article_title_visible_to_builder": False,
                              "bibliography_visible_to_builder": False, "builder_protocol_v2_bound": True,
                              "builder_output_schema_v2_bound": True, "builder_request_manifest_before_builder_calls": True,
                              "future_builder_call_count_derived_only_after_source_phase": True,
                              "builder_calls": 0, "quality_calls": 0, "provider_calls": 0, "llm_calls": 0,
                              "network_calls": 0, "retrieval_calls": 0})
    write("summary.json", {"status": "failed", "failure_code": "ALPHA3_18A_EXECUTION_MANIFEST_INCOMPLETE",
                           "specific_blocker": BLOCKER, "executable_manifest_sha256": None,
                           "next_stage_recommendation": "RESOLVE_CORRECTION_RETRACTION_REFERENCE_DECISION_OFFLINE",
                           "future_network_authorization_ready": False, "historical_assets_modified": False})
    text_file("alpha3_18a2_source_acquisition_execution_manifest_sha256", "null")
    root = all_file_root(OUT, "search_plan_v24_dev_alpha3_18a2_prereg_sha256")
    text_file("search_plan_v24_dev_alpha3_18a2_prereg_sha256", root)
    assert all_file_root(OUT, "search_plan_v24_dev_alpha3_18a2_prereg_sha256") == root
    print(json.dumps({"status": "failed_closed", "failure_code": "ALPHA3_18A_EXECUTION_MANIFEST_INCOMPLETE",
                      "specific_blocker": BLOCKER, "run_root": root, "network_calls": 0,
                      "provider_calls": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
