#!/usr/bin/env python3
"""Freeze the prospective alpha3.19 master plan without network or inference."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
OUT = RUNS / "20261001_search_plan_v24_dev_alpha3_19_fresh_heldout_attempt2_master_preregistration_offline"
C2 = RUNS / "20261001_search_plan_v24_dev_alpha3_18c2_quality_failure_interpretation_and_attempt_closure_offline"
A18 = RUNS / "20260928_search_plan_v24_dev_alpha3_18a_v2_ncbi_only_source_acquisition"
A6 = RUNS / "20261001_search_plan_v24_dev_alpha3_18a6_license_extraction_v2_offline_replay"
B = RUNS / "20261001_search_plan_v24_dev_alpha3_18b_builder_execution"
B2 = RUNS / "20261001_search_plan_v24_dev_alpha3_18b2_builder_v3_execution"
Q2 = RUNS / "20260927_search_plan_v24_dev_alpha3_17d_independent_quality_adjudication_v2_preregistration_offline"
A4 = RUNS / "20260928_search_plan_v24_dev_alpha3_18a4_pubmed_query_runtime_validation_amendment_offline"
A5 = RUNS / "20261001_search_plan_v24_dev_alpha3_18a5_primary_citation_identity_binding_offline"
A1 = RUNS / "20260927_search_plan_v24_dev_alpha3_18a1_source_contract_resolution_offline"
A3 = RUNS / "20260927_search_plan_v24_dev_alpha3_18a3_correction_reference_resolution_final_prereg_offline"
B1 = RUNS / "20261001_search_plan_v24_dev_alpha3_18b1_grounding_contract_consistency_audit_offline"
STRATA = RUNS / "20260927_search_plan_v24_dev_alpha3_17_new_blinded_proposition_pool_preregistration_offline"
LEAKAGE = RUNS / "20260927_search_plan_v24_dev_alpha3_17a_new_pool_execution_preflight_offline"
EXPECTED_C2 = "fa2f650b005458e1c65c3cd7f872cd0e353c4ad56b364e3b42ca1df50a2039c6"
NEXT = "PREREGISTER_ALPHA3_19A_NEW_SOURCE_ACQUISITION"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(path: Path) -> str:
    return sha(path.read_bytes())


def ref(path: Path) -> dict:
    return {"path": str(path.relative_to(ROOT)), "sha256": digest(path)}


def load(path: Path):
    return json.loads(path.read_bytes())


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_bytes().splitlines() if line]


def require(condition: bool, reason: str):
    if not condition:
        raise RuntimeError(reason)


def write(name: str, value):
    (OUT / name).write_bytes(canonical(value) + b"\n")


def writelines(name: str, values: list[dict]):
    (OUT / name).write_bytes(b"".join(canonical(v) + b"\n" for v in values))


def marker(name: str, value: str):
    (OUT / name).write_text(value + "\n")


def root_hash(exclude: set[str]) -> str:
    return sha(canonical([[p.name, digest(p)] for p in sorted(OUT.iterdir())
                          if p.is_file() and p.name not in exclude]))


def main():
    require(not OUT.exists(), "ALPHA3_19_OUTPUT_EXISTS")
    from scripts.search_plan_v24_alpha318c_preregister_quality_offline import root
    require(root(C2, "search_plan_v24_dev_alpha3_18c2_sha256") == EXPECTED_C2,
            "ALPHA3_18_CLOSURE_ROOT_MISMATCH")
    require((C2 / "search_plan_v24_dev_alpha3_18c2_sha256").read_text().strip() == EXPECTED_C2,
            "ALPHA3_18_CLOSURE_MARKER_MISMATCH")
    closure = load(C2 / "summary.json")
    require(closure["attempt_terminal_state"] == "TERMINATED_INCOMPLETE_AT_QUALITY_EXECUTION"
            and closure["eligible_proposition_pool_state"] == "NOT_DERIVED",
            "ALPHA3_18_NOT_CLOSED")

    frame_path = A18 / "new_pool_source_sampling_frame.jsonl"
    sampled_path = A18 / "deterministic_source_sampling_results.jsonl"
    construction_path = A6 / "private_anchor_vault_source_manifest_v4.jsonl"
    frame = rows(frame_path)
    sampled = rows(sampled_path)
    construction = rows(construction_path)
    frame_ids = {r["pmid"] for r in frame}
    sampled_ids = {r["pmid"] for r in sampled}
    require(len(frame) == len(frame_ids) == 1041 and len(sampled) == len(sampled_ids) == 72,
            "HISTORICAL_SOURCE_COUNTS_MISMATCH")
    require(sampled_ids <= frame_ids and len(construction) == 28,
            "HISTORICAL_SOURCE_SUBSET_MISMATCH")
    construction_ids = {str(r["pmid"]) for r in construction}
    require(construction_ids <= frame_ids and len(construction_ids) == 28,
            "HISTORICAL_CONSTRUCTION_SUBSET_MISMATCH")
    source_registry = [{"pmid": pmid, "identity_sha256": sha(pmid.encode()),
                        "seen_development_history": True,
                        "sampled": pmid in sampled_ids,
                        "construction_source": pmid in construction_ids}
                       for pmid in sorted(frame_ids, key=int)]

    v2_path = B / "builder_candidate_identity_manifest.jsonl"
    v3_path = B2 / "builder_v3_candidate_identity_manifest.jsonl"
    candidate_rows = rows(v2_path) + rows(v3_path)
    require(len(rows(v2_path)) == 70 and len(rows(v3_path)) == 40,
            "HISTORICAL_BUILDER_CANDIDATE_COUNTS_MISMATCH")
    candidate_registry = [{"candidate_id": r["candidate_id"],
                           "candidate_payload_sha256": r["candidate_payload_sha256"],
                           "generation": generation, "source_token": r["source_token"],
                           "seen_development_history": True}
                          for generation, source in (("BUILDER_V2", rows(v2_path)),
                                                     ("BUILDER_V3", rows(v3_path)))
                          for r in source]
    candidate_registry.sort(key=lambda x: (x["generation"], x["candidate_id"]))
    group_path = B2 / "proposition_quality_v2_request_manifest_v3.jsonl"
    groups = rows(group_path)
    require(len(groups) == 3 and sum(len(g["candidate_ids"]) for g in groups) == 5,
            "HISTORICAL_QUALITY_GROUP_COUNT_MISMATCH")
    group_registry = [{"source_group_id": g["source_group_id"],
                       "candidate_ids": sorted(g["candidate_ids"]),
                       "request_sha256": g["request_sha256"],
                       "seen_development_history": True}
                      for g in groups]
    failed_quality_raw = RUNS / "20261001_search_plan_v24_dev_alpha3_18c_quality_execution/raw_provider_responses/01.json"
    require(digest(failed_quality_raw) ==
            "4cec76b7e4681288b8e7261f3a2ab5155015fdf87097ded3849faf9eafb5efc7",
            "HISTORICAL_FAILED_QUALITY_RESPONSE_MISMATCH")

    old_requests = rows(A18 / "source_query_request_manifest.jsonl")
    old_queries = [r for r in old_requests if r["page_retstart"] == 0]
    strata = load(STRATA / "generic_source_strata.json")
    if isinstance(strata, dict):
        strata = strata["ordered_strata"]
    require(len(old_queries) == len(strata) == 6 and
            [r["stratum_id"] for r in old_queries] == strata,
            "SOURCE_STRATA_MISMATCH")
    source_queries = []
    delta_rows = []
    old_date = '"2018/01/01"[Date - Publication] : "2023/12/31"[Date - Publication]'
    new_date = '"2024/01/01"[Date - Publication] : "2025/12/31"[Date - Publication]'
    for r in old_queries:
        old = r["parameters"]["term"]
        require(old.count(old_date) == 1 and '"pubmed pmc"[sb]' in old,
                "SOURCE_QUERY_TEMPLATE_UNEXPECTED")
        new = old.replace(old_date, new_date)
        require(new.replace(new_date, old_date) == old,
                "ALPHA3_19_SOURCE_QUERY_SCIENTIFIC_DRIFT")
        source_queries.append({"stratum_id": r["stratum_id"], "term": new,
                               "query_sha256": sha(new.encode()),
                               "sort": "relevance", "page_size": 50,
                               "max_frame": 200,
                               "source_template": ref(A18 / "source_query_request_manifest.jsonl")})
        delta_rows.append({"stratum_id": r["stratum_id"],
                           "alpha3_18_v2_query_sha256": r["query_sha256"],
                           "alpha3_19_query_sha256": sha(new.encode()),
                           "allowed_changes": ["publication_date_window", "attempt_provenance"],
                           "scientific_search_terms_changed": False,
                           "round_trip_date_only_verified": True})

    q2_path = Q2 / "proposition_quality_adjudication_v2_schema.json"
    q2 = load(q2_path)
    model_schema = copy.deepcopy(q2["schema"])
    for key in ("schema_version", "source_group_id"):
        model_schema["properties"].pop(key)
        model_schema["required"].remove(key)
    item = model_schema["properties"]["judgments"]["items"]
    item["properties"].pop("schema_version")
    item["required"].remove("schema_version")
    criterion_names = item["properties"]["criteria"]["required"]
    require(len(criterion_names) == 10 and set(model_schema["required"]) == {"judgments"}
            and set(item["required"]) == {"candidate_id", "criteria", "evidence_support_reference"},
            "QUALITY_V3_OWNERSHIP_PROJECTION_INVALID")
    require(all(item["properties"]["criteria"]["properties"][c]["enum"] ==
                ["PASS", "FAIL", "UNRESOLVED"] for c in criterion_names),
            "QUALITY_RUBRIC_DRIFT")

    policy_paths = {
        "pubmed_esearch_validator_v2": A4 / "pubmed_esearch_response_validity_v2.json",
        "primary_citation_identity_v1": A5 / "pubmed_primary_citation_identity_binding_v1.json",
        "correction_reference_eligibility_v1": A3 / "correction_reference_eligibility_v1.json",
        "construction_oa_eligibility_v2": A6 / "construction_oa_eligibility_v2.json",
        "construction_license_extraction_v2": A6 / "construction_license_extraction_v2.json",
        "source_type_v1": A1 / "source_type_mechanical_eligibility_v1.json",
        "construction_document_v1": A1 / "construction_evidence_document_v1_contract.json",
        "builder_grounding_v3": B1 / "builder_grounding_contract_v3.json",
        "leakage_audit": LEAKAGE / "leakage_audit_implementation_contract.json",
        "quality_scientific_v2": Q2 / "quality_criteria_contract.json",
        "quality_schema_v2": q2_path,
    }
    bindings = {name: ref(path) for name, path in policy_paths.items()}
    seed_input = "SearchPlanV24DevAlpha3_19|FreshHeldoutAttempt2|source-sampling-v1"
    seed = sha(seed_input.encode())

    OUT.mkdir()
    write("alpha3_18_closure_verification.json", {
        "closure_root_sha256": EXPECTED_C2, "closure_root_verified": True,
        "closure_summary": ref(C2 / "summary.json"),
        "terminal_state": closure["attempt_terminal_state"], "preserved": True,
        "builder_inference_events": 56, "quality_inference_events": 1})
    write("alpha3_19_attempt_identity.json", {
        "attempt": "alpha3.19", "classification": "NEW_PROSPECTIVE_PRIMARY_FRESH_HELDOUT_ATTEMPT",
        "parent_history": "alpha3.18 historical incomplete development attempt",
        "not_continuation_or_repair": True, "builder_inferences": 0,
        "quality_inferences": 0, "model_calls_authorized_now": 0})
    writelines("alpha3_18_seen_source_registry.jsonl", source_registry)
    writelines("alpha3_18_seen_candidate_registry.jsonl", candidate_registry)
    writelines("alpha3_18_seen_quality_group_registry.jsonl", group_registry)
    write("historical_contamination_boundary.json", {
        "state": "SEEN_DEVELOPMENT_HISTORY", "source_count": 1041,
        "sampled_source_count": 72, "construction_source_count": 28,
        "builder_v2_candidate_rows": 70, "builder_v3_candidate_rows": 40,
        "quality_input_candidate_count": 5, "quality_group_count": 3,
        "failed_group_1_quality_response_seen": True,
        "failed_group_1_quality_response": ref(failed_quality_raw),
        "derived_scientific_content_primary_reuse_allowed": False,
        "candidate_scientific_text_in_registries": False,
        "alpha3_18_scientific_assets_reused": False,
        "registries": {k: ref(OUT / k) for k in (
            "alpha3_18_seen_source_registry.jsonl", "alpha3_18_seen_candidate_registry.jsonl",
            "alpha3_18_seen_quality_group_registry.jsonl")}})
    write("engineering_fix_reuse_matrix.json", {
        "classification": "ENGINEERING_INFRASTRUCTURE_ONLY",
        "reusable": ["PubMed ESearch V2 response validation", "pubmed pmc subset syntax",
                     "primary citation identity parser", "correction reference parser",
                     "PMC OA and JATS license parser", "license URI normalization",
                     "source type parser", "construction document canonicalization",
                     "EvidenceSpanAnchor implementation", "Builder BODY-only interface",
                     "deterministic candidate IDs", "exact duplicate control",
                     "grounding and leakage implementation", "Quality ID-set and enum validation",
                     "controller-owned response metadata", "DeepSeek provider adapter"],
        "scientific_sources_candidates_labels_reusable": False, "bindings": bindings})
    write("scientific_policy_nonadaptation_audit.json", {
        "alpha3_18_yield_used_for_tuning": False,
        "builder_candidates_per_source": [0, 3], "body_grounding_required": True,
        "leakage_ngram_tokens": 8,
        "jaccard_threshold": 0.8,
        "jaccard_threshold_authority": bindings["leakage_audit"],
        "jaccard_threshold_changed": False,
        "quality_criteria_count": 10, "quality_all_pass_required": True,
        "one_source_one_final_proposition": True,
        "quality_rubric_changed": False})
    write("alpha3_19_source_cohort_contract.json", {
        "publication_start": "2024-01-01", "publication_end": "2025-12-31",
        "inclusive": True, "partial_2026_excluded": True,
        "historical_cohort": ["2018-01-01", "2023-12-31"],
        "direct_yield_causality_comparison_allowed": False,
        "strata": strata, "strata_changed_from_alpha3_17": False})
    writelines("alpha3_19_source_query_templates.jsonl", source_queries)
    writelines("alpha3_19_source_query_delta_audit.jsonl", delta_rows)
    write("alpha3_19_sampling_seed_contract.json", {
        "seed": seed, "derivation": "SHA256 of fixed UTF-8 attempt/domain string",
        "seed_input": seed_input, "frozen_before_network": True,
        "depends_on_pmid_frame_findings_or_yield": False})
    write("alpha3_19_sampling_contract.json", {
        "sort": "relevance", "page_size": 50, "frame_cap_per_stratum": 200,
        "all_six_frames_freeze_before_sampling": True,
        "global_dedup_owner": "first stratum in frozen six-stratum order",
        "sample_rule": "sort by SHA256(seed || ':' || stratum || ':' || pmid), take first 12",
        "sample_cap_per_stratum": 12, "raw_sample_cap": 72,
        "refill_allowed": False, "replacement_allowed": False, "topup_allowed": False,
        "seed_sha256": seed})
    write("alpha3_19_seen_source_firewall.json", {
        "registry": ref(OUT / "alpha3_18_seen_source_registry.jsonl"),
        "comparison_key": "exact canonical PMID", "overlap_state": "SEEN_SOURCE_INELIGIBLE",
        "replacement_allowed": False, "expected_overlap": 0,
        "overlap_must_be_checked_on_new_frame": True,
        "current_overlap_count": None})
    write("alpha3_19_source_pipeline_contract.json", {
        "esearch_validation_order": ["transport", "schema", "ErrorList", "WarningList", "Count/IdList"],
        "http_200_sufficient": False, "bindings": {k: bindings[k] for k in (
            "pubmed_esearch_validator_v2", "primary_citation_identity_v1",
            "correction_reference_eligibility_v1", "construction_oa_eligibility_v2",
            "construction_license_extraction_v2", "source_type_v1",
            "construction_document_v1")},
        "canonical_pmid_path": "MedlineCitation/PMID",
        "article_id_path": "PubmedData/ArticleIdList/ArticleId direct child only",
        "reference_identity_recursion": False,
        "correction_states": {"RetractionIn": "INELIGIBLE",
                              "ExpressionOfConcernIn": "INELIGIBLE", "ErratumIn": "UNRESOLVED"},
        "oa": "PMC OA-subset verification",
        "article_level_license_paths": ["license/@xlink:href", "license/ali:license_ref",
                                        "license/license-p//ext-link/@xlink:href"],
        "license_whitelist": ["CC0", "CC BY", "CC BY-SA"],
        "semantic_llm_source_type_classification": False,
        "builder_visible_identity_fields": []})
    write("alpha3_19_builder_contract_binding.json", {
        "contract": bindings["builder_grounding_v3"], "builder_v2_interface_allowed": False,
        "source_field": "body", "abstract_grounding_allowed": False,
        "abstract_orientation_only": True, "candidate_count_min": 0,
        "candidate_count_max": 3, "zero_candidates_valid": True,
        "scientific_retry_allowed": False, "provider": "DeepSeek",
        "model": "deepseek-flash", "thinking": "enabled", "reasoning_effort": "high"})
    envelope = {
        "schema_version": "QualityResponseEnvelopeV3",
        "scientific_protocol": "PropositionQualityAdjudicationV2",
        "scientific_protocol_binding": bindings["quality_scientific_v2"],
        "model_response_body_schema": model_schema,
        "controller_envelope_fields": ["schema_version", "execution_protocol_version",
                                       "request_id", "source_group_id", "provider", "model",
                                       "request_sha256", "raw_response_sha256"],
        "controller_field_source": "frozen request and provider event, never model text",
        "model_owned_fields": ["candidate_id", "criteria", "evidence_support_reference"],
        "model_schema_version_required": False,
        "criterion_count": 10, "provider_response_format": "JSON_OBJECT_ONLY",
        "provider_native_strict_schema_required": False,
        "local_validation_required": True}
    write("quality_response_envelope_v3.json", envelope)
    write("quality_response_ownership_matrix.json", {
        "controller_owned": envelope["controller_envelope_fields"],
        "model_owned": envelope["model_owned_fields"],
        "controller_may_fill_missing_model_fields": False,
        "model_must_echo_controller_metadata": False,
        "scientific_judgment_controller_owned": False})
    write("quality_scientific_protocol_binding.json", {
        "quality_v2_criteria": bindings["quality_scientific_v2"],
        "quality_v2_original_schema": bindings["quality_schema_v2"],
        "criteria": criterion_names, "criteria_changed": False,
        "all_pass_rule_changed": False,
        "evidence_support_reference_rule_changed": False})
    write("quality_provider_binding_alpha3_19.json", {
        "provider": "DeepSeek", "model": "deepseek-flash",
        "thinking": "enabled", "reasoning_effort": "high",
        "response_format": "JSON_OBJECT_ONLY", "native_strict_schema_required": False,
        "scientific_inferences_per_source_group": 1,
        "automatic_retry": False, "repair_call": False,
        "ambiguous_execution": "STOP_STAGE",
        "completed_invalid_response": "FREEZE_INVALID_NO_REINFERENCE"})
    write("quality_response_validation_v3.json", {
        "order": ["transport_event_frozen", "parse_single_json_object", "local_schema",
                  "exact_candidate_id_set", "strict_criterion_enums",
                  "scientific_reference_rule", "controller_envelope_attach"],
        "model_body_schema_sha256": sha(canonical(model_schema)),
        "exact_candidate_id_set": True, "array_order_relevant": False,
        "missing_extra_duplicate_id_invalid": True,
        "strict_enum_values": ["PASS", "FAIL", "UNRESOLVED"],
        "alias_normalization": False, "generic_field_repair": False,
        "controller_fill_missing_scientific_fields": False,
        "missing_candidate_id_invalid": True, "missing_criterion_invalid": True,
        "invalid_enum_invalid": True, "missing_explanation_invalid": True,
        "evidence_support_reference_rule": "PASS or FAIL requires exact visible evidence fragment <=240 characters; UNRESOLVED requires null"})
    phases = [
        ("19A", "new source acquisition", "NETWORK_AUTHORIZATION_REQUIRED"),
        ("19B", "source construction and Builder request freeze", "OFFLINE"),
        ("19C", "Builder execution", "MODEL_AUTHORIZATION_REQUIRED"),
        ("19D", "Quality request freeze", "OFFLINE"),
        ("19E", "Quality execution", "MODEL_AUTHORIZATION_REQUIRED"),
        ("19F", "pool finalization", "OFFLINE"),
        ("19G", "Fresh Heldout sampling", "OFFLINE_AFTER_POOL_FREEZE"),
        ("19H", "retrieval preregistration", "OFFLINE"),
        ("19I", "retrieval execution", "NETWORK_AUTHORIZATION_REQUIRED")]
    write("alpha3_19_phase_barriers.json", {
        "phases": [{"id": x, "name": y, "authorization": z} for x, y, z in phases],
        "automatic_model_boundary_transition": False,
        "current_phase": "MASTER_PREREGISTRATION_ONLY"})
    write("alpha3_19_search_plan_firewall.json", {
        "pool_construction_may_access": ["new cohort source evidence", "frozen generic construction contracts"],
        "pool_construction_forbidden": ["Search Plan architecture", "retrieval outcomes",
                                        "development relevance labels", "known-paper identities"],
        "builder_and_quality_blind_to_search_plan": True})
    write("alpha3_19_attempt_claim_boundary.json", {
        "new_source_acquisition_done": False, "builder_done": False,
        "quality_done": False, "final_pool_derived": False,
        "fresh_heldout_selected": False, "search_plan_evaluation_done": False,
        "final_pool_size": None, "no_minimum_quota": True,
        "cohort_difference_precludes_engineering_only_yield_claim": True})
    # Active runtime paths only; archived runs and historical scripts are not prospective configuration.
    active_paths = [ROOT / ".env", ROOT / ".env.example",
                    ROOT / "src/code_engine/extraction/deepseek_client.py",
                    ROOT / "src/code_engine/extraction/policy.py",
                    ROOT / "src/code_engine/cli/print_env_template.py"]
    active = [p for p in active_paths if p.exists()]
    stale = [str(p.relative_to(ROOT)) for p in active if "deepseek-v4-pro" in p.read_text()]
    require(not stale, "ACTIVE_MODEL_MIGRATION_INCOMPLETE:" + ",".join(stale))
    require("MODEL_NAME=deepseek-flash" in (ROOT / ".env").read_text().splitlines() and
            "deepseek-flash" in (ROOT / "src/code_engine/extraction/policy.py").read_text(),
            "ACTIVE_MODEL_MIGRATION_INCOMPLETE")
    write("active_deepseek_model_audit.json", {
        "active_runtime_files_checked": [ref(p) for p in active],
        "resolved_prospective_model": "deepseek-flash",
        "stale_active_deepseek_v4_pro_references": len(stale),
        "stale_files": stale, "historical_files_excluded": True})
    write("historical_provider_reference_allowlist.json", {
        "historical_model": "deepseek-v4-pro", "allowed_scope": "frozen historical runs and archived scripts only",
        "prospective_runtime_allowed": False, "historical_occurrences_not_rewritten": True})
    write("alpha3_19_master_execution_plan.json", {
        "attempt": "alpha3.19", "stage": "MASTER_PREREGISTRATION",
        "next_stage": NEXT, "phase_order": [p[0] for p in phases],
        "source_query_count": 6, "source_cohort": ["2024-01-01", "2025-12-31"],
        "historical_source_registry_sha256": digest(OUT / "alpha3_18_seen_source_registry.jsonl"),
        "source_queries_sha256": digest(OUT / "alpha3_19_source_query_templates.jsonl"),
        "sampling_seed_sha256": seed,
        "quality_envelope_sha256": digest(OUT / "quality_response_envelope_v3.json"),
        "source_topup_allowed": False, "model_calls_authorized_now": 0,
        "network_calls_authorized_now": 0})
    write("scientific_state_safety_audit.json", {
        "historical_scientific_assets_reused": False,
        "source_query_scientific_terms_changed": False,
        "quality_rubric_changed": False,
        "no_scientific_observation_this_stage": True,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0})
    preserved = [C2 / "summary.json", frame_path, sampled_path, construction_path,
                 v2_path, v3_path, group_path, q2_path, failed_quality_raw]
    write("historical_preservation_audit.json", {
        "historical_assets_modified": False,
        "verified_read_only_sources": [ref(p) for p in preserved]})
    required = ["alpha3_18_closure_verification.json", "alpha3_19_attempt_identity.json",
                "historical_contamination_boundary.json", "alpha3_18_seen_source_registry.jsonl",
                "alpha3_18_seen_candidate_registry.jsonl", "alpha3_18_seen_quality_group_registry.jsonl",
                "engineering_fix_reuse_matrix.json", "scientific_policy_nonadaptation_audit.json",
                "alpha3_19_source_cohort_contract.json", "alpha3_19_source_query_templates.jsonl",
                "alpha3_19_source_query_delta_audit.jsonl", "alpha3_19_sampling_seed_contract.json",
                "alpha3_19_sampling_contract.json", "alpha3_19_seen_source_firewall.json",
                "alpha3_19_source_pipeline_contract.json", "alpha3_19_builder_contract_binding.json",
                "quality_response_envelope_v3.json", "quality_response_ownership_matrix.json",
                "quality_scientific_protocol_binding.json", "quality_provider_binding_alpha3_19.json",
                "quality_response_validation_v3.json", "alpha3_19_phase_barriers.json",
                "alpha3_19_search_plan_firewall.json", "alpha3_19_attempt_claim_boundary.json",
                "active_deepseek_model_audit.json", "historical_provider_reference_allowlist.json",
                "alpha3_19_master_execution_plan.json", "scientific_state_safety_audit.json",
                "historical_preservation_audit.json"]
    require(all((OUT / n).is_file() for n in required), "REQUIRED_OUTPUT_MISSING")
    write("validation.json", {"status": "completed", "required_files_present": True,
                              "source_registry_count": len(source_registry),
                              "candidate_registry_count": len(candidate_registry),
                              "quality_group_registry_count": len(group_registry),
                              "source_query_count": len(source_queries),
                              "source_scientific_terms_changed": False,
                              "quality_criteria_count": len(criterion_names),
                              "quality_model_body_excludes_controller_fields": True,
                              "active_model_stale_reference_count": 0})
    write("summary.json", {"status": "completed", "alpha3_18_closed_and_preserved": True,
                           "alpha3_19_new_attempt": True,
                           "alpha3_18_scientific_assets_reused": False,
                           "source_cohort_start": "2024-01-01",
                           "source_cohort_end": "2025-12-31",
                           "source_query_count": 6, "source_scientific_terms_changed": False,
                           "new_sampling_seed_frozen": True,
                           "source_topup_allowed": False,
                           "pubmed_esearch_validator_v2_bound": True,
                           "primary_citation_identity_v1_bound": True,
                           "construction_license_extraction_v2_bound": True,
                           "source_type_v1_bound": True,
                           "construction_document_v1_bound": True,
                           "body_only_builder_contract_bound": True,
                           "builder_model": "deepseek-flash",
                           "quality_scientific_rubric_changed": False,
                           "quality_schema_version_controller_owned": True,
                           "quality_missing_scientific_fields_controller_fill_allowed": False,
                           "quality_candidate_exact_id_binding": True,
                           "quality_enum_strict": True,
                           "quality_model": "deepseek-flash",
                           "stale_active_deepseek_v4_pro_references": 0,
                           "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
                           "next_stage_recommendation": NEXT,
                           "historical_assets_modified": False})
    marker("quality_response_envelope_v3_sha256", digest(OUT / "quality_response_envelope_v3.json"))
    marker("alpha3_19_master_execution_plan_sha256", digest(OUT / "alpha3_19_master_execution_plan.json"))
    final_root = root_hash({"search_plan_v24_dev_alpha3_19_master_prereg_sha256"})
    marker("search_plan_v24_dev_alpha3_19_master_prereg_sha256", final_root)
    print(canonical({"status": "completed", "root_sha256": final_root,
                     "out": str(OUT), "source_registry_count": len(source_registry),
                     "candidate_registry_count": len(candidate_registry)}).decode())


if __name__ == "__main__":
    main()
