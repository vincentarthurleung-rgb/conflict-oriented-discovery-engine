#!/usr/bin/env python3
"""Evidence-limited 22E replay; never manufacture a historical HTTP envelope.

Only artifact admission/downstream checks are supported by these old archives.
The original adapter did not freeze byte representation or a V2 attempt journal.
Consequently this driver cannot claim end-to-end transport/journal validation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runs/20261012_search_plan_v24_dev_alpha3_22e_focused_seen_data_replay_offline"
MARKER = "search_plan_v24_dev_alpha3_22e_sha256"
RELEASE = ROOT / "runs/20261012_search_plan_v24_dev_alpha3_22_final_independent_oracle_v2_log_namespace_offline"
PREFLIGHT = ROOT / "runs/20261012_search_plan_v24_dev_alpha3_22_release_log_namespace_preflight_offline"
ARCHIVE = ROOT / "runs/20261007_search_plan_v24_primary_alpha3_21d2_pmc_oa_jats_execution"
CLOSED = ROOT / "runs/20261007_search_plan_v24_primary_alpha3_21_terminal_incomplete_closure_offline"
MASTER = ROOT / "runs/20261008_search_plan_v24_dev_alpha3_22_runtime_hardening_master_preregistration_offline"
OLD = ROOT / "runs/20261002_search_plan_v24_dev_alpha3_19d_pmc_oa_jats_construction_eligibility"
REQUESTS = ROOT / "runs/20261006_search_plan_v24_primary_alpha3_21d_pmc_oa_jats_preregistration_offline/alpha3_21d_network_request_manifest.jsonl"
RELEASE_SHA = "f7902fbdf27cd000c91ab65d88221a8fd9966fad38fb20020c0b2a095526ed67"
PREFLIGHT_SHA = "03ce9bf97f2a82903ec8f11055048687f402fc2b7106cf4d3b298130cf52e5a4"
NETWORK_ATTEMPTS = []


def guard(event, args):
    if event in {"socket.__new__", "socket.connect", "socket.getaddrinfo", "urllib.Request", "http.client.connect"}:
        NETWORK_ATTEMPTS.append(event)
        raise RuntimeError("OFFLINE_ONLY:" + event)
    if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
        flags = args[2] if len(args) > 2 and isinstance(args[2], int) else 0
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            require(Path(os.fsdecode(args[0])).absolute().is_relative_to(OUT), "WRITE_OUTSIDE_NEW_22E_DIRECTORY")
    if event == "os.mkdir":
        require(Path(args[0]).absolute().is_relative_to(OUT), "MKDIR_OUTSIDE_NEW_22E_DIRECTORY")


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def obj(path):
    return json.loads(path.read_bytes())


def rows(path):
    return [json.loads(line) for line in path.read_bytes().splitlines()]


def ref(path):
    require(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)), "NONPHYSICAL_INPUT")
    return {"artifact_path": str(path.relative_to(ROOT)), "sha256": sha(path.read_bytes())}


def check_ref(value):
    path = ROOT / value["artifact_path"]
    require(ref(path)["sha256"] == value["sha256"], "INPUT_HASH_MISMATCH:" + str(path))
    return path


def entries(directory, marker):
    require(not any(p.is_symlink() for p in directory.rglob("*")), "ROOT_SYMLINK")
    return [[str(p.relative_to(directory)), sha(p.read_bytes())]
            for p in sorted(directory.rglob("*")) if p.is_file() and p.name != marker]


def root_hash(directory, marker):
    return sha(canonical(entries(directory, marker)).rstrip(b"\n"))


def roots_and_bindings():
    bindings = obj(RELEASE / "frozen_input_bindings.json")
    references = {}
    roots = {}

    def walk(value):
        if isinstance(value, dict):
            if "artifact_path" in value and "sha256" in value:
                path = check_ref(value)
                references[str(path.relative_to(ROOT))] = value["sha256"]
            if "expected_sha256" in value and isinstance(value.get("marker"), dict):
                path = check_ref(value["marker"])
                roots[str(path.relative_to(ROOT))] = value["expected_sha256"]
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)

    walk(bindings)
    walk(obj(PREFLIGHT / "runner_source_manifest.json"))
    explicit = [(RELEASE, "search_plan_v24_dev_alpha3_22_log_namespace_release_sha256", RELEASE_SHA),
        (PREFLIGHT, "search_plan_v24_dev_alpha3_22_log_namespace_preflight_sha256", PREFLIGHT_SHA),
        (ARCHIVE, "search_plan_v24_primary_alpha3_21d2_sha256", "6e79e6f4b48c0d670a1de7f1c6bc7627095d90ac037ce3400f19c65efa56bdc8"),
        (CLOSED, "search_plan_v24_primary_alpha3_21_terminal_closure_sha256", "3e066b012a0b422c1b1c97f68364bd9bd8373ee78c53665322f665c61d84a788"),
        (MASTER, "search_plan_v24_dev_alpha3_22_master_prereg_sha256", "0766425a2d007f5ce6e988a8404a410271b2954fb4f968aec68615ff7a8585db"),
        (OLD, "search_plan_v24_dev_alpha3_19d_sha256", "422975cb0706f19a6ee2640bc126fc49892d2e220df34b3f6c25c5a57a5b9a33")]
    for directory, marker, expected in explicit:
        roots[str((directory / marker).relative_to(ROOT))] = expected
    for name, expected in roots.items():
        marker = ROOT / name
        require(marker.read_text().strip() == root_hash(marker.parent, marker.name) == expected,
                "FROZEN_ROOT_MISMATCH:" + name)
    for pair in bindings["runtime_source_bindings"]:
        require(check_ref(pair["source"]).read_bytes() == check_ref(pair["snapshot"]).read_bytes(), "SOURCE_SNAPSHOT_MISMATCH")
    summary = obj(RELEASE / "summary.json")
    require(summary["independent_release_gate_passed"] is True and summary["passed_count"] == 59
            and summary["failed_count"] == 0 and summary["oracle_version"] == "V2", "RELEASE_NOT_QUALIFIED")
    require(obj(CLOSED / "summary.json")["same_attempt_network_continuation_allowed"] is False, "HISTORICAL_ATTEMPT_NOT_CLOSED")
    return bindings, {"roots": roots, "references": references}


def select_inputs():
    seen = obj(CLOSED / "alpha3_21_future_contamination_registry.json")
    require(ref(CLOSED / "alpha3_21_future_contamination_registry.json")["sha256"] ==
            "80e51107b6e357b210a6860888d6c27bf634eb540dee1a9ba94c3b94465f10ca", "SEEN_REGISTRY_AUTHORITY")
    seen_pmids, seen_pmcids = map(set, (seen["source_identifier_sets"]["pmids"], seen["source_identifier_sets"]["pmcids"]))
    requests = {r["logical_request_id"]: r for r in rows(REQUESTS)}
    oa = rows(ARCHIVE / "oa_source_states.jsonl")
    structure = rows(ARCHIVE / "jats_structural_states.jsonl")
    identities = {r["pmid"]: r for r in rows(ARCHIVE / "jats_primary_identity_states_v2.jsonl")}
    licenses = {r["pmid"]: r for r in rows(ARCHIVE / "jats_license_states.jsonl")}
    bodies = {r["pmid"]: r for r in rows(ARCHIVE / "canonical_body_manifest.jsonl")}
    dimensions = {r["pmid"]: r for r in rows(ARCHIVE / "d2_per_source_dimension_states.jsonl")}
    exposure = obj(ARCHIVE / "alpha3_21_current_attempt_fulltext_exposure_registry.json")
    exposed = {r["pmid"] for r in exposure["source_identities"] if r["authoritative_identity"]}
    require(len(structure) == len(identities) == len(licenses) == len(exposed) == 9, "EXPOSED_NINE_BOUNDARY")
    historical_barrier = obj(ARCHIVE / "oa_phase_completion_barrier.json")
    historical_activation = obj(ARCHIVE / "alpha3_21d2_jats_activation_manifest.json")
    require(historical_barrier["all_49_terminal_states_frozen"] is True
            and historical_barrier["JATS_requests_before_barrier"] == 0
            and len(oa) == len(historical_activation["requests"]) == 49, "HISTORICAL_ACTIVATION_BARRIER")
    check_ref(historical_barrier["OA_states"])
    by_oa = {r["pmid"]: r for r in oa}
    for r in historical_activation["requests"]:
        request = requests[r["logical_request_id"]]
        expected_activation = "REQUIRED_BY_OA_ELIGIBILITY" if by_oa[r["pmid"]]["state"] == "OA_SUBSET_ELIGIBLE" else "NOT_REQUIRED_OA_INELIGIBLE"
        require(r["activation_state"] == expected_activation
                and r["request_payload_sha256"] == request["request_payload_sha256"]
                and r["frozen_request_record_sha256"] == sha(canonical(request).rstrip(b"\n")), "HISTORICAL_ACTIVATION_BINDING")
    old_requests = {r["pmid"]: r for r in rows(OLD / "pmc_jats_request_manifest.jsonl")}
    candidates = []

    def add(kind, directory, attempt, request, expected, authority):
        pmid = attempt["pmid"]
        pmcid = request.get("pmcid", request.get("source_provenance", {}).get("pmcid"))
        require(pmid in seen_pmids and pmcid in seen_pmcids, "NEW_SOURCE_EXPOSURE_FORBIDDEN")
        artifact = ref(directory / attempt["raw_path"])
        require(artifact["sha256"] == attempt["raw_sha256"] and
                (directory / attempt["raw_path"]).stat().st_size == attempt["raw_bytes"], "RAW_PROVENANCE_MISMATCH")
        if "logical_request_id" in attempt:
            require(request["request_payload_sha256"] == attempt["request_payload_sha256"] and
                    sha(canonical(request).rstrip(b"\n")) == attempt["frozen_request_record_sha256"], "HISTORICAL_REQUEST_BINDING")
        candidates.append({"candidate_id": f"seen22e_{len(candidates)+1:02d}", "source_id": pmid, "pmcid": pmcid,
            "kind": kind, "artifact": artifact, "input_artifact_sha256": artifact["sha256"],
            "historical_attempt": attempt, "historical_request": request,
            "historical_request_record_sha256": sha(canonical(request).rstrip(b"\n")),
            "expected_state": expected, "expected_state_authority": authority,
            "historical_eligibility": dimensions.get(pmid, {}).get("construction_source_state", expected.get("historical_terminal_state")),
            "available_replay_level": "ARTIFACT_ADMISSION_AND_DOWNSTREAM_ONLY" if kind in {"JATS_COMPLETE", "OA_COMPLETE"} else "INCOMPLETE_BODY_QUARANTINE_ONLY",
            "full_transport_replay_supported": False, "journal_recovery_supported": False,
            "missing_evidence": ["original HTTP headers/framing and Content-Length availability not retained",
                "original adapter byte representation not frozen in request", "no historical durable attempt journal/hash chain"],
            "scientific_content_used_for_selection": False})

    attempts = rows(ARCHIVE / "jats_request_attempt_log.jsonl")
    for r in structure:
        pmid = r["pmid"]
        require(pmid in exposed, "UNEXPOSED_FULLTEXT")
        a = next(a for a in attempts if a["logical_request_id"] == r["logical_request_id"] and a["raw_sha256"] == r["raw_artifact"]["sha256"])
        expected = {"body_completion": "BODY_COMPLETE", "content_length_match": "UNAVAILABLE",
            "identity_result_sha256": sha(canonical(identities[pmid]["result"])),
            "normalized_jats_sha256": r["normalized_JATS"]["sha256"],
            "license_result_sha256": sha(canonical(licenses[pmid]["result"])),
            "construction_oa_result_sha256": sha(canonical(licenses[pmid]["construction_OA_result"])),
            "license_state": licenses[pmid]["state"],
            "canonical_body_sha256": bodies[pmid]["canonical_BODY_sha256"] if pmid in bodies else None,
            "canonical_body_paragraph_count": bodies[pmid]["paragraph_count"] if pmid in bodies else None,
            "source_type_result_sha256": sha(canonical(dimensions[pmid]["source_type_result"])) if dimensions[pmid]["source_type_result"] is not None else None,
            "parser_admission": True}
        add("JATS_COMPLETE", ARCHIVE, a, requests[r["logical_request_id"]], expected,
            [ref(ARCHIVE / name) for name in ("jats_structural_states.jsonl", "jats_primary_identity_states_v2.jsonl", "jats_license_states.jsonl", "canonical_body_manifest.jsonl")])
    oa_attempts = rows(ARCHIVE / "oa_request_attempt_log.jsonl")
    for state in ("OA_SUBSET_ELIGIBLE", "OA_SUBSET_INELIGIBLE"):
        r = next(r for r in oa if r["state"] == state)
        a = next(a for a in oa_attempts if a["logical_request_id"] == r["logical_request_id"] and a["raw_sha256"] == r["final_raw_artifact"]["sha256"])
        add("OA_COMPLETE", ARCHIVE, a, requests[r["logical_request_id"]],
            {"body_completion": "BODY_COMPLETE", "content_length_match": "UNAVAILABLE", "parser_admission": True,
             "oa_state": state, "oa_validity_sha256": sha(canonical(r["validity"]))}, [ref(ARCHIVE / "oa_source_states.jsonl")])
    partial = next(a for a in attempts if a.get("unhandled_frozen_client_exception"))
    unknown = next(a for a in oa_attempts if a["transport_error"] is not None)
    timeout_state = next(r for r in rows(OLD / "pmc_jats_terminal_states.jsonl") if r["terminal_state"] == "JATS_FAILED_NO_REPLACEMENT")
    for kind, directory, a, request, terminal, authority in [
        ("QUARANTINED_PARTIAL", ARCHIVE, partial, requests[partial["logical_request_id"]], "TERMINAL_UNHANDLED_FROZEN_CLIENT_EXCEPTION", MASTER / "seen_failure_fixture_usage_contract.json"),
        ("UNQUALIFIED_TRANSPORT_ERROR", ARCHIVE, unknown, requests[unknown["logical_request_id"]], "RETRYABLE_TRANSPORT_FAILURE", ARCHIVE / "oa_request_attempt_log.jsonl"),
        ("HISTORICAL_TERMINAL_TIMEOUT", OLD, timeout_state["request_attempts"][-1], old_requests[timeout_state["pmid"]], "JATS_FAILED_NO_REPLACEMENT", OLD / "pmc_jats_terminal_states.jsonl")]:
        add(kind, directory, a, request, {"body_completion": "BODY_COMPLETION_UNKNOWN", "content_length_match": "UNAVAILABLE",
            "parser_admission": False, "parser_invocations": 0, "retry_authorized": False,
            "historical_terminal_state": terminal}, [ref(authority)])
        candidates[-1]["missing_evidence"].append("original qualified exception object/traceback and occurrence binding unavailable")
    require(len(candidates) == 14, "FOCUSED_SELECTION_COUNT")
    return candidates


def runtime():
    from code_engine import append_only_attempt_journal_v2_length_bound_v1 as j
    from scripts import search_plan_v24_alpha321_jats_primary_identity_v2 as identity
    from scripts import run_search_plan_v24_alpha319d_pmc_oa_jats_construction_eligibility as legacy
    from scripts import search_plan_v24_alpha321_body_only as body
    return j, identity, legacy, body


def artifact_check(candidate):
    j, identity, legacy, body = runtime()
    t = j.t
    raw = check_ref(candidate["artifact"]).read_bytes()
    a = candidate["historical_attempt"]
    complete = candidate["kind"] in {"JATS_COMPLETE", "OA_COMPLETE"}
    # A successful legacy fetch can only be logged after response.read returns.
    # No parser-success inference, fake headers, length, or exception objects.
    require(not complete or a["http_status"] == 200 and a["transport_error"] is None, "NORMAL_READ_NOT_EVIDENCED")
    completion = t.assess_body_completion(raw, read_returned_normally=complete,
        expected_content_length=None, expected_length_trustworthy=False,
        byte_representation=t.ByteRepresentation.UNKNOWN, expected_length_representation=None,
        interruption_class=None if complete else t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE,
        timestamp=a["timestamp_utc"])
    historical_payload_hash = a.get("request_payload_sha256", candidate["historical_request_record_sha256"])
    context = t.AttemptContextV1(a.get("logical_request_id", candidate["candidate_id"]), historical_payload_hash, a["attempt"])
    artifact = t.RawArtifactV1(str(check_ref(candidate["artifact"])), candidate["input_artifact_sha256"], len(raw))
    response = t.FrozenTransportResponseV2(context, completion, artifact, a["http_status"] == 200)
    actual = {"body_completion": completion.body_completion_state.value, "content_length_match": completion.content_length_match,
              "parser_admission": response.parser_eligible}
    if not complete:
        invocations = 0

        def forbidden_parser(_):
            nonlocal invocations
            invocations += 1
            raise AssertionError("INCOMPLETE_PARSER_CALLED")

        try:
            t.guarded_parse(response, forbidden_parser)
        except t.TransportContractError as exc:
            require(str(exc) == "PARTIAL_OR_UNAUTHORITATIVE_RESPONSE_QUARANTINED", "WRONG_QUARANTINE_REJECTION")
        else:
            raise RuntimeError("QUARANTINE_BYPASSED")
        decision = t.semantic_retry_decision(t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE,
            request_replay_safe=True, attempt_ordinal=a["attempt"])
        actual.update(parser_invocations=invocations, retry_authorized=decision.retry_authorized,
                      historical_terminal_state=candidate["expected_state"]["historical_terminal_state"])
    elif candidate["kind"] == "OA_COMPLETE":
        state, verdict = t.guarded_parse(response, lambda data: legacy.oa_subset_state(data, [a], candidate["pmcid"]))
        actual.update(oa_state=state, oa_validity_sha256=sha(canonical(verdict)))
    else:
        r = candidate["historical_request"]["source_provenance"]
        result = t.guarded_parse(response, lambda data: identity.validate_jats_primary_identity_v2(data,
            expected_pmid=r["pmid"], expected_pmcid=r["pmcid"], expected_doi=r["doi"]))
        require(result["source_identity_allows_progression"] is True, "ACTUAL_IDENTITY_GATE_BLOCKED")
        normalized = t.guarded_parse(response, lambda data: ET.tostring(identity.select_primary_article(data), encoding="utf-8"))
        licensed = legacy.license_v2.extract_license_v2(normalized)
        oa = legacy.license_v2.construction_oa_v2(r["pmcid"], True, normalized)
        body_result = body.canonical_body(normalized) if licensed["state"] == "ELIGIBLE" else None
        source_type = legacy.source_policy.source_type_state(r["publication_types"], normalized) if body_result else None
        actual.update(identity_result_sha256=sha(canonical(result)), normalized_jats_sha256=sha(normalized),
            license_result_sha256=sha(canonical(licensed)), construction_oa_result_sha256=sha(canonical(oa)),
            license_state=licensed["state"], canonical_body_sha256=sha(body_result["body_text"].encode()) if body_result else None,
            source_type_result_sha256=sha(canonical(source_type)) if source_type is not None else None,
            canonical_body_paragraph_count=len(body_result["paragraphs"]) if body_result else None)
    differences = {key: {"expected": value, "actual": actual.get(key)} for key, value in candidate["expected_state"].items()
                   if actual.get(key) != value}
    # Old request records are NOT converted to synthetic V2 manifests. Probe
    # only the unchanged manifest boundary, not journal recovery.
    rejection = None
    try:
        j.FrozenRequestManifestV2(j.canonical(candidate["historical_request"]))
    except t.TransportContractError as exc:
        rejection = str(exc)
    require(rejection == "MANIFEST_FIELDS", "UNSUPPORTED_HISTORICAL_MANIFEST_NOT_REJECTED")
    return {"actual_state": actual, "partial_level_status": "FAILED" if differences else "VALIDATED",
            "differences": differences, "legacy_manifest_rejection": rejection,
            "unknown_byte_representation_preserved": True, "http_envelope_synthesized": False,
            "full_transport_replayed": False, "journal_terminal_committed": False,
            "historical_attempt_ordinal_preserved": a["attempt"], "network_calls": len(NETWORK_ATTEMPTS)}


def isolated_check(candidate):
    try:
        return artifact_check(candidate)
    except Exception as exc:
        return {"actual_state": {"error": type(exc).__name__ + ":" + str(exc)},
            "partial_level_status": "FAILED", "differences": {"unexpected_execution_failure": str(exc)},
            "legacy_manifest_rejection": None, "full_transport_replayed": False,
            "journal_terminal_committed": False, "network_calls": len(NETWORK_ATTEMPTS)}


def fresh_checks(manifest_sha):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run([sys.executable, "-B", "-m", "scripts.run_search_plan_v24_alpha322e_seen_replay_offline",
                             "--fresh-read", manifest_sha], cwd=ROOT, env=env, text=True, capture_output=True, timeout=60)
    require(result.returncode == 0, "FRESH_ARTIFACT_READER_FAILED:" + result.stderr)
    return json.loads(result.stdout)


def execute():
    require(not OUT.exists(), "NEW_22E_DIRECTORY_REQUIRED_NO_OVERWRITE")
    bindings, baseline = roots_and_bindings()
    candidates = select_inputs()
    implementation = ref(Path(__file__).resolve())
    dependencies = [ref(ROOT / name) for name in ("scripts/run_search_plan_v24_alpha319d_pmc_oa_jats_construction_eligibility.py",
        "scripts/run_search_plan_v24_alpha321d2_pmc_execution.py", "scripts/search_plan_v24_alpha318a6_license_extraction.py",
        "scripts/search_plan_v24_alpha318a1_source_contracts.py", "scripts/search_plan_v24_alpha321_body_only.py")]
    inventory = {str(d.relative_to(ROOT)): [str(p.relative_to(d)) for p in sorted(d.rglob("*"))
        if p.is_file() and ("journal" in p.name or p.name.startswith("segment-"))] for d in (ARCHIVE, OLD)}
    manifest = {"stage": "ALPHA3_22E_OFFLINE_SEEN_DATA_REPLAY", "release_root_sha256": RELEASE_SHA,
        "runner_preflight_root_sha256": PREFLIGHT_SHA, "runtime_source_bindings": bindings["runtime_source_bindings"],
        "driver": implementation, "downstream_source_bindings": dependencies,
        "selection_rule": "all frozen nine exposed complete JATS; first OA accepted and excluded; first archived unhandled partial, first unqualified OA failure, sole historical 19D terminal JATS timeout",
        "expected_results_from_runtime_under_test": False, "candidates": candidates,
        "historical_journal_file_inventory": inventory,
        "support_boundary": "Unknown original byte representation is never assigned wire/decoded/decompressed to satisfy the length-bound journal. Missing original transport evidence cannot become an authoritative handoff.",
        "historical_source_bindings": [ref(MASTER / "historical_regression_contract.json"),
            ref(MASTER / "seen_failure_fixture_usage_contract.json"), ref(CLOSED / "alpha3_21_future_contamination_registry.json"),
            ref(ARCHIVE / "alpha3_21_current_attempt_fulltext_exposure_registry.json"), ref(REQUESTS),
            ref(ARCHIVE / "oa_phase_completion_barrier.json"), ref(ARCHIVE / "alpha3_21d2_jats_activation_manifest.json")],
        "forbidden": ["network", "LLM", "Builder", "Quality", "59 synthetic scenario execution", "historical continuation", "manufactured HTTP envelope"]}
    j, _, _, _ = runtime()
    require(j.AUTHORITY == bindings["runtime_journal_authority"], "RUNTIME_AUTHORITY_DRIFT")
    OUT.mkdir()
    frozen_input = j.atomic_freeze(OUT / "input_manifest.json", canonical(manifest))
    print(json.dumps({"input_manifest_frozen_before_replay": True, "sha256": frozen_input.sha256, "candidates": len(candidates)}), flush=True)
    checks = [isolated_check(c) for c in candidates]
    fresh = fresh_checks(frozen_input.sha256)
    require(fresh["checks"] == checks and fresh["network_calls"] == 0, "FRESH_ARTIFACT_CHECK_DRIFT")
    results = []
    for c, check in zip(candidates, checks):
        failed = bool(check["differences"])
        results.append({"candidate_id": c["candidate_id"], "source_id": c["source_id"], "pmcid": c["pmcid"],
            "input_artifact_sha256": c["input_artifact_sha256"], "available_replay_level": c["available_replay_level"],
            "expected_state": c["expected_state"], "actual_state": check["actual_state"],
            "result": "FAIL" if failed else "UNSUPPORTED", "validation_state": "FAILED" if failed else "UNSUPPORTED_MISSING_EVIDENCE",
            "first_divergence": next(iter(check["differences"]), None), "partial_level_check": check,
            "fresh_process_artifact_read": "VALIDATED", "fresh_process_journal_recovery_executed": False,
            "recovery_state": "UNSUPPORTED_NO_HISTORICAL_DURABLE_JOURNAL_OR_COMPATIBLE_MANIFEST",
            "handoff_eligibility": "BLOCKED_UNSUPPORTED_END_TO_END_EVIDENCE", "missing_evidence": c["missing_evidence"]})
    after_bindings, after = roots_and_bindings()
    require(baseline == after and bindings == after_bindings and ref(Path(__file__).resolve()) == implementation,
            "HISTORICAL_OR_RUNTIME_MUTATION")
    for dependency in dependencies:
        check_ref(dependency)
    require(frozen_input.verified_bytes() == canonical(manifest) and not NETWORK_ATTEMPTS, "INPUT_OR_OFFLINE_GUARD_FAILURE")
    failed = sum(r["result"] == "FAIL" for r in results)
    summary = {"alpha3_22e_status": "FAIL" if failed else "INCOMPLETE", "selected_record_count": len(results),
        "executed_record_count": len(results), "passed_record_count": 0, "failed_record_count": failed,
        "unsupported_record_count": len(results)-failed, "record_count_semantics": "executed means only the explicitly named partial level; unsupported never counts as PASS",
        "partial_level_validated_record_count": sum(c["partial_level_status"] == "VALIDATED" for c in checks),
        "fresh_process_artifact_checks": len(fresh["checks"]), "full_transport_replay_count": 0,
        "journal_terminal_commit_count": 0, "fresh_process_journal_recovery_count": 0, "authoritative_handoff_count": 0,
        "critical_safety_failures": failed, "runtime_source_modified": False, "scientific_policy_changed": False,
        "historical_assets_modified": False, "alpha3_21_reopened": False, "fresh_primary_attempt_started": False,
        **{k: 0 for k in ("network_calls", "pubmed_calls", "pmc_calls", "provider_calls", "llm_calls", "builder_calls", "quality_calls")},
        "next_stage_recommendation": "REPORT_CONCRETE_PARTIAL_REPLAY_FAILURE" if failed else "RESOLVE_ALPHA3_22E_ARCHIVED_EVIDENCE_GAPS_OFFLINE_BEFORE_22F",
        "missing_required_evidence": manifest["support_boundary"], "automatic_repairs": 0,
        "input_manifest_sha256": frozen_input.sha256, "baseline_root_count_verified": len(baseline["roots"]),
        "release_source_snapshot_pairs_verified": len(bindings["runtime_source_bindings"]),
        "baseline_release_root_sha256": RELEASE_SHA, "baseline_runner_preflight_root_sha256": PREFLIGHT_SHA}
    validation = {"status": summary["alpha3_22e_status"], "all_executed_partial_checks_validated": failed == 0,
        "full_required_integration_path_validated": False, "unsupported_not_counted_as_pass": True,
        "no_original_byte_representation_invented": True, "no_missing_raw_http_synthesized": True,
        "input_manifest_frozen_before_execution": True, "input_manifest_sha256": frozen_input.sha256,
        "partial_parser_invocations": sum(c["actual_state"].get("parser_invocations", 0) for c in checks),
        "unknown_retry_authorizations": sum(c["actual_state"].get("retry_authorized", False) for c in checks),
        "partial_bytes_preserved": True, "fresh_process_result_byte_semantic_equality": fresh["checks"] == checks,
        "journal_hash_chain_and_durability": "UNSUPPORTED_NOT_EXECUTED", "attempt_ordinal_reuse": "NOT_EXERCISED_NO_NEW_ATTEMPTS",
        "completed_request_refetch_count": 0, "original_terminal_requests_reopened": 0,
        "new_oa_jats_activation": "BLOCKED_NO_AUTHORITATIVE_NEW_JOURNAL", "original_activation_barrier_preserved": True,
        "historical_49_source_activation_identity_binding_checked": True,
        "historical_handoff_authority_not_upgraded": True, "source_and_request_provenance_verified": True,
        "unsupported_legacy_manifest_rejections": sum(c["legacy_manifest_rejection"] == "MANIFEST_FIELDS" for c in checks),
        "critical_safety_coverage": "PARTIAL_ONLY_NOT_FULL_RELEASE_COVERAGE", "critical_safety_failures": failed,
        "no_synthetic_fault_scenarios_executed": True, "frozen_source_bindings_verified": True,
        "network_guard_attempts": NETWORK_ATTEMPTS, "historical_preservation_verified": True}
    preservation = {"historical_assets_modified": False, "runtime_source_modified": False,
        "scientific_policy_changed": False, "alpha3_21_reopened": False,
        "before": baseline, "after": after, "downstream_bindings_unchanged": dependencies,
        "write_guard": "all opened write paths restricted to the one new 22E directory; bytecode writes disabled in both processes"}
    for name, data in (("replay_results.jsonl", b"".join(canonical(r) for r in results)),
        ("historical_preservation.json", canonical(preservation)), ("validation.json", canonical(validation)),
        ("summary.json", canonical(summary))):
        j.atomic_freeze(OUT / name, data)
    digest = root_hash(OUT, MARKER)
    j.atomic_freeze(OUT / MARKER, (digest + "\n").encode())
    require(root_hash(OUT, MARKER) == digest, "NEW_22E_ROOT_READBACK_MISMATCH")
    print(json.dumps({**summary, "alpha3_22e_root_sha256": digest}, sort_keys=True), flush=True)


def main():
    sys.addaudithook(guard)
    parser = argparse.ArgumentParser()
    parser.add_argument("--fresh-read")
    args = parser.parse_args()
    if args.fresh_read:
        path = OUT / "input_manifest.json"
        require(sha(path.read_bytes()) == args.fresh_read, "FRESH_INPUT_MANIFEST_HASH")
        manifest = obj(path)
        for binding in manifest["runtime_source_bindings"]:
            check_ref(binding["source"])
        print(json.dumps({"checks": [isolated_check(c) for c in manifest["candidates"]], "network_calls": len(NETWORK_ATTEMPTS)}, sort_keys=True))
    else:
        execute()


if __name__ == "__main__":
    main()
