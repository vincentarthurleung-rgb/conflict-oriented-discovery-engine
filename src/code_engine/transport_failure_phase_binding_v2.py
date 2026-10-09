"""R0-bound failure occurrence/trace evidence. No network or retry policy.

Controller capture uses actual exception objects and the current durable prefix.
Terminal verification uses original mapping snapshots, not a later remapping.
Local hashes prove binding/integrity, not resistance to an attacker rewriting
every trusted file. The trust boundary is the source-bound cooperative writer.
"""

from __future__ import annotations

import dataclasses
from enum import Enum
from pathlib import Path

from . import append_only_attempt_journal_v1 as u

t, o, b = u.t, u.o, u.b
require, canonical, sha = u.require, u.canonical, u.sha
ROOT = Path(__file__).resolve().parents[2]
R0 = ROOT / "runs/20261008_search_plan_v24_dev_alpha3_22r0_cross_component_phase_binding_repair_design_offline"
R1 = ROOT / "runs/20261009_search_plan_v24_dev_alpha3_22r1_versioned_phase_binding_repair_offline"
DESIGN_SHA = "e2ae251bbcc1d72f59afde0c2d8879cc333402967656e31aa606836c42fe118c"
SCHEMA_SHA = "dfc493a3f86779b3520c102c7da8c7d96f263eec88a9ab2a13c43a4af107efa7"
RUNTIME_ACTIVATION_ALLOWED = False


def implementation_identity():
    path = R1 / "runtime_v2_implementation_manifest.json"
    raw = u.read_bytes(path)
    record = u.strict_json(raw)
    require(canonical(record) == raw and record["schema_version"] == "RuntimeV2ImplementationManifestR1"
            and record["r0_proposal_sha256"] == DESIGN_SHA, "RUNTIME_IMPLEMENTATION_BINDING")
    for source in record["source_files"]:
        require(sha(u.read_bytes(ROOT / source["artifact_path"])) == source["sha256"], "RUNTIME_SOURCE_BINDING")
    return sha(raw)


def binding_authority(manifest):
    return {"master_sha256": t.MASTER_ROOT_SHA256, "alpha322a_sha256": b.ALPHA322A_ROOT_SHA256,
        "alpha322b_sha256": u.AUTHORITY["alpha322b_sha256"],
        "historical_alpha322c_sha256": "54e59aae85b1ea0598e29c80288cef3025301261d709b9ab888a224d686d3ad7",
        "mapping_table_sha256": b.MAPPING_TABLE_SHA256, "semantic_retry_contract_sha256": b.SEMANTIC_RETRY_CONTRACT_SHA256,
        "retry_orchestration_contract_sha256": u.AUTHORITY["retry_orchestration_contract_sha256"],
        "phase_binding_design_sha256": DESIGN_SHA,
        "runtime_v2_implementation_manifest_sha256": manifest.record()["runtime_v2_implementation_manifest_sha256"]}


def schema(structured=False):
    raw = u.read_bytes(R0 / "transport_failure_phase_binding_v2_schema.json")
    require(sha(raw) == SCHEMA_SHA, "FROZEN_R0_SCHEMA_DRIFT")
    result = u.strict_json(raw)
    if structured:
        # Explicit separate route, never broaden the frozen concrete schema.
        result["$id"] = "urn:alpha322r1:StructuredFailurePhaseBindingV2"
        result["properties"]["schema_version"]["const"] = "StructuredFailurePhaseBindingV2"
        result["properties"]["binding_scope"]["const"] = "STRUCTURED_FAILURE_EVIDENCE"
        result["properties"]["occurrence_evidence"]["properties"]["capture_schema_version"]["const"] = "StructuredFailureOccurrenceEvidenceV2"
    return result


def validate_schema(value, rule, path="$"):
    """Strict local implementation of exactly the frozen schema vocabulary."""
    supported = {"$schema", "$id", "$comment", "type", "const", "enum", "properties", "required",
        "additionalProperties", "items", "minimum", "maximum", "pattern", "minLength", "minItems", "anyOf"}
    require(not set(rule) - supported, "UNSUPPORTED_R0_SCHEMA_KEYWORD:" + path)
    if "anyOf" in rule:
        valid = False
        for branch in rule["anyOf"]:
            try:
                validate_schema(value, branch, path)
                valid = True
                break
            except t.TransportContractError:
                pass
        require(valid, "SCHEMA_ANYOF:" + path)
    flat = {k: v for k, v in rule.items() if k not in {"$comment", "anyOf", "minLength", "minItems", "properties", "items"}}
    # Validate primitives using unchanged A utility; recurse here for V2 keywords.
    if type(value) is dict:
        flat["additionalProperties"] = True
        flat.pop("required", None)
    o.validate_schema(value, flat, path)
    if type(value) is str:
        require(len(value) >= rule.get("minLength", 0), "SCHEMA_MINLENGTH:" + path)
    if type(value) is dict:
        props = rule.get("properties", {})
        require(set(rule.get("required", [])) <= set(value), "SCHEMA_REQUIRED:" + path)
        require(rule.get("additionalProperties", True) is not False or set(value) <= set(props), "SCHEMA_EXTRA:" + path)
        for key, child in value.items():
            validate_schema(child, props.get(key, {}), path + "." + key)
    if type(value) is list:
        require(len(value) >= rule.get("minItems", 0), "SCHEMA_MINITEMS:" + path)
        if "items" in rule:
            for index, child in enumerate(value):
                validate_schema(child, rule["items"], path + f"[{index}]")


def primitive(value):
    if isinstance(value, Enum):
        return value.value
    if dataclasses.is_dataclass(value):
        return {field.name: primitive(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if type(value) in {tuple, list}:
        return [primitive(item) for item in value]
    if type(value) is dict:
        return {key: primitive(item) for key, item in value.items()}
    return value


def restore_structured_facts(saved):
    completion = saved["body_completion"]
    if completion is not None:
        completion = dict(completion)
        completion["body_completion_state"] = t.BodyState(completion["body_completion_state"])
        completion["semantic_failure"] = t.SemanticFailure(completion["semantic_failure"])
        completion["byte_representation"] = t.ByteRepresentation(completion["byte_representation"])
        if completion["expected_length_representation"] is not None:
            completion["expected_length_representation"] = t.ByteRepresentation(completion["expected_length_representation"])
        completion["framing_integrity_evidence"] = tuple(t.FramingEvidenceV1(**{**item, "failure_class": t.SemanticFailure(item["failure_class"])}) for item in completion["framing_integrity_evidence"])
        completion = t.BodyCompletionResultV2(**completion)
    backend = b.BackendValidatorOutcomeV2(**saved["backend_outcome"]) if saved["backend_outcome"] else None
    return b.TransportMappingFactsV2(t.LifecycleState(saved["phase"]), saved["client_identity_sha256"],
        headers_trusted=saved["headers_trusted"], http_status=saved["http_status"], http_status_origin=saved["http_status_origin"],
        body_completion=completion, backend_outcome=backend)


def event_ref(record):
    return {"journal_sequence_number": record["sequence_number"], "journal_entry_hash": record["entry_hash"]}


def attempt_records(prefix, identity):
    return [record for record in prefix if record["logical_request_id"] == identity["logical_request_id"]
            and record["attempt_ordinal"] == identity["attempt_ordinal"]]


def attempt_identity(manifest, context, prefix):
    starts = [record for record in prefix if record["event_type"] == "ATTEMPT_STARTED"
              and record["logical_request_id"] == context.logical_request_id and record["attempt_ordinal"] == context.attempt_ordinal]
    require(len(starts) == 1, "UNBOUND_OCCURRENCE_EVIDENCE")
    return {**{key: manifest.record()[key] for key in ("run_id", "run_epoch", "stage_id")},
        "logical_request_id": context.logical_request_id, "request_payload_sha256": context.request_payload_sha256,
        "attempt_ordinal": context.attempt_ordinal, "manifest_sha256": manifest.sha256,
        "attempt_start_entry_hash": starts[0]["entry_hash"]}


def check_identity(saved, expected):
    groups = [("RUN_IDENTITY_MISMATCH", ("run_id", "run_epoch")),
        ("STAGE_OR_PAYLOAD_IDENTITY_MISMATCH", ("stage_id", "request_payload_sha256", "manifest_sha256")),
        ("REQUEST_IDENTITY_MISMATCH", ("logical_request_id",)),
        ("ATTEMPT_IDENTITY_MISMATCH", ("attempt_ordinal", "attempt_start_entry_hash"))]
    for reason, keys in groups:
        require(type(saved) is dict and all(saved.get(key) == expected[key] and type(saved.get(key)) is type(expected[key]) for key in keys), reason)
    require(set(saved) == set(expected), "ATTEMPT_IDENTITY_FIELDS")


def read_evidence(reference, directory, reason="IMMUTABLE_EVIDENCE_HASH_MISMATCH"):
    try:
        u.exact_keys(reference, ("artifact_path", "sha256", "byte_count"), reason)
        path = u.physical(Path(reference["artifact_path"]))
        require(path.is_relative_to(u.physical(directory)), "UNBOUND_OCCURRENCE_EVIDENCE")
        raw = u.read_bytes(path)
        require(len(raw) == reference["byte_count"] and sha(raw) == reference["sha256"], reason)
        record = u.strict_json(raw)
        require(canonical(record) == raw, reason)
        return record
    except (OSError, TypeError, KeyError) as exc:
        raise t.TransportContractError(reason) from exc


@dataclasses.dataclass(frozen=True)
class FailureOccurrenceCaptureV2:
    serialized: bytes
    decision: b.ClassifiedRetryDecisionV2

    def record(self):
        return u.strict_json(self.serialized)


@dataclasses.dataclass(frozen=True)
class TransportFailurePhaseBindingV2:
    serialized: bytes

    def record(self):
        return u.strict_json(self.serialized)


def capture_failure(writer, lifecycle, exception, facts):
    """Controller entrypoint called at actual failure, BEFORE state progression.

    The actual exception goes to unchanged B. Capture is physically immutable,
    anchored to the last committed lifecycle event. No second retry function.
    """
    require(type(lifecycle) is t.TransportLifecycleV2 and type(facts) is b.TransportMappingFactsV2, "TYPED_CAPTURE_REQUIRED")
    writer.record_lifecycle(lifecycle, timestamp="synthetic:occurrence-capture")
    prefix = [event.record() for event in writer.verified().events]
    identity = attempt_identity(writer.manifest, lifecycle.context, prefix)
    current = attempt_records(prefix, identity)[-1]
    require(current["event_type"] == "LIFECYCLE_PROGRESS"
            and current["event_payload"]["lifecycle_event"]["state"] == lifecycle.state.value
            and facts.phase == lifecycle.state, "OCCURRENCE_MAPPING_PHASE_MISMATCH")
    require(facts.client_identity_sha256 == b.BOUND_CLIENT_IDENTITY_SHA256, "MAPPING_FACTS_AUTHORITY_MISMATCH")
    decision = b.classify_transport_failure_and_decide_retry_v2(exception, facts,
        request_replay_safe=writer.manifest.request(lifecycle.context.logical_request_id)["replay_safe"], attempt_ordinal=lifecycle.context.attempt_ordinal)
    require(decision.mapping.semantic_failure_class != t.SemanticFailure.NO_TECHNICAL_FAILURE, "FAILURE_CAPTURE_REQUIRES_FAILURE")
    directory = writer.directory / ("evidence-" + identity["attempt_start_entry_hash"])
    directory.mkdir()
    u.sync_directory(directory.parent)
    def freeze(name, value):
        return dict(u.atomic_freeze(directory / name, canonical(value)).__dict__)
    runtime = {"client_module": "urllib.request/http.client.HTTPResponse", "client_code_sha256": b.BOUND_CLIENT_IDENTITY_SHA256, "client_version": None}
    if exception is not None:
        captured = o.ExceptionProvenanceV1.capture(exception, lifecycle.context, writer.redactor, runtime_identity=runtime)
        if captured.provenance is None:
            captured.reraise_original()
        signal = captured.provenance.record()
    else:
        signal = {"schema_version": "StructuredFailureSignalV2", "attempt_identity": identity,
                  "structured_facts": primitive(facts)}
    signal_ref = freeze("signal.json", signal)
    facts_ref = freeze("facts.json", {"attempt_identity": identity, "facts": primitive(facts)})
    decision_ref = freeze("decision.json", {"attempt_identity": identity, "decision": decision.record()})
    mapping_ref = freeze("mapping.json", {"attempt_identity": identity, "mapping": decision.mapping.record()})
    occurrence = {"schema_version": "FailureOccurrenceEvidenceV2" if exception is not None else "StructuredFailureOccurrenceEvidenceV2",
        "attempt_identity": identity, "failure_occurrence_phase": lifecycle.state.value, "phase_anchor": event_ref(current),
        "bound_client_identity_sha256": b.BOUND_CLIENT_IDENTITY_SHA256,
        "capture_implementation_manifest_sha256": implementation_identity(), "capture_source_sha256": sha(u.read_bytes(Path(__file__))),
        "signal": signal_ref, "mapping_input_facts": facts_ref, "mapped_decision_snapshot": decision_ref, "mapping_snapshot": mapping_ref}
    occurrence_ref = freeze("occurrence.json", occurrence)
    return FailureOccurrenceCaptureV2(canonical({"occurrence": occurrence_ref, "attempt_identity": identity}), decision)


def bind_failure(writer, lifecycle, capture, observation, artifact=None):
    require(type(capture) is FailureOccurrenceCaptureV2, "CONTROLLER_CAPTURE_REQUIRED")
    writer.record_lifecycle(lifecycle, timestamp="synthetic:terminal-binding")
    prefix = [event.record() for event in writer.verified().events]
    saved = capture.record()
    identity = attempt_identity(writer.manifest, lifecycle.context, prefix)
    check_identity(saved["attempt_identity"], identity)
    occurrence = read_evidence(saved["occurrence"], writer.directory)
    progress = [record for record in attempt_records(prefix, identity) if record["event_type"] == "LIFECYCLE_PROGRESS"]
    directory = Path(saved["occurrence"]["artifact_path"]).parent
    trace = {"schema_version": "LifecycleTraceEvidenceV2", "attempt_identity": identity, "committed_progress_events": progress}
    trace_ref = dict(u.atomic_freeze(directory / "trace.json", canonical(trace)).__dict__)
    mapped = observation.record()
    structured = occurrence["schema_version"] == "StructuredFailureOccurrenceEvidenceV2"
    completion = lifecycle.completion
    authoritative = bool(completion and completion.body_completion_state == t.BodyState.COMPLETE
                         and artifact and completion.body_sha256 == artifact.sha256
                         and completion.bytes_read == artifact.byte_count and mapped["observation"]["http_response_provenance"]["status"] == 200)
    record = {"schema_version": "StructuredFailurePhaseBindingV2" if structured else "TransportFailurePhaseBindingV2",
        "binding_scope": "STRUCTURED_FAILURE_EVIDENCE" if structured else "CONCRETE_EXCEPTION_OCCURRENCE",
        "attempt_identity": identity, "authority": binding_authority(writer.manifest), "failure_event_id": saved["occurrence"]["sha256"],
        "occurrence_evidence": {"artifact": saved["occurrence"], "capture_schema_version": occurrence["schema_version"],
            "failure_occurrence_phase": occurrence["failure_occurrence_phase"], "phase_anchor": occurrence["phase_anchor"],
            "exception_provenance_sha256": occurrence["signal"]["sha256"], "bound_client_identity_sha256": occurrence["bound_client_identity_sha256"],
            "mapping_input_facts_sha256": occurrence["mapping_input_facts"]["sha256"], "mapped_decision_snapshot_sha256": occurrence["mapped_decision_snapshot"]["sha256"]},
        "mapping_evidence": {"artifact": occurrence["mapping_snapshot"], "mapping_evidence_phase": mapped["mapping"]["phase"],
            "mapping_rule_id": mapped["mapping"]["mapping_rule_id"], "mapping_table_sha256": mapped["mapping"]["mapping_table_sha256"],
            "semantic_failure_class": mapped["mapping"]["semantic_failure_class"]},
        "lifecycle_trace": {"artifact": trace_ref, "lifecycle_trace_id": trace_ref["sha256"],
            "occurrence_anchor": occurrence["phase_anchor"], "persistence_anchor": event_ref(progress[-1]),
            "ordered_progress_event_refs": [event_ref(event) for event in progress]},
        "terminal_persistence_phase": lifecycle.state.value, "raw_artifact": dict(artifact.__dict__) if artifact else None,
        "raw_admission": {"raw_artifact_frozen": artifact is not None, "body_complete": bool(completion and completion.body_completion_state == t.BodyState.COMPLETE),
            "authoritative": authoritative, "parser_eligible": authoritative,
            "completion_provenance_sha256": sha(canonical(mapped["observation"]["body_read_provenance"])) if completion else None},
        "retry_decision_binding": {"classified_retry_decision_artifact": occurrence["mapped_decision_snapshot"],
            "retry_decision_sha256": sha(canonical(capture.decision.record()["retry"])), "semantic_retry_contract_sha256": b.SEMANTIC_RETRY_CONTRACT_SHA256}}
    validate_schema(record, schema(structured))
    u.atomic_freeze(directory / "binding.json", canonical(record))
    return TransportFailurePhaseBindingV2(canonical(record))


def validate_binding(record, mapped, retry, raw_artifact, context, request, manifest, prefix, directory):
    """Verify actual committed prefix, immutable snapshots and exact R0 schema."""
    require(type(record) is dict, "UNBOUND_OCCURRENCE_EVIDENCE")
    mapping = mapped["mapping"]
    require("phase" in mapping and record.get("mapping_evidence", {}).get("mapping_evidence_phase") is not None, "MISSING_MAPPING_PHASE")
    require(record.get("lifecycle_trace") and record["lifecycle_trace"].get("ordered_progress_event_refs"), "MISSING_LIFECYCLE_TRACE")
    identity = attempt_identity(manifest, context, prefix)
    check_identity(record.get("attempt_identity"), identity)
    require(record["occurrence_evidence"]["failure_occurrence_phase"] == record["mapping_evidence"]["mapping_evidence_phase"] == mapping["phase"], "OCCURRENCE_MAPPING_PHASE_MISMATCH")
    require(record["authority"] == binding_authority(manifest) and record["mapping_evidence"]["mapping_table_sha256"] == b.MAPPING_TABLE_SHA256
            and record["mapping_evidence"]["mapping_rule_id"] == mapping["mapping_rule_id"], "MAPPING_AUTHORITY_MISMATCH")
    # Retry is still A-owned; these denials are integrity checks, not new policy.
    require(not retry["retry_authorized"] or request["replay_safe"], "REPLAY_SAFETY_MISMATCH")
    require(not retry["retry_authorized"] or context.attempt_ordinal < 4, "EXHAUSTED_RETRY_BUDGET")
    policy = t.SemanticRetryPolicyV2(provider_backend_authority=t.BACKEND_AUTHORITY_SHA256 if mapping["mapping_rule_id"] == "frozen_esearch_backend_outcome" else None)
    expected = primitive(t.semantic_retry_decision(t.SemanticFailure(mapping["semantic_failure_class"]), request_replay_safe=request["replay_safe"], attempt_ordinal=context.attempt_ordinal, policy=policy))
    require(retry == expected, "RETRY_AUTHORITY_MISMATCH")
    structured = record["binding_scope"] == "STRUCTURED_FAILURE_EVIDENCE"
    validate_schema(record, schema(structured))
    occurrence_ref = record["occurrence_evidence"]["artifact"]
    expected_path = u.physical(directory) / ("evidence-" + identity["attempt_start_entry_hash"]) / "occurrence.json"
    require(Path(occurrence_ref["artifact_path"]) == expected_path and expected_path.is_file(), "UNBOUND_OCCURRENCE_EVIDENCE")
    occurrence = read_evidence(occurrence_ref, directory)
    check_identity(occurrence["attempt_identity"], identity)
    require(record["failure_event_id"] == occurrence_ref["sha256"] and occurrence["capture_implementation_manifest_sha256"] == implementation_identity()
            and occurrence["capture_source_sha256"] == sha(u.read_bytes(Path(__file__))), "UNBOUND_OCCURRENCE_EVIDENCE")
    signal = read_evidence(occurrence["signal"], directory)
    facts_record = read_evidence(occurrence["mapping_input_facts"], directory)
    decision_record = read_evidence(record["retry_decision_binding"]["classified_retry_decision_artifact"], directory)
    mapping_record = read_evidence(record["mapping_evidence"]["artifact"], directory)
    for saved in (facts_record, decision_record, mapping_record):
        check_identity(saved["attempt_identity"], identity)
    facts = facts_record["facts"]
    require(facts["client_identity_sha256"] == b.BOUND_CLIENT_IDENTITY_SHA256
            and (facts["phase"] != "RESPONSE_BODY_READING" or facts["headers_trusted"] is True), "MAPPING_FACTS_AUTHORITY_MISMATCH")
    require(facts["phase"] == occurrence["failure_occurrence_phase"] == mapping["phase"], "IMMUTABLE_EVIDENCE_HASH_MISMATCH")
    require(occurrence["mapping_snapshot"] == record["mapping_evidence"]["artifact"]
            and mapping_record["mapping"] == mapping and decision_record["decision"]["mapping"] == mapping
            and decision_record["decision"]["retry"] == retry, "IMMUTABLE_EVIDENCE_HASH_MISMATCH")
    ev = record["occurrence_evidence"]
    require(ev["capture_schema_version"] == occurrence["schema_version"]
            and ev["bound_client_identity_sha256"] == occurrence["bound_client_identity_sha256"] == b.BOUND_CLIENT_IDENTITY_SHA256
            and ev["phase_anchor"] == occurrence["phase_anchor"] and ev["failure_occurrence_phase"] == occurrence["failure_occurrence_phase"]
            and ev["exception_provenance_sha256"] == occurrence["signal"]["sha256"]
            and ev["mapping_input_facts_sha256"] == occurrence["mapping_input_facts"]["sha256"]
            and ev["mapped_decision_snapshot_sha256"] == occurrence["mapped_decision_snapshot"]["sha256"], "IMMUTABLE_EVIDENCE_HASH_MISMATCH")
    if not structured:
        require(signal == mapped["observation"]["exception_provenance"], "IMMUTABLE_EVIDENCE_HASH_MISMATCH")
        root = next(node for node in signal["exception_nodes"] if node["node_id"] == signal["root_exception_node_id"])
        rule = next((row for row in b.table_record()["rules"] if row["rule_id"] == mapping["mapping_rule_id"]), None)
        if rule is not None:
            require(mapping["phase"] in rule["allowed_lifecycle_phases"] and root["qualified_class_name"] == rule["exception_qualified_class"], "MAPPING_AUTHORITY_MISMATCH")
        else:
            require(mapping["mapping_rule_id"] is None and mapping["semantic_failure_class"] == "UNKNOWN_RUNTIME_FAILURE", "MAPPING_AUTHORITY_MISMATCH")
    else:
        require(signal["structured_facts"] == facts, "MAPPING_FACTS_AUTHORITY_MISMATCH")
        require(b.TransportExceptionMappingV2().classify(None, restore_structured_facts(facts)).record() == mapping,
                "MAPPING_FACTS_AUTHORITY_MISMATCH")
    trace_record = read_evidence(record["lifecycle_trace"]["artifact"], directory)
    check_identity(trace_record["attempt_identity"], identity)
    progress = [event for event in attempt_records(prefix, identity) if event["event_type"] == "LIFECYCLE_PROGRESS"]
    trace = record["lifecycle_trace"]
    claimed = trace_record["committed_progress_events"]
    previous = "REQUEST_NOT_STARTED"
    for item in claimed:
        edge = item["event_payload"]["lifecycle_event"]
        require(edge["previous_state"] == previous and (t.LifecycleState(previous), t.LifecycleState(edge["state"])) in t.ALLOWED_TRANSITIONS, "INVALID_LIFECYCLE_EDGE")
        previous = edge["state"]
    require(claimed == progress and trace["ordered_progress_event_refs"] == [event_ref(event) for event in progress]
            and trace["lifecycle_trace_id"] == trace["artifact"]["sha256"], "LIFECYCLE_TRACE_BINDING_MISMATCH")
    require(trace["occurrence_anchor"] == occurrence["phase_anchor"], "IMMUTABLE_EVIDENCE_HASH_MISMATCH")
    anchors = [event for event in progress if event_ref(event) == occurrence["phase_anchor"]]
    require(len(anchors) == 1 and anchors[0]["event_payload"]["lifecycle_event"]["state"] == mapping["phase"], "UNBOUND_OCCURRENCE_EVIDENCE")
    require(trace["persistence_anchor"] == event_ref(progress[-1])
            and record["terminal_persistence_phase"] == progress[-1]["event_payload"]["lifecycle_event"]["state"] == mapped["observation"]["lifecycle_state"], "PERSISTENCE_TRACE_MISMATCH")
    body = mapped["observation"]["body_read_provenance"]
    if mapping["semantic_failure_class"] in {"RESPONSE_BODY_TRANSPORT_INTERRUPTION", "RESPONSE_BODY_LENGTH_MISMATCH"}:
        suffix = [event["event_payload"]["lifecycle_event"]["state"] for event in progress[progress.index(anchors[0]):]]
        if not structured:
            require(suffix == ["RESPONSE_BODY_READING", "RESPONSE_BODY_INTERRUPTED", "RAW_RESPONSE_FROZEN"], "CONTRADICTORY_INTERRUPTION_TRACE")
            require(progress[progress.index(anchors[0]) + 1]["event_payload"]["lifecycle_event"]["evidence_reference"]
                    == occurrence_ref["sha256"], "UNBOUND_OCCURRENCE_EVIDENCE")
        require(body and body["completion_state"] == "BODY_INTERRUPTED", "PARTIAL_QUARANTINE_VIOLATION")
    admission = record["raw_admission"]
    partial = body is not None and body["completion_state"] != "BODY_COMPLETE"
    if partial:
        require(not any(item["event_payload"]["lifecycle_event"]["state"] in {"RESPONSE_BODY_COMPLETE", "RESPONSE_VALIDATION_COMPLETE"} for item in progress), "CONTRADICTORY_INTERRUPTION_TRACE")
    require(not partial or (admission["body_complete"] is False and admission["authoritative"] is False
            and admission["parser_eligible"] is False and body["parser_invoked"] is False), "PARTIAL_QUARANTINE_VIOLATION")
    require(record["raw_artifact"] == raw_artifact and admission["raw_artifact_frozen"] is (raw_artifact is not None), "RAW_ARTIFACT_HASH_MISMATCH")
    if raw_artifact is not None:
        try:
            raw = u.verify_artifact(raw_artifact)
        except (ValueError, OSError) as exc:
            raise t.TransportContractError("RAW_ARTIFACT_HASH_MISMATCH") from exc
        path_key = "partial_body_artifact_path" if partial else "complete_body_artifact_path"
        hash_key = "partial_body_sha256" if partial else "complete_body_sha256"
        require(body and body[path_key] == raw_artifact["artifact_path"] and body[hash_key] == sha(raw) and body["bytes_read"] == len(raw), "RAW_ARTIFACT_HASH_MISMATCH")
    complete = body is not None and body["completion_state"] == "BODY_COMPLETE"
    http = mapped["observation"]["http_response_provenance"]
    authoritative = bool(complete and raw_artifact and http and http["HTTP_provenance_trusted"] is True and http["status"] == 200)
    require(admission["body_complete"] is complete and admission["authoritative"] is authoritative
            and admission["parser_eligible"] is authoritative
            and admission["completion_provenance_sha256"] == (sha(canonical(body)) if body is not None else None), "PARTIAL_QUARANTINE_VIOLATION")
    require(record["retry_decision_binding"]["classified_retry_decision_artifact"] == occurrence["mapped_decision_snapshot"]
            and record["retry_decision_binding"]["semantic_retry_contract_sha256"] == b.SEMANTIC_RETRY_CONTRACT_SHA256
            and record["retry_decision_binding"]["retry_decision_sha256"] == sha(canonical(retry)), "IMMUTABLE_EVIDENCE_HASH_MISMATCH")
    return True
