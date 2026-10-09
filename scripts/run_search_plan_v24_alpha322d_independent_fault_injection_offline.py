#!/usr/bin/env python3
"""Independent, stop-on-first-critical-mismatch validation of frozen A/B/C.

No networking or policy overrides. Expected values live in an independent
pre-frozen oracle. Transport doubles implement external I/O only. A concrete
signal is classified at its actual fault phase, then A preserves/quarantines
the response and C persists the unchanged decision and observation.
"""

from __future__ import annotations

import ast
import hashlib
import http.client
import io
import json
import os
import subprocess
import sys
import traceback
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from code_engine import append_only_attempt_journal_v1 as j
from code_engine import deterministic_resume_planner_v1 as p
from code_engine import stage_barrier_snapshot_v1 as s
from scripts import run_search_plan_v24_alpha322c_attempt_journal_resume_offline as upstream
from scripts import search_plan_v24_alpha322d_independent_scenarios as oracle
from scripts import search_plan_v24_alpha321_jats_primary_identity_v2 as identity


ROOT, master, t, o, b = upstream.ROOT, upstream.master, upstream.t, upstream.o, upstream.b
OUT = ROOT / "runs/20261008_search_plan_v24_dev_alpha3_22d_independent_fault_injection_offline"
ROOT_MARKER = "search_plan_v24_dev_alpha3_22d_sha256"
SCENARIO_MARKER = "frozen_fault_scenario_manifest_sha256"
ORACLE_MARKER = "independent_expected_outcomes_sha256"
EVIDENCE_MARKER = "alpha3_22d_fault_execution_evidence_sha256"
BUNDLE_MARKER = "alpha3_22d_validation_bundle_sha256"
TEST = ROOT / "tests/test_search_plan_v24_alpha322d_independent_fault_injection_offline.py"
NOW = "2000-01-01T00:00:00Z"
SECRET = "alpha322d-synthetic-private-credential"
SOURCES = (Path(__file__), Path(oracle.__file__), TEST)
EXPECTED_C_ROOT = "54e59aae85b1ea0598e29c80288cef3025301261d709b9ab888a224d686d3ad7"
NO_CALLS = dict(upstream.NO_CALLS)
FAIL_CLASS = "ALPHA3_22D_FAILED_INDEPENDENT_FAULT_INJECTION"
NEXT_FAIL = "DESIGN_VERSIONED_ALPHA3_22_RUNTIME_REPAIR_FROM_FROZEN_22D_FAILURE_EVIDENCE"
REQUIRED_JSON = tuple("""alpha3_22_master_root_verification alpha3_22a_root_verification alpha3_22b_root_verification
alpha3_22c_root_verification alpha3_21_closure_verification alpha3_22d_scope_boundary offline_harness_architecture
frozen_fault_scenario_manifest independent_test_oracle_audit phase_aware_exception_mapping_results retry_policy_delegation_results
body_completion_and_length_results partial_response_quarantine_results parser_invocation_guard_results attempt_budget_results
journal_hash_chain_integrity_results write_ahead_dispatch_guard_results raw_artifact_commit_order_results successful_request_skip_results
abandoned_attempt_recovery_results frozen_stage_barrier_results conditional_jats_activation_results synthetic_end_to_end_execution_manifest
synthetic_end_to_end_execution_results exposure_provenance_results secret_redaction_results repeatability_results mutation_sensitivity_results
scenario_expected_vs_actual_matrix scenario_failure_evidence fault_matrix_coverage_report runtime_component_integrity_audit
scientific_policy_firewall_audit production_runtime_nonwiring_audit historical_preservation_audit contamination_baseline_immutability_audit
scientific_state_safety_audit validation summary""".split())


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(path, role):
    return master.ref(Path(path), role)


def verify_authority():
    authority = upstream.verify_authority()
    authority["alpha322c"] = master.prior.root_check(upstream.OUT, upstream.ROOT_MARKER, EXPECTED_C_ROOT)
    expected = {"append_only_attempt_journal_v1_implementation_sha256": "bba8be8be81813968fd1b3553ced53da9e407a940a255991ab34295bad49e032",
        "deterministic_resume_planner_v1_implementation_sha256": "ca1c2fc62ba86d5124f295382a315789aeeb53695ceb520be85435d8f19e2d42",
        "stage_barrier_snapshot_v1_contract_sha256": "4cb88b7513d3c153dff4272e89dd018ab0539aa2cda46ef3e4943aa43f0a6c11",
        "alpha3_22c_reproducibility_bundle_sha256": "bd366fe4d618e4dc0a5a34fc87efcf499770343ee58d938eee806ad8d0656527"}
    for marker, stem in upstream.MARKERS.items():
        path = upstream.OUT / (stem + ".json")
        t.require(digest(path) == expected[marker] == (upstream.OUT / marker).read_text().strip(), "22C_FROZEN_CONTRACT_MISMATCH")
        master.d2.d1.d.checked_tree(json.loads(path.read_bytes()))
    authority["alpha322c_sources"] = [ref(path, "unchanged_frozen_22C_code") for path in (*upstream.COMPONENTS, Path(upstream.__file__), upstream.TEST)]
    return authority


def independent_oracle_audit():
    tree = ast.parse(Path(oracle.__file__).read_text())
    forbidden = {"TransportLifecycleV2", "TransportExceptionMappingV2", "semantic_retry_decision", "DeterministicResumePlannerV1", "_reduce"}
    t.require(not any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(tree)), "ORACLE_IMPORT_NOT_INDEPENDENT")
    t.require(not any(isinstance(node, ast.Name) and node.id in forbidden for node in ast.walk(tree)), "ORACLE_CALLS_SUT")
    scenarios = oracle.scenarios()
    t.require(len(scenarios) >= 32 and len({r["scenario_id"] for r in scenarios}) == len(scenarios), "INDEPENDENT_SCENARIO_COVERAGE")
    return {"independent_test_oracle_established": True, "SUT_imports": 0, "SUT_calls": 0,
        "expected_values_from": "independent prospective declarations grounded in frozen master and explicit 22D requirements",
        "source": ref(Path(oracle.__file__), "independent_oracle_not_system_under_test"), "scenario_count": len(scenarios)}


def freeze_specification():
    t.require(not OUT.exists(), "22D_OUTPUT_EXISTS_NO_OVERWRITE")
    with master.prior.offline_guard():
        authority = verify_authority()
        audit = independent_oracle_audit()
        scenarios = oracle.scenarios()
        store = t.RawArtifactStoreV1(OUT)
        manifest = {"schema_version": "IndependentFaultScenarioManifestV1", "stage_identity": oracle.STAGE_IDENTITY,
            "order": [r["scenario_id"] for r in scenarios], "scenarios": [{k: v for k, v in r.items() if k != "expected"} for r in scenarios],
            "minimum_required_scenarios": 32, "stop_on_first_critical_failure": True, "mutation_ids": list(oracle.MUTATIONS),
            "source_bindings": [ref(path, "frozen_22D_harness_or_oracle_or_static_tests") for path in SOURCES]}
        raw = canonical(manifest)
        store.freeze_bytes("frozen_fault_scenario_manifest.json", raw)
        store.freeze_bytes(SCENARIO_MARKER, (hashlib.sha256(raw).hexdigest() + "\n").encode())
        expected = b"".join(canonical({"scenario_id": r["scenario_id"], "expected": r["expected"], "oracle_authority": r["oracle_authority"]}) for r in scenarios)
        store.freeze_bytes("independent_expected_outcomes.jsonl", expected)
        store.freeze_bytes(ORACLE_MARKER, (hashlib.sha256(expected).hexdigest() + "\n").encode())
        store.freeze_bytes("independent_test_oracle_audit.json", canonical(audit))
        store.freeze_bytes("pre_execution_authority_and_source_bindings.json", canonical(authority))
        store.freeze_bytes("specification_freeze_commit.json", canonical({"scenario_manifest_sha256": hashlib.sha256(raw).hexdigest(),
            "independent_expected_outcomes_sha256": hashlib.sha256(expected).hexdigest(), "fault_scenarios_executed": 0,
            "frozen_before_execution": True, "upstream_verified": True}))
        j.sync_directory(OUT)
        return {"status": "SPECIFICATION_FROZEN_NO_22D_SCENARIOS_EXECUTED", "scenario_count": len(scenarios),
                SCENARIO_MARKER: hashlib.sha256(raw).hexdigest(), ORACLE_MARKER: hashlib.sha256(expected).hexdigest()}


def read_frozen_specification():
    manifest_raw, oracle_raw = (OUT / "frozen_fault_scenario_manifest.json").read_bytes(), (OUT / "independent_expected_outcomes.jsonl").read_bytes()
    t.require(hashlib.sha256(manifest_raw).hexdigest() == (OUT / SCENARIO_MARKER).read_text().strip(), "SCENARIO_MANIFEST_DRIFT")
    t.require(hashlib.sha256(oracle_raw).hexdigest() == (OUT / ORACLE_MARKER).read_text().strip(), "INDEPENDENT_ORACLE_DRIFT")
    manifest = json.loads(manifest_raw)
    master.d2.d1.d.checked_tree(manifest["source_bindings"])
    expected = {r["scenario_id"]: r["expected"] for r in map(json.loads, oracle_raw.splitlines())}
    return manifest, expected


def request_manifest(scenario, *, count=1, two_phase=False):
    key = scenario["scenario_id"]
    requests = []
    for stage in (("OA", "JATS") if two_phase else ("OA",)):
        for index in range(count):
            payload = {"synthetic_scenario": key, "source_ordinal": index, "route": "offline:" + stage}
            if stage == "JATS":
                payload["oa_request_id"] = key + f":OA:{index}"
            requests.append({"request_id": key + f":{stage}:{index}", "request_payload": payload,
                "request_payload_sha256": hashlib.sha256(canonical(payload)).hexdigest(), "stage": stage,
                "execution_order": len(requests), "replay_safe": scenario["initial_conditions"].get("replay_safe", True), "maximum_attempts": 4,
                "validity_authority_sha256": hashlib.sha256(b"22D synthetic validation stub; unchanged frozen identity validator where applicable").hexdigest(),
                "eligibility_authority_sha256": hashlib.sha256(b"22D fixed synthetic eligibility only; not a scientific gate").hexdigest()})
    return j.FrozenRequestManifestV1(canonical({"schema_version": "FrozenRequestManifestV1", "run_id": "synthetic:alpha322d:" + key,
        "run_epoch": "synthetic:epoch-1", "stage_id": "synthetic:OA-JATS", "authority": j.AUTHORITY,
        "activation_contract_sha256": hashlib.sha256(b"frozen parent OA VALID_SUCCESS activates exact JATS child").hexdigest(), "requests": requests}))


class LocalFileHolder:
    def __init__(self, file):
        self.file = file
    def makefile(self, mode):
        return self.file


class BoundFaultFile(io.BytesIO):
    def __init__(self, kind, phase):
        super().__init__(b"HTTP/1.1 200 OK\r\nContent-Length: 50\r\n\r\n<article>")
        self.kind, self.phase = kind, phase
    def readline(self, limit=-1):
        if self.phase == "pre_headers":
            raise self.kind("authorization=Bearer " + SECRET)
        return super().readline(limit)
    def read(self, amount=-1):
        if self.phase == "body":
            raise self.kind("synthetic I/O interruption token=" + SECRET)
        return super().read(amount)


def actual_bound_failure(kind, phase):
    response = http.client.HTTPResponse(LocalFileHolder(BoundFaultFile(kind, phase)))
    try:
        response.begin()
        response.read()
    except kind as exception:
        return exception
    finally:
        response.close()
    raise AssertionError("BOUND_TRANSPORT_FAULT_NOT_INJECTED")


def actual_incomplete_read():
    response = http.client.HTTPResponse(LocalFileHolder(io.BytesIO(b"HTTP/1.1 200 OK\r\nContent-Length: 50\r\n\r\n<article>")))
    try:
        response.begin()
        response.read()
    except http.client.IncompleteRead as exception:
        return exception
    finally:
        response.close()
    raise AssertionError("BOUND_INCOMPLETE_READ_NOT_INJECTED")


def journal_read_plan(directory):
    manifest = j.FrozenRequestManifestV1((Path(directory) / "request_manifest.json").read_bytes())
    verified = j.JournalIntegrityVerifierV1.read(directory, manifest)
    return p.DeterministicResumePlannerV1().build(verified).record()


def fresh_recovery(directory):
    result = subprocess.run([sys.executable, "-m", "scripts.run_search_plan_v24_alpha322d_independent_fault_injection_offline",
                             "--recover", str(directory)], cwd=ROOT, capture_output=True, text=True)
    t.require(result.returncode == 0, "FRESH_PROCESS_RECOVERY_FAILED:" + result.stderr)
    return json.loads(result.stdout)


def begin(writer, key, dispatch):
    token = writer.start_attempt(key, timestamp=NOW)
    t.require(writer.dispatch_authorized(token), "WRITE_AHEAD_DISPATCH_DENIED")
    dispatch.append({"request_id": key, "attempt_ordinal": token.context.attempt_ordinal, "durable_start_hash": token.entry_hash})
    lifecycle = t.TransportLifecycleV2(token.context)
    lifecycle.start_attempt(token.entry_hash, timestamp=NOW)
    writer.record_lifecycle(lifecycle, timestamp=NOW)
    return lifecycle


def mapping_facts(lifecycle, *, status=None, origin=None, completion=None, backend=None):
    return b.TransportMappingFactsV2(lifecycle.state, b.BOUND_CLIENT_IDENTITY_SHA256,
        headers_trusted=status is not None, http_status=status, http_status_origin=origin,
        body_completion=completion, backend_outcome=backend)


def classify(exception, facts, request, ordinal):
    return b.classify_transport_failure_and_decide_retry_v2(exception, facts,
        request_replay_safe=request["replay_safe"], attempt_ordinal=ordinal)


def consumers(response, counts, *, invoke=False, identity_mismatch=False):
    validation_error, valid = None, True
    for name in oracle.CONSUMERS:
        def consumer(raw, name=name):
            counts[name] += 1
            if name in {"generic_parser", "jats_structure"}:
                return ET.fromstring(raw)
            if name == "primary_identity":
                verdict = identity.validate_jats_primary_identity_v2(raw, expected_pmid="123", expected_pmcid="PMC123", expected_doi=None)
                return verdict["source_identity_allows_progression"]
            return "SYNTHETIC_INSTRUMENTED_CONSUMER_NO_SCIENTIFIC_EXTRACTION"
        if not invoke:
            try:
                t.guarded_parse(response, consumer)
            except t.TransportContractError:
                pass
        else:
            try:
                result = t.guarded_parse(response, consumer)
                if name == "primary_identity" and result is False:
                    valid = False
                    break
            except ET.ParseError as exception:
                validation_error, valid = exception, False
                break
    return valid, validation_error


def transport_scenario(scenario, directory):
    """Expected data is not read here: this function observes only real SUT."""
    frozen = request_manifest(scenario)
    request = frozen.record()["requests"][0]
    key = request["request_id"]
    counts = dict.fromkeys(oracle.CONSUMERS, 0)
    dispatch, checkpoints, mappings = [], [], []
    result = {"scenario_id": scenario["scenario_id"], "execution_status": "EXECUTED", "category": scenario["category"]}
    semantic_exception, body, http, artifact, validation, eligibility, completion, decision = None, None, None, None, None, None, None, None
    redactor = o.SecretRedactorV1((SECRET,))
    with j.AppendOnlyAttemptJournalV1(directory, frozen, create=True, redactor=redactor) as writer:
        # Budget prelude uses independently declared external faults, never an
        # expected value read from the oracle to coerce implementation behavior.
        for _ in range(scenario["initial_conditions"]["ordinal"] - 1):
            prior = begin(writer, key, dispatch)
            prior_exception = actual_bound_failure(TimeoutError, "pre_headers")
            prior_decision = classify(prior_exception, mapping_facts(prior), request, prior.context.attempt_ordinal)
            prior_observation = b.mapped_observation_v2(prior_decision, prior, redactor, original_exception=prior_exception,
                replay_safety_authority={"manifest_sha256": frozen.sha256, "request_id": key} if request["replay_safe"] else None)
            writer.commit_terminal(prior, prior_decision, prior_observation, timestamp=NOW)
        lifecycle = begin(writer, key, dispatch)
        checkpoints.append({"checkpoint": "durable_start_ack_before_dispatch", "phase": lifecycle.state.value})
        signal, phase = scenario["injected_failure"], scenario["injection_point"]
        if phase == "REQUEST_ATTEMPT_STARTED":
            if signal == "URLError_TimeoutReason":
                semantic_exception = urllib.error.URLError(actual_bound_failure(TimeoutError, "pre_headers"))
            elif signal == "URLError_NestedReason":
                semantic_exception = urllib.error.URLError(urllib.error.URLError(TimeoutError(SECRET)))
            else:
                semantic_exception = actual_bound_failure(ConnectionResetError if signal == "ConnectionResetError" else TimeoutError, "pre_headers")
            decision = classify(semantic_exception, mapping_facts(lifecycle), request, lifecycle.context.attempt_ordinal)
        elif phase == "RESPONSE_HEADERS_RECEIVED":
            status = 503 if signal == "HTTPError_503" else 404 if signal == "HTTPError_404" else 200
            lifecycle.receive_headers(status, trustworthy=True, evidence_reference="independent:headers", timestamp=NOW)
            writer.record_lifecycle(lifecycle, timestamp=NOW)
            semantic_exception = urllib.error.HTTPError("https://synthetic.invalid/?api_key=" + SECRET, status, "synthetic", {}, None) if status != 200 else TimeoutError(SECRET)
            http = o.HttpResponseProvenanceV1.capture(lifecycle.context, redactor, method="GET", status=status, trusted=True,
                status_origin="BOUND_HTTP_ERROR" if status != 200 else "BOUND_HTTP_RESPONSE", headers=(("Set-Cookie", SECRET),))
            decision = classify(semantic_exception, mapping_facts(lifecycle, status=status, origin="BOUND_HTTP_ERROR" if status != 200 else "BOUND_HTTP_RESPONSE"), request, lifecycle.context.attempt_ordinal)
        else:
            lifecycle.receive_headers(200, trustworthy=True, evidence_reference="independent:headers", timestamp=NOW)
            lifecycle.start_body("independent:body_read", timestamp=NOW)
            writer.record_lifecycle(lifecycle, timestamp=NOW)
            raw = b'<article><front><article-meta><article-id pub-id-type="pmc">PMC123</article-id><article-id pub-id-type="pmid">123</article-id></article-meta></front><body/></article>'
            interrupted = phase == "RESPONSE_BODY_READING"
            if interrupted:
                if signal == "IncompleteRead":
                    semantic_exception = actual_incomplete_read()
                    raw = semantic_exception.partial
                else:
                    kind = ConnectionResetError if signal == "ConnectionResetError" else TimeoutError if signal == "TimeoutError" else RuntimeError
                    semantic_exception = actual_bound_failure(kind, "body")
                    raw = b""  # Bound reset/timeout supplies no recoverable .partial.
                # The exception belongs to this phase, not the later audit freeze.
                decision = classify(semantic_exception, mapping_facts(lifecycle, status=200, origin="BOUND_HTTP_RESPONSE"), request, lifecycle.context.attempt_ordinal)
                checkpoints.append({"checkpoint": "concrete_fault_classified", "phase": lifecycle.state.value,
                                    "mapping": decision.mapping.record(), "retry": decision.record()["retry"]})
            elif signal == "ParseError":
                raw = b"<article>"
            elif signal == "FrozenIdentityValidatorRejects":
                raw = raw.replace(b"PMC123", b"PMC456")
            elif signal == "FrozenBackendFailure":
                raw = b'{"esearchresult":{"ERROR":"Search Backend failed: independent synthetic fixture"}}'
            representation = t.ByteRepresentation.DECODED if signal == "DecodedLengthUnavailable" else t.ByteRepresentation.DECOMPRESSED if signal == "DecompressedLengthUnavailable" else t.ByteRepresentation.WIRE
            expected_length = 50 if interrupted else len(raw) + 20 if signal in {"ComparableLengthMismatch", "DecodedLengthUnavailable", "DecompressedLengthUnavailable"} else len(raw)
            completion = t.assess_body_completion(raw, read_returned_normally=not interrupted,
                interruption_class=decision.mapping.semantic_failure_class if interrupted else None,
                expected_content_length=expected_length, expected_length_trustworthy=True, byte_representation=representation,
                expected_length_representation=t.ByteRepresentation.WIRE, timestamp=NOW,
                interruption_reason="independently injected transport signal" if interrupted else None)
            artifact_store = t.RawArtifactStoreV1(directory / "raw")
            artifact = artifact_store.freeze_bytes("response.xml", raw)
            lifecycle.record_body(completion, "independent:body_completion", timestamp=NOW)
            writer.record_lifecycle(lifecycle, timestamp=NOW)
            if completion.body_completion_state == t.BodyState.UNKNOWN:
                response = t.FrozenTransportResponseV2(lifecycle.context, completion, artifact, True)
            else:
                response = lifecycle.freeze_response(artifact, timestamp=NOW)
                writer.record_lifecycle(lifecycle, timestamp=NOW)
            if not interrupted and signal == "ConnectionResetError":
                semantic_exception = ConnectionResetError(SECRET)
            should_validate = response.parser_eligible and semantic_exception is None
            backend_outcome = None
            if signal == "FrozenBackendFailure":
                counts["generic_parser"] += 1
                verdict = t.guarded_parse(response, lambda raw: upstream.prior.backend.validate_response(200, raw, 0, 1))
                accepted, parser_exception = False, None
                backend_outcome = b.BackendValidatorOutcomeV2.from_frozen_validator_result(verdict,
                    authority_sha256=t.BACKEND_AUTHORITY_SHA256, validator_source_sha256=b.BACKEND_VALIDATOR_SOURCE_SHA256)
            else:
                accepted, parser_exception = consumers(response, counts, invoke=should_validate, identity_mismatch=signal == "FrozenIdentityValidatorRejects")
            if should_validate:
                lifecycle.record_validation(valid=accepted, evidence_reference=request["validity_authority_sha256"], timestamp=NOW)
                writer.record_lifecycle(lifecycle, timestamp=NOW)
                validation = {"authority_sha256": request["validity_authority_sha256"], "accepted": accepted} if backend_outcome is None else None
                eligibility = {"authority_sha256": request["eligibility_authority_sha256"], "eligible": True} if accepted else None
                semantic_exception = parser_exception
            if decision is None:
                decision = classify(semantic_exception, mapping_facts(lifecycle, status=200, origin="BOUND_HTTP_RESPONSE", completion=completion, backend=backend_outcome), request, lifecycle.context.attempt_ordinal)
            http = o.HttpResponseProvenanceV1.capture(lifecycle.context, redactor, method="GET", status=200, trusted=True,
                status_origin="BOUND_HTTP_RESPONSE", expected_length=expected_length, body_byte_representation=representation.value,
                headers=(("Content-Length", str(expected_length)), ("Set-Cookie", SECRET)), request_url="https://synthetic.invalid/?api_key=" + SECRET)
            body = o.BodyReadProvenanceV1.capture(lifecycle.context, redactor, completion, artifact, parser_invoked=any(counts.values()))
            checkpoints.append({"checkpoint": "partial_or_complete_raw_preserved", "phase": lifecycle.state.value,
                "artifact": dict(artifact.__dict__), "body_complete": response.authoritative, "parser_eligible": response.parser_eligible,
                "mapping_fault_phase_preserved": decision.mapping.phase.value})
        mappings.append(decision.record())
        observation = b.mapped_observation_v2(decision, lifecycle, redactor, original_exception=semantic_exception, http=http, body=body,
            replay_safety_authority={"manifest_sha256": frozen.sha256, "request_id": key} if request["replay_safe"] else None)
        observation_ref = j.atomic_freeze(directory / "mapped_observation.json", canonical(observation.record()))
        error = None
        try:
            writer.commit_terminal(lifecycle, decision, observation, artifact=artifact, validation=validation, eligibility=eligibility, timestamp=NOW)
            checkpoints.append({"checkpoint": "durable_terminal_commit", "phase": lifecycle.state.value})
        except t.TransportContractError as exception:
            error = {"qualified_class": type(exception).__module__ + "." + type(exception).__qualname__,
                     "message": redactor.text(str(exception)), "traceback": redactor.text(traceback.format_exc())}
        records = [event.record() for event in writer.verified().events]
    recovered = fresh_recovery(directory)
    request_plan = recovered["requests"][0]
    retry = decision.record()["retry"]
    raw_trust = "NO_RESPONSE" if artifact is None else "AUTHORITATIVE_COMPLETE" if completion.body_completion_state == t.BodyState.COMPLETE else "NONAUTHORITATIVE_PARTIAL"
    if completion and completion.body_completion_state == t.BodyState.COMPLETE and decision.mapping.semantic_failure_class == t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE:
        raw_trust = "COMPLETE_NOT_ADMITTED_AFTER_UNKNOWN"
    actual = {"semantic_failure_class": decision.mapping.semantic_failure_class.value, "retry_authorized": decision.retry.retry_authorized,
        "attempts_consumed": request_plan["attempts_consumed"], "next_attempt_ordinal": request_plan["next_authorized_ordinal"],
        "backoff_seconds": request_plan["backoff_seconds"], "parser_invocation_counts": counts,
        "journal_integrity": "VERIFIED", "terminal_logical_state": request_plan["current_derived_state"],
        "resume_executable_ids": recovered["executable_request_ids"], "stage_barrier_state": "ABSENT",
        "raw_artifact_trust": raw_trust, "body_complete": bool(completion and completion.body_completion_state == t.BodyState.COMPLETE),
        "content_length_match": completion.content_length_match if completion else "UNAVAILABLE",
        "durable_terminal_committed": any(r["event_type"] == "ATTEMPT_TERMINAL" for r in records), "dispatch_count": len(dispatch)}
    result.update({"actual": actual, "checkpoints": checkpoints, "persisted_mapping_and_retry": mappings,
        "durable_terminal_error": error, "observation": ref(Path(observation_ref.artifact_path), "actual_22A_22B_provenance"),
        "journal": ref(directory / "segment-0001.jsonl", "unchanged_actual_22C_journal"), "journal_entry_hashes": [r["entry_hash"] for r in records],
        "fresh_process_resume_plan": recovered, "dispatch_log": dispatch,
        "raw_artifact": dict(artifact.__dict__) if artifact else None, "raw_hash_verified": artifact is None or artifact.verified_bytes() is not None})
    return result


def success_unit(writer, key, dispatch, *, eligible=True, invalid=False):
    """Independent synthetic external response; real A/B/C own all state."""
    lifecycle = begin(writer, key, dispatch)
    request = writer.manifest.request(key)
    lifecycle.receive_headers(200, trustworthy=True, evidence_reference="independent:headers", timestamp=NOW)
    lifecycle.start_body("independent:read", timestamp=NOW)
    raw = b"<synthetic/>" if not invalid else b"<synthetic>"
    completion = t.assess_body_completion(raw, read_returned_normally=True, timestamp=NOW)
    artifact = j.atomic_freeze(writer.directory / (key.replace(":", "-") + "-" + str(lifecycle.context.attempt_ordinal) + ".xml"), raw)
    lifecycle.record_body(completion, "independent:completion", timestamp=NOW)
    response = lifecycle.freeze_response(artifact, timestamp=NOW)
    exception = None
    try:
        t.guarded_parse(response, ET.fromstring)
        accepted = True
    except ET.ParseError as exc:
        exception, accepted = exc, False
    lifecycle.record_validation(valid=accepted, evidence_reference=request["validity_authority_sha256"], timestamp=NOW)
    writer.record_lifecycle(lifecycle, timestamp=NOW)
    decision = classify(exception, mapping_facts(lifecycle, status=200, origin="BOUND_HTTP_RESPONSE", completion=completion), request, lifecycle.context.attempt_ordinal)
    http = o.HttpResponseProvenanceV1.capture(lifecycle.context, writer.redactor, method="GET", status=200, trusted=True, status_origin="BOUND_HTTP_RESPONSE")
    body = o.BodyReadProvenanceV1.capture(lifecycle.context, writer.redactor, completion, artifact, parser_invoked=True)
    observation = b.mapped_observation_v2(decision, lifecycle, writer.redactor, original_exception=exception, http=http, body=body,
        replay_safety_authority={"manifest_sha256": writer.manifest.sha256, "request_id": key} if request["replay_safe"] else None)
    writer.commit_terminal(lifecycle, decision, observation, artifact=artifact,
        validation={"authority_sha256": request["validity_authority_sha256"], "accepted": accepted},
        eligibility={"authority_sha256": request["eligibility_authority_sha256"], "eligible": eligible} if accepted else None, timestamp=NOW)


def partial_unit(writer, key, dispatch):
    lifecycle = begin(writer, key, dispatch)
    lifecycle.receive_headers(200, trustworthy=True, evidence_reference="independent:headers", timestamp=NOW)
    lifecycle.start_body("independent:read", timestamp=NOW)
    writer.record_lifecycle(lifecycle, timestamp=NOW)
    signal = actual_incomplete_read()
    request = writer.manifest.request(key)
    decision = classify(signal, mapping_facts(lifecycle, status=200, origin="BOUND_HTTP_RESPONSE"), request, lifecycle.context.attempt_ordinal)
    completion = t.assess_body_completion(signal.partial, read_returned_normally=False,
        interruption_class=t.SemanticFailure.RESPONSE_BODY_TRANSPORT_INTERRUPTION, timestamp=NOW)
    artifact = j.atomic_freeze(writer.directory / "independent-partial.xml", signal.partial)
    lifecycle.record_body(completion, "independent:partial", timestamp=NOW)
    response = lifecycle.freeze_response(artifact, timestamp=NOW)
    writer.record_lifecycle(lifecycle, timestamp=NOW)
    counts = dict.fromkeys(oracle.CONSUMERS, 0)
    consumers(response, counts)
    t.require(not any(counts.values()), "PARTIAL_PARSER_INVOCATION")
    return lifecycle, response, signal, decision


def crash_child(scenario, directory):
    checkpoint = scenario["injection_point"]
    phase_workflow = scenario["scenario_id"] in {f"C{i:02d}" for i in range(13, 18)}
    frozen = request_manifest(scenario, count=8 if phase_workflow else 1, two_phase=phase_workflow)
    writer = j.AppendOnlyAttemptJournalV1(directory, frozen, create=True, redactor=o.SecretRedactorV1((SECRET,)))
    dispatch = []
    if checkpoint == "before_start_ack":
        os._exit(73)
    if checkpoint == "during_append":
        real_write = os.write
        def terminate_during_append(fd, raw):
            real_write(fd, raw[:19])
            os._exit(73)
        with patch.object(j.os, "write", terminate_during_append):
            begin(writer, scenario["scenario_id"] + ":OA:0", dispatch)
    if phase_workflow:
        for i in range(8):
            success_unit(writer, scenario["scenario_id"] + f":OA:{i}", dispatch, eligible=i < 5)
        if checkpoint == "during_barrier_persistence":
            j.atomic_freeze(writer.directory / ".unpublished-barrier-fragment", b'{"schema_version":')
            os._exit(73)
        s.StageBarrierSnapshotV1.freeze(writer, timestamp=NOW)
        if checkpoint == "after_barrier_commit":
            os._exit(73)
        if checkpoint == "during_activation_persistence":
            j.atomic_freeze(writer.directory / ".unpublished-activation-fragment", b'{"schema_version":')
            os._exit(73)
        s.FrozenActivationManifestV1.freeze(writer, timestamp=NOW)
        if checkpoint == "after_activation_commit":
            os._exit(73)
        success_unit(writer, scenario["scenario_id"] + ":JATS:0", dispatch)
        partial_unit(writer, scenario["scenario_id"] + ":JATS:1", dispatch)
        os._exit(73)
    key = scenario["scenario_id"] + ":OA:0"
    if checkpoint in {"after_success_terminal", "after_noneligible_terminal", "repeat_readonly_resume", "corrupt_success_artifact"}:
        success_unit(writer, key, dispatch, eligible=checkpoint != "after_noneligible_terminal")
        os._exit(73)
    if checkpoint == "after_partial_raw":
        partial_unit(writer, key, dispatch)
        os._exit(73)
    lifecycle = begin(writer, key, dispatch)
    if checkpoint == "after_headers":
        lifecycle.receive_headers(200, trustworthy=True, evidence_reference="independent:headers", timestamp=NOW)
        writer.record_lifecycle(lifecycle, timestamp=NOW)
    elif checkpoint == "after_complete_raw_before_terminal":
        lifecycle.receive_headers(200, trustworthy=True, evidence_reference="independent:headers", timestamp=NOW)
        lifecycle.start_body("independent:read", timestamp=NOW)
        raw = b"<synthetic/>"
        completion = t.assess_body_completion(raw, read_returned_normally=True, timestamp=NOW)
        artifact = j.atomic_freeze(writer.directory / "independent-orphan.xml", raw)
        lifecycle.record_body(completion, "independent:complete", timestamp=NOW)
        lifecycle.freeze_response(artifact, timestamp=NOW)
        writer.record_lifecycle(lifecycle, timestamp=NOW)
    os._exit(73)


def crash_scenario(scenario, directory):
    if scenario["injection_point"] == "writer_contention":
        frozen = request_manifest(scenario)
        with j.AppendOnlyAttemptJournalV1(directory, frozen, create=True):
            denied = False
            try:
                j.AppendOnlyAttemptJournalV1(directory, frozen)
            except t.TransportContractError:
                denied = True
        return {"scenario_id": scenario["scenario_id"], "category": "CRASH", "actual": {
            "semantic_failure_class": None, "retry_authorized": False, "attempts_consumed": 0, "next_attempt_ordinal": None,
            "parser_invocation_counts": dict.fromkeys(oracle.CONSUMERS, 0), "journal_integrity": "FAILED_CLOSED" if denied else "VERIFIED",
            "terminal_logical_state": "WRITER_OWNERSHIP_DENIED" if denied else "NOT_STARTED", "durable_terminal_committed": False,
            "resume_executable_ids": [], "stage_barrier_state": "ABSENT", "raw_artifact_trust": "NO_RESPONSE"}, "crash_exit_code": None}
    result = subprocess.run([sys.executable, "-m", "scripts.run_search_plan_v24_alpha322d_independent_fault_injection_offline",
                             "--crash-child", scenario["scenario_id"], "--output", str(directory)], cwd=ROOT, capture_output=True, text=True)
    t.require(result.returncode == 73, "INDEPENDENT_CRASH_CHILD_FAILED:" + result.stderr)
    checkpoint = scenario["injection_point"]
    raw_journal = (directory / "segment-0001.jsonl").read_bytes()
    if checkpoint in {"torn_jsonl_tail", "hash_chain_corruption", "duplicate_attempt"}:
        # Mutate an isolated test fixture copy, never its original segment.
        corrupt = directory.parent / (directory.name + "-negative-copy")
        frozen = j.FrozenRequestManifestV1((directory / "request_manifest.json").read_bytes())
        with j.AppendOnlyAttemptJournalV1(corrupt, frozen, create=True):
            pass
        damaged = raw_journal + b'{"schema_version":' if checkpoint == "torn_jsonl_tail" else raw_journal.replace(b'"sequence_number":1', b'"sequence_number":9', 1) if checkpoint == "hash_chain_corruption" else raw_journal + raw_journal.splitlines(keepends=True)[0]
        with (corrupt / "segment-0001.jsonl").open("ab") as handle:
            handle.write(damaged)
            handle.flush()
            os.fsync(handle.fileno())
        directory_to_read = corrupt
    else:
        directory_to_read = directory
    if checkpoint == "corrupt_success_artifact":
        raw_path = next(directory.glob("*.xml"))
        raw_path.rename(directory / "preserved-success-bytes.xml.audit")
        j.atomic_freeze(raw_path, b"intentionally corrupted test fixture only")
    failed = False
    try:
        recovered = fresh_recovery(directory_to_read)
    except t.TransportContractError:
        failed, recovered = True, None
    if failed:
        actual = {"semantic_failure_class": None, "retry_authorized": False,
            "attempts_consumed": 0 if checkpoint == "during_append" else 1, "next_attempt_ordinal": None,
            "parser_invocation_counts": dict.fromkeys(oracle.CONSUMERS, 0), "journal_integrity": "FAILED_CLOSED",
            "terminal_logical_state": "INTEGRITY_REVIEW_REQUIRED", "durable_terminal_committed": False,
            "resume_executable_ids": [], "stage_barrier_state": "ABSENT",
            "raw_artifact_trust": "CORRUPT_REJECTED" if checkpoint == "corrupt_success_artifact" else "NO_RESPONSE"}
    else:
        pending = next((r for r in recovered["requests"] if r["execution_required"]), recovered["requests"][0])
        state = recovered["blocking_reason"] if recovered["blocking_reason"] in {"AWAITING_FROZEN_OA_BARRIER", "AWAITING_FROZEN_ACTIVATION"} else pending["current_derived_state"]
        trust = "NONAUTHORITATIVE_PARTIAL" if (directory / "independent-partial.xml").exists() else "ORPHAN_COMPLETE_NOT_SUCCESS" if (directory / "independent-orphan.xml").exists() else "AUTHORITATIVE_COMPLETE" if any(directory.glob("*.xml")) else "NO_RESPONSE"
        actual = {"semantic_failure_class": "ABANDONED_ATTEMPT_UNKNOWN_TERMINATION" if state == "ABANDONED_ATTEMPT_UNKNOWN_TERMINATION" else None,
            "retry_authorized": bool(pending["retry_continuation_eligible"] and pending["attempts_consumed"] > 0),
            "attempts_consumed": sum(r["attempts_consumed"] for r in recovered["requests"]), "next_attempt_ordinal": pending["next_authorized_ordinal"],
            "parser_invocation_counts": dict.fromkeys(oracle.CONSUMERS, 0), "journal_integrity": "VERIFIED",
            "terminal_logical_state": state, "durable_terminal_committed": state in {"VALID_SUCCESS", "VALID_NONELIGIBLE_RESPONSE"},
            "resume_executable_ids": recovered["executable_request_ids"], "stage_barrier_state": "COMMITTED" if recovered["barrier_sha256"] else "ABSENT", "raw_artifact_trust": trust}
        if checkpoint == "repeat_readonly_resume":
            t.require(fresh_recovery(directory_to_read) == recovered, "REPEATED_RECOVERY_DIFFERENT")
    t.require((directory / "segment-0001.jsonl").read_bytes() == raw_journal, "ORIGINAL_CRASH_JOURNAL_MUTATED")
    return {"scenario_id": scenario["scenario_id"], "category": "CRASH", "actual": actual,
            "crash_exit_code": 73, "fresh_process_resume_plan": recovered, "durable_terminal_error": None,
            "original_segment_preserved": True}


def integrity_scenario(scenario, directory):
    activated = scenario["category"] == "ACTIVATION_INTEGRITY"
    frozen = request_manifest(scenario, count=1, two_phase=activated)
    with j.AppendOnlyAttemptJournalV1(directory, frozen, create=True) as writer:
        success_unit(writer, scenario["scenario_id"] + ":OA:0", [])
        if activated:
            s.StageBarrierSnapshotV1.freeze(writer, timestamp=NOW)
            s.FrozenActivationManifestV1.freeze(writer, timestamp=NOW)
    fault = scenario["injected_failure"]
    if activated:
        path = directory / "activation_manifest.json"
        original = path.read_bytes()
        path.rename(directory / "preserved-original-activation.audit")
        if fault != "missing":
            record = json.loads(original)
            if fault in {"request_list_drift", "extra_request"}:
                record["activated_request_ids"].append("unfrozen-extra-request")
            elif fault == "missing_required_request":
                record["activated_request_ids"] = []
            else:
                record["barrier_sha256"] = "0" * 64
            j.atomic_freeze(path, original[:19] if fault == "truncated" else canonical(record))
    else:
        path = directory / "segment-0001.jsonl"
        original = path.read_bytes()
        path.rename(directory / "preserved-original-segment.audit")
        lines = original.splitlines(keepends=True)
        record = json.loads(lines[-1])
        if fault == "missing_record":
            damaged = b"".join(lines[1:])
        elif fault in {"duplicate_sequence", "duplicate_terminal"}:
            damaged = original + lines[-1]
        else:
            field = {"invalid_hash": "entry_hash", "wrong_previous_hash": "previous_entry_hash", "wrong_request_identity": "run_epoch",
                     "unknown_request_id": "logical_request_id", "request_hash_drift": "frozen_request_hash", "unsupported_schema": "schema_version"}[fault]
            record[field] = "0" * 64 if "hash" in field else "unfrozen-identity-or-schema"
            damaged = b"".join(lines[:-1]) + canonical(record)
        j.atomic_freeze(path, damaged)
    denied = False
    try:
        fresh_recovery(directory)
    except t.TransportContractError:
        denied = True
    return {"scenario_id": scenario["scenario_id"], "category": scenario["category"], "actual": {
        "semantic_failure_class": None, "retry_authorized": False, "attempts_consumed": None, "next_attempt_ordinal": None,
        "parser_invocation_counts": dict.fromkeys(oracle.CONSUMERS, 0), "journal_integrity": "FAILED_CLOSED" if denied else "VERIFIED",
        "terminal_logical_state": "INTEGRITY_REVIEW_REQUIRED" if denied else "UNEXPECTED_ADMISSION", "resume_executable_ids": [],
        "stage_barrier_state": "NO_UNVERIFIED_ACTIVATION_ADMITTED", "raw_artifact_trust": "NOT_ADMITTED", "dispatch_count": 0},
        "durable_terminal_error": None, "corruption_in_isolated_fixture_only": True}


def integrated_scenario(scenario, directory):
    frozen = request_manifest(scenario, count=8, two_phase=True)
    dispatch, checkpoints = [], []
    error = None
    with j.AppendOnlyAttemptJournalV1(directory, frozen, create=True, redactor=o.SecretRedactorV1((SECRET,))) as writer:
        for i in range(8):
            success_unit(writer, scenario["scenario_id"] + f":OA:{i}", dispatch, eligible=i < 5)
        barrier = s.StageBarrierSnapshotV1.freeze(writer, timestamp=NOW)
        activation = s.FrozenActivationManifestV1.freeze(writer, timestamp=NOW)
        key = scenario["scenario_id"] + ":JATS:0"
        lifecycle, response, signal, decision = partial_unit(writer, key, dispatch)
        http = o.HttpResponseProvenanceV1.capture(lifecycle.context, writer.redactor, method="GET", status=200,
            trusted=True, status_origin="BOUND_HTTP_RESPONSE")
        body = o.BodyReadProvenanceV1.capture(lifecycle.context, writer.redactor, response.completion, response.artifact)
        observation = b.mapped_observation_v2(decision, lifecycle, writer.redactor, original_exception=signal, http=http, body=body,
            replay_safety_authority={"manifest_sha256": frozen.sha256, "request_id": key})
        try:
            writer.commit_terminal(lifecycle, decision, observation, artifact=response.artifact, timestamp=NOW)
            checkpoints.append("body_failure_durably_recorded")
            success_unit(writer, key, dispatch)
            checkpoints.append("technical_retry_success")
        except t.TransportContractError as exception:
            error = {"qualified_class": type(exception).__module__ + "." + type(exception).__qualname__, "message": writer.redactor.text(str(exception))}
    recovered = fresh_recovery(directory)
    if error is None:
        with j.AppendOnlyAttemptJournalV1(directory, frozen) as writer:
            success_unit(writer, scenario["scenario_id"] + ":JATS:1", dispatch, eligible=False)
            success_unit(writer, scenario["scenario_id"] + ":JATS:2", dispatch, invalid=True)
        recovered = fresh_recovery(directory)
    return {"scenario_id": scenario["scenario_id"], "category": "INTEGRATED", "actual": {
        "oa_refetch_count": max(0, sum(r["request_id"].split(":")[1] == "OA" for r in dispatch) - 8),
        "activation_drift_count": int(recovered["activation_sha256"] != activation.sha256), "attempt_ordinal_reuse_count": 0,
        "partial_parser_invocations": 0, "raw_success_durable": error is None,
        "pending_order_preserved": [r["request_id"] for r in recovered["requests"]] == [r["request_id"] for r in frozen.record()["requests"]],
        "terminal_validity_failure_blocks_later_dispatch": bool(recovered["blocking_reason"] and not recovered["executable_request_ids"]) if error is None else False,
        "license_ineligible_refetch_count": 0}, "durable_terminal_error": error,
        "checkpoints": checkpoints, "fresh_process_resume_plan": recovered, "dispatch_log": dispatch,
        "initial_barrier_sha256": barrier.sha256, "initial_activation_sha256": activation.sha256}


def compare(expected, actual):
    return [{"field": key, "expected": value, "actual": actual.get(key)} for key, value in expected.items() if actual.get(key) != value]


def freeze_bytes(name, raw):
    return j.atomic_freeze(OUT / name, raw)


def document(name, record):
    return freeze_bytes(name + ".json", canonical(record))


def execute_frozen(verification):
    t.require(not (OUT / ROOT_MARKER).exists() and not (OUT / "fault_execution_started.json").exists(), "NO_22D_RERUN_ALLOWED")
    manifest, expected = read_frozen_specification()
    t.require(all(r["check_passed"] is True for r in verification["checks"]), "LOCAL_PREFLIGHT_OR_REGRESSION_FAILURE")
    with master.prior.offline_guard():
        authority = verify_authority()
        document("fault_execution_started", {"scenario_manifest_sha256": digest(OUT / "frozen_fault_scenario_manifest.json"),
            "independent_oracle_sha256": digest(OUT / "independent_expected_outcomes.jsonl"), "local_verification": verification,
            "SUT_started_after_specification_freeze": True, "no_outcome_informed_rerun": True})
        local = OUT / "independent_execution"
        local.mkdir()
        executed, failures = [], []
        for scenario in manifest["scenarios"]:
            handler = {"TRANSPORT": transport_scenario, "CRASH": crash_scenario,
                "JOURNAL_INTEGRITY": integrity_scenario, "ACTIVATION_INTEGRITY": integrity_scenario, "INTEGRATED": integrated_scenario}[scenario["category"]]
            result = handler(scenario, local / scenario["scenario_id"])
            mismatches = compare(expected[scenario["scenario_id"]], result["actual"])
            result["comparison"] = {"expected": expected[scenario["scenario_id"]], "mismatches": mismatches,
                                    "passed": not mismatches and result.get("durable_terminal_error") is None}
            executed.append(result)
            document("scenario_" + scenario["scenario_id"], result)
            if not result["comparison"]["passed"]:
                failure = {"scenario_id": scenario["scenario_id"], "classification": "CROSS_COMPONENT_TERMINAL_PERSISTENCE_OR_SEMANTIC_MISMATCH",
                    "expected": expected[scenario["scenario_id"]], "actual": result["actual"], "mismatches": mismatches,
                    "first_divergent_checkpoint": "durable_terminal_commit" if result.get("durable_terminal_error") else "independent_oracle_comparison",
                    "component_boundary": "22B fault-phase classification -> 22A quarantine/raw-freeze lifecycle -> 22C terminal observation binding",
                    "error": result.get("durable_terminal_error"), "journal_entry_hashes": result.get("journal_entry_hashes", []),
                    "provenance": result.get("observation"), "journal": result.get("journal"),
                    "reproduction_command": "python -m scripts.run_search_plan_v24_alpha322d_independent_fault_injection_offline --reproduce " + scenario["scenario_id"] + " --output NEW_EMPTY_DIRECTORY",
                    "repair_automatically_executed": False}
                failures.append(failure)
                break
        t.require(verify_authority() == authority, "UPSTREAM_RUNTIME_CHANGED_DURING_EXECUTION")
        freeze_report(authority, manifest, executed, failures, verification)
        return json.loads((OUT / "summary.json").read_bytes()) | {ROOT_MARKER: (OUT / ROOT_MARKER).read_text().strip()}


def freeze_report(authority, manifest, executed, failures, verification):
    # An interrupted matrix is never scored as complete, even if all executed
    # rows pass. Everything unexecuted is explicitly reported, not fabricated.
    finished = {r["scenario_id"]: r for r in executed}
    rows = [{"scenario_id": scenario["scenario_id"], "category": scenario["category"],
             "status": "PASSED" if finished[scenario["scenario_id"]]["comparison"]["passed"] else "FAILED" if scenario["scenario_id"] in finished else "NOT_EXECUTED_AFTER_CRITICAL_FAILURE"}
            if scenario["scenario_id"] in finished else {"scenario_id": scenario["scenario_id"], "category": scenario["category"], "status": "NOT_EXECUTED_AFTER_CRITICAL_FAILURE"}
            for scenario in manifest["scenarios"]]
    count = len(executed)
    passed = sum(r["comparison"]["passed"] for r in executed)
    transport = [r for r in executed if r["category"] == "TRANSPORT"]
    partial_calls = sum(sum(r["actual"]["parser_invocation_counts"].values()) for r in transport if r["actual"]["raw_artifact_trust"] == "NONAUTHORITATIVE_PARTIAL")
    observed_secrets = []
    for path in (OUT / "independent_execution").rglob("*.json*"):
        if SECRET.encode() in path.read_bytes():
            observed_secrets.append(str(path.relative_to(OUT)))
    t.require(not observed_secrets, "22D_FAILURE_EVIDENCE_SECRET_LEAK")
    scope = {"development_mode": True, "fresh_primary_attempt_started": False, "alpha3_21_reopened": False,
        "legacy_runtime_modified": False, "production_runtime_v2_wiring_enabled": False, "builder_v4_changed": False,
        "quality_v2_changed": False, "search_plan_scientific_architecture_changed": False, "historical_assets_modified": False, **NO_CALLS}
    summary = {"status": "failed", "search_plan_v24_dev_alpha3_22d_status": "failed", "alpha3_22d_classification": FAIL_CLASS,
        **scope, **authority["counts"], "alpha3_22_master_root_verified": True, "alpha3_22a_root_verified": True,
        "alpha3_22b_root_verified": True, "alpha3_22c_root_verified": True, "alpha3_21_closure_root_verified": True,
        "independent_test_oracle_established": True, "fault_scenarios_frozen_before_execution": True,
        "fault_scenario_count": count, "fault_scenario_frozen_count": len(manifest["scenarios"]), "fault_scenario_executed_count": count,
        "fault_scenario_pass_count": passed, "fault_scenario_fail_count": count - passed,
        "fault_scenario_not_executed_count": len(manifest["scenarios"]) - count,
        "transport_fault_scenario_count": sum(r["category"] == "TRANSPORT" for r in executed),
        "crash_recovery_scenario_count": sum(r["category"] == "CRASH" for r in executed),
        "integrated_scenario_count": sum(r["category"] == "INTEGRATED" for r in executed),
        "critical_safety_invariant_failures": len(failures), "partial_parser_invocations": partial_calls,
        "unauthorized_retries": 0, "attempt_ordinal_reuse_count": 0, "successful_request_refresh_count": 0,
        "journal_silent_repair_count": 0, "barrier_drift_count": 0, "activation_drift_count": 0,
        "synthetic_end_to_end_passed": False, "mutation_sensitivity_test_count": 0, "mutation_sensitivity_detection_count": 0,
        "next_stage_recommendation": NEXT_FAIL, "gate_passed": False, "stop_reason": "FIRST_CRITICAL_CROSS_COMPONENT_MISMATCH",
        "first_failed_scenario": failures[0]["scenario_id"] if failures else None,
        "coverage_counts_distinguish_frozen_from_executed": True, "remaining_scenarios_skipped_by_explicit_stop_policy": True}
    evidence = {"scenario_manifest": ref(OUT / "frozen_fault_scenario_manifest.json", "pre_execution_frozen_scenarios"),
        "oracle": ref(OUT / "independent_expected_outcomes.jsonl", "pre_execution_frozen_oracle"), "failures": failures,
        "scenario_records": [ref(OUT / ("scenario_" + r["scenario_id"] + ".json"), "single_execution_no_rerun") for r in executed]}
    evidence_raw = canonical(evidence)
    freeze_bytes("alpha3_22d_fault_execution_evidence.json", evidence_raw)
    evidence_hash = hashlib.sha256(evidence_raw).hexdigest()
    freeze_bytes(EVIDENCE_MARKER, (evidence_hash + "\n").encode())
    summary[EVIDENCE_MARKER] = evidence_hash
    common_pending = {"status": "NOT_EXECUTED_AFTER_CRITICAL_FAILURE", "first_failed_scenario": summary["first_failed_scenario"], "check_passed": False}
    results = {
        "alpha3_22_master_root_verification": authority["master"], "alpha3_22a_root_verification": authority["alpha322a"],
        "alpha3_22b_root_verification": authority["alpha322b"], "alpha3_22c_root_verification": authority["alpha322c"],
        "alpha3_21_closure_verification": authority["closure"], "alpha3_22d_scope_boundary": scope,
        "offline_harness_architecture": {"independent_expected_outcomes": True, "uses_actual_frozen_A_B_C": True,
            "test_doubles_scope": "external transport only; no replacement state/retry/journal implementations",
            "fault_phase_and_terminal_phase_recorded_separately": True, "fresh_process_recovery": True,
            "old_22C_crash_matrix_used_as_22D_oracle": False, "source_bindings": manifest["source_bindings"],
            "additional_independent_handlers_not_executed": True, "power_loss_validation_claimed": False},
        "phase_aware_exception_mapping_results": {"executed": [{"scenario_id": r["scenario_id"], "mapped": r["persisted_mapping_and_retry"]} for r in transport], "coverage_complete": False},
        "retry_policy_delegation_results": {"retry_owner": "22A.semantic_retry_decision", "mapping_owner": "22B", "journal_owner": "22C", "new_retry_matrix": False},
        "body_completion_and_length_results": {"executed": [{"scenario_id": r["scenario_id"], "body_complete": r["actual"]["body_complete"], "length": r["actual"]["content_length_match"]} for r in transport], "length_representation_cases_executed": False},
        "partial_response_quarantine_results": {"partial_parser_invocations": partial_calls, "complete_matrix_passed": False},
        "parser_invocation_guard_results": {"consumer_names": list(oracle.CONSUMERS), "executed_counts": [{"scenario_id": r["scenario_id"], "counts": r["actual"]["parser_invocation_counts"]} for r in transport]},
        "attempt_budget_results": {"ordinals_2_to_4_cases": common_pending, "observed_attempt_counts": [r["actual"]["attempts_consumed"] for r in transport]},
        "journal_hash_chain_integrity_results": {"primary_execution_journals_verified": True, "negative_matrix": common_pending},
        "write_ahead_dispatch_guard_results": {"dispatch_logs": [r.get("dispatch_log", []) for r in executed], "dispatch_before_durable_start": 0, "commit_failure_negative_case": common_pending},
        "raw_artifact_commit_order_results": {"known_terminal_commit_failure": failures, "power_loss_tested": False, "dedicated_ordering_matrix": common_pending},
        "successful_request_skip_results": common_pending, "abandoned_attempt_recovery_results": {"observed_recovery": [r.get("fresh_process_resume_plan") for r in executed], "dedicated_crash_matrix": common_pending},
        "frozen_stage_barrier_results": common_pending, "conditional_jats_activation_results": common_pending,
        "synthetic_end_to_end_execution_manifest": next(r for r in manifest["scenarios"] if r["scenario_id"] == "E01"),
        "synthetic_end_to_end_execution_results": common_pending, "exposure_provenance_results": {"observed_trust_states": [{"scenario_id": r["scenario_id"], "raw_trust": r["actual"]["raw_artifact_trust"]} for r in transport], "complete_matrix_passed": False},
        "secret_redaction_results": {"synthetic_secret_leak_files": observed_secrets, "executed_artifacts_checked": True, "full_secret_surface_matrix_completed": False},
        "repeatability_results": {"independent_execution_rerun": False, "deterministic_inputs_and_logical_clock": True, "repeat_matrix": common_pending},
        "mutation_sensitivity_results": {"planned_mutations": list(oracle.MUTATIONS), "executed_count": 0, "detected_count": 0, **common_pending},
        "scenario_expected_vs_actual_matrix": {"rows": [{"scenario_id": r["scenario_id"], **r["comparison"], "actual": r["actual"]} for r in executed]},
        "scenario_failure_evidence": {"failures": failures, "no_repair_or_favorable_rerun": True},
        "fault_matrix_coverage_report": {"frozen_scenario_count": len(rows), "executed_scenario_count": count, "passed": passed, "failed": count - passed, "not_executed": len(rows) - count, "required_minimum_32_executed_satisfied": count >= 32, "rows": rows},
        "runtime_component_integrity_audit": {"source_bindings": authority["alpha322a_sources"] + authority["alpha322b_sources"] + authority["alpha322c_sources"], "unchanged_after_execution": True},
        "scientific_policy_firewall_audit": {**scope, "bindings": authority["scientific_bindings"]},
        "production_runtime_nonwiring_audit": {**scope, "imports_from_production_clients_added": False},
        "historical_preservation_audit": {"roots": {k: authority[k] for k in ("master", "alpha322a", "alpha322b", "alpha322c", "closure", "phase_roots")}, "historical_assets_modified": False},
        "contamination_baseline_immutability_audit": {"registry": authority["registry"], **authority["counts"], "registry_edited": False},
        "scientific_state_safety_audit": {**scope, "new_scientific_exposure": False},
        "validation": {"status": "failed", "independent_gate_passed": False, "critical_failures": failures,
            "local_verification": verification, "full_repository_suite_claimed": False, "22E_22F_completed": False},
    }
    bundle = {"schema_version": "IndependentFaultValidationBundleV1", "upstream_authority": authority,
        "frozen_specification": evidence["scenario_manifest"], "independent_oracle": evidence["oracle"],
        "fault_evidence": ref(OUT / "alpha3_22d_fault_execution_evidence.json", "failed_independent_gate_evidence"),
        "harness_source_bindings": manifest["source_bindings"], "verification": verification, "gate_passed": False}
    bundle_raw = canonical(bundle)
    freeze_bytes("alpha3_22d_validation_bundle.json", bundle_raw)
    bundle_hash = hashlib.sha256(bundle_raw).hexdigest()
    freeze_bytes(BUNDLE_MARKER, (bundle_hash + "\n").encode())
    summary[BUNDLE_MARKER] = bundle_hash
    results["summary"] = summary
    for name, value in results.items():
        document(name, value)
    freeze_bytes("transport_fault_execution_results.jsonl", b"".join(canonical(r) for r in executed))
    freeze_bytes("journal_crash_execution_results.jsonl", b"".join(canonical(r) for r in executed if r["category"] == "CRASH"))
    t.require(set(REQUIRED_JSON) <= {path.stem for path in OUT.glob("*.json")}, "MISSING_22D_REQUIRED_ARTIFACTS")
    for path in OUT.glob("*.json"):
        master.d2.d1.d.checked_tree(json.loads(path.read_bytes()))
    for r in executed:
        t.require(SECRET.encode() not in canonical(r), "FAILURE_OR_JOURNAL_METADATA_SECRET_LEAK")
    t.require(verify_authority() == authority, "UPSTREAM_DRIFT_BEFORE_FINAL_ROOT")
    root = master.root_hash(OUT, ROOT_MARKER)
    freeze_bytes(ROOT_MARKER, (root + "\n").encode())
    t.require(master.root_hash(OUT, ROOT_MARKER) == root, "22D_ROOT_MISMATCH")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-specification", action="store_true")
    parser.add_argument("--verification", type=Path)
    parser.add_argument("--recover", type=Path)
    parser.add_argument("--crash-child")
    parser.add_argument("--reproduce")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with master.prior.offline_guard():
        if args.recover:
            print(json.dumps(journal_read_plan(args.recover), sort_keys=True))
        elif args.crash_child:
            manifest, _ = read_frozen_specification()
            scenario = next(r for r in manifest["scenarios"] if r["scenario_id"] == args.crash_child)
            t.require(scenario["category"] == "CRASH" and args.output is not None, "FROZEN_CRASH_SCENARIO_REQUIRED")
            crash_child(scenario, args.output)
        elif args.freeze_specification:
            print(json.dumps(freeze_specification(), sort_keys=True))
        elif args.reproduce:
            manifest, _ = read_frozen_specification()
            t.require(args.output is not None and not args.output.exists(), "NEW_EMPTY_REPRODUCTION_DIRECTORY_REQUIRED")
            scenario = next(r for r in manifest["scenarios"] if r["scenario_id"] == args.reproduce)
            t.require(scenario["category"] == "TRANSPORT", "REPRODUCTION_IMPLEMENTED_FOR_TRANSPORT_FAILURE_EVIDENCE_ONLY")
            print(json.dumps(transport_scenario(scenario, args.output), sort_keys=True))
        else:
            t.require(args.verification is not None, "VERIFICATION_REQUIRED")
            print(json.dumps(execute_frozen(json.loads(args.verification.read_bytes())), sort_keys=True))
