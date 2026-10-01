#!/usr/bin/env python3
"""Offline, prospective alpha3.17a execution preflight. Never performs I/O to network."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UP = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17_new_blinded_proposition_pool_preregistration_offline"
OUT = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17a_new_pool_execution_preflight_offline"
UP_ROOT = "10bc7cc1f03b0cdf38b4409f624b10697ffef3939053601cfba2dc4ea74cece6"
POOL_ROOT = "69a63d7ce9f08e8714413247aa4a39478a5eb0acbb39925e3dadeb9b6a45b64b"
ARCH_ROOT = "ba82369f45c8a4fcee373fb36011e7bd5817af1e9568765ce0be7801518ff5d1"
STRATA = ["basic_cell_signaling", "immunology", "metabolism", "neuroscience", "cancer_biology", "therapy_response_biology"]
MESH = ["Signal Transduction", "Immune System", "Metabolism", "Nervous System", "Neoplasms", "Therapeutics"]
POOL_FILES = ["new_pool_construction_contract.json", "source_universe_contract.json", "source_date_policy.json",
              "generic_source_strata.json", "source_query_restriction_policy.json", "source_sampling_policy.json",
              "sampling_seed_contract.json", "source_exclusion_policy.json", "proposition_builder_isolation_contract.json",
              "proposition_builder_schema.json", "construction_grounding_contract.json", "source_evidence_span_contract.json",
              "paraphrase_leakage_policy.json", "lexical_overlap_audit_contract.json", "proposition_quality_gate.json",
              "architecture_compatibility_nonuse_policy.json", "pool_size_policy.json", "one_proposition_per_source_policy.json",
              "duplicate_control_policy.json", "pool_eligibility_state_contract.json", "anchor_vault_contract.json",
              "public_pool_contract.json", "anchor_firewall_policy.json", "heldout_sampling_policy.json",
              "development_label_nonuse_policy.json", "future_stage_boundary.json"]


def canonical(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def root_for(names: list[str], directory: Path) -> str:
    return sha(canonical([[name, sha((directory / name).read_bytes())] for name in sorted(names)]))


def load(name: str) -> dict:
    return json.loads((UP / name).read_text())


def write(name: str, content: object) -> None:
    path = OUT / name
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path}")
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_bytes(canonical(content) + b"\n")


def main() -> None:
    if OUT.exists():
        raise RuntimeError("alpha3.17a preflight already exists; never regenerate")
    up_names = [p.name for p in UP.iterdir() if p.is_file() and p.name != "search_plan_v24_dev_alpha3_17_sha256"]
    assert root_for(up_names, UP) == UP_ROOT == (UP / "search_plan_v24_dev_alpha3_17_sha256").read_text().strip()
    assert root_for(POOL_FILES, UP) == POOL_ROOT == (UP / "new_blinded_proposition_pool_protocol_sha256").read_text().strip()
    assert load("architecture_freeze_verification.json")["expected_sha256"] == ARCH_ROOT
    assert load("generic_source_strata.json")["ordered_strata"] == STRATA
    assert load("source_date_policy.json")["publication_date_start_inclusive"] == "2018-01-01"
    assert load("source_date_policy.json")["publication_date_end_inclusive"] == "2023-12-31"
    seed = load("sampling_seed_contract.json")["seed_sha256"]
    assert seed == sha((ARCH_ROOT + "|SearchPlanV24DevAlpha3_17NewBlindedPropositionPoolProtocolV1|source-sampling-v1").encode("ascii"))
    assert load("proposition_quality_gate.json")["generic_required_checks"]
    OUT.mkdir()
    write("alpha3_17_root_verification.json", {"status": "PASS", "expected": UP_ROOT, "actual": root_for(up_names, UP),
          "historical_files_mutated": False})
    write("pool_protocol_verification.json", {"status": "PASS", "expected": POOL_ROOT,
          "actual": root_for(POOL_FILES, UP), "architecture_freeze_sha256": ARCH_ROOT,
          "architecture_freeze_verified": True, "source_date_window": ["2018-01-01", "2023-12-31"],
          "strata": STRATA})
    queries = []
    for i, (stratum, term) in enumerate(zip(STRATA, MESH, strict=True)):
        query = (f'"{term}"[MeSH Terms] AND "2018/01/01"[Date - Publication] : '
                 f'"2023/12/31"[Date - Publication] AND "journal article"[Publication Type] '
                 f'AND pmc[filter] NOT "review"[Publication Type]')
        queries.append({"stratum_order": i, "stratum_id": stratum, "query_utf8": query,
                        "query_sha256": sha(query.encode("utf-8")), "date_start": "2018-01-01",
                        "date_end": "2023-12-31", "pmc_accessibility_proxy": "pmc[filter]",
                        "legal_pmc_oa_must_be_verified_after_retrieval": True})
    query_bytes = b"".join(canonical(q) + b"\n" for q in queries)
    write("exact_source_queries.jsonl", query_bytes)
    write("exact_source_queries_sha256", (sha(query_bytes) + "\n").encode())
    write("source_query_development_nonuse_audit.json", {
        "method": "closed allowlist construction from alpha3.17 ordered generic strata; no case, label, candidate or Search Plan query file opened",
        "allowed_variable_tokens": MESH, "fixed_tokens": ["MeSH Terms", "Date - Publication", "journal article", "pmc", "filter", "review"],
        "development_derived_source_query_term_count": 0, "seen_case_literal_audit": "provenance-isolated, not a comparison against forbidden case files",
        "known_pmid_or_title_lookup": False, "failure_derived_or_architecture_query_family_terms_used": False,
        "query_count": 6, "query_set_sha256": sha(query_bytes)})
    write("source_execution_policy.json", {
        "interface": "NCBI PubMed ESearch", "request_method": "GET", "db": "pubmed", "retmode": "json",
        "query_parameter": "term", "query_bytes_source": "exact_source_queries.jsonl", "stratum_order": STRATA,
        "sort": "relevance", "page_size": 50, "retstart_sequence": [0, 50, 100, 150],
        "frame_cap_per_stratum": 200, "stop_on_short_page": True, "no_query_rewriting": True,
        "timeout_seconds": 60, "maximum_attempts_per_request": 4, "backoff_seconds": [2, 4, 8],
        "terminal_failure": "STOP_ALL_NETWORK_AND_FAIL_CLOSED", "technical_retry_only": True,
        "http_status_retryable": [408, 429, 500, 502, 503, 504], "nonretryable_response": "FAIL_CLOSED",
        "one_logical_execution_per_query": True, "no_result_driven_expansion": True})
    write("source_frame_freeze_policy.json", {
        "ordered_frame": "first at most 200 PMID strings in returned PubMed relevance order, preserving page order",
        "within_stratum_duplicate": "retain first occurrence only, do not fetch extra pages to refill",
        "freeze_barrier": "all expected pages for all six strata must succeed; write ordered per-stratum frame and SHA-256 before any sampling",
        "partial_frame_sampling": False, "date_and_publication_type_authority": "frozen PubMed query then metadata recheck",
        "oa_authority": "PMC legal OA check after source sampling; pmc[filter] is only an accessibility proxy"})
    write("cross_stratum_duplicate_policy.json", {
        "identity": "normalized decimal PMID from PubMed ESearch", "earliest_owner_order": STRATA,
        "all_memberships_preserved": True, "duplicate_article_constructed_once": True,
        "operation_order": "freeze all frames; enumerate earliest owner for each PMID; remove from later owned frames; then sample each owned frame",
        "no_cross_stratum_refill": True})
    sampling = {"seed_sha256": seed, "seed_encoding": "lowercase ASCII hex", "source_id": "canonical decimal PMID with no leading zeros",
                "key_preimage": "ASCII seed_sha256 + ':' + stratum_id + ':' + canonical PMID",
                "key": "SHA256(key_preimage UTF-8 bytes)", "order": "ascending raw 32-byte digest, then ascending decimal PMID as tie-break",
                "sample": "first min(12, owned frame length)", "frame_cap": 200, "sample_cap_per_stratum": 12,
                "global_maximum": 72, "no_refill_after_exclusions_or_builder_results": True}
    write("source_sampling_algorithm.json", sampling)
    write("source_sampling_algorithm_sha256", (sha((OUT / "source_sampling_algorithm.json").read_bytes()) + "\n").encode())
    write("mechanical_source_exclusion_order.json", {
        "ordered_checks": ["duplicate_source_article", "source_provenance_failure", "overlap_with_frozen_seen_development_source",
                           "article_unavailable", "not_primary_experimental_research", "no_usable_experimental_result"],
        "pre_acquisition_checks": ["duplicate_source_article", "source_provenance_failure",
                                   "overlap_with_frozen_seen_development_source"],
        "post_acquisition_checks": ["article_unavailable", "not_primary_experimental_research", "no_usable_experimental_result"],
        "classification": "metadata publication type and frozen article-type/Results-section presence only; ambiguous means exclude, not infer biology",
        "no_search_plan_performance_signal": True, "no_replacement": True})
    # The registry deliberately reads only local fulltext artifact basenames, never candidate metadata or labels.
    pmcids = set()
    source_paths = []
    for path in sorted((ROOT / "runs").glob("*/retrieval_assets/fulltext/PMC*.xml")):
        if re.fullmatch(r"PMC[0-9]+\.xml", path.name):
            pmcids.add(path.stem)
            source_paths.append(str(path.relative_to(ROOT)))
    registry = {"identity_type": "PMCID", "hash_domain": "seen-source-local-pmcid-v1:",
                "hashed_pmcids": sorted(sha(("seen-source-local-pmcid-v1:" + x).encode()) for x in pmcids),
                "local_fulltext_artifact_count": len(source_paths), "unique_pmcid_count": len(pmcids),
                "registry_scope": "locally preserved retrieval_assets/fulltext/PMC*.xml from prior runs; no candidate metadata or known-paper lookup",
                "source_path_sha256": sha(canonical(source_paths)), "no_network_identity_expansion": True,
                "future_comparison": "hash normalized PMCID with exact domain and test membership; unresolved identity fails closed",
                "completeness_limit": "Only already-preserved local fulltext artifacts are covered; other historical identifiers are not claimed covered"}
    write("seen_source_local_registry.json", registry)
    write("seen_source_local_registry_sha256", (sha((OUT / "seen_source_local_registry.json").read_bytes()) + "\n").encode())
    write("construction_fulltext_acquisition_policy.json", {
        "source": "NCBI PMC EFetch XML only", "pmcid_required": True,
        "legal_oa_evidence": "PMC OA eligibility recorded before EFetch; PMCID alone is insufficient",
        "publisher_fallback": False, "general_web_fallback": False, "doi_inference": False,
        "ordering": "sampled source order by stratum then keyed order", "one_download_per_unique_source": True,
        "source_text": "XML title, abstract and body itertext; Unicode NFKC and whitespace collapse; preserve exact frozen strings and SHA-256",
        "builder_body_limit_characters": 60000, "builder_abstract_limit_characters": 10000,
        "text_slice": "first N Unicode code points of each normalized field; no semantic selection",
        "source_title_private": True})
    write("construction_fulltext_failure_policy.json", {
        "timeout_seconds": 60, "attempts_max": 4, "backoff_seconds": [2, 4, 8],
        "retryable_status": [408, 429, 500, 502, 503, 504], "parse_or_oa_failure": "SOURCE_INELIGIBLE",
        "failed_selected_source_replacement": False, "stratum_topup": False, "no_new_source_after_builder_phase_begins": True})
    write("proposition_builder_role_contract.json", {"role": "proposition_pool_builder",
          "not_roles": ["Search Planner", "model_retrieval_adjudicator", "Human Gold"],
          "authority": "source-grounded proposal only", "cannot_declare": ["heldout eligibility", "Search compatibility", "retrievability", "DIRECT relevance", "gold truth"]})
    write("proposition_builder_visibility_contract.json", {"one_source_article_per_call": True,
          "allow": ["opaque source token", "one frozen title/abstract/body representation", "generic construction prompt", "output schema"],
          "deny": ["Search Plan architecture", "current query vocabulary", "development cases or labels", "retrieval outcomes",
                   "P0/P1/P2", "historical review results", "other source articles"], "private_source_identity_not_model_visible": True})
    write("proposition_builder_provider_config.json", {"provider": "DeepSeek", "api_surface": "Chat Completions",
          "model": "deepseek-v4-pro", "thinking": {"type": "enabled"}, "reasoning_effort": "high",
          "response_format": {"type": "json_object"}, "temperature": "omitted", "top_p": "omitted",
          "initial_inferences_per_source": 1, "automatic_retry": False, "scientific_repair_calls": False,
          "ambiguous_transport_outcome": "fail closed; no replacement inference", "fallback": None})
    system = ("You are proposition_pool_builder. Analyze only the single supplied source article. "
              "Propose zero or one neutral, experimentally grounded scientific proposition. "
              "Do not use external knowledge, search behavior, retrieval performance, or other articles. "
              "If no sufficiently grounded proposition is available, return an empty propositions array. "
              "A nonzero proposition must cite one exact source-local span with zero-based character offsets. "
              "Return one JSON object matching the supplied schema; no Markdown or commentary.\n")
    user = ("Source token: {source_record_token}\nTitle: {source_title}\nAbstract: {frozen_abstract}\n"
            "Body: {frozen_body}\nOutput schema: {output_schema_json}\n")
    write("proposition_builder_system_prompt.txt", system.encode())
    write("proposition_builder_user_prompt_template.txt", user.encode())
    schema = load("proposition_builder_schema.json")["schema"]
    assert schema["properties"]["propositions"]["maxItems"] == 3
    schema["properties"]["propositions"]["maxItems"] = 1
    write("proposition_builder_output_schema.json", {"alpha3_17a_cardinality_refinement": "0..1; alpha3.17 historical 0..3 remains unchanged",
          "schema": schema})
    write("proposition_builder_request_contract.json", {"one_fresh_session_per_source": True,
          "one_initial_inference_per_eligible_source": True, "request_fields": ["model", "thinking", "reasoning_effort", "response_format", "messages"],
          "messages": ["system prompt bytes", "user template rendered with one frozen source"],
          "request_manifest_precedes_first_call": True, "source_order": "stratum order then keyed sample order, after mechanical eligibility",
          "raw_response_frozen_before_validation": True, "no_semantic_repair": True})
    write("proposition_builder_validation_policy.json", {"order": ["JSON parse", "exact schema", "source token equality",
          "zero-or-one cardinality", "required nonempty scientific fields", "source field and exact span offsets", "source text SHA-256"],
          "span_offsets": "zero-based Unicode code-point offsets in frozen normalized abstract/body; exact_text == field[start:end]",
          "invalid_output": "preserve raw output and fail closed for source; no retry", "zero_candidate": "valid, no replacement",
          "provider_output_is_scientific_authority": False})
    write("proposition_quality_gate_execution_audit.json", {"status": "QUALITY_GATE_EXECUTION_NOT_PREREGISTERED",
          "upstream_required_checks": load("proposition_quality_gate.json")["generic_required_checks"],
          "deterministically_checkable_subset": ["actor_and_response_identifiable via required nonempty fields"],
          "semantic_checks_need_separate_future_preregistration": True,
          "reason": "scientific coherence, experimental testability, directionality and specificity cannot be honestly validated by syntactic rules alone",
          "semantic_model_or_reviewer_calls_added": 0, "eligible_pool_freeze_authorized": False})
    write("leakage_audit_implementation_contract.json", {"normalization": "Unicode NFKC, lowercase, maximal Unicode-alphanumeric spans",
          "implementation": "scripts/search_plan_v24_alpha317a_safety_audits.py:leakage_failed",
          "implementation_sha256": sha((ROOT / "scripts/search_plan_v24_alpha317a_safety_audits.py").read_bytes()),
          "contiguous_rule": "fail if any contiguous run of 8 or more normalized tokens is shared between neutral proposition and source title or construction evidence sentence",
          "jaccard_rule": "set intersection / set union; fail if >=0.80 and both token lists have at least 8 tokens",
          "sentence_boundary": "span's containing sentence in the normalized frozen source field, segmented at . ! ? and newline; if ambiguous use entire field",
          "thresholds_unchanged": True, "comparison_inputs": ["private source title", "private evidence sentence", "public neutral proposition"],
          "no_model_repair": True})
    write("anchor_vault_filesystem_contract.json", {"anchor_restricted_root": "future_alpha3_18/private_anchor_vault/",
          "public_pool_eligible_root": "future_alpha3_18/public_pool/", "execution_provenance_root": "future_alpha3_18/source_execution/",
          "vault_creation_barrier": "only after both source identity and proposition candidate are known",
          "vault_required_fields": load("anchor_vault_contract.json")["future_fields"],
          "public_forbidden_fields": load("public_pool_contract.json")["forbidden_public_fields"],
          "no_symlink_or_hardlink_across_roots": True})
    write("anchor_firewall_implementation_contract.json", {"status": "FROZEN_CONTRACT_NOT_YET_EXECUTED",
          "implementation": "scripts/search_plan_v24_alpha317a_safety_audits.py:audit_search_plan_inputs",
          "implementation_sha256": sha((ROOT / "scripts/search_plan_v24_alpha317a_safety_audits.py").read_bytes()),
          "artifact_classes": {"ANCHOR_RESTRICTED": ["private_anchor_vault/*", "raw source identifiers and span mappings"],
                               "PUBLIC_POOL_ELIGIBLE": ["public_pool/*"],
                               "EXECUTION_PROVENANCE_ONLY": ["source_execution/*", "builder raw outputs and request manifests"]},
          "search_plan_input_allowlist": ["public_pool/*"],
          "audit": "resolve every path; reject symlinks/hardlinks and any input outside public root; recursively reject source-identity keys, PMCID and DOI patterns, and restricted path references in JSON inputs; standalone PMID or copied source-title values without identifying keys require a separate construction-time audit",
          "deny_on_unknown_class_or_reference": True, "compiler_or_reviewer_vault_access": False})
    write("builder_call_budget_formula.json", {"formula": "number_of_mechanically_eligible_sampled_sources_with_successfully_frozen_construction_evidence",
          "maximum_builder_scientific_calls": 72, "actual_builder_call_count_not_yet_known": True,
          "derive_after_phase_a_before_first_builder_call": True, "one_call_per_source": True,
          "no_call_for_failed_fulltext": True, "no_topup_or_repair": True})
    write("alpha3_18_phase_barrier_contract.json", {"phase_a": ["six source queries", "six complete frozen frames",
          "deduplication and keyed sampling", "mechanical exclusions", "PMC OA fulltext acquisition",
          "mechanically eligible construction-source manifest", "derive exact call count",
          "freeze construction_source_manifest_sha256", "freeze builder_request_manifest and SHA-256"],
          "phase_b": ["one DeepSeek builder inference per manifest source", "freeze raw outputs", "validate"],
          "phase_b_requires_all_phase_a_freezes": True, "dynamic_source_topup_after_builder_start": False,
          "quality_gate_is_separate_unpreregistered_blocker": True})
    write("future_execution_authorization_contract.json", {"current_authorization": "OFFLINE_PREFLIGHT_ONLY",
          "network_authorization_needed": "six frozen NCBI source-query streams and selected PMC construction fulltexts",
          "model_authorization_needed": "exact call count from frozen phase-A manifest, upper bound 72, DeepSeek deepseek-v4-pro",
          "semantic_quality_adjudication_requires_separate_preregistration": True,
          "no_alpha3_18_execution_now": True})
    write("scientific_state_safety_audit.json", {"provider_calls": 0, "llm_calls": 0, "network_calls": 0,
          "retrieval_calls": 0, "propositions_constructed": 0, "heldout_cases_sampled": 0,
          "query_compilation_calls": 0, "historical_assets_modified": False})
    source_manifest_names = ["exact_source_queries.jsonl", "source_execution_policy.json", "source_frame_freeze_policy.json",
          "cross_stratum_duplicate_policy.json", "source_sampling_algorithm.json", "mechanical_source_exclusion_order.json",
          "seen_source_local_registry.json", "construction_fulltext_acquisition_policy.json", "construction_fulltext_failure_policy.json"]
    builder_names = ["proposition_builder_role_contract.json", "proposition_builder_visibility_contract.json",
          "proposition_builder_provider_config.json", "proposition_builder_system_prompt.txt",
          "proposition_builder_user_prompt_template.txt", "proposition_builder_output_schema.json",
          "proposition_builder_request_contract.json", "proposition_builder_validation_policy.json",
          "builder_call_budget_formula.json"]
    source_root = root_for(source_manifest_names, OUT)
    builder_root = root_for(builder_names, OUT)
    write("new_pool_source_acquisition_manifest_sha256", (source_root + "\n").encode())
    write("proposition_builder_protocol_sha256", (builder_root + "\n").encode())
    write("validation.json", {"status": "FAILED_CLOSED", "reason": "QUALITY_GATE_EXECUTION_NOT_PREREGISTERED",
          "architecture_freeze_verified": True, "exact_source_query_count": 6, "source_query_bytes_frozen": True,
          "development_derived_source_query_term_count": 0, "source_sampling_algorithm_frozen": True,
          "source_sampling_seed_unchanged": True, "source_frame_cap_per_stratum": 200, "sample_cap_per_stratum": 12,
          "builder_one_source_per_call": True, "builder_provider": "DeepSeek", "builder_model": "deepseek-v4-pro",
          "builder_prompt_frozen": True, "builder_output_schema_frozen": True,
          "builder_scientific_repair_calls_allowed": False, "maximum_builder_scientific_calls": 72,
          "actual_builder_call_count_not_yet_known": True, "source_phase_before_builder_phase": True,
          "dynamic_source_topup_after_builder_start": False, "anchor_firewall_implementation_frozen": True,
          "provider_calls": 0, "llm_calls": 0, "network_calls": 0, "retrieval_calls": 0})
    write("summary.json", {"status": "failed", "reason": "QUALITY_GATE_EXECUTION_NOT_PREREGISTERED",
          "new_pool_source_acquisition_manifest_sha256": source_root,
          "proposition_builder_protocol_sha256": builder_root,
          "next_stage_recommendation": "PREREGISTER_INDEPENDENT_PROPOSITION_QUALITY_ADJUDICATION",
          "historical_assets_modified": False})
    names = [p.name for p in OUT.iterdir() if p.is_file()]
    overall = root_for(names, OUT)
    write("search_plan_v24_dev_alpha3_17a_sha256", (overall + "\n").encode())
    assert root_for(names, OUT) == overall
    print(json.dumps({"status": "failed_closed", "root": overall, "source_manifest_root": source_root,
                      "builder_root": builder_root, "seen_pmcid_count": len(pmcids)}, sort_keys=True))


if __name__ == "__main__":
    main()
