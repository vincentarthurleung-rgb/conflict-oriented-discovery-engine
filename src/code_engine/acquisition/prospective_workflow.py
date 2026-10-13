"""Prospective OA/JATS wiring over the unchanged release-validated runtime.

Local POSIX durability only. Inputs are frozen pre-OA source records, not a
source discovery/metadata-selection interface. No generic scientific workflow,
Builder, Quality, model, historical continuation or scientific adjudication.
"""

from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from code_engine import deterministic_resume_planner_v2_length_bound_v1 as planner
from code_engine import stage_barrier_snapshot_v2_length_bound_v1 as barriers
from code_engine import validator_outcome_adapter_length_bound_v1 as validity
from scripts import run_search_plan_v24_alpha319d_pmc_oa_jats_construction_eligibility as legacy
from scripts import search_plan_v24_alpha318a1_source_contracts as source_policy
from scripts import search_plan_v24_alpha318a3_correction_reference as correction
from scripts import search_plan_v24_alpha318a6_license_extraction as license_policy
from scripts import search_plan_v24_alpha321_body_only as body_policy
from scripts import search_plan_v24_alpha321_jats_primary_identity_v2 as identity_policy
from scripts import search_plan_v24_alpha319a1_esearch_response_validity_v2_1 as backend_policy

from . import prospective_transport as transport_module

j, t, o, b = transport_module.j, transport_module.t, transport_module.o, transport_module.b
ROOT, utc = transport_module.ROOT, transport_module.utc
BASELINES = (
    ("20261012_search_plan_v24_dev_alpha3_22_final_independent_oracle_v2_log_namespace_offline",
     "search_plan_v24_dev_alpha3_22_log_namespace_release_sha256", "f7902fbdf27cd000c91ab65d88221a8fd9966fad38fb20020c0b2a095526ed67"),
    ("20261012_search_plan_v24_dev_alpha3_22e_focused_seen_data_replay_offline",
     "search_plan_v24_dev_alpha3_22e_sha256", "eeb8d8c63b39abe9ee1339828f1893356744ed258197fd7d189118d7c3c1c7bc"),
    ("20261012_search_plan_v24_dev_alpha3_22e_bounded_historical_evidence_gap_assessment_offline",
     "search_plan_v24_dev_alpha3_22e_historical_evidence_gap_assessment_sha256", "261e1c26661084a2f224b1a2f33e545dbd6c0f8a6a8b76f6fc897f221870ae5a"),
)
POLICY_SOURCES = {
    "scripts/search_plan_v24_alpha318a4_esearch_response_validity.py": "402f35d497fa89fbab911bf02d3cdbaa6aa58d5547f66d46836725f34b1d0025",
    "scripts/search_plan_v24_alpha318a1_source_contracts.py": "88c4370ebe45c157f9501ea1c7e6350f0348d67a15463254be68d8c315546c5e",
    "scripts/search_plan_v24_alpha318a3_correction_reference.py": "68befecf70cd008a7b0a9154d713decbb14f8e39dc4b945331450d96bf2a3e09",
    "scripts/search_plan_v24_alpha318a6_license_extraction.py": "c4c18cea73e5714ce6107c655805a5772c27c608af13b30d95e1a0659c17e415",
    "scripts/search_plan_v24_alpha321_jats_primary_identity_v2.py": "4a33e0be976f4dd1af1b5f498a9d484e4e45b8ffae70c06d172d7fbff2d4db2a",
    "scripts/search_plan_v24_alpha321_body_only.py": "86b63eba8e19df97c1431204261378abf685269d2b4c04f96803104c93bd91da",
    "scripts/search_plan_v24_alpha319a1_esearch_response_validity_v2_1.py": "2abfdd4bad858bbfcf67a624aacf318b62435cf11992388de8fa8e0c18ec826b",
}
IMPLEMENTATION = ("src/code_engine/acquisition/prospective_transport.py",
                  "src/code_engine/acquisition/prospective_workflow.py",
                  "scripts/run_search_plan_v24_prospective_acquisition.py")
ACTIVATION_SHA = j.sha(b"activate JATS iff frozen parent OA terminal VALID_SUCCESS")


def root_hash(directory, marker):
    directory = Path(directory)
    paths = sorted(directory.rglob("*"))
    j.require(not any(p.is_symlink() for p in paths), "FROZEN_DIRECTORY_SYMLINK")
    entries = [[p.relative_to(directory).as_posix(), j.sha(j.read_bytes(p))]
               for p in paths if p.is_file() and p.name != marker]
    return j.sha(json.dumps(entries, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def verify_baselines():
    for name, marker, expected in BASELINES:
        directory = ROOT / "runs" / name
        j.require(root_hash(directory, marker) == expected == j.read_bytes(directory / marker).decode().strip(),
                  "FROZEN_BASELINE_DRIFT:" + name)
    bindings = j.strict_json(j.read_bytes(ROOT / "runs" / BASELINES[0][0] / "frozen_input_bindings.json"))
    for pair in bindings["runtime_source_bindings"]:
        source, snapshot = pair["source"], pair["snapshot"]
        raw = j.read_bytes(ROOT / source["artifact_path"])
        j.require(raw == j.read_bytes(ROOT / snapshot["artifact_path"]) and
                  j.sha(raw) == source["sha256"] == snapshot["sha256"], "RELEASE_SOURCE_DRIFT")
    for path, expected in POLICY_SOURCES.items():
        j.require(j.sha(j.read_bytes(ROOT / path)) == expected, "SCIENTIFIC_POLICY_SOURCE_DRIFT")
    return {name: expected for name, _, expected in BASELINES}


def configuration(manifest):
    return {"schema_version": "ProspectiveAcquisitionConfigurationV1", "manifest_sha256": manifest.sha256,
        "baseline_roots": {name: expected for name, _, expected in BASELINES},
        "runtime_authority": j.AUTHORITY, "runtime_implementation_sha256": j.phase.implementation_identity(),
        "client": transport_module.client_identity(), "scientific_policy_sources": POLICY_SOURCES,
        "implementation_sources": {p: j.sha(j.read_bytes(ROOT / p)) for p in IMPLEMENTATION},
        "retry_policy": {"maximum_attempts": j.POLICY.maximum_attempts,
            "timeout_seconds": j.POLICY.timeout_seconds, "backoff_seconds": list(j.POLICY.backoff_seconds)},
        "live_execution_not_proven_by_offline_acceptance": True}


def reference(path):
    raw = j.read_bytes(Path(path))
    return {"artifact_path": str(Path(path).absolute()), "sha256": j.sha(raw), "byte_count": len(raw)}


def freeze_same(path, value):
    raw = j.canonical(value)
    if Path(path).exists():
        j.require(j.read_bytes(Path(path)) == raw, "IMMUTABLE_COMPANION_CONFLICT:" + Path(path).name)
        return reference(path)
    return dict(j.atomic_freeze(Path(path), raw).__dict__)


def source_record(ref):
    source = j.strict_json(j.verify_artifact(ref))
    j.require(type(source) is dict and type(source.get("source_id")) is str and source["source_id"] and
              re.fullmatch(r"[1-9][0-9]*", source.get("pmid", "")) and
              re.fullmatch(r"PMC[1-9][0-9]*", source.get("pmcid", "")) and
              "doi" in source and isinstance(source.get("publication_types"), list) and
              isinstance(source.get("correction_relationships"), list), "FROZEN_SOURCE_IDENTITY_REQUIRED")
    j.require(o.SecretRedactorV1().tree(source)[0] == source, "SECRET_BEARING_SOURCE_FORBIDDEN")
    before = correction.classify(source["publication_types"], source["correction_relationships"])
    deferred = before["unresolved_reasons"] == ["REF_TYPE:UpdateOf:INDEPENDENT_SOURCE_NOT_YET_ELIGIBLE"] and not before["ineligible_reasons"]
    j.require((source.get("pre_oa_handoff_state") == "PRE_OA_CLEAR" and before["state"] == "CORRECTION_REFERENCE_CLEAR") or
              (source.get("pre_oa_handoff_state") == "PRE_OA_CONDITIONAL_UPDATEOF" and deferred),
              "FROZEN_PRE_OA_SOURCE_REQUIRED")
    return source


def request_payload(ref, stage, parent=None):
    source = source_record(ref)
    parameters = ({"db": "pmc", "retmode": "json", "retmax": "1",
                   "term": source_policy.oa_subset_esearch_term(source["pmcid"])} if stage == "OA" else
                  {"db": "pmc", "id": source["pmcid"][3:], "retmode": "xml"})
    payload = {"source_reference": ref, "source_id": source["source_id"], "pmid": source["pmid"],
        "pmcid": source["pmcid"], "method": "GET", "endpoint": legacy.ES if stage == "OA" else legacy.EF,
        "parameters": parameters, "scientific_policy_sha256": j.sha(j.canonical(POLICY_SOURCES)),
        "captured_representation": transport_module.REPRESENTATION,
        "length_evidence_contract": j.lengths.length_contract(t.ByteRepresentation.DECODED)}
    if stage == "JATS":
        payload["oa_request_id"] = parent
    return payload


def build_manifest(source_references, *, run_id, run_epoch="epoch-1", replay_safe=False):
    """Freeze supplied source identities; never discover, replace or resample."""
    verify_baselines()
    sources = [source_record(ref) for ref in source_references]
    j.require(sources and len({s["source_id"] for s in sources}) == len(sources) and
              len({s["pmid"] for s in sources}) == len(sources) and
              len({s["pmcid"] for s in sources}) == len(sources), "DUPLICATE_OR_EMPTY_SOURCE_UNIVERSE")
    requests = []
    for stage in ("OA", "JATS"):
        for ref, source in zip(source_references, sources):
            payload = request_payload(ref, stage, source["source_id"] + ":OA")
            requests.append({"request_id": source["source_id"] + ":" + stage, "request_payload": payload,
                "request_payload_sha256": j.sha(j.canonical(payload)), "stage": stage,
                "execution_order": len(requests), "replay_safe": replay_safe,
                "maximum_attempts": j.POLICY.maximum_attempts,
                "validity_authority_sha256": validity.contract_sha("literal_boolean" if stage == "OA" else "jats_primary_identity_v2"),
                "eligibility_authority_sha256": j.sha(j.canonical(POLICY_SOURCES))})
    return j.FrozenRequestManifestV2(j.canonical({"schema_version": "FrozenRequestManifestV2",
        "run_id": run_id, "run_epoch": run_epoch, "stage_id": "prospective:OA-JATS", "authority": j.AUTHORITY,
        "runtime_v2_implementation_manifest_sha256": j.phase.implementation_identity(),
        "activation_contract_sha256": ACTIVATION_SHA, "requests": requests}))


def validate_manifest(manifest):
    verify_baselines()
    transport_module.client_identity()
    j.require(type(manifest) is j.FrozenRequestManifestV2 and
              manifest.record()["activation_contract_sha256"] == ACTIVATION_SHA, "PROSPECTIVE_MANIFEST_REQUIRED")
    seen = {}
    for request in manifest.record()["requests"]:
        payload, stage = request["request_payload"], request["stage"]
        source = source_record(payload["source_reference"])
        expected = request_payload(payload["source_reference"], stage, source["source_id"] + ":OA")
        j.require(payload == expected and request["request_id"] == source["source_id"] + ":" + stage and
                  request["validity_authority_sha256"] == validity.contract_sha("literal_boolean" if stage == "OA" else "jats_primary_identity_v2") and
                  request["eligibility_authority_sha256"] == j.sha(j.canonical(POLICY_SOURCES)), "UNSUPPORTED_REQUEST_BINDING")
        if stage == "OA":
            j.require(source["source_id"] not in seen and source["pmid"] not in [v["pmid"] for v in seen.values()] and
                      source["pmcid"] not in [v["pmcid"] for v in seen.values()], "DUPLICATE_SOURCE_UNIVERSE")
            seen[source["source_id"]] = source
        else:
            j.require(seen.get(source["source_id"]) == source, "OA_JATS_SOURCE_BINDING")
    j.require(len(manifest.record()["requests"]) == 2 * len(seen), "EXACT_OA_JATS_UNIVERSE_REQUIRED")


def evaluate(request, raw):
    """Only frozen validators; no model/content-based source selection."""
    source = source_record(request["request_payload"]["source_reference"])
    if request["stage"] == "OA":
        state, _ = legacy.oa_subset_state(raw, [{"http_status": 200}], source["pmcid"])
        actual = backend_policy.validate_response(200, raw, 0, 1)
        if actual["state"] not in backend_policy.VALID_STATES:
            state = "OA_SUBSET_UNRESOLVED"
        return {"kind": "literal_boolean", "validator_result": state in {"OA_SUBSET_ELIGIBLE", "OA_SUBSET_INELIGIBLE"},
            "oa_state": state, "oa_validator_result": actual, "eligible": state == "OA_SUBSET_ELIGIBLE"}, {}
    actual = identity_policy.validate_jats_primary_identity_v2(raw, expected_pmid=source["pmid"],
        expected_pmcid=source["pmcid"], expected_doi=source["doi"])
    result = {"kind": "jats_primary_identity_v2", "validator_result": actual, "eligible": False,
              "license": None, "source_type": None, "UpdateOf": None, "body_state": None}
    outputs = {}
    if actual["source_identity_allows_progression"]:
        normalized = ET.tostring(identity_policy.select_primary_article(raw), encoding="utf-8")
        outputs["normalized_jats"] = normalized
        result["license"] = license_policy.construction_oa_v2(source["pmcid"], True, normalized)
        if result["license"]["state"] == "CONSTRUCTION_OA_ELIGIBLE":
            try:
                body = body_policy.canonical_body(normalized)
            except ValueError as exc:
                j.require(str(exc) in {"JATS body missing", "construction body empty"}, "UNEXPECTED_BODY_VALIDATOR_FAILURE")
                result["body_state"] = "CANONICAL_BODY_UNUSABLE"
            else:
                outputs["canonical_body"] = body["body_text"].encode("utf-8")
                result["body_state"] = "CANONICAL_BODY_USABLE"
                result["source_type"] = source_policy.source_type_state(source["publication_types"], normalized)
                result["UpdateOf"] = correction.classify(source["publication_types"], source["correction_relationships"],
                    independent_primary_state=result["source_type"]["state"])
                result["eligible"] = (result["source_type"]["state"] == "SOURCE_TYPE_ELIGIBLE" and
                                      result["UpdateOf"]["state"] == "CORRECTION_REFERENCE_CLEAR")
    return result, outputs


def _commit_failure(writer, item, replay):
    lifecycle, decision = item.lifecycle, item.failure.decision
    observation = b.mapped_observation_v2(decision, lifecycle, writer.redactor, original_exception=item.exception,
        http=item.http, body=item.body, runtime_identity=item.failure.runtime_identity.record(), replay_safety_authority=replay)
    binding = j.phase.bind_failure(writer, lifecycle, item.failure, observation,
                                   item.response.artifact if item.response is not None else None)
    return writer.commit_terminal(lifecycle, decision, observation,
        artifact=item.response.artifact if item.response is not None else None,
        failure_phase_binding=binding, timestamp=utc())


def commit_capture(writer, item):
    lifecycle = item.lifecycle
    request = writer.manifest.request(lifecycle.context.logical_request_id)
    replay = {"manifest_sha256": writer.manifest.sha256, "request_id": request["request_id"]} if request["replay_safe"] else None
    if item.failure is not None:
        return _commit_failure(writer, item, replay)
    result, outputs = t.guarded_parse(item.response, lambda raw: evaluate(request, raw))
    start = j.strict_json(j.verify_artifact(item.reference))["start_entry_hash"]
    output_refs = {name: dict(j.atomic_freeze(writer.directory / (name + "-" + start + ".bin"), raw).__dict__)
                   for name, raw in outputs.items()}
    gate = {"context": lifecycle.context.record(), "source_reference": request["request_payload"]["source_reference"],
        "raw_artifact": dict(item.response.artifact.__dict__), "policy_sources": POLICY_SOURCES,
        "actual": result, "outputs": output_refs}
    freeze_same(writer.directory / ("gates-" + start + ".json"), gate)
    if request["stage"] == "OA" and result["oa_validator_result"]["state"] == "NCBI_ESearch_BACKEND_ERROR":
        backend = b.BackendValidatorOutcomeV2.from_frozen_validator_result(result["oa_validator_result"],
            authority_sha256=t.BACKEND_AUTHORITY_SHA256, validator_source_sha256=b.BACKEND_VALIDATOR_SOURCE_SHA256)
        facts = b.TransportMappingFactsV2(lifecycle.state, b.BOUND_CLIENT_IDENTITY_SHA256, headers_trusted=True,
            http_status=200, http_status_origin="BOUND_HTTP_RESPONSE", body_completion=lifecycle.completion, backend_outcome=backend)
        item.failure = j.phase.capture_failure(writer, lifecycle, None, facts)
        item.body = o.BodyReadProvenanceV1.capture(lifecycle.context, writer.redactor, lifecycle.completion,
            item.response.artifact, started_at=item.body.record()["body_read_started_at"], parser_invoked=True)
        return _commit_failure(writer, item, replay)
    outcome = validity.record_result(writer, lifecycle, result["validator_result"], kind=result["kind"], timestamp=utc(), response=item.response)
    decision = validity.decision_for_outcome(lifecycle, outcome, request)
    body = o.BodyReadProvenanceV1.capture(lifecycle.context, writer.redactor, lifecycle.completion,
        item.response.artifact, started_at=item.body.record()["body_read_started_at"], parser_invoked=True)
    observation = b.mapped_observation_v2(decision, lifecycle, writer.redactor, http=item.http, body=body, replay_safety_authority=replay)
    eligibility = {"authority_sha256": request["eligibility_authority_sha256"], "eligible": result["eligible"]} if outcome.record()["accepted"] else None
    return writer.commit_validator_outcome(lifecycle, outcome, observation, eligibility=eligibility, timestamp=utc())


def archive_records(verified):
    records = []
    for event in verified.events:
        terminal = event.record()
        if terminal["event_type"] != "ATTEMPT_TERMINAL":
            continue
        request = verified.manifest.request(terminal["logical_request_id"])
        starts = [e.record() for e in verified.events if e.record()["event_type"] == "ATTEMPT_STARTED" and
                  e.record()["logical_request_id"] == terminal["logical_request_id"] and
                  e.record()["attempt_ordinal"] == terminal["attempt_ordinal"]]
        start = starts[0]["entry_hash"]
        ref = reference(Path(verified.directory) / ("capture-" + start + ".json"))
        capture = j.strict_json(j.verify_artifact(ref))
        payload = terminal["event_payload"]
        observed = payload["mapped_observation"]["observation"]
        j.require(capture["manifest_sha256"] == verified.manifest.sha256 and capture["start_entry_hash"] == start and
                  capture["context"] == t.AttemptContextV1(request["request_id"], request["request_payload_sha256"], terminal["attempt_ordinal"]).record() and
                  capture["representation"] == transport_module.REPRESENTATION and
                  capture["actual_client_identity"] == transport_module.client_identity() and
                  capture["http"] == observed["http_response_provenance"] and
                  capture["raw_artifact"] == payload["raw_artifact"], "CAPTURE_TERMINAL_BINDING")
        if capture["http_reference"] is not None:
            j.require(j.strict_json(j.verify_artifact(capture["http_reference"])) == capture["http"], "HTTP_CAPTURE_CONFLICT")
        if capture["body"] is not None:
            expected_body = {**observed["body_read_provenance"], "parser_invoked": False}
            j.require(capture["body"] == expected_body and capture["captured_bytes"] == payload["raw_artifact"]["byte_count"],
                      "BODY_CAPTURE_CONFLICT")
        gate_ref = None
        gate_path = Path(verified.directory) / ("gates-" + start + ".json")
        if "validator_outcome" in payload or gate_path.exists():
            gate_ref = reference(Path(verified.directory) / ("gates-" + start + ".json"))
            gate = j.strict_json(j.verify_artifact(gate_ref))
            actual, outputs = evaluate(request, j.verify_artifact(payload["raw_artifact"]))
            j.require(gate["context"] == capture["context"] and gate["source_reference"] == request["request_payload"]["source_reference"] and
                      gate["raw_artifact"] == payload["raw_artifact"] and gate["policy_sources"] == POLICY_SOURCES and gate["actual"] == actual and
                      set(gate["outputs"]) == set(outputs), "GATE_CAPTURE_CONFLICT")
            for name, raw in outputs.items():
                j.require(j.verify_artifact(gate["outputs"][name]) == raw, "DOWNSTREAM_ARTIFACT_CONFLICT")
            if "validator_outcome" in payload:
                saved = j.strict_json(j.verify_artifact(payload["validator_outcome"]))
                j.require(saved["actual_validator_result"] == actual["validator_result"] and
                          (payload["eligibility"] is None or payload["eligibility"]["eligible"] is actual["eligible"]), "GATE_TERMINAL_CONFLICT")
            else:
                j.require(request["stage"] == "OA" and actual["oa_validator_result"]["state"] == "NCBI_ESearch_BACKEND_ERROR" and
                          payload["mapped_observation"]["mapping"]["semantic_failure_class"] == "RETRYABLE_PROVIDER_BACKEND_FAILURE",
                          "BACKEND_OUTCOME_BINDING")
        records.append({"request_id": request["request_id"], "source_id": request["request_payload"]["source_id"],
            "attempt_ordinal": terminal["attempt_ordinal"], "terminal": j.phase.event_ref(terminal),
            "capture": ref, "gates": gate_ref})
    return records


def _handoff_value(writer):
    verified = writer.verified()
    plan = planner.DeterministicResumePlannerV2().build(verified).record()
    states, barrier, activation = j._reduce(verified.events, writer.manifest, writer.directory)
    j.require(plan["stage_complete"] and barrier is not None and activation is not None, "HANDOFF_REQUIRES_COMPLETED_OA_JATS_GATES")
    records = archive_records(verified)
    sources = []
    for request in writer.manifest.record()["requests"]:
        if request["stage"] != "JATS" or states[request["request_id"]]["outcome"] != "VALID_SUCCESS":
            continue
        record = next(r for r in reversed(records) if r["request_id"] == request["request_id"])
        j.require(request["request_id"] in activation.record()["activated_request_ids"] and
                  states[request["request_payload"]["oa_request_id"]]["outcome"] == "VALID_SUCCESS" and record["gates"] is not None,
                  "HANDOFF_ACTIVATION_REQUIRED")
        gate = j.strict_json(j.verify_artifact(record["gates"]))
        actual = gate["actual"]
        j.require(actual["eligible"] is True and actual["validator_result"]["source_identity_allows_progression"] is True and
                  actual["license"]["state"] == "CONSTRUCTION_OA_ELIGIBLE" and actual["body_state"] == "CANONICAL_BODY_USABLE" and
                  actual["source_type"]["state"] == "SOURCE_TYPE_ELIGIBLE" and actual["UpdateOf"]["state"] == "CORRECTION_REFERENCE_CLEAR",
                  "HANDOFF_ELIGIBILITY_REQUIRED")
        sources.append({**record, "source_reference": request["request_payload"]["source_reference"],
                        "raw_artifact": gate["raw_artifact"], "outputs": gate["outputs"]})
    j.require(sources, "HANDOFF_NO_ELIGIBLE_SOURCES")
    return {"schema_version": "ProspectiveAuthoritativeHandoffV1",
        "manifest_sha256": writer.manifest.sha256, "configuration": reference(writer.directory / "configuration.json"),
        "journal_tip_sha256": verified.last_hash, "barrier": reference(writer.directory / "stage_barrier.json"),
        "activation": reference(writer.directory / "activation_manifest.json"), "sources": sources,
        "scientific_result": False, "historical_evidence": False}


def freeze_handoff(writer):
    """Derivable immutable companion; no invented journal event or bypass."""
    return freeze_same(writer.directory / "handoff.json", _handoff_value(writer))


def _has_handoff(writer, plan, records):
    return plan["stage_complete"] and any(r["gates"] is not None and
        writer.manifest.request(r["request_id"])["stage"] == "JATS" and
        j.strict_json(j.verify_artifact(r["gates"]))["actual"]["eligible"] for r in records)


def _index_value(writer, plan, records, handoff):
    return {"schema_version": "ProspectiveEvidenceIndexV1", "manifest": reference(writer.directory / "request_manifest.json"),
        "configuration": reference(writer.directory / "configuration.json"), "journal": reference(writer.directory / "segment-0001.jsonl"),
        "journal_tip_sha256": plan["journal_tip_sha256"], "journal_integrity": "VERIFIED",
        "recovery": reference(writer.directory / ("recovery-" + plan["journal_tip_sha256"] + ".json")),
        "attempts": records, "barrier": reference(writer.directory / "stage_barrier.json") if plan["barrier_sha256"] else None,
        "activation": reference(writer.directory / "activation_manifest.json") if plan["activation_sha256"] else None,
        "handoff": handoff, "historical_22e_evidence": False}


def finalize(writer):
    verified = writer.verified()
    plan = planner.DeterministicResumePlannerV2().build(verified).record()
    records = archive_records(verified)
    handoff = None
    if _has_handoff(writer, plan, records):
        handoff = freeze_handoff(writer)
    else:
        j.require(not (writer.directory / "handoff.json").exists(), "UNAUTHORIZED_HANDOFF_PRESENT")
    freeze_same(writer.directory / ("recovery-" + verified.last_hash + ".json"), plan)
    index = _index_value(writer, plan, records, handoff)
    freeze_same(writer.directory / "evidence_index.json", index)
    return index


def inspect(directory):
    directory = j.physical(Path(directory))
    manifest = j.FrozenRequestManifestV2(j.read_bytes(directory / "request_manifest.json"))
    validate_manifest(manifest)
    j.require(j.read_bytes(directory / "configuration.json") == j.canonical(configuration(manifest)), "FROZEN_CONFIGURATION_DRIFT")
    verified = j.JournalIntegrityVerifierV2.read(directory, manifest)
    return planner.DeterministicResumePlannerV2().build(verified).record()


def read_archive(directory):
    plan = inspect(directory)
    directory = j.physical(Path(directory))
    manifest = j.FrozenRequestManifestV2(j.read_bytes(directory / "request_manifest.json"))
    with j.AppendOnlyAttemptJournalV2(directory, manifest) as writer:
        # Strict readback: every companion must ALREADY exist; no creation.
        before = {str(p): j.sha(j.read_bytes(p)) for p in directory.rglob("*") if p.is_file()}
        j.require((directory / "evidence_index.json").exists(), "EVIDENCE_INDEX_MISSING")
        index = j.strict_json(j.read_bytes(directory / "evidence_index.json"))
        for key in ("manifest", "configuration", "journal", "recovery", "barrier", "activation", "handoff"):
            if index[key] is not None:
                j.verify_artifact(index[key])
        records = archive_records(writer.verified())
        handoff = None
        if _has_handoff(writer, plan, records):
            j.require(j.read_bytes(directory / "handoff.json") == j.canonical(_handoff_value(writer)), "HANDOFF_INDEX_CONFLICT")
            handoff = reference(directory / "handoff.json")
        else:
            j.require(not (directory / "handoff.json").exists(), "UNAUTHORIZED_HANDOFF_PRESENT")
        j.require(index == _index_value(writer, plan, records, handoff) and
                  j.strict_json(j.verify_artifact(index["recovery"])) == plan, "EVIDENCE_INDEX_BINDING")
        after = {str(p): j.sha(j.read_bytes(p)) for p in directory.rglob("*") if p.is_file()}
        j.require(before == after, "READBACK_MUTATION_FORBIDDEN")
    return index


def run(directory, manifest, *, transport=None, authorize_live_network=False,
        credential_parameters=None, sleep=time.sleep, create=True):
    validate_manifest(manifest)  # Includes actual client compatibility before start/dispatch.
    if transport is None:
        transport = transport_module.UrllibTransport(authorize_live_network=authorize_live_network)
    j.require(getattr(transport, "offline", False) is True or authorize_live_network is True, "LIVE_NETWORK_NOT_AUTHORIZED")
    credentials = credential_parameters or {}
    redactor = o.SecretRedactorV1(tuple(credentials.values()))
    with j.AppendOnlyAttemptJournalV2(Path(directory), manifest, create=create, redactor=redactor) as writer:
        freeze_same(writer.directory / "configuration.json", configuration(manifest))
        writer.classify_abandoned(timestamp=utc())
        while True:
            plan = planner.DeterministicResumePlannerV2().build(writer.verified()).record()
            if plan["blocking_reason"] in {"AWAITING_FROZEN_OA_BARRIER", "AWAITING_FROZEN_ACTIVATION"}:
                barriers.StageBarrierSnapshotV2.freeze(writer, timestamp=utc())
                barriers.FrozenActivationManifestV2.freeze(writer, timestamp=utc())
                continue
            key = plan["next_executable_request_id"]
            if key is None:
                return finalize(writer)
            request_plan = next(r for r in plan["requests"] if r["request_id"] == key)
            if request_plan["backoff_seconds"]:
                sleep(request_plan["backoff_seconds"])
            token = writer.start_attempt(key, timestamp=utc())
            item = transport_module.capture_once(writer, token, transport, credential_parameters=credentials)
            commit_capture(writer, item)


def resume(directory, **kwargs):
    inspect(directory)  # Reject drift/corruption before writer, recovery or dispatch.
    manifest = j.FrozenRequestManifestV2(j.read_bytes(Path(directory) / "request_manifest.json"))
    return run(directory, manifest, create=False, **kwargs)
