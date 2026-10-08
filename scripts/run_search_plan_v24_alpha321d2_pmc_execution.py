#!/usr/bin/env python3
"""Execute frozen D requests with the D.1 identity overlay, stopping before 21E.

The historical PMCTransport.fetch supplies all network/retry mechanics. Its
two persistence hooks are scoped to this new output directory and enriched
with immutable request provenance; no historical file or policy is changed.
"""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from scripts import run_search_plan_v24_alpha321d1_identity_authority_offline as d1


ROOT, D, D1, C2, MASTER = d1.ROOT, d1.d.OUT, d1.OUT, d1.d.C2, d1.d.MASTER
OUT = ROOT / "runs/20261007_search_plan_v24_primary_alpha3_21d2_pmc_oa_jats_execution"
ROOT_MARKER = "search_plan_v24_primary_alpha3_21d2_sha256"
D1_SHA = "1b85496e593a927e13f59fd8e1e8432d807c2fedd8aa26daeda888ab683c6e0e"
IDENTITY_SHA = "aa01ee09bd469dcc986d065c2c0ef944db430642094bfec45fd0b4b0d7ee904a"
COMPOSITE_SHA = "36525d873c1ae1c62acad36bbfbc914231852f814552c8c1f388d2d0dd4abb85"
CLASS_OK = "FRESH_PRIMARY_PMC_OA_JATS_AND_CONSTRUCTION_SOURCE_RESOLUTION_COMPLETE_AND_FROZEN"
CLASS_FAIL = "FRESH_PRIMARY_PMC_OA_JATS_EXECUTION_FAILED_CLOSED"
STAGE = "FRESH_PRIMARY_ALPHA3_21_PMC_OA_JATS_EXECUTION"
canonical, sha, digest, obj, rows, ref, root_hash, require = d1.canonical, d1.sha, d1.digest, d1.obj, d1.rows, d1.ref, d1.root_hash, d1.require
legacy, identity, body = d1.d.d19, d1.v2, d1.d.body_only
NO_CALLS = {k: 0 for k in ("pubmed_calls", "provider_calls", "llm_calls", "builder_calls", "quality_calls")}
UNCHANGED = {k: False for k in ("oa_policy_changed", "license_policy_changed", "jats_identity_policy_changed",
    "body_policy_changed", "updateof_policy_changed", "sample_changed", "network_request_manifest_changed",
    "source_type_policy_changed", "scientific_policy_changed", "source_queries_changed", "sampling_seed_changed")}
STREAMS = ["oa_request_attempt_log.jsonl", "oa_raw_response_manifest.jsonl", "oa_source_states.jsonl",
    "jats_request_attempt_log.jsonl", "jats_raw_response_manifest.jsonl", "jats_structural_states.jsonl",
    "jats_direct_identifier_extraction.jsonl", "jats_primary_identity_states_v2.jsonl", "jats_license_states.jsonl",
    "canonical_body_states.jsonl", "canonical_body_manifest.jsonl", "updateof_structural_resolution_states.jsonl"]
REQUIRED_JSON = ["alpha3_21d1_root_verification", "alpha3_21d_root_verification", "alpha3_21c2_root_verification",
    "alpha3_21_master_root_verification", "alpha3_21d_input_manifest_verification",
    "alpha3_21d_network_manifest_preexecution_verification", "alpha321_pmc_jats_execution_authority_v2_binding",
    "d2_pre_network_integrity_barrier", "oa_phase_completion_barrier", "alpha3_21d2_jats_activation_manifest",
    "jats_primary_identity_v2_audit", "d2_source_funnel", "alpha3_21_current_attempt_fulltext_exposure_registry",
    "alpha3_21e_construction_source_handoff", "alpha3_21d_network_manifest_postexecution_verification",
    "no_self_contamination_audit", "downstream_no_replacement_audit", "network_execution_accounting",
    "fresh_primary_policy_nonadaptation_audit", "builder_v4_nonuse_audit", "quality_nonuse_audit",
    "known_preexisting_test_environment_issue", "historical_preservation_audit", "scientific_state_safety_audit",
    "protocol_compliance_audit", "validation", "summary"]
REQUIRED_MARKERS = ["oa_source_states_sha256", "alpha3_21d2_jats_activation_manifest_sha256",
    "canonical_body_manifest_sha256", "alpha3_21_current_attempt_fulltext_exposure_registry_sha256",
    "alpha3_21e_construction_source_handoff_sha256"]


def utc():
    return datetime.now(timezone.utc).isoformat()


def put_bytes(name, raw):
    path = OUT / name
    require(path.resolve().is_relative_to(OUT.resolve()), "OUTPUT_PATH_ESCAPE")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return sha(raw)


def put(name, value):
    return put_bytes(name, canonical(value) + b"\n")


def append(name, value):
    with (OUT / name).open("ab") as handle:
        handle.write(canonical(value) + b"\n")
        handle.flush()
        os.fsync(handle.fileno())


def put_rows(name, values):
    return put_bytes(name, b"".join(canonical(value) + b"\n" for value in values))


def mark(stem, value):
    put_bytes(stem + "_sha256", (value + "\n").encode("ascii"))


def freeze(stem, value):
    result = put(stem + ".json", value)
    mark(stem, result)
    return result


def preflight():
    require((D1 / d1.ROOT_MARKER).read_text().strip() == D1_SHA and root_hash(D1, d1.ROOT_MARKER) == D1_SHA,
            "D1_ROOT_MISMATCH_STOP_BEFORE_NETWORK")
    state = d1.preflight()
    for path in sorted(D1.glob("*.json")):
        d1.d.checked_tree(obj(path))
    for stem, expected in (("jats_primary_source_identity_contract_v2", IDENTITY_SHA),
                           ("alpha321_pmc_jats_execution_authority_v2", COMPOSITE_SHA)):
        require(digest(D1 / (stem + ".json")) == expected and (D1 / (stem + "_sha256")).read_text().strip() == expected,
                "V2_AUTHORITY_HASH_MISMATCH_STOP_BEFORE_NETWORK")
    require(obj(D1 / "summary.json")["status"] == "completed"
            and obj(D1 / "summary.json")["pmc_end_to_end_execution_authority_resolved"] is True,
            "D1_AUTHORITY_UNRESOLVED")
    requests = rows(d1.REQUESTS)
    require(len(state["input_sources"]) == 49
            and sum(s["pre_oa_handoff_state"] == "PRE_OA_CLEAR" for s in state["input_sources"]) == 46
            and sum(s["pre_oa_handoff_state"] == "PRE_OA_CONDITIONAL_UPDATEOF" for s in state["input_sources"]) == 3,
            "SOURCE_BOUNDARY_MISMATCH")
    return {**state, "requests": requests}


class FrozenTransportAdapter:
    """Use unchanged fetch; route only its output hooks to the new stage."""

    def __init__(self):
        self.client = legacy.PMCTransport(attempts_max=4, timeout=60, backoff=(2, 4, 8))
        self.attempts = []
        self.executed = set()
        self.current = None

    def persist_attempt(self, name, entry):
        require(name == "pmc_request_attempts.jsonl" and self.current is not None, "UNEXPECTED_PMC_PERSISTENCE_HOOK")
        request = self.current
        source = request["source_provenance"]
        phase = "oa" if request["request_class"] == "PMC_OA_SUBSET" else "jats"
        succeeded = entry["http_status"] == 200 and entry["transport_error"] is None
        retryable = entry["http_status"] is None or entry["http_status"] in {408, 429, 500, 502, 503, 504}
        transport_state = "TERMINAL_UNHANDLED_FROZEN_CLIENT_EXCEPTION" if entry.get("unhandled_frozen_client_exception") else "TRANSPORT_SUCCESS" if succeeded else "RETRYABLE_TRANSPORT_FAILURE" if retryable and entry["attempt"] < 4 else "TERMINAL_TRANSPORT_FAILURE"
        record = {**entry, "logical_request_id": request["logical_request_id"],
            "frozen_source_input_ordinal": request["source_input_ordinal"], "expected_pmcid": source["pmcid"],
            "expected_doi": source["doi"], "request_payload_sha256": request["request_payload_sha256"],
            "frozen_request_record_sha256": sha(canonical(request)), "transport_attempt_state": transport_state,
            "raw_artifact": ref(OUT / entry["raw_path"], "preserved_before_response_parsing"),
            "source_terminal_link": {"artifact_path": str((OUT / ("oa_source_states.jsonl" if phase == "oa" else "jats_structural_states.jsonl")).relative_to(ROOT)),
                "record_key": {"pmid": source["pmid"], "logical_request_id": request["logical_request_id"]}}}
        require(digest(OUT / entry["raw_path"]) == entry["raw_sha256"], "RAW_ATTEMPT_HASH_MISMATCH")
        self.attempts.append(record)
        append(phase + "_request_attempt_log.jsonl", record)
        append(phase + "_raw_response_manifest.jsonl", record)

    @contextmanager
    def persistence_hooks(self):
        original_bytes, original_append = legacy.write_bytes, legacy.append_jsonl
        legacy.write_bytes, legacy.append_jsonl = put_bytes, self.persist_attempt
        try:
            yield
        finally:
            legacy.write_bytes, legacy.append_jsonl = original_bytes, original_append

    def fetch(self, request, ordinal):
        require(request["logical_request_id"] not in self.executed, "SUCCESSFUL_OR_TERMINAL_REQUEST_REFRESH_FORBIDDEN")
        payload = request["request_payload"]
        require(payload["method"] == "GET" and sha(canonical(payload)) == request["request_payload_sha256"]
                and payload["endpoint"] == (legacy.ES if request["request_class"] == "PMC_OA_SUBSET" else legacy.EF)
                and payload["parameters"]["db"] == "pmc" and len(self.executed) < 98, "FROZEN_NETWORK_SCOPE_MISMATCH")
        if request["request_class"] == "PMC_JATS":
            require((OUT / "oa_phase_completion_barrier.json").is_file()
                    and obj(OUT / "oa_phase_completion_barrier.json")["all_49_terminal_states_frozen"] is True
                    and digest(OUT / "oa_source_states.jsonl") == (OUT / "oa_source_states_sha256").read_text().strip()
                    and digest(OUT / "alpha3_21d2_jats_activation_manifest.json") ==
                        (OUT / "alpha3_21d2_jats_activation_manifest_sha256").read_text().strip(), "OA_ACTIVATION_BARRIER_VIOLATION")
            active = obj(OUT / "alpha3_21d2_jats_activation_manifest.json")["requests"]
            require(any(r["logical_request_id"] == request["logical_request_id"] and r["activation_state"] == "REQUIRED_BY_OA_ELIGIBILITY" for r in active),
                    "JATS_NOT_ACTIVATED")
        self.executed.add(request["logical_request_id"])
        self.current = request
        before_calls, before_logs = self.client.calls, len(self.attempts)
        phase = "oa" if request["request_class"] == "PMC_OA_SUBSET" else "jats"
        try:
            with self.persistence_hooks():
                return self.client.fetch(request["request_class"], ordinal, request["pmid"],
                    payload["endpoint"], payload["parameters"], "pmc_" + phase + "_raw_responses")
        except Exception as exc:
            # Do not invent a recovery/retry for exceptions outside frozen fetch.
            # Preserve any attempt that began but escaped its historical logger.
            if self.client.calls - before_calls > len(self.attempts) - before_logs:
                number = self.client.calls - before_calls
                path = f"pmc_{phase}_raw_responses/{ordinal:03d}_{request['pmid']}_attempt{number}.bin"
                raw = getattr(exc, "partial", b"")
                if not isinstance(raw, bytes):
                    raw = b""
                if not (OUT / path).exists():
                    put_bytes(path, raw)
                entry = {"stage": request["request_class"], "ordinal": ordinal, "pmid": request["pmid"],
                    "attempt": number, "method": "GET", "endpoint": payload["endpoint"], "parameters": payload["parameters"],
                    "timestamp_utc": utc(), "timestamp_kind": "unhandled_exception_observed_UTC",
                    "http_status": getattr(exc, "code", None), "transport_error": type(exc).__name__ + ":" + str(exc),
                    "raw_path": path, "raw_sha256": digest(OUT / path), "raw_bytes": (OUT / path).stat().st_size,
                    "unhandled_frozen_client_exception": True}
                self.persist_attempt("pmc_request_attempts.jsonl", entry)
            raise
        finally:
            self.current = None
            require(self.client.calls <= 392, "TRANSPORT_BUDGET_EXCEEDED")


def initialize(state):
    OUT.mkdir()
    for name in STREAMS:
        put_bytes(name, b"")
    for name, path, marker, expected in (("alpha3_21d1", D1, d1.ROOT_MARKER, D1_SHA),
        ("alpha3_21d", D, d1.d.ROOT_MARKER, d1.D_SHA), ("alpha3_21c2", C2, d1.d.c2.ROOT_MARKER, d1.d.C2_SHA),
        ("alpha3_21_master", MASTER, d1.MASTER_MARKER, d1.d.c2.authority.c.b.MASTER_SHA)):
        put(name + "_root_verification.json", {"verified": True, "root_sha256": expected,
            "root_marker": ref(path / marker, "unchanged_upstream_root")})
    put("alpha3_21d_input_manifest_verification.json", {"input": ref(d1.INPUT, "only_frozen_49_sources"),
        "source_count": 49, "clear": 46, "deferred": 3, "sample": ref(d1.d.B / "sampled_source_manifest.jsonl", "unchanged_72_sample"),
        "source_replacement_or_resampling": False})
    put("alpha3_21d_network_manifest_preexecution_verification.json", {"network_manifest": ref(d1.REQUESTS, "consume_frozen_requests_read_only"),
        "unchanged": True, "requests_regenerated": False, "mandatory_OA": 49, "conditional_JATS_maximum": 49})
    put("alpha321_pmc_jats_execution_authority_v2_binding.json", {
        "authority": ref(D1 / "alpha321_pmc_jats_execution_authority_v2.json", "all_D2_execution_rules"),
        "identity": ref(D1 / "jats_primary_source_identity_contract_v2.json", "unchanged_V2"),
        "UpdateOf": ref(D / "updateof_structural_resolution_contract.json", "unchanged_deferred_resolution"),
        "historical_transport": d1.d.implementation(legacy.PMCTransport.fetch, "unchanged_network_and_retry_mechanics"),
        "persistence_adapter": d1.d.implementation(FrozenTransportAdapter, "new_output_only_provenance_hooks"),
        "historical_D_failed_status_unchanged": True})
    put("execution_implementation_binding.json", d1.d.implementation(run, "new_D2_orchestration_only"))
    put("focused_test_implementation_binding.json", ref(ROOT / "tests/test_search_plan_v24_alpha321d2_pmc_execution.py", "synthetic_network_free_D2_tests"))
    put("d2_pre_network_integrity_barrier.json", {"all_required_authorities_verified": True, "timestamp_utc": utc(),
        "network_authorization": "explicit current-user alpha3.21D2 authorization only",
        "authorized_scope": "49 frozen OA requests plus OA-activated frozen conditional JATS requests",
        "request_manifest_sha256": d1.REQUEST_SHA, "input_manifest_sha256": d1.INPUT_SHA,
        "D1_root_sha256": D1_SHA, "identity_contract_sha256": IDENTITY_SHA, "composite_authority_sha256": COMPOSITE_SHA,
        "network_requests_before_barrier": 0, "all_49_OA_before_any_JATS": True, "other_network_authorized": False})


def execute_oa(state, transport):
    for ordinal, request in enumerate(state["requests"][:49], 1):
        raw, attempts = transport.fetch(request, ordinal)
        terminal, verdict = legacy.oa_subset_state(raw, attempts, request["pmcid"])
        require(terminal in {"OA_SUBSET_ELIGIBLE", "OA_SUBSET_INELIGIBLE", "OA_SUBSET_UNRESOLVED"}, "UNKNOWN_OA_AUTHORITY_STATE")
        append("oa_source_states.jsonl", {"logical_request_id": request["logical_request_id"], "pmid": request["pmid"],
            "pmcid": request["pmcid"], "state": terminal, "validity": verdict, "request_attempts": attempts,
            "final_raw_artifact": ref(OUT / attempts[-1]["raw_path"], "last_preserved_OA_attempt"),
            "transport_succeeded": raw is not None, "state_frozen_utc": utc()})
        print(json.dumps({"phase": "OA", "completed": ordinal, "total": 49, "state": terminal}), flush=True)
    oa = rows(OUT / "oa_source_states.jsonl")
    require(len(oa) == len({r["pmid"] for r in oa}) == 49, "OA_TERMINAL_STATES_INCOMPLETE")
    oa_sha = digest(OUT / "oa_source_states.jsonl")
    mark("oa_source_states", oa_sha)
    # Both names are requested in the task; alias is a physical byte copy.
    put_bytes("alpha3_21d2_oa_source_states.jsonl", (OUT / "oa_source_states.jsonl").read_bytes())
    mark("alpha3_21d2_oa_source_states", oa_sha)
    put("oa_phase_completion_barrier.json", {"all_49_terminal_states_frozen": True, "timestamp_utc": utc(),
        "OA_states": ref(OUT / "oa_source_states.jsonl", "frozen_before_activation"),
        "eligible_count": sum(r["state"] == "OA_SUBSET_ELIGIBLE" for r in oa), "JATS_requests_before_barrier": 0})
    by_pmid = {r["pmid"]: r for r in oa}
    active = []
    for request in state["requests"][49:]:
        oa_state = by_pmid[request["pmid"]]["state"]
        activation = "REQUIRED_BY_OA_ELIGIBILITY" if oa_state == "OA_SUBSET_ELIGIBLE" else "NOT_REQUIRED_OA_INELIGIBLE" if oa_state == "OA_SUBSET_INELIGIBLE" else "NOT_REQUIRED_OA_TERMINAL_FAILURE"
        active.append({"logical_request_id": request["logical_request_id"], "pmid": request["pmid"], "pmcid": request["pmcid"],
            "source_input_ordinal": request["source_input_ordinal"], "request_payload_sha256": request["request_payload_sha256"],
            "frozen_request_record_sha256": sha(canonical(request)), "oa_state": oa_state, "activation_state": activation})
    freeze("alpha3_21d2_jats_activation_manifest", {"frozen_request_manifest": ref(d1.REQUESTS, "only_original_conditional_universe"),
        "OA_states": ref(OUT / "oa_source_states.jsonl", "mechanical_activation_authority"), "requests": active,
        "conditional_count": 49, "required_count": sum(r["activation_state"] == "REQUIRED_BY_OA_ELIGIBILITY" for r in active),
        "timestamp_utc": utc(), "post_freeze_changes_allowed": False})
    return [request for request in state["requests"][49:] if by_pmid[request["pmid"]]["state"] == "OA_SUBSET_ELIGIBLE"]


def execute_jats(state, transport, activated):
    for ordinal, request in enumerate(activated, 1):
        raw, attempts = transport.fetch(request, ordinal)
        source = request["source_provenance"]
        base = {"pmid": source["pmid"], "pmcid": source["pmcid"], "doi": source["doi"],
            "logical_request_id": request["logical_request_id"], "frozen_source_input_ordinal": request["source_input_ordinal"],
            "runtime_ordinal": ordinal, "raw_artifact": ref(OUT / attempts[-1]["raw_path"], "last_preserved_JATS_attempt"),
            "request_attempts": attempts, "transport_succeeded": raw is not None}
        result = identity.validate_jats_primary_identity_v2(raw, expected_pmid=source["pmid"], expected_pmcid=source["pmcid"], expected_doi=source["doi"]) if raw is not None else None
        structure_valid = result is not None and result["jats_validity_state"] == "JATS_XML_ARTICLE_STRUCTURE_VALID"
        normalized = ET.tostring(identity.select_primary_article(raw), encoding="utf-8") if structure_valid else None
        normalized_ref = None
        if normalized is not None:
            path = f"pmc_jats_normalized/{ordinal:03d}_{source['pmid']}.xml"
            put_bytes(path, normalized)
            normalized_ref = ref(OUT / path, "structurally_valid_JATS_not_identity_rescue")
        structural = {**base, "state": "JATS_XML_ARTICLE_STRUCTURE_VALID" if structure_valid else "JATS_FAILED_NO_REPLACEMENT",
            "failure_kind": None if structure_valid else "STRUCTURAL_VALIDITY_FAILURE" if raw is not None else "TERMINAL_TRANSPORT_FAILURE",
            "error": result["structural_error"] if result is not None else "TERMINAL_JATS_TRANSPORT_FAILURE",
            "normalized_JATS": normalized_ref}
        append("jats_structural_states.jsonl", structural)
        if structure_valid:
            fact_path = f"jats_identity_facts/{ordinal:03d}_{source['pmid']}.json"
            put(fact_path, {**base, "result": result, "frozen_utc": utc()})
            # Individual identity file is durable before any license/BODY work.
            append("jats_primary_identity_states_v2.jsonl", {**base, "result": result,
                "immutable_identity_facts": ref(OUT / fact_path, "identity_frozen_before_downstream")})
            append("jats_direct_identifier_extraction.jsonl", {**base, "direct_identifiers": result["direct_identifiers"]})
        if structure_valid and result["source_identity_allows_progression"]:
            license_result = legacy.license_v2.extract_license_v2(normalized)
            combined = legacy.license_v2.construction_oa_v2(source["pmcid"], True, normalized)
            require(combined["state"] == "CONSTRUCTION_OA_" + license_result["state"], "LICENSE_AUTHORITY_INCONSISTENCY")
            append("jats_license_states.jsonl", {**base, "state": license_result["state"], "result": license_result,
                "construction_OA_result": combined, "normalized_JATS": normalized_ref})
            if license_result["state"] == "ELIGIBLE":
                normalize_body(source, normalized, base)
        print(json.dumps({"phase": "JATS", "completed": ordinal, "total": len(activated),
            "structure": structural["state"], "identity": result["identity_state"] if result is not None else None}), flush=True)


def normalize_body(source, normalized, base):
    try:
        result = body.canonical_body(normalized)
    except ValueError as exc:
        require(str(exc) in {"JATS body missing", "construction body empty"}, "NEW_BODY_AUTHORITY_AMBIGUITY:" + str(exc))
        append("canonical_body_states.jsonl", {**base, "state": "CANONICAL_BODY_UNUSABLE", "error": str(exc)})
        return
    pmid = source["pmid"]
    text_path = f"canonical_body/{pmid}.txt"
    provenance_path = f"canonical_body/{pmid}_paragraph_provenance.json"
    body_sha = put_bytes(text_path, result["body_text"].encode("utf-8"))
    put(provenance_path, {"canonical_BODY_sha256": body_sha, "normalization": result["normalization"], "paragraphs": result["paragraphs"],
        "controller_only": True, "span_anchors_generated": False, "ConstructionEvidenceDocument_generated": False})
    record = {**base, "state": "CANONICAL_BODY_USABLE", "canonical_BODY": ref(OUT / text_path, "unchanged_BODY_only_projection"),
        "canonical_BODY_sha256": body_sha, "paragraph_count": len(result["paragraphs"]),
        "paragraph_provenance": ref(OUT / provenance_path, "ordered_paragraph_offsets_not_span_anchors"),
        "normalization": result["normalization"], "model_visible_payload_generated": False}
    append("canonical_body_states.jsonl", record)
    append("canonical_body_manifest.jsonl", record)


def dimensions(state):
    by_oa = {r["pmid"]: r for r in rows(OUT / "oa_source_states.jsonl")}
    by_jats = {r["pmid"]: r for r in rows(OUT / "jats_structural_states.jsonl")}
    by_identity = {r["pmid"]: r for r in rows(OUT / "jats_primary_identity_states_v2.jsonl")}
    by_license = {r["pmid"]: r for r in rows(OUT / "jats_license_states.jsonl")}
    by_body = {r["pmid"]: r for r in rows(OUT / "canonical_body_states.jsonl")}
    result = []
    for source in state["input_sources"]:
        pmid = source["pmid"]
        oa, jats, bound, licensed, normalized = (mapping.get(pmid) for mapping in (by_oa, by_jats, by_identity, by_license, by_body))
        entry = {"pmid": pmid, "pmcid": source["pmcid"], "doi": source["doi"], "stratum": source["stratum"],
            "pre_oa_handoff_state": source["pre_oa_handoff_state"], "selection_provenance": source["selection_provenance"],
            "C2_correction_update_state": source["correction_update_state"], "C2_UpdateOf_deferred_state": source["updateof_deferred_state"],
            "oa_state": oa["state"] if oa else "NOT_EXECUTED_AFTER_ABORT",
            "jats_transport_state": "TRANSPORT_SUCCESS" if jats and jats["transport_succeeded"] else "TERMINAL_TRANSPORT_FAILURE" if jats else "NOT_REQUESTED",
            "jats_validity_state": jats["state"] if jats else "NOT_REQUESTED_OA_NOT_ELIGIBLE" if oa else "NOT_EXECUTED_AFTER_ABORT",
            "identity_state": bound["result"]["identity_state"] if bound else "NOT_EVALUATED_NO_VALID_JATS",
            "identity_failures": bound["result"]["identity_failures"] if bound else [],
            "identity_facts": bound["immutable_identity_facts"] if bound else None,
            "license_state": licensed["state"] if licensed else "NOT_EVALUATED_UPSTREAM_GATE",
            "body_state": normalized["state"] if normalized else "NOT_EVALUATED_UPSTREAM_GATE",
            "BODY": normalized if normalized and normalized["state"] == "CANONICAL_BODY_USABLE" else None,
            "source_type_state": "NOT_EVALUATED_UPSTREAM_GATE", "source_type_result": None,
            "normalized_JATS": jats["normalized_JATS"] if jats else None,
            "raw_JATS": jats["raw_artifact"] if jats else None, "updateof_resolution_reached": False,
            "updateof_terminal_resolution_state": None,
            "updateof_structural_state": "DEFERRED_TO_STRUCTURE_STAGE" if source["updateof_deferred_state"] == "DEFERRED_TO_STRUCTURE_STAGE" else "NOT_DEFERRED_METADATA_CLEAR"}
        if entry["body_state"] == "CANONICAL_BODY_USABLE":
            xml = (ROOT / jats["normalized_JATS"]["artifact_path"]).read_bytes()
            type_result = legacy.source_policy.source_type_state(source["publication_types"], xml)
            require(type_result["state"] in {"SOURCE_TYPE_ELIGIBLE", "SOURCE_TYPE_INELIGIBLE", "SOURCE_TYPE_UNRESOLVED"}, "UNKNOWN_SOURCE_TYPE_AUTHORITY")
            entry["source_type_result"], entry["source_type_state"] = type_result, type_result["state"]
        if source["updateof_deferred_state"] == "DEFERRED_TO_STRUCTURE_STAGE" and entry["source_type_result"] is not None:
            resolved = d1.d.d19_1.correction.classify(source["publication_types"], source["correction_relationships"], independent_primary_state=entry["source_type_state"])
            terminal = resolved["state"].removeprefix("CORRECTION_REFERENCE_")
            require(terminal in {"CLEAR", "INELIGIBLE", "UNRESOLVED"}, "UNKNOWN_UPDATEOF_AUTHORITY")
            entry.update({"updateof_resolution_reached": True, "updateof_terminal_resolution_state": terminal,
                "updateof_structural_state": resolved["state"], "updateof_resolution_result": resolved})
        terminal = primary_terminal_reason(entry)
        entry["construction_source_state"] = terminal
        if source["updateof_deferred_state"] == "DEFERRED_TO_STRUCTURE_STAGE":
            append("updateof_structural_resolution_states.jsonl", {"pmid": pmid, "pmcid": source["pmcid"],
                "resolution_reached": entry["updateof_resolution_reached"], "terminal_resolution_state": entry["updateof_terminal_resolution_state"],
                "preserved_C2_deferred_state": source["updateof_deferred_state"],
                "not_reached_prior_terminal_state": None if entry["updateof_resolution_reached"] else terminal,
                "result": entry.get("updateof_resolution_result"), "source_type_result": entry["source_type_result"],
                "authority": ref(D / "updateof_structural_resolution_contract.json", "exact_existing_structural_rule"),
                "C2_source_state_sha256": source["c2_source_state_sha256"], "scientific_content_used": False})
        result.append(entry)
    return result


def primary_terminal_reason(entry):
    if entry["oa_state"] == "NOT_EXECUTED_AFTER_ABORT":
        return "NOT_EXECUTED_AFTER_ABORT"
    if entry["oa_state"] != "OA_SUBSET_ELIGIBLE":
        return "BLOCKED_OA_SUBSET"
    if entry["jats_validity_state"] != "JATS_XML_ARTICLE_STRUCTURE_VALID":
        return "BLOCKED_JATS"
    if entry["identity_state"] != identity.SUCCESS:
        return "BLOCKED_PRIMARY_IDENTITY"
    if entry["license_state"] != "ELIGIBLE":
        return "BLOCKED_LICENSE"
    if entry["body_state"] != "CANONICAL_BODY_USABLE":
        return "BLOCKED_BODY_UNAVAILABLE"
    if entry["source_type_state"] != "SOURCE_TYPE_ELIGIBLE":
        return "BLOCKED_SOURCE_TYPE"
    if entry["C2_UpdateOf_deferred_state"] == "DEFERRED_TO_STRUCTURE_STAGE":
        if entry["updateof_terminal_resolution_state"] == "INELIGIBLE":
            return "BLOCKED_UPDATEOF_INELIGIBLE"
        if entry["updateof_terminal_resolution_state"] != "CLEAR":
            return "BLOCKED_UPDATEOF_UNRESOLVED"
    return "CONSTRUCTION_SOURCE_ELIGIBLE"


def exposure_registry(state, dimensions):
    by_dimension = {r["pmid"]: r for r in dimensions}
    by_identity = {r["pmid"]: r["result"] for r in rows(OUT / "jats_primary_identity_states_v2.jsonl")}
    authoritative, untrusted, observations = [], [], []
    for jats in rows(OUT / "jats_structural_states.jsonl"):
        pmid = jats["pmid"]
        dimension = by_dimension[pmid]
        ids = by_identity.get(pmid)
        base = {"controller_expected_identity": {"pmid": pmid, "pmcid": jats["pmcid"], "doi": jats["doi"]},
            "logical_request_id": jats["logical_request_id"], "raw_JATS": jats["raw_artifact"],
            "raw_JATS_sha256": jats["raw_artifact"]["sha256"], "retrieval_provenance": jats["request_attempts"],
            "canonical_BODY_sha256": dimension["BODY"]["canonical_BODY_sha256"] if dimension["BODY"] else None,
            "final_construction_state": dimension["construction_source_state"], "current_exclusion_authority": False,
            "direct_asserted_identifiers": ids["direct_identifiers"] if ids else None,
            "identity_state": ids["identity_state"] if ids else None}
        bound = ids is not None and ids["identity_state"] == identity.SUCCESS
        observations.append({**base, "authoritative_identity": bound, "transport_succeeded": jats["transport_succeeded"]})
        if bound:
            authoritative.append({**base, "pmid": pmid, "pmcid": jats["pmcid"], "doi": jats["doi"] or ids["authoritative_new_doi_assertion"],
                "authority": "immutable_C2_identity_bound_by_JATSPrimarySourceIdentityContractV2",
                "JATS_secondary_assertions": ids["per_identifier_states"], "authoritative_identity": True})
        elif any(a["raw_bytes"] > 0 for a in jats["request_attempts"]):
            untrusted.append({**base, "authoritative_identity": False, "canonical_future_source_identity": None})
    recorded = {j["pmid"] for j in rows(OUT / "jats_structural_states.jsonl")}
    pending = {}
    for attempt in rows(OUT / "jats_request_attempt_log.jsonl"):
        if attempt["pmid"] not in recorded:
            pending.setdefault(attempt["pmid"], []).append(attempt)
    for pmid, attempts in pending.items():
        source = next(s for s in state["input_sources"] if s["pmid"] == pmid)
        observation = {"controller_expected_identity": {"pmid": pmid, "pmcid": source["pmcid"], "doi": source["doi"]},
            "logical_request_id": attempts[-1]["logical_request_id"], "raw_JATS": attempts[-1]["raw_artifact"],
            "retrieval_provenance": attempts, "authoritative_identity": False, "direct_asserted_identifiers": None,
            "canonical_future_source_identity": None, "identity_processing_not_reached": True, "current_exclusion_authority": False}
        observations.append(observation)
        if any(a["raw_bytes"] > 0 for a in attempts):
            untrusted.append(observation)
    return {"schema_version": "Alpha321CurrentAttemptFulltextExposureRegistryV1", "future_history_only": True,
        "current_exclusion_authority": False, "current_attempt_fulltext_self_excludes": False,
        "source_identities": authoritative, "untrusted_observations": untrusted, "all_JATS_request_observations": observations,
        "authoritative_exposure_count": len(authoritative), "untrusted_observation_count": len(untrusted),
        "snapshot_interpretation": "NCBI PMC/OA/JATS observed during this frozen D2 run; no later refresh/topup"}


def funnel(state, source_states, transport):
    oa = rows(OUT / "oa_source_states.jsonl")
    jats = rows(OUT / "jats_structural_states.jsonl")
    ids = [r["result"] for r in rows(OUT / "jats_primary_identity_states_v2.jsonl")]
    licenses = rows(OUT / "jats_license_states.jsonl")
    bodies = rows(OUT / "canonical_body_states.jsonl")
    deferred = [s for s in source_states if s["C2_UpdateOf_deferred_state"] == "DEFERRED_TO_STRUCTURE_STAGE"]
    eligible = [s for s in source_states if s["construction_source_state"] == "CONSTRUCTION_SOURCE_ELIGIBLE"]
    oa_attempts = [a for a in transport.attempts if a["stage"] == "PMC_OA_SUBSET"]
    jats_attempts = [a for a in transport.attempts if a["stage"] == "PMC_JATS"]
    activation = obj(OUT / "alpha3_21d2_jats_activation_manifest.json") if (OUT / "alpha3_21d2_jats_activation_manifest.json").exists() else None
    values = {"pre_oa_input_source_count": 49, "pre_oa_clear_source_count": 46, "pre_oa_deferred_source_count": 3,
        "oa_logical_requests_planned": 49, "oa_logical_requests_executed": len({a["logical_request_id"] for a in oa_attempts}),
        "oa_transport_attempts": len(oa_attempts), "oa_technical_retry_count": sum(a["attempt"] > 1 for a in oa_attempts),
        "oa_valid_response_count": sum(r["state"] in {"OA_SUBSET_ELIGIBLE", "OA_SUBSET_INELIGIBLE"} for r in oa),
        "oa_terminal_failure_count": sum(r["state"] == "OA_SUBSET_UNRESOLVED" for r in oa),
        "oa_eligible_count": sum(r["state"] == "OA_SUBSET_ELIGIBLE" for r in oa),
        "oa_ineligible_count": sum(r["state"] == "OA_SUBSET_INELIGIBLE" for r in oa),
        "jats_logical_requests_conditionally_available": 49, "jats_logical_requests_activated": activation["required_count"] if activation else 0,
        "jats_logical_requests_executed": len({a["logical_request_id"] for a in jats_attempts}), "jats_transport_attempts": len(jats_attempts),
        "jats_technical_retry_count": sum(a["attempt"] > 1 for a in jats_attempts),
        "jats_valid_structure_count": sum(r["state"] == "JATS_XML_ARTICLE_STRUCTURE_VALID" for r in jats),
        "jats_structural_failure_count": sum(r["failure_kind"] == "STRUCTURAL_VALIDITY_FAILURE" for r in jats),
        "jats_terminal_transport_failure_count": sum(r["failure_kind"] == "TERMINAL_TRANSPORT_FAILURE" for r in jats),
        "jats_identity_exact_bound_count": sum(r["identity_state"] == identity.SUCCESS for r in ids),
        "jats_identity_failure_count": sum(r["identity_state"] != identity.SUCCESS for r in ids),
        "license_eligible_count": sum(r["state"] == "ELIGIBLE" for r in licenses),
        "license_ineligible_count": sum(r["state"] == "INELIGIBLE" for r in licenses),
        "license_unresolved_or_missing_count": sum(r["state"] == "UNRESOLVED" for r in licenses),
        "license_not_evaluated_upstream_count": 49 - len(licenses),
        "canonical_body_usable_count": sum(r["state"] == "CANONICAL_BODY_USABLE" for r in bodies),
        "canonical_body_unusable_count": sum(r["state"] == "CANONICAL_BODY_UNUSABLE" for r in bodies),
        "canonical_body_not_evaluated_upstream_count": 49 - len(bodies),
        "deferred_input_count": 3, "deferred_reached_structural_resolution_count": sum(s["updateof_resolution_reached"] for s in deferred),
        "deferred_not_reached_due_to_prior_terminal_state_count": sum(not s["updateof_resolution_reached"] for s in deferred),
        "construction_source_count": len(eligible), "construction_source_clear_count": sum(s["pre_oa_handoff_state"] == "PRE_OA_CLEAR" for s in eligible),
        "construction_source_deferred_or_other_permitted_count": sum(s["pre_oa_handoff_state"] == "PRE_OA_CONDITIONAL_UPDATEOF" for s in eligible),
        "per_stratum_construction_source_counts": {stratum: sum(s["stratum"] == stratum for s in eligible) for stratum in sorted({s["stratum"] for s in source_states})},
        "primary_terminal_counts": dict(Counter(s["construction_source_state"] for s in source_states)),
        "total_body_paragraph_count": sum(b["paragraph_count"] for b in bodies if b["state"] == "CANONICAL_BODY_USABLE"),
        "construction_source_BODY_paragraph_count": sum(s["BODY"]["paragraph_count"] for s in eligible),
        "total_logical_requests_executed": len(transport.executed), "total_transport_attempts": transport.client.calls}
    for name, terminal in (("pmcid_missing", "JATS_PRIMARY_PMCID_MISSING"), ("pmcid_mismatch", "JATS_PRIMARY_PMCID_MISMATCH"),
        ("pmid_mismatch", "JATS_DIRECT_PMID_MISMATCH"), ("doi_mismatch", "JATS_DIRECT_DOI_MISMATCH"),
        ("internal_identifier_conflict", identity.CONFLICT), ("other_identity_unresolved", identity.UNRESOLVED)):
        values["jats_" + name + "_count"] = sum(terminal in r["identity_failures"] for r in ids)
    for terminal in ("CLEAR", "INELIGIBLE", "UNRESOLVED"):
        values["deferred_" + terminal.lower() + "_count"] = sum(s["updateof_terminal_resolution_state"] == terminal for s in deferred)
    return values


def finalize(state, transport, status, failure=None):
    source_states = dimensions(state)
    put_rows("d2_per_source_dimension_states.jsonl", source_states)
    put_rows("d2_final_source_terminal_states.jsonl", [{"pmid": s["pmid"], "pmcid": s["pmcid"],
        "state": s["construction_source_state"], "per_dimension_record_sha256": sha(canonical(s))} for s in source_states])
    mark("canonical_body_manifest", digest(OUT / "canonical_body_manifest.jsonl"))
    handoff = []
    for source, dimension in zip(state["input_sources"], source_states):
        if dimension["construction_source_state"] != "CONSTRUCTION_SOURCE_ELIGIBLE":
            continue
        handoff.append({"pmid": source["pmid"], "expected_pmcid": source["pmcid"], "expected_doi": source["doi"], "stratum": source["stratum"],
            "selection_provenance": source["selection_provenance"], "C2_source_state_sha256": source["c2_source_state_sha256"],
            "pre_oa_handoff_state": source["pre_oa_handoff_state"], "canonical_BODY": dimension["BODY"]["canonical_BODY"],
            "canonical_BODY_sha256": dimension["BODY"]["canonical_BODY_sha256"], "BODY_paragraph_count": dimension["BODY"]["paragraph_count"],
            "BODY_paragraph_provenance": dimension["BODY"]["paragraph_provenance"], "oa_state": dimension["oa_state"],
            "license_state": dimension["license_state"], "JATS_identity_state": dimension["identity_state"],
            "JATS_identity_facts": dimension["identity_facts"], "raw_JATS": dimension["raw_JATS"], "normalized_JATS": dimension["normalized_JATS"],
            "source_type_state": dimension["source_type_state"], "UpdateOf_state": dimension["updateof_structural_state"],
            "UpdateOf_terminal_resolution_state": dimension["updateof_terminal_resolution_state"],
            "eligibility_provenance": ref(OUT / "d2_per_source_dimension_states.jsonl", "all_dimensions_required"),
            "eligibility_record_sha256": sha(canonical(dimension))})
    exposure = exposure_registry(state, source_states)
    exposure_sha = freeze("alpha3_21_current_attempt_fulltext_exposure_registry", exposure)
    handoff_sha = freeze("alpha3_21e_construction_source_handoff", {"for_stage": "alpha3.21E", "source_count": len(handoff),
        "sources": handoff, "complete_D2_execution": status == "completed", "21E_execution_authorized": False,
        "source_identity_universe": ref(d1.INPUT, "only_49_input_sources"), "no_replacement": True,
        "construction_documents_or_tokens_or_span_anchors_generated": False})
    values = funnel(state, source_states, transport)
    put("d2_source_funnel.json", {**values, "identity_failure_dimensions_may_overlap": True,
        "license_and_BODY_not_evaluated_states_are_not_failures": True})
    put("jats_primary_identity_v2_audit.json", {"identity_contract_sha256": IDENTITY_SHA,
        "structure_valid_count": values["jats_valid_structure_count"], "exact_bound_count": values["jats_identity_exact_bound_count"],
        "identity_failure_count": values["jats_identity_failure_count"], "direct_scope_only": True,
        "secondary_missing_is_nonblocking": True, "conflicts_cannot_be_rescued": True,
        "identity_facts_frozen_before_license_BODY": True, "old_PMCID_only_parser_used_for_identity": False})
    post = preflight()
    put("alpha3_21d_network_manifest_postexecution_verification.json", {"unchanged": True,
        "network_manifest": ref(d1.REQUESTS, "original_manifest_unchanged"), "requests_regenerated": False})
    raw_complete = len(transport.attempts) == transport.client.calls and all(digest(OUT / a["raw_path"]) == a["raw_sha256"] for a in transport.attempts)
    completed = status == "completed"
    execution_complete = values["oa_logical_requests_executed"] == 49 and len(rows(OUT / "oa_source_states.jsonl")) == 49 and values["jats_logical_requests_executed"] == values["jats_logical_requests_activated"] == values["oa_eligible_count"] and len(rows(OUT / "jats_structural_states.jsonl")) == values["oa_eligible_count"]
    require(raw_complete and len(source_states) == len({s["pmid"] for s in source_states}) == 49
            and values["total_transport_attempts"] <= 392 and values["total_logical_requests_executed"] <= 98,
            "RAW_ACCOUNTING_OR_SOURCE_UNIVERSE_INVARIANT_FAILED")
    if completed:
        require(execution_complete, "COMPLETE_OA_JATS_EXECUTION_INVARIANT_FAILED")
    put("network_execution_accounting.json", {**values, "network_calls": transport.client.calls, "pmc_calls": transport.client.calls,
        **NO_CALLS, "attempts_maximum": 392, "logical_requests_maximum": 98, "every_attempt_raw_artifact_verified": raw_complete})
    put("no_self_contamination_audit.json", {"current_attempt_fulltext_self_excludes": False,
        "D2_registry_used_as_current_exclusion_input": False, "earlier_exposure_registries_mutated": False})
    put("downstream_no_replacement_audit.json", {"downstream_replacement_used": False, "replacement_source_count": 0,
        "source_universe_unchanged": True, "C2_exclusions_restored": False, "unsampled_sources_used": False})
    put("fresh_primary_policy_nonadaptation_audit.json", {**UNCHANGED, "successful_responses_refreshed": False,
        "new_rules_derived_from_fresh_data": False})
    for name in ("builder_v4_nonuse_audit.json", "quality_nonuse_audit.json"):
        put(name, {"requests_constructed": 0, "calls": 0, "execution_started": False})
    put("known_preexisting_test_environment_issue.json", {"issue": "historical alpha3.19A startup preflight expects absent run directory, but frozen historical directory already exists",
        "historical_directory_exists": legacy.frozen_rules.OUT.exists(), "historical_directory_deleted": False,
        "historical_test_weakened": False, "issue_claimed_fixed": False, "not_D2_protocol_or_scientific_failure": True})
    put("historical_preservation_audit.json", {"D1_D_C2_master_and_inherited_roots_reverified": True,
        "D_failed_classification_preserved": True, "sample_unchanged": True, "historical_assets_modified": False})
    safety = {**NO_CALLS, "construction_evidence_document_generation_started": False, "source_record_tokens_generated": 0,
        "BODY_span_anchors_generated": 0, "Builder_requests_constructed": 0, "Quality_requests_constructed": 0,
        "builder_execution_started": False, "quality_execution_started": False, "retrieval_evaluation_started": False}
    put("scientific_state_safety_audit.json", safety)
    compliance = {"complete_authorized_execution": execution_complete, "raw_responses_complete": raw_complete,
        "source_universe_preserved": [s["pmid"] for s in source_states] == [s["pmid"] for s in post["input_sources"]],
        "request_manifest_unchanged": True, "network_scope_ncbi_pmc_only": all(a["endpoint"] in {legacy.ES, legacy.EF} and a["parameters"]["db"] == "pmc" for a in transport.attempts),
        "identity_conflicts_never_handed_off": all(s["JATS_identity_state"] == identity.SUCCESS for s in handoff),
        "all_deferred_sources_accounted": values["deferred_reached_structural_resolution_count"] + values["deferred_not_reached_due_to_prior_terminal_state_count"] == 3,
        "historical_two_phase_order_preserved": all(a["stage"] == "PMC_OA_SUBSET" for a in transport.attempts[:values["oa_transport_attempts"]]) and all(a["stage"] == "PMC_JATS" for a in transport.attempts[values["oa_transport_attempts"]:]),
        "policies_unchanged": True, "failure": failure}
    put("protocol_compliance_audit.json", compliance)
    next_stage = "PREREGISTER_ALPHA3_21E_CONSTRUCTION_DOCUMENT_AND_BUILDER_V4_REQUEST_FREEZE" if completed and handoff else "CLOSE_ALPHA3_21_PRIMARY_WITH_ZERO_CONSTRUCTION_SOURCES" if completed else "AUDIT_ALPHA3_21D2_RUNTIME_FAILURE_OFFLINE"
    result = {"status": status, "stage_identity": STAGE, "alpha3_21d2_classification": CLASS_OK if completed else CLASS_FAIL,
        "alpha3_21d1_root_verified": True, "alpha3_21d_root_verified": True, "alpha3_21c2_root_verified": True, "alpha3_21_master_root_verified": True,
        **values, "current_attempt_fulltext_self_excludes": False, "downstream_replacement_used": False,
        "alpha3_21_current_attempt_fulltext_exposure_registry_sha256": exposure_sha,
        "alpha3_21e_construction_source_handoff_sha256": handoff_sha, **UNCHANGED, **safety,
        "network_calls": transport.client.calls, "pmc_calls": transport.client.calls, "historical_assets_modified": False,
        "next_stage_recommendation": next_stage, "failure": failure}
    put("validation.json", {**result, **compliance})
    put("summary.json", result)
    if completed:
        require(all((OUT / name).is_file() for name in STREAMS + REQUIRED_MARKERS + [n + ".json" for n in REQUIRED_JSON]
                    + ["d2_per_source_dimension_states.jsonl", "d2_final_source_terminal_states.jsonl"]), "REQUIRED_ARTIFACT_MISSING")
    for path in sorted(OUT.glob("*.json")):
        d1.d.checked_tree(obj(path))
    output_root = root_hash(OUT, ROOT_MARKER)
    put_bytes(ROOT_MARKER, (output_root + "\n").encode("ascii"))
    require(root_hash(OUT, ROOT_MARKER) == output_root, "OUTPUT_ROOT_VERIFICATION_FAILED")
    return {**result, ROOT_MARKER: output_root}


def run():
    require(not OUT.exists(), "D2_OUTPUT_ALREADY_EXISTS_NO_RERUN_OR_REFRESH")
    state = preflight()
    initialize(state)
    transport = FrozenTransportAdapter()
    try:
        activated = execute_oa(state, transport)
        execute_jats(state, transport, activated)
    except Exception as exc:
        return finalize(state, transport, "failed", type(exc).__name__ + ":" + str(exc))
    return finalize(state, transport, "completed")


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, sort_keys=True), flush=True)
    raise SystemExit(0 if result["status"] == "completed" else 1)
