#!/usr/bin/env python3
"""Append-only terminal closure. Read frozen states; never execute their policies.

This module contains no acquisition, parser, retry classifier, sampling,
Builder, Quality, or evaluation implementation. Unknown final counts stay null.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

from scripts import run_search_plan_v24_alpha321d22_final_retry_authority_offline as terminal


ROOT, prior, d2 = terminal.ROOT, terminal.prior, terminal.d2
d1, d = d2.d1, d2.d1.d
c2, c1, c, b = d.c2, d.c2.authority, d.c2.authority.c, d.c2.authority.c.b
OUT = ROOT / "runs/20261007_search_plan_v24_primary_alpha3_21_terminal_incomplete_closure_offline"
ROOT_MARKER = "search_plan_v24_primary_alpha3_21_terminal_closure_sha256"
REGISTRY_MARKER = "alpha3_21_future_contamination_registry_sha256"
STAGE = "FRESH_PRIMARY_ALPHA3_21_TERMINAL_INCOMPLETE_CLOSURE"
CLASSIFICATION = "TERMINATED_INCOMPLETE_AT_D2_RUNTIME_AUTHORITY_GAP"
NEXT = "DESIGN_POST_ALPHA3_21_RUNTIME_HARDENING_PROTOCOL_BEFORE_NEXT_FRESH_ATTEMPT"
D22_SHA = "188ca6993ade152bede08c1baabaa42d07f050378e4b50c4b857da3f1ff2737f"
NO_CALLS = dict(prior.NO_CALLS)
canonical, sha, digest, obj, rows, ref, require = (
    prior.canonical, prior.sha, prior.digest, prior.obj, prior.rows, prior.ref, prior.require)
root_hash = prior.root_hash
TEST = ROOT / "tests/test_search_plan_v24_alpha321_terminal_closure_offline.py"
PHASES = (
    ("master", d2.MASTER, d1.MASTER_MARKER, b.MASTER_SHA),
    ("21A", b.A, "search_plan_v24_primary_alpha3_21a_prereg_sha256", b.A_SHA),
    ("21A1", b.A1, "search_plan_v24_primary_alpha3_21a1_sha256", b.A1_SHA),
    ("21B", b.OUT, b.ROOT_MARKER, c.B_SHA),
    ("21C", c.OUT, c.ROOT_MARKER, c1.C_SHA),
    ("21C.1", c1.OUT, c1.ROOT_MARKER, c2.C1_SHA),
    ("21C2", d2.C2, c2.ROOT_MARKER, d.C2_SHA),
    ("21D", d2.D, d.ROOT_MARKER, d1.D_SHA),
    ("21D.1", d2.D1, d1.ROOT_MARKER, d2.D1_SHA),
    ("21D2", d2.OUT, d2.ROOT_MARKER, prior.D2_SHA),
    ("21D2.1", prior.OUT, prior.ROOT_MARKER, terminal.D21_SHA),
    ("21D2.2", terminal.OUT, terminal.ROOT_MARKER, D22_SHA),
)
REQUIRED = (
    "alpha3_21_master_root_verification", "alpha3_21_phase_root_inventory",
    "alpha3_21_terminal_authority_verification", "alpha3_21_complete_source_funnel",
    "alpha3_21_metadata_funnel", "alpha3_21_oa_jats_partial_funnel",
    "alpha3_21_runtime_terminal_reason", "alpha3_21_partial_handoff_semantics",
    "alpha3_21_builder_state", "alpha3_21_quality_state", "alpha3_21_retrieval_evaluation_state",
    "alpha3_21_final_pool_state", "alpha3_21_llm_inference_accounting", "alpha3_21_network_accounting",
    "alpha3_21_source_exposure_summary", "alpha3_21_metadata_identity_exposure_summary",
    "alpha3_21_fulltext_exposure_summary", "alpha3_21_body_exposure_summary",
    "alpha3_21_future_contamination_registry", "alpha3_21_future_contamination_counts",
    "alpha3_21_candidate_contamination_state", "alpha3_21_incomplete_attempt_assets_remain_seen_contract",
    "alpha3_21_publication_safe_interpretation", "alpha3_21_engineering_lessons",
    "alpha3_21_no_post_outcome_repair_audit", "builder_v4_nonchange_audit", "quality_v2_nonchange_audit",
    "search_plan_non_evaluation_audit", "future_development_boundary",
    "known_preexisting_test_environment_issue", "historical_preservation_audit",
    "scientific_state_safety_audit", "protocol_compliance_audit", "validation", "summary",
)
LONG = (
    "Alpha3.21 prospectively constructed a fresh 2026 source cohort and froze a 72-source stratified sample. "
    "Deterministic metadata screening produced a 49-source pre-OA handoff, of which 47 were OA-eligible. "
    "During the prospectively frozen JATS acquisition stage, nine activated JATS requests completed successfully "
    "before the tenth encountered an interrupted response-body read. Because the preexisting retry authority "
    "did not uniquely determine whether this failure class was retryable, the attempt was terminated fail-closed "
    "without continuing the remaining JATS requests. Consequently no complete construction-source cohort, fresh "
    "Builder V4 output, Quality V2 adjudication, or Search Plan retrieval evaluation was derived."
)
SHORT = (
    "Alpha3.21 was terminated incomplete during JATS acquisition because the pre-registered runtime authority "
    "did not resolve retry semantics for an interrupted response-body read. No fresh Builder, Quality, or "
    "retrieval evaluation was performed."
)


def exact_ids(records, field="pmid", *, optional=False):
    values = []
    for record in records:
        value = record.get(field)
        if optional and value is None:
            continue
        require(isinstance(value, str) and value == value.strip() and bool(value),
                "IDENTITY_UNRESOLVED:" + field)
        if field == "pmid":
            require(re.fullmatch(r"[1-9][0-9]*", value) is not None, "INVALID_PMID")
        elif field == "pmcid":
            require(re.fullmatch(r"PMC[1-9][0-9]*", value) is not None, "INVALID_PMCID")
        elif field == "doi":
            require(re.fullmatch(r"10\.[0-9]+/\S+", value) is not None, "INVALID_DIRECT_DOI")
        values.append(value)
    return set(values)


def unique_ids(records, field="pmid"):
    values = exact_ids(records, field)
    require(len(values) == len(records), "DUPLICATE_IDENTITY:" + field)
    return values


def expect(actual, expected, label):
    require(actual == expected, "FROZEN_COUNT_OR_STATE_MISMATCH:" + label)


def verify_roots():
    inventory = []
    for name, directory, marker, expected in PHASES:
        check = prior.root_check(directory, marker, expected)
        summary = obj(directory / "summary.json")
        inventory.append({"phase": name, "directory": str(directory.relative_to(ROOT)),
                          "execution_status": summary["status"], **check})
    statuses = {i["phase"]: i["execution_status"] for i in inventory}
    expect(statuses, {name: "failed" if name in {"21C", "21D", "21D2"} else "completed"
                      for name, *_ in PHASES}, "historical_phase_truth")
    return inventory


def attempt_accounting(path):
    """Count preserved events by identity; hash responses without parsing them."""
    records = rows(path)
    grouped = defaultdict(list)
    for record in records:
        grouped[record["logical_request_id"]].append(record)
        raw = path.parent / record["raw_path"]
        require(raw.resolve().is_relative_to(path.parent) and not raw.is_symlink(), "RAW_PATH_ESCAPE")
        require(raw.stat().st_size == record["raw_bytes"] and digest(raw) == record["raw_sha256"],
                "ATTEMPT_RAW_PROVENANCE_MISMATCH")
    for history in grouped.values():
        expect([r["attempt"] for r in history], list(range(1, len(history) + 1)), "attempt_ordinal_sequence")
        require(len(history) <= 4, "ATTEMPT_BUDGET_EXCEEDED")
        expect(len({r["request_payload_sha256"] for r in history}), 1, "immutable_request_identity")
    return {"logical_requests": len(grouped), "transport_attempts": len(records),
            "log": ref(path, "independently_counted_frozen_events_no_requests_issued")}


def future_registry(history, exposure, metadata, fulltext, bodies):
    """Exact stored-identifier union; no normalization, inference, or selection."""
    old_sources = history["source_identities"]
    old_pmids = unique_ids(old_sources)
    current_pmids = unique_ids(exposure["exposed_unique_pmids"])
    meta_pmids = unique_ids(metadata["source_identities"])
    require(meta_pmids <= current_pmids, "METADATA_OUTSIDE_ACQUIRED_EXPOSURE")
    sources = {r["pmid"]: dict(r) for r in old_sources}
    require(not old_pmids & current_pmids, "FROZEN_HISTORICAL_PMID_INTERSECTION_MISMATCH")
    metadata_by_pmid = {r["pmid"]: r for r in metadata["source_identities"]}
    for r in exposure["exposed_unique_pmids"]:
        source = {"pmid": r["pmid"], "pmcid": None, "doi": None,
                  "seen_lineages": ["alpha3_21_A1"], "future_attempt_seen": True}
        if r["pmid"] in metadata_by_pmid:
            m = metadata_by_pmid[r["pmid"]]
            source.update(pmcid=m["pmcid"], doi=m["doi"], seen_lineages=["alpha3_21_A1", "alpha3_21_C2"])
        sources[r["pmid"]] = source
    old_aliases = {k: exact_ids(old_sources, k, optional=True) for k in ("pmcid", "doi")}
    new_aliases = {k: unique_ids(metadata["source_identities"], k) for k in ("pmcid", "doi")}
    union = list(sources.values())
    for field in ("pmcid", "doi"):
        require(not old_aliases[field] & new_aliases[field], "FROZEN_HISTORICAL_ALIAS_INTERSECTION_MISMATCH")
        expect(exact_ids(union, field, optional=True), old_aliases[field] | new_aliases[field], field + "_union")
    candidates = history["candidate_identities"]
    unique_ids(candidates, "candidate_id")
    unique_ids(candidates, "candidate_payload_sha256")
    for item in fulltext["untrusted_observations"]:
        require(item["authoritative_identity"] is False and item["canonical_future_source_identity"] is None,
                "PARTIAL_RESPONSE_PROMOTED_TO_AUTHORITY")
    require(unique_ids(fulltext["source_identities"]) <= meta_pmids
            and unique_ids(bodies) <= unique_ids(fulltext["source_identities"]), "EXPOSURE_LAYER_BOUNDARY")
    return {
        "schema_version": "Alpha321TerminalFutureContaminationSnapshotV1",
        "use": "future_attempt_history_only", "current_exclusion_authority": False,
        "current_attempt_self_exclusion": False, "master_preexisting_registry_mutated": False,
        "failed_or_incomplete_attempt_assets_return_to_fresh": False,
        "source_identities": sorted(union, key=lambda r: int(r["pmid"])),
        "source_identifier_sets": {"pmids": sorted(old_pmids | current_pmids, key=int),
                                   **{k + "s": sorted(old_aliases[k] | new_aliases[k]) for k in old_aliases}},
        "current_attempt_source_exposures": exposure["exposed_unique_pmids"],
        "current_attempt_metadata_identities": metadata["source_identities"],
        "current_authoritative_fulltext_exposures": fulltext["source_identities"],
        "current_partial_non_authoritative_transport_observations": fulltext["untrusted_observations"],
        "current_seen_canonical_BODY_artifacts": bodies,
        "candidate_identities": candidates,
        "seen_development_case_ids": history["seen_development_case_ids"],
        "candidate_additions_from_alpha3_21": 0,
        "identity_normalization_or_fuzzy_matching_performed": False,
        "unexecuted_JATS_fulltext_exposed": False,
    }


def collect_closure():
    """Offline record reconciliation, not another retry-authority audit."""
    inventory = verify_roots()
    state = d2.preflight()  # read-only, frozen byte/ref bindings; no XML parsing
    for path in d2.MASTER.glob("*.json"):
        d.checked_tree(obj(path))
    adjudication = obj(terminal.OUT / "final_body_read_retry_authority_classification.json")
    terminal_summary = obj(terminal.OUT / "summary.json")
    continuation = obj(terminal.OUT / "d2_continuation_eligibility.json")
    expect(adjudication["classification"], terminal.CLASS_C, "D22_final_unresolved_class")
    expect(adjudication["retry_authority_model"], "UNRESOLVED", "D22_retry_authority_model")
    expect(adjudication["runtime_behavior_label"], "RUNTIME_FAILURE_WITH_UNRESOLVED_RETRY_AUTHORITY", "D22_runtime_wording")
    expect(adjudication["final_same_attempt_authority_audit"], True, "D22_finality")
    expect(terminal_summary["actual_exception_qualified_class_known"], False, "qualified_exception_unknown")
    for key in ("positive_retry_authority_established", "positive_retry_exclusion_established",
                "runtime_recovery_within_same_primary_attempt_allowed"):
        expect(adjudication[key], False, key)
    expect(adjudication["body_read_interruption_covered_by_preexisting_retry_authority"], None, "retry_coverage")
    expect(terminal_summary["further_same_attempt_authority_audit_allowed"], False, "authority_loop_finality")
    expect(terminal_summary["primary_attempt_must_close_incomplete"], True, "terminal_closure_required")
    expect(continuation["eligible"], False, "continuation_prohibited")
    terminal_state = {
        "classification": adjudication["classification"], "retry_authority_model": "UNRESOLVED",
        "positive_retry_authority_established": False, "positive_retry_exclusion_established": False,
        "body_read_interruption_covered_by_preexisting_retry_authority": None,
        "same_attempt_network_continuation_allowed": False, "same_attempt_retry_policy_development_allowed": False,
        "additional_alpha3_21_retry_authority_audit_allowed": False,
        "alpha3_21_runtime_policy_development_allowed": False, "alpha3_21_d2_continuation_allowed": False,
        "alpha3_21e_allowed": False, "runtime_recovery_within_same_primary_attempt_allowed": False,
        "terminal_authority": ref(terminal.OUT / "final_body_read_retry_authority_classification.json", "consumed_without_reopening"),
    }
    history_path = d2.MASTER / "alpha3_21_seen_contamination_registry.json"
    history_sha_before = digest(history_path)
    expect(history_sha_before, b.SEEN_SHA, "master_seen_registry")
    history = obj(history_path)
    exposure = obj(b.A1 / "alpha3_21_current_attempt_source_exposure_registry.json")
    require(exposure["acquisition_complete"] is True and exposure["not_current_alpha3_21_preexisting_exclusion"] is True,
            "A1_EXPOSURE_STATE_MISMATCH")
    raw = rows(b.A1 / "alpha3_21a1_raw_acquisition_corpus.jsonl")
    dedup = rows(b.OUT / "deduplicated_source_universe.jsonl")
    fresh = rows(b.OUT / "fresh_source_universe_global.jsonl")
    sampled = rows(b.OUT / "sampled_source_manifest.jsonl")
    unsampled = rows(b.OUT / "unsampled_fresh_source_manifest.jsonl")
    acquired = exact_ids(raw)
    old_pmids = unique_ids(history["source_identities"])
    expect(acquired, unique_ids(dedup), "frozen_dedup_universe")
    expect(acquired, unique_ids(exposure["exposed_unique_pmids"]), "A1_full_exposure_universe")
    expect(acquired - old_pmids, unique_ids(fresh), "fresh_set_difference")
    expect(unique_ids(sampled) | unique_ids(unsampled), unique_ids(fresh), "sample_unsampled_partition")
    require(not unique_ids(sampled) & unique_ids(unsampled), "SAMPLE_PARTITION_OVERLAP")
    expect(acquired & old_pmids, exact_ids(rows(b.OUT / "preexisting_seen_pmid_intersection.jsonl")), "historical_intersection")
    sample_strata = Counter(r["owner_stratum"] for r in sampled)
    expect(sample_strata, {q["stratum_id"]: 12 for q in rows(d2.MASTER / "alpha3_21_source_query_set.jsonl")}, "six_by_twelve")
    source_funnel = {
        "raw_pmid_occurrence_count": len(raw), "unique_acquired_pmid_count": len(acquired),
        "duplicate_occurrence_count": len(raw) - len(acquired),
        "preexisting_seen_pmid_intersection_count": len(acquired & old_pmids),
        "fresh_unique_pmid_count": len(unique_ids(fresh)), "sampled_source_count": len(sampled),
        "unsampled_fresh_source_count": len(unsampled), "stratum_count": len(sample_strata),
        "per_stratum_sampled_sources": dict(sample_strata), "top_up_used": False, "replacement_used": False,
        "count_semantics": "COMPLETE_SOURCE_ACQUISITION_AND_FROZEN_SAMPLING",
        "sampling_or_deduplication_rerun": False,
    }
    for key, expected in {"raw_pmid_occurrence_count": 1200, "unique_acquired_pmid_count": 1015,
                          "preexisting_seen_pmid_intersection_count": 0, "fresh_unique_pmid_count": 1015,
                          "sampled_source_count": 72, "unsampled_fresh_source_count": 943}.items():
        expect(source_funnel[key], expected, key)
    frozen_b = obj(b.OUT / "summary.json")
    for key in ("raw_pmid_occurrence_count", "fresh_unique_pmid_count", "sampled_source_count", "unsampled_fresh_source_count"):
        expect(source_funnel[key], frozen_b[key], "B_report_" + key)
    meta = rows(d2.C2 / "metadata_final_source_states.jsonl")
    unique_ids(meta)
    expect([r["pmid"] for r in meta], [r["pmid"] for r in sampled], "metadata_sample_order")
    meta_exposure = obj(d2.C2 / "alpha3_21_current_attempt_metadata_identity_exposure_registry.json")
    require(meta_exposure["current_exclusion_authority"] is False
            and meta_exposure["current_attempt_aliases_self_exclude"] is False
            and meta_exposure["preexisting_registry_mutated"] is False, "METADATA_SELF_CONTAMINATION")
    expect(unique_ids(meta_exposure["source_identities"]), unique_ids(meta), "metadata_exposure_complete")
    for m in meta:
        x = next(x for x in meta_exposure["source_identities"] if x["pmid"] == m["pmid"])
        for k in ("pmcid", "doi"):
            expect(x[k], m["direct_" + k], "metadata_direct_identity_" + k)
        for k in ("pmid", "pmc", "doi"):
            # The preserved article-ID list retains raw DOI case; the already
            # frozen direct_doi field is its canonical exposure identity.
            # Compare each representation to its own frozen representation;
            # do not normalize or regenerate either at closure.
            expected_value = m[{"pmid": "pmid", "pmc": "pmcid", "doi": "doi"}[k]]
            id_type = "pubmed" if k == "pmid" else k
            require({"id_type": id_type, "value": expected_value} in x["direct_primary_article_ids"], "NON_DIRECT_METADATA_IDENTITY")
    collision_nodes = rows(d2.C2 / "same_attempt_identity_collision_nodes.jsonl")
    collision_edges = rows(d2.C2 / "same_attempt_identity_collision_edges.jsonl")
    expect(unique_ids(collision_nodes), unique_ids(meta), "collision_audit_universe")
    require(not collision_edges and all(r["collision_state"] == "CLEAR" for r in collision_nodes), "UNEXPECTED_ALIAS_COLLISION")
    metadata_funnel = {
        "sampled_source_count": len(meta),
        "metadata_valid_count": sum(r["metadata_response_state"] == "RESOLVED" for r in meta),
        "metadata_terminal_failure_count": sum(r["metadata_response_state"] != "RESOLVED" for r in meta),
        "date_clear_in_window_count": sum(r["date_resolution_state"] == "DATE_CLEAR_IN_WINDOW" for r in meta),
        "date_clear_outside_window_count": sum(r["date_resolution_state"] == "DATE_CLEAR_OUTSIDE_WINDOW" for r in meta),
        "date_unresolved_count": sum(r["date_state"] == "UNRESOLVED" for r in meta),
        "publication_type_eligible_count": sum(r["publication_type_state"] == "CLEAR" for r in meta),
        "publication_type_excluded_count": sum(r["publication_type_state"] != "CLEAR" for r in meta),
        "correction_update_clear_count": sum(r["correction_update_state"] == "CLEAR" for r in meta),
        "correction_update_deferred_count": sum(r.get("updateof_deferred_state") == "DEFERRED_TO_STRUCTURE_STAGE" for r in meta),
        "correction_update_excluded_count": sum(r["correction_update_state"] != "CLEAR" and
            r.get("updateof_deferred_state") != "DEFERRED_TO_STRUCTURE_STAGE" for r in meta),
        "historical_pmcid_contaminated_count": sum(r["historical_pmcid_contaminated"] for r in meta),
        "historical_doi_contaminated_count": sum(r["historical_doi_contaminated"] for r in meta),
        "same_attempt_collision_component_count": 0, "same_attempt_collision_source_count": 0,
        "pre_oa_clear_count": sum(r["pre_oa_handoff_state"] == "PRE_OA_CLEAR" for r in meta),
        "pre_oa_deferred_count": sum(r["pre_oa_handoff_state"] == "PRE_OA_CONDITIONAL_UPDATEOF" for r in meta),
        "pre_oa_handoff_count": sum(r["pre_oa_handoff_state"] != "BLOCKED" for r in meta),
        "count_semantics": "COMPLETE_FROZEN_METADATA_DIMENSIONS_NOT_SCIENTIFIC_LABELS",
        "dimension_counts_overlap": True, "eligibility_rules_reexecuted": False,
    }
    frozen_meta = obj(d2.C2 / "metadata_source_funnel.json")
    for key, value in metadata_funnel.items():
        if key in frozen_meta:
            expect(value, frozen_meta[key], "C2_report_" + key)
    for key, expected in {"metadata_valid_count": 72, "date_clear_in_window_count": 54, "date_unresolved_count": 18,
                          "publication_type_eligible_count": 67, "publication_type_excluded_count": 5,
                          "correction_update_clear_count": 69, "correction_update_deferred_count": 3,
                          "pre_oa_clear_count": 46, "pre_oa_deferred_count": 3, "pre_oa_handoff_count": 49}.items():
        expect(metadata_funnel[key], expected, key)
    expect(metadata_funnel["metadata_terminal_failure_count"], frozen_meta["metadata_terminal_failure_count"], "metadata_failure")
    activation = obj(d2.OUT / "alpha3_21d2_jats_activation_manifest.json")
    oa = rows(d2.OUT / "oa_source_states.jsonl")
    structural = rows(d2.OUT / "jats_structural_states.jsonl")
    jats_attempts = rows(d2.OUT / "jats_request_attempt_log.jsonl")
    reconstruction = prior.reconstruct(activation["requests"], state["requests"], jats_attempts, structural, 4)
    identities = rows(d2.OUT / "jats_primary_identity_states_v2.jsonl")
    licenses = rows(d2.OUT / "jats_license_states.jsonl")
    bodies = rows(d2.OUT / "canonical_body_manifest.jsonl")
    updates = rows(d2.OUT / "updateof_structural_resolution_states.jsonl")
    handoff = obj(d2.OUT / "alpha3_21e_construction_source_handoff.json")
    fulltext = obj(d2.OUT / "alpha3_21_current_attempt_fulltext_exposure_registry.json")
    require(fulltext["current_exclusion_authority"] is False
            and fulltext["current_attempt_fulltext_self_excludes"] is False
            and fulltext["future_history_only"] is True, "FULLTEXT_SELF_CONTAMINATION")
    for records in (oa, structural, identities, licenses, bodies, updates, handoff["sources"], fulltext["source_identities"]):
        unique_ids(records)
        for record in records:
            d.checked_tree(record)  # only artifact hashes, not XML/BODY content
    expect(unique_ids(oa), {r["pmid"] for r in meta if r["pre_oa_handoff_state"] != "BLOCKED"}, "pre_OA_set")
    expect(unique_ids(identities), unique_ids(structural), "completed_identity_boundary")
    expect(unique_ids(licenses), unique_ids(structural), "completed_license_boundary")
    require(all(r["state"] == "JATS_XML_ARTICLE_STRUCTURE_VALID" for r in structural), "NONVALID_COMPLETED_JATS")
    for r in identities:
        expect(r["result"]["expected_identity"]["pmid"], r["pmid"], "identity_record_PMID")
    expect(unique_ids(bodies), {r["pmid"] for r in licenses if r["state"] == "ELIGIBLE"}, "license_BODY_boundary")
    expect(unique_ids(updates), {r["pmid"] for r in meta if r.get("updateof_deferred_state") == "DEFERRED_TO_STRUCTURE_STAGE"}, "UpdateOf_boundary")
    expect(unique_ids(bodies), unique_ids(handoff["sources"]), "partial_BODY_handoff_boundary")
    require(handoff["complete_D2_execution"] is False and handoff["21E_execution_authorized"] is False, "PARTIAL_HANDOFF_PROMOTED")
    partial_funnel = {
        "oa_logical_requests_executed": len(oa),
        "oa_eligible_count": sum(r["state"] == "OA_SUBSET_ELIGIBLE" for r in oa),
        "oa_ineligible_count": sum(r["state"] == "OA_SUBSET_INELIGIBLE" for r in oa),
        "oa_terminal_failure_count": sum(r["state"] not in {"OA_SUBSET_ELIGIBLE", "OA_SUBSET_INELIGIBLE"} for r in oa),
        "conditional_jats_request_count": len(activation["requests"]),
        "activated_jats_request_count": len(reconstruction["active"]),
        "not_required_jats_request_count": len(activation["requests"]) - len(reconstruction["active"]),
        "completed_valid_jats_count": len(structural), "pending_interrupted_jats_count": len({r["logical_request_id"] for r in reconstruction["failed_attempts"]}),
        "not_executed_after_abort_count": len(reconstruction["untouched"]),
        "jats_identity_exactly_bound_count": sum(r["result"]["identity_state"] == "JATS_PRIMARY_IDENTITY_EXACTLY_BOUND" for r in identities),
        "jats_identity_failure_count": sum(bool(r["result"]["identity_failures"]) for r in identities),
        "license_eligible_count": sum(r["state"] == "ELIGIBLE" for r in licenses),
        "license_ineligible_count": sum(r["state"] == "INELIGIBLE" for r in licenses),
        "license_unresolved_count": sum(r["state"] not in {"ELIGIBLE", "INELIGIBLE"} for r in licenses),
        "canonical_body_usable_count": sum(r["state"] == "CANONICAL_BODY_USABLE" for r in bodies),
        "canonical_body_paragraph_count": sum(r["paragraph_count"] for r in bodies),
        "partial_construction_source_count": len(handoff["sources"]),
        "initial_updateof_deferred_count": len(updates),
        "updateof_reached_resolution_count": sum(r["resolution_reached"] for r in updates),
        "updateof_clear_count": sum(r["terminal_resolution_state"] == "CLEAR" for r in updates),
        "updateof_not_reached_due_to_abort_count": sum(not r["resolution_reached"] for r in updates),
        "OA_count_semantics": "COMPLETE", "JATS_license_BODY_construction_count_semantics": "PARTIAL_ONLY",
        "unexecuted_sources_scientifically_classified": False,
        "completed_identity_outcomes_extrapolated": False,
        "not_executed_request_identities": [{"pmid": r["pmid"], "logical_request_id": r["logical_request_id"],
                                               "state": "NOT_EXECUTED_AFTER_ABORT"} for r in reconstruction["untouched"]],
    }
    for key, expected in {"oa_logical_requests_executed": 49, "oa_eligible_count": 47, "oa_ineligible_count": 2,
                          "oa_terminal_failure_count": 0, "conditional_jats_request_count": 49,
                          "activated_jats_request_count": 47, "not_required_jats_request_count": 2,
                          "completed_valid_jats_count": 9, "pending_interrupted_jats_count": 1,
                          "not_executed_after_abort_count": 37, "jats_identity_exactly_bound_count": 9,
                          "jats_identity_failure_count": 0, "license_eligible_count": 6, "license_ineligible_count": 3,
                          "license_unresolved_count": 0, "canonical_body_usable_count": 6,
                          "canonical_body_paragraph_count": 318, "partial_construction_source_count": 6,
                          "initial_updateof_deferred_count": 3, "updateof_reached_resolution_count": 1,
                          "updateof_clear_count": 1, "updateof_not_reached_due_to_abort_count": 2}.items():
        expect(partial_funnel[key], expected, key)
    for key in ("completed_valid_jats_count", "pending_interrupted_jats_count", "not_executed_after_abort_count",
                "partial_construction_source_count", "activated_jats_request_count"):
        expect(partial_funnel[key], terminal_summary[key], "D22_report_" + key)
    interrupted = reconstruction["failed_attempts"]
    expect(len(interrupted), 1, "interrupted_consumed_attempts")
    expect(interrupted[0]["pmid"], "42731998", "interrupted_PMID")
    expect(interrupted[0]["raw_bytes"], 188590, "partial_bytes")
    require(interrupted[0].get("unhandled_frozen_client_exception") is True, "INTERRUPTED_EVENT_MISSING")
    fulltext_pmids = unique_ids(fulltext["source_identities"])
    expect(fulltext_pmids, unique_ids(structural), "authoritative_fulltext_exposure_boundary")
    expect(len(fulltext["untrusted_observations"]), len(interrupted), "untrusted_partial_boundary")
    registry = future_registry(history, exposure, meta_exposure, fulltext, bodies)
    counts = {
        "preexisting_seen_unique_pmid_count": len(old_pmids),
        "preexisting_seen_unique_pmcid_count": len(exact_ids(history["source_identities"], "pmcid", optional=True)),
        "preexisting_seen_unique_doi_count": len(exact_ids(history["source_identities"], "doi", optional=True)),
        "current_attempt_unique_pmid_exposure_count": len(acquired),
        "current_attempt_metadata_pmid_exposure_count": len(unique_ids(meta_exposure["source_identities"])),
        "current_attempt_metadata_pmcid_exposure_count": len(unique_ids(meta_exposure["source_identities"], "pmcid")),
        "current_attempt_metadata_doi_exposure_count": len(unique_ids(meta_exposure["source_identities"], "doi")),
        "current_authoritative_fulltext_exposure_count": len(fulltext["source_identities"]),
        "current_partial_fulltext_observation_count": len(fulltext["untrusted_observations"]),
        "current_canonical_body_exposure_count": len(bodies),
        "future_seen_unique_pmid_count": len(registry["source_identifier_sets"]["pmids"]),
        "future_seen_unique_pmcid_count": len(registry["source_identifier_sets"]["pmcids"]),
        "future_seen_unique_doi_count": len(registry["source_identifier_sets"]["dois"]),
        "future_seen_candidate_identity_count": len(registry["candidate_identities"]),
        "candidate_contamination_additions_from_alpha3_21": 0, "exact_set_unions_independently_verified": True,
    }
    for key, expected in {"future_seen_unique_pmid_count": 3560, "future_seen_unique_pmcid_count": 218,
                          "future_seen_unique_doi_count": 252, "future_seen_candidate_identity_count": 271}.items():
        expect(counts[key], expected, key)
    for field in ("pmid", "pmcid", "doi"):
        expect(counts["preexisting_seen_unique_" + field + "_count"], history["seen_unique_" + field + "s"], "historical_registry_" + field)
    expect(len(registry["candidate_identities"]), history["seen_unique_candidate_identities"], "candidate_registry_count")
    network = {"21A1": attempt_accounting(b.A1 / "all_pubmed_request_attempt_log.jsonl"),
               "21C2": attempt_accounting(d2.C2 / "metadata_request_attempt_log.jsonl"),
               "21D2_OA": attempt_accounting(d2.OUT / "oa_request_attempt_log.jsonl"),
               "21D2_JATS": attempt_accounting(d2.OUT / "jats_request_attempt_log.jsonl")}
    for name, expected in {"21A1": (24, 25), "21C2": (72, 75), "21D2_OA": (49, 55), "21D2_JATS": (10, 11)}.items():
        expect((network[name]["logical_requests"], network[name]["transport_attempts"]), expected, name + "_network")
    network_state = {"by_stage": network,
                     "alpha3_21_total_external_logical_requests": sum(r["logical_requests"] for r in network.values()),
                     "alpha3_21_total_transport_attempts": sum(r["transport_attempts"] for r in network.values()),
                     "21D2_logical_requests": network["21D2_OA"]["logical_requests"] + network["21D2_JATS"]["logical_requests"],
                     "21D2_transport_attempts": network["21D2_OA"]["transport_attempts"] + network["21D2_JATS"]["transport_attempts"],
                     "closure_new_network_calls": 0, "external_data_requests_are_not_LLM_inferences": True}
    for name, path, logical_key, attempts_key in (
        ("21A1", b.A1 / "acquisition_execution_accounting.json", "pubmed_logical_page_requests", "transport_attempts"),
        ("21C2", d2.C2 / "metadata_execution_accounting.json", "metadata_logical_requests_executed", "metadata_transport_attempts"),
    ):
        report = obj(path)
        expect(network[name]["logical_requests"], report[logical_key], name + "_accounting_logical")
        expect(network[name]["transport_attempts"], report[attempts_key], name + "_accounting_transport")
    d2_account = obj(d2.OUT / "network_execution_accounting.json")
    expect(network_state["21D2_logical_requests"], d2_account["total_logical_requests_executed"], "D2_logical")
    expect(network_state["21D2_transport_attempts"], d2_account["total_transport_attempts"], "D2_transport")
    expect((network_state["alpha3_21_total_external_logical_requests"], network_state["alpha3_21_total_transport_attempts"]), (155, 166), "total_network")
    # No new scientific inference exists in any phase: bind the frozen
    # initialization, all reports, and fail-closed D2 document boundary.
    initialization = obj(d2.MASTER / "alpha3_21_inference_accounting_initialization.json")
    for key in ("builder", "quality", "other_scientific_llm", "provider_calls"):
        expect(initialization[key], 0, "inference_initialization_" + key)
    for _, path, _, _ in PHASES:
        for key, value in obj(path / "summary.json").items():
            if key in {"builder_calls", "quality_calls", "llm_calls", "provider_calls"}:
                expect(value, 0, "phase_scientific_calls")
    d2_summary = obj(d2.OUT / "summary.json")
    for key in ("source_record_tokens_generated", "Builder_requests_constructed", "Quality_requests_constructed", "BODY_span_anchors_generated"):
        expect(d2_summary[key], 0, "no_Builder_prep_" + key)
    for key in ("builder_execution_started", "quality_execution_started", "retrieval_evaluation_started",
                "construction_evidence_document_generation_started", *d2.UNCHANGED):
        expect(d2_summary[key], False, "frozen_scientific_nonchange_" + key)
    builder = {"fresh_builder_requests_constructed": 0, "fresh_builder_calls": 0,
               "fresh_builder_candidates": 0, "fresh_builder_outcome": "NOT_EVALUATED",
               "builder_v4_fresh_outcome": "NOT_EVALUATED", "binding": ref(d2.MASTER / "alpha3_21_builder_v4_binding.json", "unchanged_frozen_Builder_V4")}
    quality = {"fresh_quality_requests_constructed": 0, "fresh_quality_calls": 0,
               "fresh_quality_candidate_judgments": 0, "fresh_quality_outcome": "NOT_EVALUATED",
               "quality_v2_fresh_outcome": "NOT_EVALUATED", "binding": ref(d2.MASTER / "alpha3_21_quality_v2_binding.json", "unchanged_frozen_Quality_V2")}
    retrieval = {"search_plan_primary_evaluation_started": False, "search_plan_primary_evaluation_completed": False,
                 "search_plan_primary_evaluation_ready": False, "retrieval_cases_evaluated": 0,
                 "retrieval_outcome": "NOT_EVALUATED", "search_plan_v24_primary_outcome": "NOT_EVALUATED",
                 "search_plan_v24_primary_result_from_alpha3_21": "NOT_EVALUATED", "metrics_computed": False,
                 "minimum_eight_source_group_threshold_evaluated": False, "scientific_threshold_failure_claimed": False,
                 "binding": ref(d2.MASTER / "alpha3_21_search_plan_architecture_binding.json", "unchanged_frozen_architecture")}
    pool = {"eligible_proposition_pool_state": "NOT_DERIVED", "eligible_proposition_pool_size": None,
            "fresh_primary_eligible_proposition_pool_state": "NOT_DERIVED", "fresh_primary_eligible_proposition_count": None,
            "zero_proposition_pool_claimed": False}
    partial = {"partial_construction_source_count": len(handoff["sources"]), "final_construction_source_state": "NOT_DERIVED",
               "final_construction_source_count": None, "construction_source_handoff_complete": False,
               "alpha3_21e_handoff_eligible": False, "alpha3_21e_allowed": False,
               "partial_sources_not_a_final_cohort": True, "construction_documents_generated": False,
               "opaque_tokens_generated": False, "span_anchors_generated": False,
               "original_partial_handoff": ref(d2.OUT / "alpha3_21e_construction_source_handoff.json", "preserved_nonfinal_diagnostic_only")}
    seen_contract = {
        "failed_or_incomplete_attempt_assets_return_to_fresh": False,
        "unsampled_acquired_PMIDs_remain_seen": sorted(unique_ids(unsampled), key=int),
        "metadata_excluded_PMIDs_remain_seen": sorted({r["pmid"] for r in meta if r["pre_oa_handoff_state"] == "BLOCKED"}, key=int),
        "OA_ineligible_PMIDs_remain_seen": sorted({r["pmid"] for r in oa if r["state"] == "OA_SUBSET_INELIGIBLE"}, key=int),
        "JATS_unexecuted_PMIDs_remain_source_and_metadata_seen": sorted({r["pmid"] for r in reconstruction["untouched"]}, key=int),
        "JATS_unexecuted_fulltexts_exposed": False, "BODY_artifacts_remain_seen": True,
        "future_contamination_not_restricted_to_sample": True, "current_attempt_self_exclusion": False,
    }
    for key, expected in {"unsampled_acquired_PMIDs_remain_seen": 943, "metadata_excluded_PMIDs_remain_seen": 23,
                          "OA_ineligible_PMIDs_remain_seen": 2, "JATS_unexecuted_PMIDs_remain_source_and_metadata_seen": 37}.items():
        expect(len(seen_contract[key]), expected, key)
        require(set(seen_contract[key]) <= set(registry["source_identifier_sets"]["pmids"]), "EXPOSED_ASSET_LOST")
    require(not set(seen_contract["JATS_unexecuted_PMIDs_remain_source_and_metadata_seen"]) & fulltext_pmids, "UNEXECUTED_FULLTEXT_CLAIMED_EXPOSED")
    no_repair = {"retry_policy_changed_after_failure": False, "scientific_policy_changed_after_failure": False,
                 "retry_policy_modified_in_alpha3_21": False, "runtime_exception_mapping_modified_in_alpha3_21": False,
                 "scientific_policy_modified_after_fresh_failure": False,
                 "runtime_fix_implemented": False, "retry_authority_reopened": False, **terminal_state}
    future = {"next_stage_recommendation": NEXT, "next_stage_is_part_of_alpha3_21": False,
              "next_fresh_attempt_preregistered": False, "future_development_requires_new_protocol": True,
              "alpha3_21_assets_must_remain_seen": True, "improvements_implemented_here": False,
              "minimum_prospective_contract_topics": ["response-body completion semantics", "retryable interrupted-transfer semantics",
                  "qualified exception / traceback / cause / context provenance", "trusted HTTP and partial-body state",
                  "retry-attempt continuation semantics", "append-only continuation logs", "body-read interruption tests"]}
    after = verify_roots()
    expect(after, inventory, "all_12_roots_preserved_after_closure_reconciliation")
    expect(digest(history_path), history_sha_before, "master_registry_unchanged")
    summary = {"status": "completed", "stage_identity": STAGE,
               "alpha3_21_terminal_classification": CLASSIFICATION,
               "alpha3_21_master_root_verified": True, "alpha3_21d22_root_verified": True,
               "fresh_primary_attempt_started": True, "fresh_primary_attempt_completed": False,
               "fresh_primary_attempt_terminated": True, "fresh_primary_attempt_terminal_reason": "D2_RUNTIME_AUTHORITY_GAP",
               **source_funnel, **metadata_funnel,
               **{k: v for k, v in partial_funnel.items() if k != "not_executed_request_identities"},
               **partial, **pool, **builder, **quality, **retrieval, **counts,
               "alpha3_21_total_external_logical_requests": network_state["alpha3_21_total_external_logical_requests"],
               "alpha3_21_total_transport_attempts": network_state["alpha3_21_total_transport_attempts"],
               "same_attempt_network_continuation_allowed": False, "same_attempt_retry_policy_development_allowed": False,
               "retry_policy_changed_after_failure": False, "scientific_policy_changed_after_failure": False,
               **NO_CALLS, "next_stage_recommendation": NEXT, "historical_assets_modified": False}
    artifacts = {
        "alpha3_21_master_root_verification": inventory[0],
        "alpha3_21_phase_root_inventory": {"critical_root_count": len(inventory), "before": inventory, "after": after,
                                          "all_roots_verified_and_unchanged": True, "historical_failures_preserved": True},
        "alpha3_21_terminal_authority_verification": terminal_state,
        "alpha3_21_complete_source_funnel": source_funnel, "alpha3_21_metadata_funnel": metadata_funnel,
        "alpha3_21_oa_jats_partial_funnel": partial_funnel,
        "alpha3_21_runtime_terminal_reason": {"terminal_reason": "D2_RUNTIME_AUTHORITY_GAP",
            "runtime_behavior_label": "RUNTIME_FAILURE_WITH_UNRESOLVED_RETRY_AUTHORITY", "pmid": interrupted[0]["pmid"],
            "attempts_consumed": len(interrupted), "partial_bytes": interrupted[0]["raw_bytes"],
            "actual_qualified_exception_class": "UNKNOWN", "retry_authority": "UNRESOLVED",
            "partial_body_authoritative": False, "confirmed_retry_implementation_bug": False,
            "confirmed_non_retryable_failure": False, "provider_scientific_failure": False,
            "frozen_failed_attempt": interrupted[0], "terminal_authority_state": terminal_state},
        "alpha3_21_partial_handoff_semantics": partial,
        "alpha3_21_builder_state": builder, "alpha3_21_quality_state": quality,
        "alpha3_21_retrieval_evaluation_state": retrieval, "alpha3_21_final_pool_state": pool,
        "alpha3_21_llm_inference_accounting": {"fresh_builder_calls": 0, "fresh_quality_calls": 0,
            "other_LLM_scientific_calls": 0, "total_LLM_scientific_calls": 0,
            "initialization": ref(d2.MASTER / "alpha3_21_inference_accounting_initialization.json", "frozen_zero_initialization"),
            "all_phase_reports_zero": True, "data_network_not_counted_as_inference": True, **NO_CALLS},
        "alpha3_21_network_accounting": network_state,
        "alpha3_21_source_exposure_summary": {"current_attempt_unique_pmid_exposure_count": len(acquired),
            "entire_A1_universe_remains_seen": True, "original": ref(b.A1 / "alpha3_21_current_attempt_source_exposure_registry.json", "immutable_A1_exposure")},
        "alpha3_21_metadata_identity_exposure_summary": {"pmids": len(unique_ids(meta)),
            "pmcids": counts["current_attempt_metadata_pmcid_exposure_count"], "dois": counts["current_attempt_metadata_doi_exposure_count"],
            "includes_metadata_excluded_sources": True, "original": ref(d2.C2 / "alpha3_21_current_attempt_metadata_identity_exposure_registry.json", "immutable_C2_exposure")},
        "alpha3_21_fulltext_exposure_summary": {"authoritative_count": len(fulltext["source_identities"]),
            "partial_non_authoritative_count": len(fulltext["untrusted_observations"]), "partial_identity_promoted": False,
            "unexecuted_fulltexts_exposed": False, "original": ref(d2.OUT / "alpha3_21_current_attempt_fulltext_exposure_registry.json", "immutable_D2_exposure")},
        "alpha3_21_body_exposure_summary": {"seen_BODY_count": len(bodies), "paragraph_count": sum(r["paragraph_count"] for r in bodies),
            "BODY_content_inspected_or_regenerated": False, "assets": bodies},
        "alpha3_21_future_contamination_registry": registry, "alpha3_21_future_contamination_counts": counts,
        "alpha3_21_candidate_contamination_state": {"preexisting_candidate_count": len(history["candidate_identities"]),
            "alpha3_21_additions": 0, "future_candidate_count": len(registry["candidate_identities"]),
            "candidate_identities_verbatim_unchanged": registry["candidate_identities"] == history["candidate_identities"],
            "candidate_identities_invented_from_sources": False},
        "alpha3_21_incomplete_attempt_assets_remain_seen_contract": seen_contract,
        "alpha3_21_publication_safe_interpretation": {"long_wording": LONG, "short_wording": SHORT,
            "positive_or_negative_generalization_claim": False, "scientific_failure_claim": False,
            "unevaluated_claims_prohibited": ["precision", "recall", "direct retrieval rate", "proposition retrieval success",
                "Builder V4 fresh-data quality", "Quality V2 fresh-data pass rate", "end-to-end generalization"]},
        "alpha3_21_engineering_lessons": {"engineering_only": True, "future_contract_topics": future["minimum_prospective_contract_topics"],
            "improvements_implemented_here": False, "scientific_configuration_change_justified": False},
        "alpha3_21_no_post_outcome_repair_audit": no_repair,
        "builder_v4_nonchange_audit": {"builder_v4_change_justified_by_alpha3_21": False, "builder_v4_modified": False, **builder},
        "quality_v2_nonchange_audit": {"quality_v2_change_justified_by_alpha3_21": False, "quality_v2_modified": False, **quality},
        "search_plan_non_evaluation_audit": {"search_plan_architecture_modified": False, **retrieval},
        "future_development_boundary": future,
        "known_preexisting_test_environment_issue": obj(d2.OUT / "known_preexisting_test_environment_issue.json"),
        "historical_preservation_audit": {"historical_assets_modified": False, "all_12_roots_before_after_equal": True,
            "master_preexisting_registry_before_sha256": history_sha_before, "master_preexisting_registry_after_sha256": digest(history_path),
            "new_snapshot_does_not_amend_original_registry": True, "historical_failed_stage_statuses_preserved": True},
        "scientific_state_safety_audit": {**NO_CALLS, **partial, **pool, "scientific_content_inspected": False,
            "new_metadata_extraction": False, "JATS_parsing": False, "license_reinterpretation": False,
            "new_sampling": False, "new_scientific_selection": False, "retrieval_evaluation_performed": False},
        "protocol_compliance_audit": {"offline_only": True, "phase_frozen_roots_verified": 12,
            "counts_derived_from_frozen_records": True, "source_and_alias_unions_independently_derived": True,
            "null_not_zero_semantics": True, "stage_is_terminal_closure_not_continuation": True,
            "historical_assets_modified": False, "git_mutations": False, **NO_CALLS},
        "validation": {"status": "completed", "all_required_checks_passed": True,
            "critical_root_count": 12, "count_reconciliation_passed": True, "exposure_union_passed": True,
            "null_and_partial_semantics_passed": True, "terminal_authority_not_reopened": True, **NO_CALLS},
        "summary": summary,
    }
    # Bind the exact record inputs used by the new presentation sidecars.
    # XML, fulltexts and BODY are only hashed through their preserved refs.
    record_bindings = {
        "alpha3_21_complete_source_funnel": [b.A1 / "alpha3_21a1_raw_acquisition_corpus.jsonl",
            b.OUT / "deduplicated_source_universe.jsonl", b.OUT / "fresh_source_universe_global.jsonl",
            b.OUT / "sampled_source_manifest.jsonl", b.OUT / "unsampled_fresh_source_manifest.jsonl"],
        "alpha3_21_metadata_funnel": [d2.C2 / "metadata_final_source_states.jsonl", d2.C2 / "metadata_source_funnel.json",
            d2.C2 / "same_attempt_identity_collision_nodes.jsonl", d2.C2 / "same_attempt_identity_collision_edges.jsonl"],
        "alpha3_21_oa_jats_partial_funnel": [d2.OUT / "oa_source_states.jsonl", d2.OUT / "alpha3_21d2_jats_activation_manifest.json",
            d2.OUT / "jats_structural_states.jsonl", d2.OUT / "jats_primary_identity_states_v2.jsonl",
            d2.OUT / "jats_license_states.jsonl", d2.OUT / "canonical_body_manifest.jsonl",
            d2.OUT / "updateof_structural_resolution_states.jsonl"],
        "alpha3_21_future_contamination_registry": [history_path,
            b.A1 / "alpha3_21_current_attempt_source_exposure_registry.json",
            d2.C2 / "alpha3_21_current_attempt_metadata_identity_exposure_registry.json",
            d2.OUT / "alpha3_21_current_attempt_fulltext_exposure_registry.json", d2.OUT / "canonical_body_manifest.jsonl"],
    }
    for name, paths in record_bindings.items():
        artifacts[name]["frozen_input_bindings"] = [ref(path, "read_only_frozen_record_input") for path in paths]
    # Input bindings are part of the snapshot, so compute its final byte hash
    # only after they are attached.
    summary[REGISTRY_MARKER] = sha(canonical(registry) + b"\n")
    expect(set(artifacts), set(REQUIRED), "required_output_membership")
    return artifacts


def run(verification=None):
    require(not OUT.exists(), "CLOSURE_OUTPUT_ALREADY_EXISTS_NO_OVERWRITE")
    if verification is not None:
        require(verification["implementation_sha256"] == digest(Path(__file__))
                and verification["test_implementation_sha256"] == digest(TEST)
                and verification["checks"] and all(x["check_passed"] is True for x in verification["checks"]),
                "VERIFICATION_REPORT_MISMATCH")
    with prior.offline_guard():
        try:
            artifacts = collect_closure()
        except Exception as exc:
            result = {"status": "failed", "stage_identity": STAGE,
                      "closure_failure": type(exc).__name__ + ":" + str(exc),
                      "closure_state": "NOT_DERIVED_AFTER_INTEGRITY_BARRIER_FAILURE",
                      "same_attempt_network_continuation_allowed": False, "alpha3_21e_allowed": False, **NO_CALLS}
            artifacts = {name: dict(result) for name in REQUIRED}
        OUT.mkdir()

        def write(name, raw):
            path = OUT / name
            require(path.parent == OUT and not path.is_symlink(), "OUTPUT_PATH_ESCAPE_OR_SYMLINK")
            with path.open("xb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())

        for name, value in artifacts.items():
            write(name + ".json", canonical(value) + b"\n")
        registry_sha = digest(OUT / "alpha3_21_future_contamination_registry.json")
        write(REGISTRY_MARKER, (registry_sha + "\n").encode())
        if artifacts["summary"]["status"] == "completed":
            expect(registry_sha, artifacts["summary"][REGISTRY_MARKER], "written_future_registry_hash")
            write("alpha3_21_publication_wording_long.txt", (LONG + "\n").encode())
            write("alpha3_21_publication_wording_short.txt", (SHORT + "\n").encode())
        write("closure_implementation_binding.json", canonical(ref(Path(__file__), "terminal_closure_not_runtime_policy")) + b"\n")
        write("focused_test_implementation_binding.json", canonical(ref(TEST, "offline_terminal_closure_tests")) + b"\n")
        if verification is not None:
            write("offline_verification_results.json", canonical(verification) + b"\n")
        # Repeat immutable-root checks after output writes, before the seal.
        verify_roots()
        sealed = root_hash(OUT, ROOT_MARKER)
        write(ROOT_MARKER, (sealed + "\n").encode())
        expect(root_hash(OUT, ROOT_MARKER), sealed, "closure_output_root")
        return {**artifacts["summary"], ROOT_MARKER: sealed}


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, sort_keys=True), flush=True)
    raise SystemExit(0 if result["status"] == "completed" else 1)
