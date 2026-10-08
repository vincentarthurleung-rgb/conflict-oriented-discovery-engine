#!/usr/bin/env python3
"""Offline D policy/request freeze, blocking unbound JATS PMID/DOI semantics."""

from __future__ import annotations

import inspect
import json
import os
from pathlib import Path

from scripts import run_search_plan_v24_alpha321c2_metadata_execution as c2
from scripts import run_search_plan_v24_alpha319d_pmc_oa_jats_construction_eligibility as d19
from scripts import run_search_plan_v24_alpha319d1_updateof_resolution_offline as d19_1
from scripts import search_plan_v24_alpha321_body_only as body_only


ROOT, MASTER, C2, B = c2.ROOT, c2.MASTER, c2.OUT, c2.B
OUT = ROOT / "runs/20261006_search_plan_v24_primary_alpha3_21d_pmc_oa_jats_preregistration_offline"
ROOT_MARKER = "search_plan_v24_primary_alpha3_21d_prereg_sha256"
C2_SHA = "d6b93b567b6c643fc81d255c12542a1000ae1aee809f452991a0eb6c2eb837f6"
HANDOFF_SHA = "4744cb175e57297d0f5a08c52b001b78e05b81e4f06b3b22a8d7e31f8439405f"
D19_SHA = "422975cb0706f19a6ee2640bc126fc49892d2e220df34b3f6c25c5a57a5b9a33"
D19_1_SHA = "2914e34c003aa8aa7a4949e4a276f68fb11b81b3f77f8796a7fb7469f5a0a545"
CLASS_BLOCKED = "FRESH_PRIMARY_PMC_ACQUISITION_AUTHORITY_UNRESOLVED"
NO_CALLS = {k: 0 for k in ("network_calls", "pubmed_calls", "pmc_calls", "provider_calls", "llm_calls", "builder_calls", "quality_calls")}
canonical, sha, digest, obj, rows, ref, root_hash, require = c2.canonical, c2.sha, c2.digest, c2.obj, c2.rows, c2.ref, c2.root_hash, c2.require
implementation = c2.authority.implementation


def put_bytes(name: str, raw: bytes) -> str:
    with (OUT / name).open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return sha(raw)


def put(name, value):
    return put_bytes(name, canonical(value) + b"\n")


def freeze(stem, value, jsonl=False):
    raw = b"".join(canonical(r) + b"\n" for r in value) if jsonl else canonical(value) + b"\n"
    value_sha = put_bytes(stem + (".jsonl" if jsonl else ".json"), raw)
    put_bytes(stem + "_sha256", (value_sha + "\n").encode("ascii"))
    return value_sha


def checked_tree(value):
    if isinstance(value, dict):
        if "sha256" in value and ("path" in value or "artifact_path" in value):
            c2.authority.c.b.checked_ref(value)
        for child in value.values():
            checked_tree(child)
    elif isinstance(value, list):
        for child in value:
            checked_tree(child)


def preflight():
    require((C2 / c2.ROOT_MARKER).read_text().strip() == C2_SHA and root_hash(C2, c2.ROOT_MARKER) == C2_SHA,
            "C2_ROOT_MISMATCH")
    c2.preflight()
    for module, expected in ((d19, D19_SHA), (d19_1, D19_1_SHA)):
        require((module.OUT / module.ROOT_MARKER).read_text().strip() == expected
                and root_hash(module.OUT, module.ROOT_MARKER) == expected, "HISTORICAL_PMC_ROOT_MISMATCH")
    handoff_path = C2 / "alpha3_21d_pre_oa_source_handoff.json"
    require(digest(handoff_path) == HANDOFF_SHA and (C2 / "alpha3_21d_pre_oa_source_handoff_sha256").read_text().strip() == HANDOFF_SHA,
            "C2_HANDOFF_HASH_MISMATCH")
    handoff = obj(handoff_path)
    sources = handoff["sources"]
    final = rows(C2 / "metadata_final_source_states.jsonl")
    by_pmid = {r["pmid"]: r for r in final}
    require(obj(C2 / "summary.json")["status"] == "completed"
            and len(sources) == handoff["source_count"] == len({s["pmid"] for s in sources}) == 49
            and len(by_pmid) == 72
            and [s["pmid"] for s in sources] == [f["pmid"] for f in final if f["pre_oa_handoff_state"] != "BLOCKED"]
            and sum(s["pre_oa_handoff_state"] == "PRE_OA_CLEAR" for s in sources) == 46
            and sum(s["pre_oa_handoff_state"] == "PRE_OA_CONDITIONAL_UPDATEOF" for s in sources) == 3,
            "EXACT_49_SOURCE_INPUT_BOUNDARY_MISMATCH")
    for source in sources:
        facts = by_pmid[source["pmid"]]
        require(all(source[k] == facts[k] for k in ("pmid", "stratum", "metadata_state", "pre_oa_handoff_state",
                    "correction_update_state", "updateof_deferred_state", "raw_response_sha256", "selection_provenance"))
                and source["pmcid"] == facts["direct_pmcid"] and source["doi"] == facts["direct_doi"],
                "C2_SOURCE_IDENTITY_OR_PROVENANCE_MISMATCH")
    bindings = obj(MASTER / "alpha3_21_pmc_oa_policy_binding.json")
    documents = obj(MASTER / "alpha3_21_construction_document_binding.json")
    checked_tree(bindings)
    checked_tree(documents)
    exposure = obj(C2 / "alpha3_21_current_attempt_metadata_identity_exposure_registry.json")
    require(digest(C2 / "alpha3_21_current_attempt_metadata_identity_exposure_registry.json") ==
            obj(C2 / "summary.json")["alpha3_21_current_attempt_metadata_identity_exposure_registry_sha256"]
            and exposure["current_exclusion_authority"] is False and len(exposure["source_identities"]) == 72,
            "C2_EXPOSURE_BINDING_MISMATCH")
    require(obj(C2 / "downstream_no_replacement_audit.json")["downstream_replacement_used"] is False,
            "NO_REPLACEMENT_BOUNDARY_MISMATCH")
    oa_path = c2.authority.c.b.checked_ref(bindings["oa_subset"])
    jats_path = c2.authority.c.b.checked_ref(bindings["jats"])
    handoff_contract_path = c2.authority.c.b.checked_ref(bindings["construction_handoff"])
    oa, jats, handoff_contract = obj(oa_path), obj(jats_path), obj(handoff_contract_path)
    for contract in (oa, jats, handoff_contract):
        checked_tree(contract)
    license_path = c2.authority.c.b.checked_ref(handoff_contract["handoff_contracts"]["future_license_extraction"])
    type_path = c2.authority.c.b.checked_ref(handoff_contract["handoff_contracts"]["future_source_type"])
    license_contract = obj(license_path)
    checked_tree(license_contract)
    rule = obj(d19_1.RULE_PATH)
    checked_tree(rule)
    require(digest(d19_1.RULE_PATH) == d19_1.RULE_SHA and rule["only_clear_admitted"] is True
            and rule["UpdateOf_finalization"] ==
            "provisional UNRESOLVED before JATS; final CLEAR only when frozen independent SourceTypeMechanicalEligibilityV1 is ELIGIBLE; INELIGIBLE if it is INELIGIBLE; otherwise UNRESOLVED",
            "UPDATEOF_AUTHORITY_MISMATCH")
    require(oa["endpoint"] == d19.ES and oa["db"] == "pmc" and oa["retmax"] == 1
            and oa["PMCID_alone_sufficient"] is False and jats["route"]["endpoint"] == d19.EF
            and jats["route"]["db"] == "pmc" and jats["route"]["retmode"] == "xml"
            and jats["requires_oa_subset_state"] == "OA_SUBSET_ELIGIBLE"
            and jats["technical_max_attempts"] == 4 and jats["timeout_seconds"] == 60
            and jats["backoff_seconds"] == [2, 4, 8] and jats["terminal_failure"] == "RECORD_NO_REPLACEMENT",
            "HISTORICAL_CLIENT_SEQUENCE_MISMATCH")
    failure_path = c2.authority.c.b.checked_ref(jats["failure_policy"])
    require(obj(failure_path)["retryable_status"] == [408, 429, 500, 502, 503, 504], "RETRYABLE_STATUS_MISMATCH")
    require(digest(ROOT / "scripts/search_plan_v24_alpha318a1_source_contracts.py") ==
            obj(c2.authority.c.b.checked_ref(documents["document_contract"]))["implementation_sha256"],
            "HISTORICAL_BODY_IMPLEMENTATION_MISMATCH")
    return {"sources": sources, "facts": by_pmid, "oa_path": oa_path, "jats_path": jats_path,
        "handoff_path": handoff_contract_path, "license_path": license_path, "type_path": type_path,
        "failure_path": failure_path, "documents": documents}


def license_fixtures():
    examples = [
        ("eligible_href", '<license href="https://creativecommons.org/licenses/by/4.0/"/>', "ELIGIBLE"),
        ("nonwhitelist", '<license href="https://creativecommons.org/licenses/by-nc/4.0/"/>', "INELIGIBLE"),
        ("missing", "", "UNRESOLVED"),
        ("multiple_agree", '<license href="https://creativecommons.org/licenses/by/4.0/"/><license href="http://creativecommons.org/licenses/by/4.0/"/>', "ELIGIBLE"),
        ("multiple_conflict", '<license href="https://creativecommons.org/licenses/by/4.0/"/><license href="https://creativecommons.org/licenses/by-nc/4.0/"/>', "UNRESOLVED"),
        ("ali_license_ref", '<license><ali:license_ref>https://creativecommons.org/licenses/by/4.0/</ali:license_ref></license>', "ELIGIBLE"),
        ("xlink_namespace", '<license xlink:href="https://creativecommons.org/publicdomain/zero/1.0/"/>', "ELIGIBLE"),
        ("wrong_ali_namespace", '<license><fake:license_ref>https://creativecommons.org/licenses/by/4.0/</fake:license_ref></license>', "UNRESOLVED"),
        ("nested_ext_link", '<license><license-p><ext-link xlink:href="https://creativecommons.org/licenses/by-sa/4.0/"/></license-p></license>', "ELIGIBLE"),
        ("malformed_uri", '<license href="not-a-license-uri"/>', "UNRESOLVED"),
        ("malformed_xml", '<license href="', "INVALID_XML"),
    ]
    return [{"fixture_id": name, "expected_state": expected,
        "raw_xml": '<article xmlns:ali="http://www.niso.org/schemas/ali/1.0/" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:fake="urn:fake"><front><article-meta><permissions>' + content + '</permissions></article-meta></front><body/></article>',
        "origin": "OFFLINE_SYNTHETIC_NOT_PRIMARY_SOURCE_JATS"} for name, content, expected in examples]


def identity_gap_probe():
    results = []
    for name, pmid, doi in (("contradictory_direct_pmid", "999", "10.fixture/expected"),
                            ("contradictory_direct_doi", "123", "10.fixture/other")):
        raw = (f'<article><front><article-meta><article-id pub-id-type="pmc">123</article-id>'
            f'<article-id pub-id-type="pmid">{pmid}</article-id><article-id pub-id-type="doi">{doi}</article-id>'
            '</article-meta></front><body/></article>').encode()
        canonical_xml = d19.frozen_rules.canonical_jats(raw, "PMC123")
        results.append({"fixture_id": name, "expected_source_pmid": "123", "expected_source_doi": "10.fixture/expected",
            "synthetic_xml": raw.decode(), "historical_canonicalizer_accepts": bool(canonical_xml),
            "historical_canonicalizer_checks_this_identifier": False})
    return results


def requests_for(sources):
    result = []
    for request_class in ("PMC_OA_SUBSET", "PMC_JATS"):
        for ordinal, source in enumerate(sources, 1):
            pmcid = source["pmcid"]
            params = {"db": "pmc", "retmode": "json", "retmax": "1",
                "term": d19.source_policy.oa_subset_esearch_term(pmcid)} if request_class == "PMC_OA_SUBSET" else {
                "db": "pmc", "retmode": "xml", "id": pmcid[3:]}
            payload = {"method": "GET", "endpoint": d19.ES if request_class == "PMC_OA_SUBSET" else d19.EF, "parameters": params}
            request_sha = sha(canonical(payload))
            result.append({"logical_request_id": "a321d_" + request_sha, "request_class": request_class,
                "source_input_ordinal": ordinal, "pmid": source["pmid"], "pmcid": pmcid,
                "request_payload": payload, "request_payload_sha256": request_sha,
                "activation_condition": "always after separate D1 authorization and authority resolution" if request_class == "PMC_OA_SUBSET" else
                    "all 49 OA requests terminal and this source OA_SUBSET_ELIGIBLE; separate D1 authorization and authority resolution",
                "network_authorized": False, "source_provenance": source})
    return result


def run():
    require(not OUT.exists(), "D_OUTPUT_ALREADY_EXISTS_NO_OVERWRITE")
    state = preflight()
    fixtures = license_fixtures()
    fixture_results = []
    for fixture in fixtures:
        try:
            result = d19.license_v2.extract_license_v2(fixture["raw_xml"].encode())
            terminal = result["state"]
        except d19.ET.ParseError:
            result, terminal = None, "INVALID_XML"
        require(terminal == fixture["expected_state"], "LICENSE_FIXTURE_MISMATCH")
        fixture_results.append({"fixture_id": fixture["fixture_id"], "state": terminal, "result": result})
    probes = identity_gap_probe()
    require(all(p["historical_canonicalizer_accepts"] for p in probes), "IDENTITY_GAP_EVIDENCE_CHANGED_REAUDIT_REQUIRED")
    sources = [{**source, "c2_source_state_sha256": sha(canonical(state["facts"][source["pmid"]])),
        "c2_source_state_artifact": ref(C2 / "metadata_final_source_states.jsonl", "unchanged_source_states"),
        "publication_types": state["facts"][source["pmid"]]["publication_types"],
        "correction_relationships": state["facts"][source["pmid"]]["correction_relationships"]} for source in state["sources"]]
    OUT.mkdir()
    put("alpha3_21c2_root_verification.json", {"verified": True, "sha256": C2_SHA})
    put("alpha3_21_master_root_verification.json", {"verified": True, "sha256": c2.authority.c.b.MASTER_SHA})
    put("pre_oa_handoff_verification.json", {"source_artifact": ref(C2 / "alpha3_21d_pre_oa_source_handoff.json", "only_49_source_input"),
        "sample": ref(B / "sampled_source_manifest.jsonl", "immutable_72_sample"), "source_count": 49, "clear": 46, "deferred": 3,
        "metadata_identity_exposure": ref(C2 / "alpha3_21_current_attempt_metadata_identity_exposure_registry.json", "unchanged_future_metadata_history"),
        "metadata_excluded_23_restored": False, "unsampled_sources_added": False})
    input_sha = freeze("alpha3_21d_input_source_manifest", sources, jsonl=True)
    put("historical_alpha3_19d_policy_binding.json", {"root_sha256": D19_SHA, "root_verified": True,
        "master_policy": ref(MASTER / "alpha3_21_pmc_oa_policy_binding.json", "inherited_PMC_OA_policy"),
        "client_code": ref(Path(inspect.getsourcefile(d19)).resolve(), "historical_PMC_execution"),
        "historical_yields_used_as_targets": False})
    put("historical_alpha3_19d1_updateof_resolution_binding.json", {"root_sha256": D19_1_SHA, "root_verified": True,
        "rule": ref(d19_1.RULE_PATH, "exact_UpdateOf_eligibility_rule"),
        "execution_code": ref(Path(inspect.getsourcefile(d19_1)).resolve(), "historical_structural_resolution_orchestration"),
        "classifier": implementation(d19_1.correction.classify, "unchanged_direction_sensitive_classifier")})
    put("pmc_acquisition_client_authority.json", {"client_mechanics_resolved": True, "complete_acquisition_authority_resolved": False,
        "client": implementation(d19.PMCTransport.fetch, "unchanged_PMC_transport"),
        "OA_route": ref(state["oa_path"], "unchanged_OA_lookup"), "JATS_route": ref(state["jats_path"], "unchanged_JATS_fetch"),
        "sequence": ["all source OA lookups", "freeze all OA terminal states", "JATS only for OA eligible sources"],
        "grouping": "one PMCID per request", "blocking_reason": "DIRECT_JATS_PMID_DOI_COMPARISON_AUTHORITY_NOT_BOUND"})
    put("pmc_oa_policy_binding.json", {"contract": ref(state["oa_path"], "exact_OA_subset_contract"),
        "term_builder": implementation(d19.source_policy.oa_subset_esearch_term, "exact_numeric_UID_query"),
        "response_validator": implementation(d19.oa_subset_state, "frozen_OA_three_state_validator"),
        "PMCID_alone_is_OA_proof": False})
    put("pmc_license_policy_binding.json", {"contract": ref(state["license_path"], "hardened_article_level_license_V2"),
        "parser": implementation(d19.license_v2.extract_license_v2, "exact_A_B_C_machine_readable_license_paths"),
        "construction_OA": implementation(d19.license_v2.construction_oa_v2, "subset_plus_article_license"),
        "whitelist": sorted(d19.license_v2.WHITELIST), "external_lookup": False})
    fixture_sha = put_bytes("pmc_license_synthetic_fixtures.jsonl", b"".join(canonical(f) + b"\n" for f in fixtures))
    put("pmc_license_parser_fixture_manifest.json", {"fixture_count": len(fixtures), "fixture_sha256": fixture_sha,
        "fixtures": ref(OUT / "pmc_license_synthetic_fixtures.jsonl", "synthetic_only_license_fixtures"),
        "results": fixture_results, "all_expected_states_passed": True, "primary_source_JATS_observed": False})
    put("pmc_jats_response_validity_contract.json", {"canonicalizer": implementation(d19.frozen_rules.canonical_jats, "historical_article_and_direct_PMCID_validator"),
        "historical_guards": ["XML parseability", "exactly one article in response", "direct front/article-meta/article-id pmc/pmcid set equals requested PMCID"],
        "front_body_back_not_all_required_by_canonicalizer": True, "BODY_prerequisite_applied_separately": True,
        "XML_repair_or_fallback_allowed": False, "complete_identity_contract_resolved": False})
    put("pmc_jats_parser_authority.json", {"historical_parser_located": True,
        "canonicalizer": implementation(d19.frozen_rules.canonical_jats, "historical_JATS_canonicalizer"),
        "complete_requested_identity_authority_resolved": False})
    put("pmc_primary_source_identity_binding_contract.json", {"authority_resolved": False,
        "PMCID_binding": "existing direct article PMCID set must equal requested PMCID; missing/conflicting PMCID rejected",
        "ReferenceList_cannot_supply_primary_PMCID": True,
        "direct_JATS_PMID_comparison_authority": None, "direct_JATS_DOI_comparison_authority": None,
        "PMID_DOI_comparison_not_silently_added": True,
        "missing_JATS_PMID_DOI_are_not_newly_rejected": True,
        "incompatibility_fixture_results": probes,
        "historical_parser_and_results_unchanged": True,
        "required_next_action": "offline prospective authority resolution before D1 authorization"})
    put("pmc_body_normalization_binding.json", {"master_document_binding": ref(MASTER / "alpha3_21_construction_document_binding.json", "unchanged_BODY_only_evidence_boundary"),
        "historical_semantics": implementation(d19.source_policy.build_construction_document, "source_of_BODY_normalization_only_not_executed"),
        "body_only_projection": implementation(body_only.canonical_body, "same_BODY_traversal_and_truncation_without_document_or_anchors"),
        "Unicode": "NFKC", "within_paragraph_whitespace": "collapsed", "separator": "two LF",
        "limit": "60000 Unicode code points including separators", "ordering": "recursive BODY child order",
        "included": ["p text", "figure captions", "table captions"],
        "excluded_section_headings": sorted(d19.source_policy.OTHER_EXCLUDED_HEADINGS),
        "excluded_sec_types": ["supplementary-material", "references", "acknowledgments", "funding"],
        "bibliographic_xrefs_removed": True, "abstract_front_back_not_evidence": True,
        "future_21E_identity_firewall_not_replaced_by_BODY_availability": True,
        "construction_document_and_anchor_generation_started": False})
    put("pmc_body_paragraph_provenance_contract.json", {"fields": ["section_path", "section_headings", "kind", "ordinal", "text", "start_offset", "end_offset"],
        "units": "Unicode code points", "end_exclusive": True, "body_hash": "SHA256 of canonical BODY UTF-8 bytes",
        "paragraph_identity": "controller-side BODY hash plus paragraph position/path", "span_anchor_ids_generated": False,
        "opaque_source_tokens_generated": False})
    update_sha = freeze("updateof_structural_resolution_contract", {"authority_resolved": True,
        "rule": ref(d19_1.RULE_PATH, "existing_UpdateOf_finalization"),
        "classifier": implementation(d19_1.correction.classify, "existing_structural_state_finalization"),
        "source_type": implementation(d19.source_policy.source_type_state, "frozen_mechanical_source_type"),
        "source_type_contract": ref(state["type_path"], "SourceTypeMechanicalEligibilityV1"),
        "deferred_pmids": [s["pmid"] for s in sources if s["updateof_deferred_state"] == "DEFERRED_TO_STRUCTURE_STAGE"],
        "timing": "after OA, valid JATS, license and independent mechanical source-type facts are frozen; never before inputs exist",
        "classifier_inputs": ["frozen C2 publication_types", "frozen C2 correction_relationships", "independent_primary_state=frozen source_type_state"],
        "terminal_states": ["CLEAR", "INELIGIBLE", "UNRESOLVED"], "only_CLEAR_admitted": True,
        "nondeferred_46_sources_reclassified": False, "scientific_content_or_Builder_compatibility_used": False,
        "currently_deferred_sources_precleared": False})
    requests = requests_for(sources)
    request_sha = freeze("alpha3_21d_network_request_manifest", requests, jsonl=True)
    put("alpha3_21d_execution_order.json", {"OA_source_order": [s["pmid"] for s in sources],
        "OA_completion_barrier_before_any_JATS": True,
        "JATS_order": "OA-eligible subsequence of frozen 49-source order; compact runtime ordinal as historical client",
        "runtime_new_request_payloads_or_sources_allowed": False, "conditional_JATS_request_universe_frozen": True})
    put("alpha3_21d_technical_retry_policy.json", {"source": ref(state["failure_path"], "historical_PMC_failure_policy"),
        "client": implementation(d19.PMCTransport.fetch, "same_OA_and_JATS_transport_policy"),
        "maximum_attempts_per_request": 4, "timeout_seconds": 60, "backoff_seconds": [2, 4, 8],
        "retryable_http_status": [408, 429, 500, 502, 503, 504], "missing_HTTP_status_retryable": True,
        "HTTP_200_without_transport_error_ends_retry": True, "parse_license_identity_BODY_failure_retry_allowed": False,
        "terminal_source_failure": "record unresolved/ineligible according to frozen dimension; no replacement; continue other authorized sources"})
    put("alpha3_21d_raw_response_preservation_contract.json", {"every_attempt_before_parsing": True,
        "fields": ["logical_request_id", "PMID", "PMCID", "request_payload_sha256", "attempt", "UTC_timestamp", "HTTP_or_transport_metadata", "raw_response_path", "raw_SHA256"],
        "raw_invalid_responses_preserved": True, "normalized_JATS_preserved_separately": True})
    put("alpha3_21d_source_state_contract.json", {"source_count": 49,
        "dimensions": ["PMC acquisition", "OA subset", "license", "JATS validity", "direct identity binding", "BODY availability", "source type", "correction_update_structural", "construction_source_handoff"],
        "per_source_failure_isolation": True, "per_dimension_states_preserved": True, "identity_dimension_authority_unresolved": True,
        "zero_construction_handoff_valid": True})
    put("alpha3_21d_terminal_reason_contract.json", {"historical_D_gate_order": ["BLOCKED_OA_SUBSET", "BLOCKED_JATS", "BLOCKED_LICENSE", "BLOCKED_SOURCE_TYPE"],
        "historical_D1_updateof_failure_states": ["BLOCKED_UPDATEOF_INELIGIBLE", "BLOCKED_UPDATEOF_UNRESOLVED"],
        "identity_and_BODY_reporting_completion_deferred_to_authority_resolution": True,
        "complete_terminal_precedence_frozen": False, "no_progression_rule_invented": True})
    put("alpha3_21d_construction_source_handoff_contract.json", {"for_stage": "alpha3.21E",
        "source_maximum": 49, "only_all_relevant_frozen_dimensions_permit_progression": True,
        "fields": ["PMID", "PMCID", "DOI", "stratum", "canonical_BODY_artifact", "BODY_SHA256", "source_state_provenance", "UpdateOf_resolution_provenance"],
        "zero_handoff_valid": True, "final_handoff_generated_here": False,
        "ConstructionEvidenceDocument_or_Builder_requests_generated": False,
        "execution_blocked_until_primary_identity_authority_resolved": True})
    put("alpha3_21_fulltext_exposure_registry_contract.json", {"future_artifact": "alpha3_21_current_attempt_fulltext_exposure_registry",
        "fields": ["PMID", "PMCID", "DOI_if_known", "raw_JATS_SHA256", "canonical_BODY_SHA256_if_available", "retrieval_provenance_and_UTC_timestamp"],
        "valid_but_excluded_retrieved_sources_remain_future_exposure": True,
        "invalid_response_identifiers_are_not_authoritative": True, "current_exclusion_authority": False,
        "successful_JATS_snapshot_refresh_allowed": False})
    put("alpha3_21d_no_self_contamination_contract.json", {"current_attempt_fulltext_self_excludes": False,
        "A1_C2_master_registry_mutation_allowed": False})
    put("alpha3_21d_no_replacement_binding.json", {"C2_binding": ref(C2 / "downstream_no_replacement_audit.json", "unchanged_no_replacement"),
        "historical_failure_policy": ref(state["failure_path"], "no_failed_source_replacement"),
        "metadata_excluded_23_restored": False, "unsampled_943_used": False, "stratum_topup_allowed": False})
    put("alpha3_21d1_execution_handoff.json", {"execution_ready": False, "network_authorized": False,
        "input_sources": ref(OUT / "alpha3_21d_input_source_manifest.jsonl", "frozen_49_source_input"),
        "potential_request_universe": ref(OUT / "alpha3_21d_network_request_manifest.jsonl", "frozen_conditional_request_payloads"),
        "mandatory_OA_logical_requests": 49, "conditional_JATS_logical_requests_maximum": 49,
        "actual_JATS_count_unknown_until_OA_completion": True, "maximum_transport_attempts": 392,
        "blocked_by": ["DIRECT_JATS_PMID_DOI_COMPARISON_AUTHORITY_NOT_BOUND"],
        "separate_offline_authority_resolution_then_network_authorization_required": True})
    for name in ("builder_v4_nonuse_audit.json", "quality_nonuse_audit.json"):
        put(name, {"requests_constructed": 0, "calls": 0, "execution_started": False})
    put("fresh_primary_policy_nonadaptation_audit.json", {"OA_license_JATS_source_type_UpdateOf_scientific_rules_changed": False,
        "new_PMID_DOI_gate_silently_added": False, "request_sequence_or_retry_changed": False,
        "BODY_text_projection_only_no_document_or_anchor": True, "source_selection_changed": False})
    preflight()
    put("historical_preservation_audit.json", {"C2_C1_C_B_master_unchanged": True,
        "D19_D19_1_roots_unchanged": True, "historical_assets_modified": False})
    put("scientific_state_safety_audit.json", {**NO_CALLS, "primary_JATS_observed": False,
        "construction_evidence_document_generation_started": False, "span_anchor_generation_started": False,
        "opaque_source_token_generation_started": False, "builder_execution_started": False,
        "quality_execution_started": False, "retrieval_evaluation_started": False})
    put("execution_implementation_binding.json", implementation(run, "offline_preregistration_and_identity_gap_audit"))
    put("focused_test_implementation_binding.json", ref(ROOT / "tests/test_search_plan_v24_alpha321d_prereg_offline.py", "offline_authority_and_no_network_tests"))
    result = {"status": "failed", "stage_identity": "FRESH_PRIMARY_ALPHA3_21_PMC_OA_JATS_CONSTRUCTION_SOURCE_PREREGISTRATION",
        "alpha3_21d_classification": CLASS_BLOCKED, "blocking_reason": "DIRECT_JATS_PMID_DOI_COMPARISON_AUTHORITY_NOT_BOUND",
        "alpha3_21c2_root_verified": True, "alpha3_21_master_root_verified": True,
        "pre_oa_input_source_count": 49, "pre_oa_clear_source_count": 46, "pre_oa_deferred_source_count": 3,
        "alpha3_21d_input_source_manifest_sha256": input_sha, "pmc_acquisition_authority_resolved": False,
        "pmc_client_mechanics_resolved": True, "pmc_oa_policy_frozen": True, "pmc_license_policy_frozen": True,
        "pmc_jats_parser_authority_resolved": False, "historical_jats_parser_located": True,
        "canonical_body_policy_frozen": True, "body_only_evidence_policy_frozen": True,
        "updateof_structural_resolution_authority_resolved": True, "updateof_structural_resolution_contract_sha256": update_sha,
        "planned_pmc_logical_requests": 98, "planned_pmc_request_class_count": 2, "maximum_pmc_transport_attempts": 392,
        "mandatory_OA_requests": 49, "conditional_JATS_requests_maximum": 49, "actual_future_request_count_not_yet_known": True,
        "alpha3_21d_network_request_manifest_sha256": request_sha, "downstream_replacement_allowed": False,
        "current_attempt_fulltext_self_excludes": False, "construction_evidence_document_generation_started": False,
        "builder_execution_started": False, "quality_execution_started": False, "retrieval_evaluation_started": False,
        **NO_CALLS, "execution_ready": False, "historical_assets_modified": False,
        "next_stage_recommendation": "AUDIT_ALPHA3_21D_PRIMARY_JATS_IDENTITY_AUTHORITY_OFFLINE"}
    put("validation.json", result)
    put("summary.json", result)
    root = root_hash(OUT, ROOT_MARKER)
    put_bytes(ROOT_MARKER, (root + "\n").encode("ascii"))
    return {**result, ROOT_MARKER: root}


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result["status"] == "completed" else 1)
