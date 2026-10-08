#!/usr/bin/env python3
"""Freeze prospective D2 identity authority; never create requests or observe JATS."""

from __future__ import annotations

import json
import os
from pathlib import Path
from xml.sax.saxutils import escape

from scripts import run_search_plan_v24_alpha321d_prereg_offline as d
from scripts import search_plan_v24_alpha321_jats_primary_identity_v2 as v2


ROOT = d.ROOT
OUT = ROOT / "runs/20261007_search_plan_v24_primary_alpha3_21d1_jats_identity_authority_resolution_offline"
ROOT_MARKER = "search_plan_v24_primary_alpha3_21d1_sha256"
D_SHA = "055a6c91c07f6d8ea9ab448072cafa1fec2194d45a7e9d79c49f59bc2cd089c0"
INPUT_SHA = "015c4f3d493416996dffc41aa0b5d8bdcfa9dbded624c58ea860083a10453d53"
REQUEST_SHA = "eb5b893746e4ac62274d5d400bb54d9a4365ff1e01ac11e3eb2f9bf5c6298ab0"
UPDATEOF_SHA = "94852ae084c502a108b405cbb74a088a5cd144ebf2af96efde986b20429decac"
SAMPLE_SHA = "721ead72b454bb0cb8dee044e678c41f5e42393771726220a76cd7bee2e19a75"
CLASS_OK = "PMC_JATS_EXECUTION_AUTHORITY_RESOLVED_BEFORE_FRESH_JATS_OBSERVATION"
canonical, sha, digest, obj, rows, ref, root_hash, require = d.canonical, d.sha, d.digest, d.obj, d.rows, d.ref, d.root_hash, d.require
NO_CALLS = d.NO_CALLS
INPUT = d.OUT / "alpha3_21d_input_source_manifest.jsonl"
REQUESTS = d.OUT / "alpha3_21d_network_request_manifest.jsonl"
MASTER_MARKER = "search_plan_v24_primary_alpha3_21_master_prereg_sha256"
EXPECTED = {"expected_pmid": "123", "expected_pmcid": "PMC123", "expected_doi": "10.fixture/expected"}
PROCESSING_ORDER = ["raw response preservation", "XML/JATS structural validation",
    "direct article-id extraction", "identifier canonicalization", "internal identifier conflict detection",
    "mandatory PMCID binding", "asserted PMID consistency comparison", "asserted DOI consistency comparison",
    "primary identity state freeze", "unchanged license/BODY/source-type/UpdateOf processing"]
REQUIRED = ["alpha3_21d_root_verification.json", "alpha3_21c2_root_verification.json",
    "alpha3_21_master_root_verification.json", "alpha3_21d_input_manifest_verification.json",
    "alpha3_21d_network_manifest_preservation_audit.json", "historical_canonical_jats_identity_gap_audit.json",
    "jats_direct_article_id_scope_contract.json", "jats_pmcid_normalization_binding.json",
    "jats_pmid_normalization_binding.json", "jats_doi_normalization_binding.json",
    "jats_direct_identifier_multiplicity_contract.json", "jats_primary_source_identity_contract_v2.json",
    "jats_primary_source_identity_contract_v2_sha256", "jats_primary_identity_terminal_state_contract.json",
    "jats_secondary_identifier_missing_semantics.json", "jats_identity_processing_order.json",
    "jats_identity_fixture_manifest.json", "jats_identity_fixture_results.json",
    "historical_jats_parser_preservation_audit.json", "alpha321_pmc_jats_execution_authority_v2.json",
    "alpha321_pmc_jats_execution_authority_v2_sha256", "pmc_request_mechanics_authority_audit.json",
    "pmc_end_to_end_execution_readiness_audit.json", "alpha3_21d2_execution_handoff.json",
    "fresh_jats_not_observed_audit.json", "scientific_policy_nonadaptation_audit.json",
    "no_replacement_binding.json", "historical_preservation_audit.json",
    "scientific_state_safety_audit.json", "validation.json", "summary.json"]


def put_bytes(name: str, raw: bytes) -> str:
    path = OUT / name
    require(path.resolve().is_relative_to(OUT.resolve()), "OUTPUT_PATH_ESCAPE")
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return sha(raw)


def put(name, value):
    return put_bytes(name, canonical(value) + b"\n")


def freeze(stem, value):
    value_sha = put(stem + ".json", value)
    put_bytes(stem + "_sha256", (value_sha + "\n").encode("ascii"))
    return value_sha


def binding(name, role):
    return ref(d.OUT / name, role)


def preflight():
    require((d.OUT / d.ROOT_MARKER).read_text().strip() == D_SHA
            and root_hash(d.OUT, d.ROOT_MARKER) == D_SHA, "D_ROOT_MISMATCH")
    state = d.preflight()
    summary = obj(d.OUT / "summary.json")
    require(summary["status"] == "failed" and summary["alpha3_21d_classification"] == d.CLASS_BLOCKED
            and summary["pmc_client_mechanics_resolved"] is True
            and all(summary[k] == 0 for k in NO_CALLS), "D_FAILED_PREREG_STATE_MISMATCH")
    for filename, expected in ((INPUT.name, INPUT_SHA), (REQUESTS.name, REQUEST_SHA),
                              ("updateof_structural_resolution_contract.json", UPDATEOF_SHA)):
        path = d.OUT / filename
        require(digest(path) == expected and (d.OUT / (path.stem + "_sha256")).read_text().strip() == expected,
                "D_ARTIFACT_HASH_MISMATCH:" + filename)
    require(digest(d.B / "sampled_source_manifest.jsonl") == SAMPLE_SHA, "SAMPLE_HASH_MISMATCH")
    sources, requests = rows(INPUT), rows(REQUESTS)
    require(len(sources) == len({s["pmid"] for s in sources}) == 49
            and [s["pmid"] for s in sources] == [s["pmid"] for s in state["sources"]], "D_INPUT_MISMATCH")
    for source, original in zip(sources, state["sources"]):
        facts = state["facts"][source["pmid"]]
        require(all(source[k] == value for k, value in original.items())
                and source["c2_source_state_sha256"] == sha(canonical(facts))
                and source["pmcid"] == facts["direct_pmcid"] and source["doi"] == facts["direct_doi"],
                "IMMUTABLE_C2_EXPECTED_IDENTITY_MISMATCH")
    require(len(requests) == len({r["logical_request_id"] for r in requests}) == 98
            and [r["source_provenance"] for r in requests[:49]] == sources
            and [r["source_provenance"] for r in requests[49:]] == sources
            and all(r["request_class"] == "PMC_OA_SUBSET" for r in requests[:49])
            and all(r["request_class"] == "PMC_JATS" and "OA_SUBSET_ELIGIBLE" in r["activation_condition"] for r in requests[49:])
            and all(r["network_authorized"] is False and r["request_payload_sha256"] == sha(canonical(r["request_payload"]))
                    for r in requests), "FROZEN_REQUEST_UNIVERSE_MISMATCH")
    for path in sorted(d.OUT.glob("*.json")):
        d.checked_tree(obj(path))
    historical = d.implementation(d.d19.frozen_rules.canonical_jats, "unchanged_historical_parser")
    require(historical["sha256"] == "0d8527913c20de75fab29e15cfd79009a1407195cbe0d4131054ec49ef4721d3"
            and historical["entrypoint_source_sha256"] == "652fb8a87f88d780cf6e4f9f9891311e73e54702cdddbd27fb46b2d8c4ee664c",
            "HISTORICAL_PARSER_MODIFIED")
    return {**state, "input_sources": sources, "historical_parser": historical}


def synthetic_xml(ids, *, outside="", namespace=False):
    content = "".join('<article-id pub-id-type="' + kind + '">' + escape(value) + '</article-id>' for kind, value in ids)
    xmlns = ' xmlns="urn:synthetic-jats"' if namespace else ""
    return '<article' + xmlns + '><front><article-meta>' + content + '</article-meta></front><body/>' + outside + '</article>'


def identity_fixtures():
    base = [("pmc", "123"), ("pmid", "123"), ("doi", "10.fixture/expected")]
    fixtures = []

    def add(name, ids, expected=v2.SUCCESS, *, outside="", namespace=False, expected_identity=None, raw=None, diagnostics=None):
        fixtures.append({"fixture_id": name, "origin": "OFFLINE_SYNTHETIC_NOT_PRIMARY_SOURCE_JATS",
            "raw_xml": raw if raw is not None else synthetic_xml(ids, outside=outside, namespace=namespace),
            "expected_identity": EXPECTED if expected_identity is None else expected_identity,
            "expected_identity_state": expected, "expected_diagnostics": diagnostics or {}})

    add("correct_all", base)
    add("missing_pmid", [base[0], base[2]], diagnostics={"pmid": "JATS_DIRECT_PMID_NOT_ASSERTED"})
    add("missing_doi", base[:2], diagnostics={"doi": "JATS_DIRECT_DOI_NOT_ASSERTED"})
    add("missing_both_secondary", base[:1], diagnostics={"pmid": "JATS_DIRECT_PMID_NOT_ASSERTED", "doi": "JATS_DIRECT_DOI_NOT_ASSERTED"})
    add("wrong_pmcid", [("pmc", "456"), *base[1:]], "JATS_PRIMARY_PMCID_MISMATCH")
    add("wrong_pmid", [base[0], ("pmid", "999"), base[2]], "JATS_DIRECT_PMID_MISMATCH")
    add("wrong_doi", [*base[:2], ("doi", "10.fixture/other")], "JATS_DIRECT_DOI_MISMATCH")
    add("wrong_both_secondary", [base[0], ("pmid", "999"), ("doi", "10.fixture/other")], "JATS_DIRECT_PMID_MISMATCH",
        diagnostics={"doi": "JATS_DIRECT_DOI_MISMATCH"})
    add("duplicate_equal_pmid", [*base, ("pmid", "PMID:123")])
    add("conflicting_pmid", [*base, ("pmid", "999")], v2.CONFLICT)
    add("duplicate_equal_doi", [*base, ("doi", "https://doi.org/10.FIXTURE/EXPECTED.")])
    add("conflicting_doi", [*base, ("doi", "10.fixture/other")], v2.CONFLICT)
    add("missing_pmcid", base[1:], "JATS_PRIMARY_PMCID_MISSING")
    reference = lambda kind, value: '<back><ref-list><ref><article-id pub-id-type="' + kind + '">' + value + '</article-id></ref></ref-list></back>'
    add("pmcid_only_reference_list", base[1:], "JATS_PRIMARY_PMCID_MISSING", outside=reference("pmc", "123"))
    add("pmid_only_reference_list", [base[0], base[2]], outside=reference("pmid", "999"), diagnostics={"pmid": "JATS_DIRECT_PMID_NOT_ASSERTED"})
    add("doi_only_reference_list", base[:2], outside=reference("doi", "10.fixture/other"), diagnostics={"doi": "JATS_DIRECT_DOI_NOT_ASSERTED"})
    add("duplicate_equal_pmcid", [*base, ("pmcid", "pmc123")])
    add("conflicting_pmcid", [*base, ("pmcid", "PMC456")], v2.CONFLICT)
    add("normalization_and_type_case", [("PMCID", " pmc123 "), ("PMID", " PMID: 123 "), ("DOI", "HTTPS://DX.DOI.ORG/10.FIXTURE/EXPECTED.")])
    add("no_numeric_closeness", [base[0], ("pmid", "0123"), base[2]], "JATS_DIRECT_PMID_MISMATCH")
    add("unknown_type_not_pmid", [base[0], ("pubmed", "999"), base[2]], diagnostics={"pmid": "JATS_DIRECT_PMID_NOT_ASSERTED"})
    add("unknown_type_not_pmcid", [("pmc-id", "123"), *base[1:]], "JATS_PRIMARY_PMCID_MISSING")
    add("empty_pmcid", [("pmc", ""), *base[1:]], "JATS_PRIMARY_PMCID_MISSING")
    add("empty_pmid_not_absent", [base[0], ("pmid", ""), base[2]], v2.UNRESOLVED)
    add("empty_doi_not_absent", [*base[:2], ("doi", "doi:")], v2.UNRESOLVED)
    add("empty_plus_matching_assertion", [*base, ("pmid", "")], v2.UNRESOLVED)
    add("doi_new_assertion", base, expected_identity={**EXPECTED, "expected_doi": None}, diagnostics={"doi": "JATS_DIRECT_DOI_NEW_ASSERTION"})
    add("doi_new_cannot_rescue_pmcid", base[1:], "JATS_PRIMARY_PMCID_MISSING", expected_identity={**EXPECTED, "expected_doi": None})
    add("malformed_xml", [], None, raw="<article>")
    add("multiple_articles", [], None, raw="<set><article/><article/></set>")
    add("no_article", [], None, raw="<root/>")
    add("namespace_direct_chain", base, namespace=True)
    add("related_supplement_updateof_ids_ignored", base, outside='<related-article><article-id pub-id-type="doi">10.fixture/other</article-id></related-article><supplementary-material><article-id pub-id-type="pmid">999</article-id></supplementary-material><UpdateOf><article-id pub-id-type="pmc">456</article-id></UpdateOf>')
    nested = '<article><front><article-meta><custom><article-id pub-id-type="pmc">123</article-id></custom></article-meta></front></article>'
    add("nested_article_id_not_direct", [], "JATS_PRIMARY_PMCID_MISSING", raw=nested)
    return fixtures


def fixture_results(fixtures):
    results = []
    for fixture in fixtures:
        result = v2.validate_jats_primary_identity_v2(fixture["raw_xml"].encode(), **fixture["expected_identity"])
        require(result["identity_state"] == fixture["expected_identity_state"], "IDENTITY_FIXTURE_FAILED:" + fixture["fixture_id"])
        require(all(result["per_identifier_states"][k] == value for k, value in fixture["expected_diagnostics"].items()), "IDENTITY_DIAGNOSTIC_FAILED")
        require(result["source_identity_allows_progression"] is (fixture["expected_identity_state"] == v2.SUCCESS), "IDENTITY_PROGRESSION_FAILED")
        require(canonical(result) == canonical(v2.validate_jats_primary_identity_v2(fixture["raw_xml"].encode(), **fixture["expected_identity"])), "IDENTITY_NOT_DETERMINISTIC")
        results.append({"fixture_id": fixture["fixture_id"], "passed": True, "result": result})
    return results


def run():
    require(not OUT.exists(), "D1_OUTPUT_ALREADY_EXISTS_NO_OVERWRITE")
    state = preflight()
    fixtures = identity_fixtures()
    results = fixture_results(fixtures)
    probes = d.identity_gap_probe()
    for probe in probes:
        probe["new_v2_result"] = v2.validate_jats_primary_identity_v2(probe["synthetic_xml"].encode(), **EXPECTED)
        require(probe["historical_canonicalizer_accepts"] and not probe["new_v2_result"]["source_identity_allows_progression"], "IDENTITY_GAP_REGRESSION")
    OUT.mkdir()
    for name, path, marker, expected in (("alpha3_21d", d.OUT, d.ROOT_MARKER, D_SHA),
        ("alpha3_21c2", d.C2, d.c2.ROOT_MARKER, d.C2_SHA), ("alpha3_21_master", d.MASTER, MASTER_MARKER, d.c2.authority.c.b.MASTER_SHA)):
        put(name + "_root_verification.json", {"verified": True, "root_sha256": expected,
            "root_marker": ref(path / marker, "unchanged_upstream_root"), "historical_artifacts_modified": False})
    put("alpha3_21d_input_manifest_verification.json", {"verified": True,
        "input_manifest": ref(INPUT, "unchanged_49_C2_expected_identities"), "source_count": 49,
        "clear_source_count": 46, "UpdateOf_deferred_source_count": 3,
        "C2_direct_identity_facts": ref(d.C2 / "metadata_final_source_states.jsonl", "immutable_primary_metadata_identity_authority"),
        "C2_handoff": ref(d.C2 / "alpha3_21d_pre_oa_source_handoff.json", "unchanged_C2_boundary"),
        "sample": ref(d.B / "sampled_source_manifest.jsonl", "unchanged_sample"), "all_49_identity_provenances_verified": True,
        "metadata_exclusions_restored": False, "replacement_or_resampling_used": False})
    put("alpha3_21d_network_manifest_preservation_audit.json", {"request_manifest": ref(REQUESTS, "only_authoritative_D2_request_universe"),
        "unchanged": True, "replacement_request_manifest_created": False, "requests_regenerated": False,
        "mandatory_OA_logical_requests": 49, "conditional_JATS_logical_requests_maximum": 49,
        "maximum_transport_attempts": 392, "JATS_condition": "OA_SUBSET_ELIGIBLE and all 49 OA requests terminal",
        "frozen_activation_conditions_not_rewritten": True,
        "activation_naming_overlay": "D2 is the future execution epoch; original D1 authorization placeholders require separate explicit D2 authorization"})
    put("historical_canonical_jats_identity_gap_audit.json", {"historical_parser": state["historical_parser"], "synthetic_probes": probes,
        "historical_checks": ["parseable XML", "exactly one article", "direct PMCID set equals expected"],
        "PMID_DOI_comparison_previously_absent": True, "absence_is_not_stronger_conflicting_authority": True,
        "explicit_D_identity_authority_unresolved": binding("pmc_primary_source_identity_binding_contract.json", "previous_unresolved_authority"),
        "stronger_frozen_conflicting_authority_found": False, "prospective_V2_explicitly_authorized": True,
        "historical_results_recomputed_or_reinterpreted": False})
    put("jats_direct_article_id_scope_contract.json", {"scope": v2.SCOPE,
        "extraction": d.implementation(v2.direct_identifiers, "direct_child_identifier_extraction_only"),
        "structural_guard": d.implementation(v2.select_primary_article, "unchanged_XML_and_article_count_guards"),
        "historical_guard": state["historical_parser"], "namespace_handling": "existing local-name semantics",
        "pub_id_type_spellings": v2.TYPE_MAP, "pub_id_type_comparison": "casefold only; no new spellings or aliases",
        "vocabulary_authority": [binding("pmc_jats_response_validity_contract.json", "historical_pmc_pmcid_vocabulary"),
            d.implementation(d.identity_gap_probe, "already_frozen_pmid_doi_vocabulary")],
        "identifier_text": d.implementation(v2.policy.node_text, "unchanged_identifier_text_extraction"),
        "arbitrary_descendant_article_id_scan": False,
        "excluded": ["ref-list", "ReferenceList", "citations", "related-article", "supplements", "correction targets", "UpdateOf targets"]})
    normalization_sha = {}
    descriptions = {
        "pmcid": "strip surrounding whitespace; remove case-insensitive leading pmc; prefix PMC for digits; otherwise uppercase; no numeric reinterpretation",
        "pmid": "strip surrounding whitespace; remove case-insensitive leading pmid: and following whitespace; no numeric conversion or leading-zero removal",
        "doi": "strip surrounding whitespace; remove doi: or http(s)://(dx.)doi.org/ prefix; casefold; rstrip dot/space"}
    for kind in ("pmcid", "pmid", "doi"):
        normalization_sha[kind] = put("jats_" + kind + "_normalization_binding.json", {
            "identifier_type": kind, "normalizer": d.implementation(v2.normalize_identifier, "existing_exact_identifier_normalization"),
            "expected_and_asserted_same_normalizer": True, "comparison": "exact canonical equality",
            "description": descriptions[kind], "fuzzy_or_numeric_matching": False,
            "C2_normalization_authority": d.implementation(d.c2.v2.parse_source, "unchanged_C2_primary_identifier_parser")})
    put("jats_direct_identifier_multiplicity_contract.json", {"supported_types": ["pmcid", "pmid", "doi"],
        "same_canonical_values": "DIRECT_IDENTIFIER_REDUNDANT_SAME_VALUE", "multiple_distinct_values": v2.CONFLICT,
        "multiplicity_and_each_raw_assertion_preserved": True, "conflict_blocks_identity": True,
        "majority_vote_or_preferred_value": False,
        "recognized_empty_or_unusable_assertion": "UNRESOLVED; no usable PMCID is PMCID_MISSING; never silent secondary absence"})
    put("jats_primary_identity_terminal_state_contract.json", {"success": v2.SUCCESS,
        "failure_states_in_reporting_precedence": v2.FAILURE_PRECEDENCE,
        "per_identifier_states_and_all_failures_preserved": True, "precedence_is_reporting_only": True,
        "XML_parse_or_article_count_failure": "JATS_FAILED_NO_REPLACEMENT", "XML_failure_is_identifier_mismatch": False,
        "invalid_controller_expected_identity": "abort D2 controller before processing, never derive expected identity from response",
        "failure_blocks_all_downstream_progression": True, "license_BODY_UpdateOf_cannot_rescue": True})
    put("jats_secondary_identifier_missing_semantics.json", {"PMID": "PRESENT_MUST_AGREE_ABSENT_NOT_MISMATCH",
        "DOI": "PRESENT_MUST_AGREE_WHEN_C2_HAS_EXPECTED_DOI_ABSENT_NOT_MISMATCH",
        "missing_PMID": "JATS_DIRECT_PMID_NOT_ASSERTED", "missing_DOI": "JATS_DIRECT_DOI_NOT_ASSERTED",
        "missing_secondary_blocks": False, "missing_secondary_strengthens_identity": False,
        "expected_DOI_absent_direct_DOI_present": "JATS_DIRECT_DOI_NEW_ASSERTION",
        "new_DOI_only_authoritative_when_primary_identity_bound": True, "new_DOI_replaces_PMCID_anchor": False})
    put("jats_identity_processing_order.json", {"order": PROCESSING_ORDER, "all_OA_terminal_before_JATS": True,
        "original_D_order": binding("alpha3_21d_execution_order.json", "unchanged_request_sequence"),
        "identity_must_pass_before_downstream": True, "raw_failures_preserved": True})
    identity_sha = freeze("jats_primary_source_identity_contract_v2", {"schema_version": v2.VERSION,
        "prospective_only": True, "expected_identity_authority": ref(INPUT, "immutable_C2_expected_identities"),
        "expected_PMID": "sampled PMID; never overwritten by JATS", "expected_PMCID_DOI": "frozen C2 direct article IDs",
        "normalization_bindings": {kind: ref(OUT / ("jats_" + kind + "_normalization_binding.json"), "canonical_" + kind) for kind in normalization_sha},
        "scope": ref(OUT / "jats_direct_article_id_scope_contract.json", "only_primary_direct_identifiers"),
        "multiplicity": ref(OUT / "jats_direct_identifier_multiplicity_contract.json", "conflicts_block_equal_redundancy_allowed"),
        "secondary_missing": ref(OUT / "jats_secondary_identifier_missing_semantics.json", "missing_nonblocking_not_positive_evidence"),
        "terminal_states": ref(OUT / "jats_primary_identity_terminal_state_contract.json", "all_failure_dimensions_preserved"),
        "processing_order": ref(OUT / "jats_identity_processing_order.json", "identity_gate_before_downstream"),
        "validator": d.implementation(v2.validate_jats_primary_identity_v2, "prospective_identity_validator_V2"),
        "mandatory_PMCID": True, "PMCID_comparison": "singleton canonical direct PMCID must equal expected C2 PMCID",
        "PMID_comparison": "if asserted, singleton canonical direct PMID must equal sampled PMID",
        "DOI_comparison": "if asserted and expected DOI exists, singleton canonical DOI must equal expected DOI",
        "success_iff": "exact mandatory PMCID; no supported internal conflicts; every asserted expected secondary constraint agrees; no other integrity failure",
        "internal_conflict_winner_selected": False, "expected_identifiers_replaced": False,
        "future_exposure": "identity-bound direct assertions authoritative even if later license/BODY/source-type exclude; unbound/conflicting observations audit-only nonauthoritative",
        "current_attempt_self_exclusion": False, "zero_identity_valid_sources_is_valid_outcome": True})
    put("jats_identity_fixture_manifest.json", {"fixture_count": len(fixtures), "fixtures": fixtures,
        "all_synthetic": True, "fresh_primary_JATS_observed": False, "source_XML_files_parsed": 0,
        "historical_XML_bytes_used_only_for_existing_root_hash_verification": True})
    put("jats_identity_fixture_results.json", {"fixture_count": len(results), "all_passed": True,
        "results": results, "deterministic_replay_passed": True})
    put("historical_jats_parser_preservation_audit.json", {"parser_before": state["historical_parser"],
        "parser_after": d.implementation(d.d19.frozen_rules.canonical_jats, "unchanged_historical_parser"),
        "historical_canonical_jats_modified": False, "historical_behavior_preserved": True,
        "historical_test_expectations_modified": False, "gap_probes_preserve_old_acceptance": True,
        "V2_is_separate_callable_not_monkeypatch": True})
    composite_sha = freeze("alpha321_pmc_jats_execution_authority_v2", {
        "schema_version": "Alpha321PmcJatsExecutionAuthorityV2", "D_root_sha256": D_SHA, "C2_root_sha256": d.C2_SHA,
        "prospective_overlay": "only JATS direct identity authority and completed identity/BODY terminal reporting; historical artifacts stay unchanged",
        "input_sources": ref(INPUT, "unchanged_49_source_universe"), "network_requests": ref(REQUESTS, "only_frozen_98_potential_requests"),
        "OA_policy": binding("pmc_oa_policy_binding.json", "unchanged_OA_subset_rules"),
        "license_policy": binding("pmc_license_policy_binding.json", "unchanged_article_level_license_V2"),
        "JATS_structure": {"historical_contract": binding("pmc_jats_response_validity_contract.json", "historical_parseability_and_article_count"),
            "structural_only_projection": d.implementation(v2.select_primary_article, "same_XML_article_guards_no_old_identity_fallback"),
            "old_identity_check_not_double_applied": True, "V2_normalized_PMCID_binding_is_authoritative": True},
        "primary_identity": ref(OUT / "jats_primary_source_identity_contract_v2.json", "prospective_exact_identity_V2"),
        "BODY_policy": binding("pmc_body_normalization_binding.json", "unchanged_canonical_BODY_only"),
        "BODY_provenance": binding("pmc_body_paragraph_provenance_contract.json", "unchanged_BODY_provenance_no_span_anchors"),
        "source_type": ref(state["type_path"], "unchanged_mechanical_source_type"),
        "UpdateOf": binding("updateof_structural_resolution_contract.json", "unchanged_deferred_structural_finalization"),
        "retry": binding("alpha3_21d_technical_retry_policy.json", "unchanged_four_attempt_transport_policy"),
        "raw_preservation": binding("alpha3_21d_raw_response_preservation_contract.json", "unchanged_every_attempt_before_parse"),
        "request_order": binding("alpha3_21d_execution_order.json", "all_OA_terminal_before_conditional_JATS"),
        "source_state": binding("alpha3_21d_source_state_contract.json", "retain_each_dimension_replace_unresolved_identity_only"),
        "handoff": binding("alpha3_21d_construction_source_handoff_contract.json", "unchanged_all_required_dimensions_pass"),
        "exposure": binding("alpha3_21_fulltext_exposure_registry_contract.json", "identity_bound_only_authoritative_future_exposure"),
        "no_self_contamination": binding("alpha3_21d_no_self_contamination_contract.json", "no_current_self_exclusion_or_registry_mutation"),
        "no_replacement": binding("alpha3_21d_no_replacement_binding.json", "unchanged_no_replacement"),
        "processing_order": PROCESSING_ORDER,
        "primary_reporting_order": ["BLOCKED_OA_SUBSET", "BLOCKED_JATS", "BLOCKED_PRIMARY_IDENTITY", "BLOCKED_LICENSE",
            "BLOCKED_BODY_UNAVAILABLE", "BLOCKED_SOURCE_TYPE", "BLOCKED_UPDATEOF_INELIGIBLE", "BLOCKED_UPDATEOF_UNRESOLVED", "CONSTRUCTION_SOURCE_ELIGIBLE"],
        "reporting_precedence_does_not_change_eligibility": True, "all_dimension_failures_preserved": True,
        "source_failure_isolation": True, "zero_handoff_valid": True,
        "D_old_incomplete_readiness_flags_superseded_only_for_prospective_D2": True,
        "scientific_policy_changed": False, "network_authorized": False})
    put("pmc_request_mechanics_authority_audit.json", {"resolved": True,
        "client": binding("pmc_acquisition_client_authority.json", "unchanged_PMC_client_mechanics"),
        "retry": binding("alpha3_21d_technical_retry_policy.json", "unchanged_retry_and_failure_isolation"),
        "request_sequence_or_grouping_changed": False, "new_transport_constructed": False})
    put("pmc_end_to_end_execution_readiness_audit.json", {"resolved": True, "execution_ready": True,
        "authority": ref(OUT / "alpha321_pmc_jats_execution_authority_v2.json", "complete_prospective_execution_authority"),
        "client_OA_license_JATS_identity_BODY_UpdateOf_retry_no_replacement_all_bound": True,
        "network_request_manifest_unchanged": True, "fresh_JATS_observed": False,
        "execution_started": False, "separate_D2_network_authorization_required": True})
    put("alpha3_21d2_execution_handoff.json", {"execution_ready": True, "network_authorized": False,
        "input_sources": ref(INPUT, "consume_original_49_source_manifest"), "network_requests": ref(REQUESTS, "consume_original_frozen_network_manifest"),
        "execution_authority": ref(OUT / "alpha321_pmc_jats_execution_authority_v2.json", "D2_authority"),
        "mandatory_OA_requests": 49, "conditional_JATS_requests_maximum": 49, "maximum_attempts": 392,
        "clear_sources": 46, "deferred_UpdateOf_sources": 3, "all_49_sources_preserved": True,
        "actual_JATS_count_not_yet_known": True, "later_construction_documents_or_anchors_not_authorized": True,
        "next_stage": "AUTHORIZE_ALPHA3_21D2_PMC_OA_JATS_NETWORK_EXECUTION"})
    put("fresh_jats_not_observed_audit.json", {"fresh_jats_observed": False, "fresh_XML_files_read": 0,
        "fixtures_only": "in-memory synthetic XML plus already-frozen synthetic D gap probes",
        "D2_started": False, **NO_CALLS})
    unchanged = {key: False for key in ("sample_changed", "network_request_manifest_changed", "oa_policy_changed",
        "license_policy_changed", "body_policy_changed", "updateof_policy_changed", "scientific_policy_changed",
        "source_queries_changed", "cohort_changed", "sampling_seed_changed", "source_type_policy_changed")}
    put("scientific_policy_nonadaptation_audit.json", {**unchanged, "primary_source_identity_integrity_V2_prospectively_authorized": True,
        "fresh_data_or_scientific_outcomes_used": False})
    put("no_replacement_binding.json", {"binding": binding("alpha3_21d_no_replacement_binding.json", "unchanged_no_replacement"),
        "identity_failure": "exclude and preserve raw response; never retry identity or replace source",
        "zero_construction_sources_permitted": True, "replacements": 0})
    preflight()
    put("historical_preservation_audit.json", {"D_C2_master_and_inherited_roots_unchanged": True,
        "D_failed_classification_unchanged": True, "sample_sha256": SAMPLE_SHA,
        "input_sha256": INPUT_SHA, "network_manifest_sha256": REQUEST_SHA,
        "UpdateOf_contract_sha256": UPDATEOF_SHA, "historical_assets_modified": False})
    put("scientific_state_safety_audit.json", {**NO_CALLS, "fresh_jats_observed": False,
        "construction_evidence_documents_generated": 0, "span_anchors_generated": 0, "opaque_source_tokens_generated": 0,
        "Builder_requests_generated": 0, "Quality_requests_generated": 0, "heldout_cases_generated": 0,
        "scientific_selection_or_relevance_adjudication_performed": False})
    put("execution_implementation_binding.json", d.implementation(run, "offline_D1_authority_freeze"))
    put("focused_test_implementation_binding.json", ref(ROOT / "tests/test_search_plan_v24_alpha321d1_identity_authority_offline.py", "V2_synthetic_and_offline_preservation_tests"))
    result = {"status": "completed", "alpha3_21d1_classification": CLASS_OK,
        "alpha3_21d_root_verified": True, "alpha3_21c2_root_verified": True, "alpha3_21_master_root_verified": True,
        "pre_oa_input_source_count": 49, "pre_oa_clear_source_count": 46, "pre_oa_deferred_source_count": 3,
        "alpha3_21d_network_request_manifest_sha256": REQUEST_SHA, "alpha3_21d_network_request_manifest_unchanged": True,
        "fresh_jats_observed": False, "direct_jats_article_id_scope_resolved": True,
        "expected_pmcid_required": True, "missing_direct_pmcid_blocks_identity": True, "mismatched_direct_pmcid_blocks_identity": True,
        "direct_pmid_present_must_match": True, "missing_direct_pmid_blocks_identity": False, "mismatched_direct_pmid_blocks_identity": True,
        "direct_doi_present_must_match": True, "missing_direct_doi_blocks_identity": False, "mismatched_direct_doi_blocks_identity": True,
        "multiple_distinct_direct_identifier_values_fail_closed": True, "duplicate_equal_direct_identifier_values_allowed": True,
        "jats_primary_source_identity_contract_v2_frozen": True, "jats_primary_source_identity_contract_v2_sha256": identity_sha,
        "historical_canonical_jats_modified": False, "historical_jats_behavior_preserved": True,
        "pmc_request_mechanics_resolved": True, "pmc_end_to_end_execution_authority_resolved": True,
        "alpha321_pmc_jats_execution_authority_v2_sha256": composite_sha,
        "identity_fixture_count": len(fixtures), "all_identity_fixtures_passed": True,
        **unchanged, **NO_CALLS, "network_authorized": False,
        "next_stage_recommendation": "AUTHORIZE_ALPHA3_21D2_PMC_OA_JATS_NETWORK_EXECUTION", "historical_assets_modified": False}
    put("validation.json", result)
    put("summary.json", result)
    require(all((OUT / name).is_file() for name in REQUIRED), "REQUIRED_ARTIFACT_MISSING")
    for path in sorted(OUT.glob("*.json")):
        d.checked_tree(obj(path))
    root = root_hash(OUT, ROOT_MARKER)
    put_bytes(ROOT_MARKER, (root + "\n").encode("ascii"))
    require(root_hash(OUT, ROOT_MARKER) == root, "OUTPUT_ROOT_VERIFICATION_FAILED")
    return {**result, ROOT_MARKER: root}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
