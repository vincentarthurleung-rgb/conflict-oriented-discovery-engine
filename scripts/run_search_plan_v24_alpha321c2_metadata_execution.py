#!/usr/bin/env python3
"""Execute the immutable 72-request PubMed universe under frozen C.1 authority.

Only orchestration/provenance is new. Transport, parsing and scientific policies
are inherited without edits. First-pass facts and the graph are separate barriers.
"""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from scripts import run_search_plan_v24_alpha321c1_authority_resolution_offline as authority
from scripts import search_plan_v24_alpha321_metadata_eligibility_v2 as v2


ROOT, C, B, MASTER, C1 = authority.ROOT, authority.C, authority.B, authority.MASTER, authority.OUT
OUT = ROOT / "runs/20261006_search_plan_v24_primary_alpha3_21c2_metadata_source_type_execution"
ROOT_MARKER = "search_plan_v24_primary_alpha3_21c2_sha256"
C1_SHA = "1c0475ff62d71570b3791ae9814bfd659059c8675c6f39e14002bcc8caec5d90"
DATE_SHA = "f1ad61e8d05e96950936069211ff2c1e95fdf07970730e1e833f59b89bb50e87"
PARSER_SHA = "830fd16b5a2a83cb279a97348cbed0dc1c14fafaeda3eff642d13750c5756044"
CLASS_OK = "FRESH_PRIMARY_METADATA_AND_SOURCE_IDENTITY_RESOLUTION_COMPLETE_AND_FROZEN"
CLASS_FAIL = "FRESH_PRIMARY_METADATA_EXECUTION_FAILED_CLOSED"
IDENTITY = "FRESH_PRIMARY_ALPHA3_21_METADATA_AND_SOURCE_TYPE_EXECUTION"
ZERO_CALLS = {k: 0 for k in ("pmc_calls", "provider_calls", "llm_calls", "builder_calls", "quality_calls")}
canonical, digest, sha, root_hash, ref = authority.canonical, authority.digest, authority.sha, authority.root_hash, authority.ref
obj, rows, require = authority.obj, authority.rows, authority.require
legacy = authority.c.historical


def put_bytes(name: str, raw: bytes) -> str:
    path = OUT / name
    require(path.resolve().is_relative_to(OUT.resolve()), "OUTPUT_PATH_ESCAPE")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return sha(raw)


def put(name: str, value: object) -> str:
    return put_bytes(name, canonical(value) + b"\n")


def put_rows(name: str, values: list[dict]) -> str:
    return put_bytes(name, b"".join(canonical(value) + b"\n" for value in values))


def append(name: str, value: dict) -> None:
    with (OUT / name).open("ab") as handle:
        handle.write(canonical(value) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())


def marker(name: str, value: str) -> None:
    put_bytes(name, (value + "\n").encode("ascii"))


def checked_tree(value: object) -> None:
    if isinstance(value, dict):
        if "artifact_path" in value and "sha256" in value:
            authority.c.b.checked_ref(value)
        for child in value.values():
            checked_tree(child)
    elif isinstance(value, list):
        for child in value:
            checked_tree(child)


def preflight() -> dict:
    require((C1 / authority.ROOT_MARKER).read_text().strip() == C1_SHA
            and root_hash(C1, authority.ROOT_MARKER) == C1_SHA, "C1_ROOT_MISMATCH")
    state = authority.verify_inputs()
    for path in C1.glob("*.json"):
        checked_tree(obj(path))
    for stem, expected in (("publication_date_resolution_contract_v2", DATE_SHA),
                           ("alpha321_metadata_eligibility_parser_contract_v2", PARSER_SHA)):
        require(digest(C1 / (stem + ".json")) == expected
                and (C1 / (stem + "_sha256")).read_text().strip() == expected,
                "C1_PARSER_CONTRACT_MISMATCH:" + stem)
    summary = obj(C1 / "summary.json")
    require(summary["status"] == "completed" and summary["metadata_execution_ready"] is True
            and summary["fresh_metadata_observed"] is False, "C1_NOT_READY")
    request_list = rows(C / "metadata_request_manifest.jsonl")
    require(len(request_list) == 72 and len({r["logical_request_id"] for r in request_list}) == 72,
            "REQUEST_UNIVERSE_NOT_72")
    for ordinal, request in enumerate(request_list, 1):
        pmid = request["sampled_pmids"][0]
        payload = {"method": "GET", "endpoint": legacy.EFETCH,
                   "parameters": {"db": "pubmed", "retmode": "xml", "id": pmid}}
        require(request["execution_ordinal"] == ordinal
                and request["sampled_pmids"] == [state["sample"][ordinal - 1]["pmid"]]
                and request["source_selection_provenance"] == state["sample"][ordinal - 1]
                and request["request_payload"] == payload
                and all(request[k] == payload[k] for k in payload)
                and request["request_payload_sha256"] == sha(canonical(payload)),
                "FROZEN_REQUEST_ROUTE_ORDER_OR_HASH_MISMATCH")
    retry = obj(C / "metadata_technical_retry_policy.json")
    require(retry["maximum_attempts_per_request"] == 4 and retry["timeout_seconds"] == 60
            and retry["backoff_seconds"] == [2, 4, 8]
            and retry["http_status_retryable"] == state["transport"]["http_status_retryable"],
            "FROZEN_TRANSPORT_POLICY_MISMATCH")
    state.update(requests=request_list, accepted=obj(state["acceptance_path"]),
                 excluded=obj(state["exclusion_path"]), retry=retry)
    return state


class FrozenTransportAdapter:
    """Redirect only the frozen client's output sink; reuse its request/retry body."""

    def __init__(self, policy: dict):
        self.client = legacy.PubMedTransport(policy)

    @property
    def calls(self):
        return self.client.calls

    def fetch(self, request: dict):
        original_out, original_writer = legacy.OUT, legacy.write_bytes
        try:
            # No on-disk historical code or artifacts are changed.
            legacy.OUT, legacy.write_bytes = OUT, put_bytes
            return self.client.fetch(request["execution_ordinal"], request["sampled_pmids"][0])
        finally:
            legacy.OUT, legacy.write_bytes = original_out, original_writer


def preserve_attempts(request: dict, attempts: list[dict]) -> list[dict]:
    result = []
    require(1 <= len(attempts) <= 4, "ATTEMPT_COUNT_OUTSIDE_FROZEN_POLICY")
    for number, attempt in enumerate(attempts, 1):
        require(attempt["attempt"] == number
                and attempt["parameters"] == request["parameters"]
                and attempt["endpoint"] == request["endpoint"]
                and attempt["method"] == request["method"]
                and digest(OUT / attempt["raw_path"]) == attempt["raw_sha256"],
                "ATTEMPT_PROVENANCE_OR_RAW_HASH_MISMATCH")
        success = attempt["http_status"] == 200 and attempt["transport_error"] is None
        terminal = success or number == len(attempts)
        enriched = {**attempt, "logical_request_id": request["logical_request_id"],
            "sampled_pmid": request["sampled_pmids"][0],
            "request_payload_sha256": request["request_payload_sha256"],
            "raw_response_path": attempt["raw_path"], "raw_response_sha256": attempt["raw_sha256"],
            "transport_terminal_state": "HTTP_SUCCESS" if success else "TERMINAL_TRANSPORT_FAILURE" if terminal else "TECHNICAL_RETRY",
            "terminal_attempt": terminal}
        append("metadata_request_attempt_log.jsonl", enriched)
        append("metadata_transport_provenance.jsonl", enriched)
        append("metadata_raw_response_manifest.jsonl", enriched)
        result.append(enriched)
    return result


def first_pass_fact(request: dict, raw: bytes | None, attempts: list[dict], state: dict) -> dict:
    pmid = request["sampled_pmids"][0]
    try:
        if raw is None:
            raise ValueError("TERMINAL_METADATA_TRANSPORT_FAILURE")
        parsed = v2.parse_source(raw, pmid, state["accepted"], state["excluded"])
    except (ValueError, ET.ParseError) as exc:
        parsed = {"pmid": pmid, "metadata_response_state": "SOURCE_FAILED_CLOSED",
            "metadata_state": "SOURCE_FAILED_CLOSED", "metadata_error": type(exc).__name__ + ":" + str(exc),
            "direct_pmcid": None, "direct_doi": None, "date_resolution_state": None,
            "date_state": "UNRESOLVED", "publication_type_state": "UNRESOLVED",
            "correction_update_state": "UNRESOLVED", "updateof_deferred_state": None}
    pmc_set = set(state["canonical_aliases"]["pmcid"]["canonical_values"])
    doi_set = set(state["canonical_aliases"]["doi"]["canonical_values"])
    pmc_contaminated = bool(parsed["direct_pmcid"] and parsed["direct_pmcid"] in pmc_set)
    doi_contaminated = bool(parsed["direct_doi"] and parsed["direct_doi"] in doi_set)
    conflicts = []
    for kind, xml_type in (("pmcid", "pmc"), ("doi", "doi")):
        values = {row["value"] for row in parsed.get("direct_primary_article_ids", []) if row["id_type"] == xml_type}
        if len(values) > 1:
            conflicts.append(kind)
    return {**parsed, "logical_request_id": request["logical_request_id"],
        "execution_ordinal": request["execution_ordinal"],
        "stratum": request["source_selection_provenance"]["owner_stratum"],
        "selection_provenance": request["source_selection_provenance"],
        "raw_response_sha256": sha(raw) if raw is not None else None,
        "raw_response_path": attempts[-1]["raw_response_path"] if raw is not None else None,
        "transport_terminal_state": attempts[-1]["transport_terminal_state"],
        "historical_pmcid_contaminated": pmc_contaminated,
        "historical_doi_contaminated": doi_contaminated,
        "historical_alias_contamination_state": "POST_SAMPLE_EXACT_SOURCE_CONTAMINATION" if pmc_contaminated or doi_contaminated else "CLEAR",
        "single_record_identifier_conflict_state": "FAIL_CLOSED" if conflicts else "CLEAR",
        "single_record_conflicting_identifier_kinds": conflicts,
        "single_record_identity_unresolved_reasons": parsed.get("metadata_unresolved_reasons", [])}


def write_initial_barrier(state: dict) -> None:
    for name, expected in (("alpha3_21c1_root_verification.json", C1_SHA),
        ("alpha3_21c_root_verification.json", authority.C_SHA),
        ("alpha3_21b_root_verification.json", authority.c.B_SHA),
        ("alpha3_21_master_root_verification.json", authority.c.b.MASTER_SHA)):
        put(name, {"root_sha256": expected, "verified_before_network": True})
    put("metadata_request_manifest_preexecution_verification.json", {
        "artifact": ref(C / "metadata_request_manifest.jsonl", "only_72_request_universe"),
        "logical_request_count": 72, "execution_order_unchanged": True, "regenerated": False})
    put("metadata_parser_v2_binding.json", ref(C1 / "alpha321_metadata_eligibility_parser_contract_v2.json", "frozen_C1_composite_parser"))
    put("publication_date_contract_v2_binding.json", ref(C1 / "publication_date_resolution_contract_v2.json", "frozen_C1_date_resolver"))
    put("execution_implementation_binding.json", authority.implementation(run, "C2_transport_and_barrier_orchestration"))
    put("focused_test_implementation_binding.json", ref(ROOT / "tests/test_search_plan_v24_alpha321c2_metadata_execution.py", "offline_mocked_transport_and_barrier_tests"))
    put("metadata_pre_network_integrity_barrier.json", {
        "passed": True, "verified_before_request_1": True, "logical_request_count": 72,
        "metadata_network_authorized": True, "PMC_network_authorized": False,
        "C_remains_historically_failed": True,
        "frozen_client": authority.implementation(legacy.PubMedTransport.fetch, "unchanged_frozen_transport_body"),
        "component_bindings": ref(C1 / "metadata_parser_component_binding_manifest.json", "unchanged_frozen_components"),
        "request_manifest_sha256": authority.REQUEST_SHA, "sample_manifest_sha256": authority.c.SAMPLE_SHA})
    for name in ("metadata_request_attempt_log.jsonl", "metadata_transport_provenance.jsonl", "metadata_raw_response_manifest.jsonl",
                 "metadata_first_pass_source_facts.jsonl", "metadata_per_source_response_terminal_states.jsonl"):
        put_bytes(name, b"")


def first_pass(state: dict, transport) -> tuple[list[dict], list[dict], list[dict]]:
    facts, responses, all_attempts = [], [], []
    for request in state["requests"]:
        raw, attempts = transport.fetch(request)
        enriched = preserve_attempts(request, attempts)
        all_attempts.extend(enriched)
        require(len(all_attempts) <= 288, "TRANSPORT_BUDGET_EXCEEDED")
        require((raw is not None) == (enriched[-1]["transport_terminal_state"] == "HTTP_SUCCESS"),
                "TRANSPORT_RETURN_STATE_MISMATCH")
        if raw is not None:
            require(sha(raw) == enriched[-1]["raw_response_sha256"], "RETURNED_RAW_BYTES_MISMATCH")
        fact = first_pass_fact(request, raw, enriched, state)
        append("metadata_first_pass_source_facts.jsonl", fact)
        append("metadata_per_source_response_terminal_states.jsonl", {
            "pmid": fact["pmid"], "logical_request_id": fact["logical_request_id"],
            "metadata_response_state": fact["metadata_response_state"], "metadata_state": fact["metadata_state"],
            "transport_terminal_state": fact["transport_terminal_state"], "metadata_error": fact["metadata_error"],
            "attempt_count": len(enriched), "terminal": True})
        facts.append(fact)
        responses.append({"pmid": fact["pmid"], "raw_xml": raw})
        print(json.dumps({"stage": "metadata_first_pass", "logical_requests_terminal": len(facts),
                          "total": 72, "transport_attempts": len(all_attempts)}, sort_keys=True), flush=True)
    require(len(facts) == 72 and [r["pmid"] for r in facts] == [r["pmid"] for r in state["sample"]],
            "FIRST_PASS_NOT_COMPLETE")
    return facts, responses, all_attempts


def freeze_first_pass(facts: list[dict], attempts: list[dict]) -> None:
    fact_sha = digest(OUT / "metadata_first_pass_source_facts.jsonl")
    require(rows(OUT / "metadata_first_pass_source_facts.jsonl") == facts, "FIRST_PASS_FACT_FILE_MISMATCH")
    marker("metadata_first_pass_source_facts_sha256", fact_sha)
    marker("metadata_raw_response_manifest_sha256", digest(OUT / "metadata_raw_response_manifest.jsonl"))
    projections = {
        "metadata_direct_date_extraction.jsonl": lambda f: {"representations": f.get("date_resolution", {}).get("representations", [])},
        "metadata_date_resolution_states.jsonl": lambda f: {"state": f["date_resolution_state"], "date_state": f["date_state"]},
        "metadata_publication_type_states.jsonl": lambda f: {"state": f["publication_type_state"], "result": f.get("publication_type_result")},
        "metadata_correction_update_states.jsonl": lambda f: {"state": f["correction_update_state"], "deferred_state": f["updateof_deferred_state"], "result": f.get("correction_result")},
        "metadata_direct_identifier_extraction.jsonl": lambda f: {"direct_pmcid": f["direct_pmcid"], "direct_doi": f["direct_doi"],
            "direct_primary_article_ids": f.get("direct_primary_article_ids", []), "single_record_identifier_conflict_state": f["single_record_identifier_conflict_state"],
            "identity_unresolved_reasons": f["single_record_identity_unresolved_reasons"]},
        "metadata_historical_alias_contamination_states.jsonl": lambda f: {"pmcid_contaminated": f["historical_pmcid_contaminated"], "doi_contaminated": f["historical_doi_contaminated"], "state": f["historical_alias_contamination_state"]},
    }
    for name, project in projections.items():
        put_rows(name, [{"pmid": f["pmid"], "stratum": f["stratum"], **project(f)} for f in facts])
    put("metadata_requested_pmid_binding_audit.json", {"all_structurally_valid_responses_bound_to_requested_pmid": True,
        "invalid_response_identifiers_imported": False, "no_borrowed_returned_record": True,
        "valid_response_count": sum(f["metadata_response_state"] == "RESOLVED" for f in facts)})
    put("metadata_identity_freeze_before_collision_analysis.json", {
        "passed": True, "all_72_logical_requests_terminal": True,
        "per_source_fact_count": len(facts), "transport_attempt_count": len(attempts),
        "first_pass_facts": ref(OUT / "metadata_first_pass_source_facts.jsonl", "immutable_first_pass_before_collision_graph"),
        "raw_responses": ref(OUT / "metadata_raw_response_manifest.jsonl", "raw_attempt_manifest"),
        "same_attempt_collision_analysis_started": False, "handoff_derivation_started": False})


def freeze_graph(facts: list[dict]) -> dict:
    barrier = obj(OUT / "metadata_identity_freeze_before_collision_analysis.json")
    require(barrier["all_72_logical_requests_terminal"] and barrier["per_source_fact_count"] == 72
            and digest(OUT / "metadata_first_pass_source_facts.jsonl") == barrier["first_pass_facts"]["sha256"],
            "COLLISION_ANALYSIS_BEFORE_IDENTITY_FREEZE")
    graph = v2.collision_components([{"pmid": f["pmid"], "pmcid": f["direct_pmcid"], "doi": f["direct_doi"]} for f in facts])
    put_rows("same_attempt_identity_collision_edges.jsonl", graph["edges"])
    put_rows("same_attempt_identity_collision_nodes.jsonl", [{"pmid": f["pmid"], "direct_pmcid": f["direct_pmcid"],
        "direct_doi": f["direct_doi"], "usable_direct_identity": bool(f["direct_pmcid"] or f["direct_doi"]),
        "collision_state": graph["source_states"][f["pmid"]]} for f in facts])
    put("same_attempt_identity_collision_components.json", graph)
    put("same_attempt_identity_collision_audit.json", {"frozen_before_final_handoff_derivation": True,
        "component_count": len(graph["components"]), "affected_pmids": sorted([p for p, state in graph["source_states"].items() if state == v2.COLLISION], key=int),
        "historically_contaminated_valid_identities_included": True,
        "resolution": "FAIL_CLOSE_ALL_COMPONENT_MEMBERS", "winner_selection_used": False,
        "collapse_used": False, "replacement_allowed": False,
        "identity_freeze": ref(OUT / "metadata_identity_freeze_before_collision_analysis.json", "completed_first_pass_barrier")})
    return graph


def finalize(state: dict, facts: list[dict], responses: list[dict], attempts: list[dict], graph: dict) -> dict:
    # The unchanged composite function is run only after both barriers are frozen.
    evaluation = v2.evaluate_batch(responses, state["accepted"], state["excluded"],
        set(state["canonical_aliases"]["pmcid"]["canonical_values"]),
        set(state["canonical_aliases"]["doi"]["canonical_values"]))
    require(canonical(evaluation["collision_graph"]) == canonical(graph), "FROZEN_GRAPH_REPLAY_MISMATCH")
    final = []
    for fact, decision in zip(facts, evaluation["records"]):
        require(all(fact[k] == value for k, value in decision.items() if k in fact), "FIRST_PASS_REPLAY_MISMATCH")
        final.append({**fact, **decision})
    require(len(final) == 72 and [f["pmid"] for f in final] == [s["pmid"] for s in state["sample"]], "FINAL_SOURCE_UNIVERSE_MISMATCH")
    put_rows("metadata_final_source_states.jsonl", final)
    reasons = Counter(f["primary_terminal_reason"] for f in final)
    put("metadata_terminal_reason_summary.json", {"primary_reason_counts": dict(sorted(reasons.items())),
        "source_count": 72, "per_dimension_counts_may_overlap": True, "precedence": v2.PRECEDENCE})
    exposed = [{"pmid": f["pmid"], "stratum": f["stratum"], "pmcid": f["direct_pmcid"], "doi": f["direct_doi"],
        "direct_primary_article_ids": f.get("direct_primary_article_ids", []), "metadata_identity_state": f["metadata_state"],
        "raw_response_sha256": f["raw_response_sha256"], "raw_response_path": f["raw_response_path"],
        "final_source_state": f["pre_oa_handoff_state"], "use": "future_attempt_history_only"}
        for f in final if f["metadata_response_state"] == "RESOLVED"]
    exposure_sha = put("alpha3_21_current_attempt_metadata_identity_exposure_registry.json", {
        "source_identities": exposed, "source_identity_count": len(exposed),
        "includes_valid_but_currently_excluded_sources": True, "current_exclusion_authority": False,
        "preexisting_registry_mutated": False, "current_attempt_aliases_self_exclude": False})
    marker("alpha3_21_current_attempt_metadata_identity_exposure_registry_sha256", exposure_sha)
    handoff = [{"pmid": f["pmid"], "stratum": f["stratum"], "pmcid": f["direct_pmcid"], "doi": f["direct_doi"],
        "metadata_state": f["metadata_state"], "pre_oa_handoff_state": f["pre_oa_handoff_state"],
        "correction_update_state": f["correction_update_state"], "updateof_deferred_state": f["updateof_deferred_state"],
        "raw_response_sha256": f["raw_response_sha256"], "selection_provenance": f["selection_provenance"]}
        for f in final if f["pre_oa_handoff_state"] != "BLOCKED"]
    handoff_sha = put("alpha3_21d_pre_oa_source_handoff.json", {"sources": handoff, "source_count": len(handoff),
        "frozen_before_any_PMC_request": True, "PMC_execution_authorized": False,
        "sampled_source_manifest_sha256": authority.c.SAMPLE_SHA,
        "metadata_final_source_states": ref(OUT / "metadata_final_source_states.jsonl", "all_dimension_terminal_decisions")})
    marker("alpha3_21d_pre_oa_source_handoff_sha256", handoff_sha)
    funnel = {"sampled_source_count": 72, "metadata_valid_response_count": len(exposed),
        "metadata_terminal_failure_count": 72 - len(exposed),
        "metadata_identity_resolved_count": sum(f["metadata_state"] == "RESOLVED" for f in final),
        "metadata_identity_unresolved_count": sum(f["metadata_state"] == "UNRESOLVED" for f in final),
        "date_clear_in_window_count": sum(f["date_resolution_state"] == v2.DATE_IN for f in final),
        "date_clear_outside_window_count": sum(f["date_resolution_state"] == v2.DATE_OUT for f in final),
        "date_unresolved_count": sum(f["date_resolution_state"] not in (v2.DATE_IN, v2.DATE_OUT) for f in final),
        "publication_type_eligible_count": sum(f["publication_type_state"] == "CLEAR" for f in final),
        "publication_type_excluded_count": sum(f["publication_type_state"] != "CLEAR" for f in final),
        "correction_update_clear_count": sum(f["correction_update_state"] == "CLEAR" for f in final),
        "correction_update_deferred_count": sum(f["updateof_deferred_state"] is not None for f in final),
        "correction_update_excluded_count": sum(f["correction_update_state"] != "CLEAR" and f["updateof_deferred_state"] is None for f in final),
        "historical_pmcid_contaminated_count": sum(f["historical_pmcid_contaminated"] for f in final),
        "historical_doi_contaminated_count": sum(f["historical_doi_contaminated"] for f in final),
        "single_record_identifier_conflict_count": sum(f["single_record_identifier_conflict_state"] != "CLEAR" for f in final),
        "same_attempt_collision_component_count": len(graph["components"]),
        "same_attempt_collision_source_count": sum(f["same_attempt_alias_collision_state"] != "CLEAR" for f in final),
        "pre_oa_handoff_count": len(handoff), "pre_oa_clear_count": sum(h["pre_oa_handoff_state"] == "PRE_OA_CLEAR" for h in handoff),
        "pre_oa_conditional_deferred_count": sum(h["pre_oa_handoff_state"] == "PRE_OA_CONDITIONAL_UPDATEOF" for h in handoff)}
    put("metadata_source_funnel.json", {**funnel, "per_dimension_counts_overlap": True,
        "metadata_valid_response_means_structural_validity_not_identity_or_scientific_eligibility": True,
        "unavailable_date_type_correction_dimensions_on_failed_metadata_are_reported_unresolved": True})
    accounting = {"metadata_logical_requests": 72, "metadata_logical_requests_executed": len(facts),
        "pubmed_metadata_logical_requests": 72, "metadata_transport_attempts": len(attempts),
        "metadata_technical_retry_count": len(attempts) - len(facts), "metadata_valid_responses": len(exposed),
        "metadata_terminal_failures": 72 - len(exposed), "network_calls": len(attempts),
        "pubmed_calls": len(attempts), "pubmed_metadata_calls": len(attempts), **ZERO_CALLS}
    put("metadata_execution_accounting.json", accounting)
    preflight()
    put("metadata_request_manifest_postexecution_verification.json", {
        "sha256": digest(C / "metadata_request_manifest.jsonl"), "unchanged": True})
    put("sampled_source_manifest_postexecution_verification.json", {
        "sha256": digest(B / "sampled_source_manifest.jsonl"), "unchanged": True})
    put("downstream_no_replacement_audit.json", {"downstream_replacement_used": False,
        "source_additions": 0, "sample_changes": 0, "unsampled_sources_used": 0})
    put("current_attempt_no_self_contamination_audit.json", {"current_attempt_aliases_self_exclude": False,
        "only_master_preexisting_alias_sets_used": True, "historical_pmcid_count": 146, "historical_doi_count": 180,
        "future_exposure_registry_used_for_current_exclusion": False})
    nonadaptation = {k: False for k in ("publication_date_policy_changed", "publication_type_policy_changed",
        "correction_update_policy_changed", "collision_policy_changed", "sample_changed", "query_changed", "metadata_request_manifest_changed")}
    put("fresh_primary_policy_nonadaptation_audit.json", nonadaptation)
    for name in ("builder_v4_nonuse_audit.json", "quality_nonuse_audit.json"):
        put(name, {"requests_constructed": 0, "provider_calls": 0, "execution_started": False})
    put("historical_preservation_audit.json", {"C1_C_B_master_roots_unchanged": True,
        "failed_C_state_unchanged": True, "preexisting_registries_unchanged": True, "historical_assets_modified": False})
    safety = {k: False for k in ("pmc_execution_started", "builder_execution_started", "quality_execution_started", "retrieval_evaluation_started")}
    put("scientific_state_safety_audit.json", {**safety, **ZERO_CALLS})
    put("protocol_compliance_audit.json", {"all_72_logical_requests_terminal": True,
        "raw_bytes_frozen_before_parse": True, "facts_frozen_before_graph": True, "graph_frozen_before_handoff": True,
        "transport_policy_unchanged": True, "source_failure_isolation_preserved": True,
        "all_raw_attempt_hashes_verified": all(digest(OUT / a["raw_response_path"]) == a["raw_response_sha256"] for a in attempts),
        "maximum_transport_attempts_respected": len(attempts) <= 288,
        "primary_terminal_reasons_cover_exactly_72_sources": sum(reasons.values()) == 72,
        "no_scientific_content_selection": True, "no_network_beyond_PubMed_metadata": True})
    result = {"status": "completed", "stage_identity": IDENTITY, "alpha3_21c2_classification": CLASS_OK,
        "alpha3_21c1_root_verified": True, "alpha3_21c_root_verified": True, "alpha3_21b_root_verified": True,
        "alpha3_21_master_root_verified": True, "metadata_request_manifest_unchanged": True,
        **funnel, **accounting, **nonadaptation, **safety,
        "same_attempt_collision_resolution": "FAIL_CLOSE_ALL_COMPONENT_MEMBERS",
        "current_attempt_aliases_self_exclude": False, "downstream_replacement_used": False,
        "alpha3_21_current_attempt_metadata_identity_exposure_registry_sha256": exposure_sha,
        "alpha3_21d_pre_oa_source_handoff_sha256": handoff_sha, "historical_assets_modified": False,
        "next_stage_recommendation": "PREREGISTER_ALPHA3_21D_PMC_OA_JATS_AND_CONSTRUCTION_SOURCE_RESOLUTION" if handoff
            else "CLOSE_ALPHA3_21_PRIMARY_WITH_ZERO_PRE_OA_HANDOFF"}
    put("validation.json", result)
    put("summary.json", result)
    root = root_hash(OUT, ROOT_MARKER)
    marker(ROOT_MARKER, root)
    return {**result, ROOT_MARKER: root}


def run(transport_factory=FrozenTransportAdapter) -> dict:
    require(not OUT.exists(), "C2_OUTPUT_ALREADY_EXISTS_NO_RERUN_OR_OVERWRITE")
    transport = None
    try:
        state = preflight()
        OUT.mkdir()
        write_initial_barrier(state)
        transport = transport_factory(state["transport"])
        facts, responses, attempts = first_pass(state, transport)
        require(transport.calls == len(attempts), "TRANSPORT_CALL_ACCOUNTING_MISMATCH")
        freeze_first_pass(facts, attempts)
        graph = freeze_graph(facts)
        return finalize(state, facts, responses, attempts, graph)
    except Exception as exc:
        # No retry/rerun on an authority or orchestration defect. Keep raw history.
        OUT.mkdir(parents=True, exist_ok=True)
        result = {"status": "failed", "stage_identity": IDENTITY, "alpha3_21c2_classification": CLASS_FAIL,
            "failure": type(exc).__name__ + ":" + str(exc), "metadata_transport_attempts": transport.calls if transport else 0,
            "deterministic_progression_stopped": True, **ZERO_CALLS,
            "next_stage_recommendation": "AUDIT_ALPHA3_21C2_AUTHORITY_OR_RUNTIME_FAILURE_OFFLINE"}
        if not (OUT / "validation.json").exists():
            put("validation.json", result)
        if not (OUT / "summary.json").exists():
            put("summary.json", result)
        root = root_hash(OUT, ROOT_MARKER)
        if not (OUT / ROOT_MARKER).exists():
            marker(ROOT_MARKER, root)
        return {**result, ROOT_MARKER: root}


if __name__ == "__main__":
    outcome = run()
    print(json.dumps(outcome, sort_keys=True), flush=True)
    raise SystemExit(0 if outcome["status"] == "completed" else 1)
