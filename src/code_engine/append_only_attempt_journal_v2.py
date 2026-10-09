"""Versioned R1 journal, mechanically ported from immutable 22C V1.

Only the failure phase binding path changes. Explicit V2 events/manifests and
readers; no monkeypatch, historical conversion or production wiring.

Local POSIX write-ahead journal. Unwired; never dispatches or retries.

Only acknowledged, fsynced appends authorize synthetic dispatch. Uncertain
append failures poison the writer. Damaged histories are preserved, not fixed.
The storage guarantee assumes a local filesystem honoring fsync and flock;
it is not a distributed lock or a claim about faulty disks/power-loss hardware.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass, fields
from pathlib import Path

from . import transport_lifecycle_v2 as t
from . import transport_observability_v1 as o
from . import transport_exception_mapping_v2 as b
from . import transport_failure_phase_binding_v2 as phase


require = t.require
canonical = o.canonical_bytes
POLICY = t.SemanticRetryPolicyV2()
RUNTIME_ACTIVATION_ALLOWED = False
ABANDONED = "ABANDONED_ATTEMPT_UNKNOWN_TERMINATION"
AUTHORITY = {
    "master_sha256": t.MASTER_ROOT_SHA256,
    "alpha322a_sha256": b.ALPHA322A_ROOT_SHA256,
    "alpha322b_sha256": "b01024e90fbe4748ef89626a84cb468e5c0988de3726ce1623f766a460b5d4db",
    "semantic_retry_contract_sha256": b.SEMANTIC_RETRY_CONTRACT_SHA256,
    "mapping_table_sha256": b.MAPPING_TABLE_SHA256,
    "mapping_version": b.MAPPING_VERSION,
    "retry_orchestration_contract_sha256": "c23be919b9e74ed49796d83818b0a957c68aa3c9d2648c6a31000833cf2fc75c",
}
LEGACY_AUTHORITY = dict(AUTHORITY)
AUTHORITY["phase_binding_design_sha256"] = phase.DESIGN_SHA
EVENT_TYPES = ("ATTEMPT_STARTED", "LIFECYCLE_PROGRESS", "ATTEMPT_TERMINAL",
               "ABANDONED_ATTEMPT_CLASSIFIED", "STAGE_BARRIER_COMMITTED", "ACTIVATION_MANIFEST_COMMITTED")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def exact_keys(record, keys, reason):
    require(type(record) is dict and set(record) == set(keys), reason)


def hash_value(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None, "INVALID_SHA256")


def physical(path: Path) -> Path:
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), "SYMLINK_FORBIDDEN")
    return path


def sync_directory(path: Path):
    fd = os.open(physical(path), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def read_bytes(path: Path) -> bytes:
    fd = os.open(physical(path), os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as handle:
        return handle.read()


def atomic_freeze(path: Path, raw: bytes) -> t.RawArtifactV1:
    """Sync temporary bytes, atomically link without overwrite, sync directory.

    A crash may leave an unreferenced .pending file. It is never read as a
    manifest or terminal record. Historical destination files cannot be replaced.
    """
    path = physical(path)
    require(type(raw) is bytes and not path.exists(), "IMMUTABLE_ARTIFACT_EXISTS_OR_INVALID")
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path, follow_symlinks=False)
        sync_directory(path.parent)
    finally:
        # Only this invocation's unpublished temporary file is removed.
        os.unlink(temporary)
    return t.RawArtifactV1(str(path), sha(raw), len(raw))


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda value: require(False, "NONFINITE_JSON"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise t.TransportContractError("INVALID_JSON_RECORD") from exc


@dataclass(frozen=True)
class FrozenRequestManifestV2:
    serialized: bytes

    def __post_init__(self):
        record = strict_json(self.serialized)
        require(canonical(record) == self.serialized, "NONCANONICAL_REQUEST_MANIFEST")
        exact_keys(record, ("schema_version", "run_id", "run_epoch", "stage_id", "authority",
                            "activation_contract_sha256", "requests", "runtime_v2_implementation_manifest_sha256"), "MANIFEST_FIELDS")
        require(record["schema_version"] == "FrozenRequestManifestV2" and record["authority"] == AUTHORITY, "MANIFEST_AUTHORITY")
        require(record["runtime_v2_implementation_manifest_sha256"] == phase.implementation_identity(), "RUNTIME_IMPLEMENTATION_BINDING")
        for key in ("run_id", "run_epoch", "stage_id"):
            require(type(record[key]) is str and bool(record[key]), "RUN_IDENTITY_REQUIRED")
            require("alpha321" not in re.sub(r"[^a-z0-9]", "", record[key].lower()), "ALPHA3_21_PERMANENTLY_CLOSED")
        hash_value(record["activation_contract_sha256"])
        requests = record["requests"]
        require(type(requests) is list and bool(requests), "EMPTY_REQUEST_MANIFEST")
        ids = set()
        for order, request in enumerate(requests):
            exact_keys(request, ("request_id", "request_payload", "request_payload_sha256", "stage", "execution_order",
                                 "replay_safe", "maximum_attempts", "validity_authority_sha256", "eligibility_authority_sha256"), "REQUEST_FIELDS")
            require(type(request["request_id"]) is str and request["request_id"] and request["request_id"] not in ids, "REQUEST_ID_COLLISION")
            ids.add(request["request_id"])
            require(request["stage"] in {"OA", "JATS"} and type(request["execution_order"]) is int and request["execution_order"] == order,
                    "FROZEN_REQUEST_ORDER")
            require(type(request["replay_safe"]) is bool and type(request["maximum_attempts"]) is int
                    and request["maximum_attempts"] == POLICY.maximum_attempts, "FROZEN_REPLAY_OR_BUDGET")
            require(type(request["request_payload"]) is dict, "FROZEN_PAYLOAD_REQUIRED")
            require(sha(canonical(request["request_payload"])) == request["request_payload_sha256"], "REQUEST_HASH_MISMATCH")
            hash_value(request["validity_authority_sha256"])
            hash_value(request["eligibility_authority_sha256"])
        oa_ids = {r["request_id"] for r in requests if r["stage"] == "OA"}
        require(oa_ids, "PHASE_ONE_REQUESTS_REQUIRED")
        jats_started = False
        for request in requests:
            if request["stage"] == "JATS":
                jats_started = True
                require(request["request_payload"].get("oa_request_id") in oa_ids, "ACTIVATION_PARENT_NOT_FROZEN")
            else:
                require(not jats_started, "PHASE_ORDER_NOT_FROZEN_OA_BEFORE_JATS")
        clean, _ = o.SecretRedactorV1().tree(record)
        require(clean == record, "SECRET_BEARING_REQUEST_MANIFEST_FORBIDDEN")

    @property
    def sha256(self):
        return sha(self.serialized)

    def record(self):
        return strict_json(self.serialized)

    def request(self, request_id):
        found = [r for r in self.record()["requests"] if r["request_id"] == request_id]
        require(len(found) == 1, "UNKNOWN_FROZEN_REQUEST_ID")
        return found[0]


def journal_event_schema_v2():
    strings = ("run_id", "run_epoch", "stage_id", "journal_segment_id", "timestamp")
    properties = {k: {"type": "string"} for k in strings}
    properties.update({k: {"type": "string", "pattern": "^[0-9a-f]{64}$"} for k in
                       ("manifest_sha256", "runtime_contract_sha256", "runtime_v2_implementation_manifest_sha256", "previous_entry_hash", "entry_hash")})
    properties.update({"schema_version": {"const": "JournalEventV2"},
        "sequence_number": {"type": "integer", "minimum": 1}, "event_type": {"enum": list(EVENT_TYPES)},
        "logical_request_id": {"type": ["string", "null"]}, "frozen_request_hash": {"type": ["string", "null"]},
        "attempt_ordinal": {"type": ["integer", "null"], "minimum": 1, "maximum": POLICY.maximum_attempts},
        "event_payload": {"type": "object"}})
    return {"type": "object", "additionalProperties": False, "properties": properties, "required": list(properties)}


@dataclass(frozen=True)
class JournalEventV2:
    serialized: bytes

    def __post_init__(self):
        record = strict_json(self.serialized)
        o.validate_schema(record, journal_event_schema_v2())
        require(canonical(record) == self.serialized, "NONCANONICAL_JOURNAL_EVENT")
        base = {k: v for k, v in record.items() if k != "entry_hash"}
        require(sha(canonical(base)) == record["entry_hash"], "ENTRY_HASH_MISMATCH")

    def record(self):
        return strict_json(self.serialized)


@dataclass(frozen=True)
class VerifiedJournalV2:
    manifest: FrozenRequestManifestV2
    events: tuple[JournalEventV2, ...]
    directory: str

    @property
    def last_hash(self):
        return self.events[-1].record()["entry_hash"] if self.events else self.manifest.sha256


def _observation_schemas():
    # Consume physical frozen schemas, never replace or broaden them.
    root = Path(__file__).resolve().parents[2] / "runs/20261008_search_plan_v24_dev_alpha3_22a_transport_state_observability_implementation_offline"
    names = {"observation": "transport_attempt_observation_schema", "exception_provenance": "exception_provenance_v1_schema",
             "http_response_provenance": "http_response_provenance_v1_schema", "body_read_provenance": "body_read_provenance_v1_schema",
             "retry_decision_provenance": "retry_decision_provenance_v1_schema"}
    expected = OBSERVATION_SCHEMA_HASHES
    result = {}
    for key, stem in names.items():
        raw = read_bytes(root / (stem + ".json"))
        require(sha(raw) == expected[stem], "FROZEN_OBSERVABILITY_SCHEMA_MISMATCH")
        result[key] = strict_json(raw)
    return result


# Populated from the verified 22A freeze, not a competing schema.
OBSERVATION_SCHEMA_HASHES = {
    "transport_attempt_observation_schema": "330d46a91d7abb0a45c63912cd004a18a6cdba5cd9199b5064f6229891411156",
    "exception_provenance_v1_schema": "47b881c7e6432aec67e7ba37779be94d6f0e7a159d432f364153484132799076",
    "http_response_provenance_v1_schema": "a9965a785b8e8e501d0caaf8e52ce5cb276a78fdf1a120cfd010a9421e9c4970",
    "body_read_provenance_v1_schema": "501a94f933d678b674308d8f7f3c1bdc96178ea61a0f66052c7afa41a32c6d9c",
    "retry_decision_provenance_v1_schema": "04e2d00e672f0900a5c3f1a587b83324df7ede8b865a91bab67ca8c3e2d9d698",
}


def validate_mapped_observation(mapped, context, request, retry, *, phase_binding_verified=False):
    exact_keys(mapped, ("schema_version", "mapping", "observation"), "MAPPED_OBSERVATION_FIELDS")
    require(mapped["schema_version"] == "MappedTransportObservationV2", "MAPPED_OBSERVATION_VERSION")
    observation = mapped["observation"]
    schemas = _observation_schemas()
    o.validate_schema(observation, schemas["observation"])
    for key in schemas:
        if key != "observation" and observation[key] is not None:
            o.validate_schema(observation[key], schemas[key])
            require(all(observation[key][k] == v for k, v in context.record().items()), "NESTED_PROVENANCE_CONTEXT")
    require(all(observation[k] == v for k, v in context.record().items()), "OBSERVATION_CONTEXT")
    mapping = mapped["mapping"]
    exact_keys(mapping, (f.name for f in fields(b.TransportMappingResultV2)), "MAPPING_RECORD_FIELDS")
    require(mapping["mapping_authority_version"] == b.MAPPING_VERSION and mapping["mapping_table_sha256"] == b.MAPPING_TABLE_SHA256
            and mapping["semantic_retry_contract_sha256"] == b.SEMANTIC_RETRY_CONTRACT_SHA256, "MAPPING_BINDINGS")
    failure = t.SemanticFailure(mapping["semantic_failure_class"])
    # ONLY a fully verified V2 failure envelope can use distinct phases.
    require(phase_binding_verified or mapping["phase"] == observation["lifecycle_state"], "MAPPING_PHASE_BINDING")
    rule_ids = {r["rule_id"] for r in b.table_record()["rules"]} | {"structured_http_status", "structured_body_completion", "frozen_esearch_backend_outcome", "complete_body_no_technical_failure"}
    require(mapping["mapping_rule_id"] is None or mapping["mapping_rule_id"] in rule_ids, "UNKNOWN_MAPPING_RULE")
    rules = {r["rule_id"]: r for r in b.table_record()["rules"]}
    rule = rules.get(mapping["mapping_rule_id"])
    if rule is not None:
        require(mapping["phase"] in rule["allowed_lifecycle_phases"], "MAPPING_RULE_PHASE_DRIFT")
        semantics = rule["semantic_transport_class"]
        semantics = semantics if type(semantics) is list else [semantics]
        require(failure.value in semantics, "MAPPING_RULE_SEMANTIC_DRIFT")
        wrapper = rule["wrapper_requirements"]
        if mapping["matched_wrapper_path"]:
            require(wrapper is not None and mapping["matched_wrapper_path"] == wrapper["field_path"]
                and mapping["matched_exception_class"] in {b.qualified(b.CONCRETE_CLASSES[key]) for key in wrapper["inner_exact_class_keys"]}, "MAPPING_WRAPPER_DRIFT")
        else:
            require(mapping["matched_exception_class"] == b.qualified(b.CONCRETE_CLASSES[rule["class_binding_key"]]), "MAPPING_EXACT_CLASS_DRIFT")
    elif mapping["mapping_rule_id"] is None:
        require(failure == t.SemanticFailure.UNKNOWN_RUNTIME_FAILURE, "UNMAPPED_FAILURE_CANNOT_GAIN_RETRY_AUTHORITY")
    http = observation["http_response_provenance"]
    if mapping["mapping_rule_id"] in {"http_error_status", "structured_http_status"}:
        require(http is not None and http["HTTP_provenance_trusted"] is True
            and http["status_origin"] in {"BOUND_HTTP_RESPONSE", "BOUND_HTTP_ERROR"}, "MAPPING_STATUS_NOT_TRUSTED")
        status_contract = b.table_record()["http_status_adapter"]
        expected_failure = t.SemanticFailure.RETRYABLE_HTTP_STATUS if http["status"] in status_contract["retryable_statuses"] else t.SemanticFailure.NONRETRYABLE_HTTP_STATUS
        require(failure == expected_failure, "PERSISTED_HTTP_MAPPING_DRIFT")
    policy = t.SemanticRetryPolicyV2(provider_backend_authority=t.BACKEND_AUTHORITY_SHA256
                                   if mapping["mapping_rule_id"] == "frozen_esearch_backend_outcome" else None)
    expected = t.semantic_retry_decision(failure, request_replay_safe=request["replay_safe"], attempt_ordinal=context.attempt_ordinal, policy=policy)
    # Validation equality only: never reclassify exception text or upgrade a saved decision.
    expected_record = {key: value.value if isinstance(value, t.SemanticFailure) else value for key, value in expected.__dict__.items()}
    exact_keys(retry, expected_record, "PERSISTED_RETRY_DECISION_FIELDS")
    require(retry == expected_record and all(type(retry[key]) is type(value) for key, value in expected_record.items()), "PERSISTED_RETRY_DECISION_INCONSISTENT")
    require(observation["retry_decision_provenance"] is not None, "RETRY_PROVENANCE_REQUIRED")
    provenance = o.RetryDecisionProvenanceV1.capture(context, o.SecretRedactorV1(), expected,
        replay_safety_authority=observation["retry_decision_provenance"]["replay_safety_authority"])
    require(observation["retry_decision_provenance"] == provenance.record(), "RETRY_PROVENANCE_INCONSISTENT")
    require(not request["replay_safe"] or observation["retry_decision_provenance"]["replay_safety_authority"] is not None, "REPLAY_AUTHORITY_MISSING")
    return observation


def verify_artifact(reference):
    exact_keys(reference, ("artifact_path", "sha256", "byte_count"), "RAW_ARTIFACT_FIELDS")
    return t.RawArtifactV1(**reference).verified_bytes()


def _verify_terminal(payload, context, request, progress, manifest_sha, manifest, prefix, directory):
    exact_keys(payload, ("outcome", "mapped_observation", "retry_decision", "raw_artifact", "validation", "eligibility", "failure_phase_binding"), "TERMINAL_FIELDS")
    binding = payload["failure_phase_binding"]
    failed = payload["mapped_observation"]["mapping"]["semantic_failure_class"] != t.SemanticFailure.NO_TECHNICAL_FAILURE.value
    require((binding is not None) is failed, "FAILURE_BINDING_REQUIRED_ONLY_FOR_FAILURE")
    if failed:
        phase.validate_binding(binding, payload["mapped_observation"], payload["retry_decision"], payload["raw_artifact"],
            context, request, manifest, prefix, directory)
    observation = validate_mapped_observation(payload["mapped_observation"], context, request, payload["retry_decision"], phase_binding_verified=failed)
    require(observation["lifecycle_events"] == progress, "JOURNAL_LIFECYCLE_PROVENANCE_MISMATCH")
    require(progress and observation["lifecycle_state"] == progress[-1]["state"], "OBSERVATION_LAST_PHASE_MISMATCH")
    retry = payload["retry_decision"]
    replay = observation["retry_decision_provenance"]["replay_safety_authority"]
    require(not request["replay_safe"] or replay == {"manifest_sha256": manifest_sha, "request_id": request["request_id"]}, "REPLAY_MANIFEST_BINDING")
    outcome = payload["outcome"]
    if outcome in {"VALID_SUCCESS", "VALID_NONELIGIBLE_RESPONSE", "TERMINAL_RESPONSE_VALIDITY_FAILURE"}:
        raw = verify_artifact(payload["raw_artifact"])
        body, http = observation["body_read_provenance"], observation["http_response_provenance"]
        require(body is not None and body["completion_state"] == t.BodyState.COMPLETE.value and body["read_returned_normally"] is True
                and body["complete_body_sha256"] == sha(raw) and body["bytes_read"] == len(raw)
                and body["complete_body_artifact_path"] == payload["raw_artifact"]["artifact_path"]
                and body["partial_body_artifact_path"] is None and body["partial_body_sha256"] is None, "COMPLETE_RAW_REQUIRED")
        require(http is not None and http["HTTP_provenance_trusted"] is True and http["status"] == 200
                and observation["lifecycle_state"] == t.LifecycleState.RESPONSE_VALIDATION_COMPLETE.value, "TRUSTED_VALIDATED_HTTP_REQUIRED")
        require(body["semantic_failure_state"] is None
            and (body["expected_content_length_bytes"] is None or body["expected_content_length_bytes"] == len(raw))
            and not any(e.get("authoritative") is True and e.get("passed") is not True for e in body["framing_integrity_checks"]),
            "CONTRADICTORY_COMPLETE_BODY_EVIDENCE")
        exact_keys(payload["validation"], ("authority_sha256", "accepted"), "VALIDATION_FIELDS")
        require(type(payload["validation"]["accepted"]) is bool
                and payload["validation"]["authority_sha256"] == request["validity_authority_sha256"], "VALIDATOR_AUTHORITY")
        require(payload["validation"]["accepted"] == (outcome != "TERMINAL_RESPONSE_VALIDITY_FAILURE"), "VALIDATOR_OUTCOME_CONFLICT")
        if outcome != "TERMINAL_RESPONSE_VALIDITY_FAILURE":
            require(retry["semantic_failure"] == t.SemanticFailure.NO_TECHNICAL_FAILURE.value, "SUCCESS_HAS_TECHNICAL_FAILURE")
            exact_keys(payload["eligibility"], ("authority_sha256", "eligible"), "ELIGIBILITY_FIELDS")
            require(type(payload["eligibility"]["eligible"]) is bool and payload["eligibility"]["authority_sha256"] == request["eligibility_authority_sha256"]
                    and payload["eligibility"]["eligible"] == (outcome == "VALID_SUCCESS"), "ELIGIBILITY_OUTCOME_CONFLICT")
        else:
            require(payload["eligibility"] is None and retry["terminal_state"] == outcome, "VALIDITY_FAILURE_OUTCOME_CONFLICT")
    else:
        require(payload["validation"] is None and payload["eligibility"] is None, "TECHNICAL_FAILURE_NOT_SCIENTIFIC_ELIGIBILITY")
        require(outcome == ("RETRYABLE_FAILURE_WITH_BUDGET" if retry["retry_authorized"] else retry["terminal_state"]), "TECHNICAL_TERMINAL_DECISION_CONFLICT")
        require(retry["semantic_failure"] != t.SemanticFailure.NO_TECHNICAL_FAILURE.value, "TECHNICAL_FAILURE_MISSING")
        if payload["raw_artifact"] is not None:
            raw = verify_artifact(payload["raw_artifact"])
            body = observation["body_read_provenance"]
            require(body is not None and body["bytes_read"] == len(raw), "PARTIAL_OBSERVATION_BINDING")
            require(not body["parser_invoked"] or body["completion_state"] == t.BodyState.COMPLETE.value, "PARTIAL_PARSER_FORBIDDEN")
            complete = body["completion_state"] == t.BodyState.COMPLETE.value
            path_key = "complete_body_artifact_path" if complete else "partial_body_artifact_path"
            hash_key = "complete_body_sha256" if complete else "partial_body_sha256"
            require(body[path_key] == payload["raw_artifact"]["artifact_path"] and body[hash_key] == sha(raw), "TECHNICAL_BODY_ARTIFACT_PROVENANCE_MISMATCH")
            if not complete:
                require(body["complete_body_artifact_path"] is None and body["complete_body_sha256"] is None, "PARTIAL_COMPLETE_HASH_FORBIDDEN")
        else:
            require(observation["body_read_provenance"] is None, "MISSING_OBSERVED_RAW")


def _reduce(events, manifest, directory=None):
    """Shared verifier/reconstructor, never an independent retry policy."""
    requests = {r["request_id"]: r for r in manifest.record()["requests"]}
    states = {key: {"attempts": [], "outcome": None, "barrier": None} for key in requests}
    barrier = activation = None
    for event_index, event in enumerate(events):
        record = event.record()
        kind, key, ordinal, payload = (record[k] for k in ("event_type", "logical_request_id", "attempt_ordinal", "event_payload"))
        if kind in {"STAGE_BARRIER_COMMITTED", "ACTIVATION_MANIFEST_COMMITTED"}:
            require(key is None and ordinal is None and record["frozen_request_hash"] is None, "STAGE_EVENT_REQUEST_FIELDS")
            if kind == "STAGE_BARRIER_COMMITTED":
                require(barrier is None and activation is None, "DUPLICATE_BARRIER")
                from .stage_barrier_snapshot_v2 import StageBarrierSnapshotV2
                barrier = StageBarrierSnapshotV2.from_reference(payload, manifest, states)
            else:
                require(barrier is not None and activation is None, "ACTIVATION_WITHOUT_BARRIER_OR_DUPLICATE")
                from .stage_barrier_snapshot_v2 import FrozenActivationManifestV2
                activation = FrozenActivationManifestV2.from_reference(payload, manifest, barrier)
            continue
        require(key in requests, "UNKNOWN_REQUEST_EVENT")
        request, state = requests[key], states[key]
        require(record["frozen_request_hash"] == request["request_payload_sha256"], "EVENT_REQUEST_HASH_CHANGED")
        if request["stage"] == "JATS":
            require(activation is not None and key in activation.record()["activated_request_ids"], "DISPATCH_BEFORE_FROZEN_ACTIVATION")
        require(type(ordinal) is int and 1 <= ordinal <= POLICY.maximum_attempts, "ATTEMPT_ORDINAL_REQUIRED")
        if kind == "ATTEMPT_STARTED":
            required = [r["request_id"] for r in manifest.record()["requests"]
                if states[r["request_id"]]["outcome"] not in {"VALID_SUCCESS", "VALID_NONELIGIBLE_RESPONSE"}
                and not (activation is not None and r["request_id"] in activation.record()["not_required_request_ids"])]
            require(required and key == required[0], "FROZEN_DISPATCH_ORDER_VIOLATION")
            require(ordinal == len(state["attempts"]) + 1, "DUPLICATE_OR_REUSED_ATTEMPT_ORDINAL")
            require(state["outcome"] is None or state["outcome"] == "RETRYABLE_FAILURE_WITH_BUDGET", "TERMINAL_REQUEST_NOT_REOPENABLE")
            if state["attempts"]:
                previous = state["attempts"][-1]
                if previous["abandoned"]:
                    require(request["replay_safe"] and len(state["attempts"]) < POLICY.maximum_attempts, "ABANDONED_CONTINUATION_NOT_AUTHORIZED")
                else:
                    require(previous["terminal"] is not None and previous["terminal"]["retry_decision"]["retry_authorized"], "NO_PERSISTED_RETRY_AUTHORIZATION")
            exact_keys(payload, ("replay_safe", "authority", "maximum_attempts", "timeout_seconds", "recovery_from_abandoned"), "START_PAYLOAD_FIELDS")
            require(payload["authority"] == AUTHORITY and payload["replay_safe"] is request["replay_safe"] and payload["maximum_attempts"] == POLICY.maximum_attempts
                    and payload["timeout_seconds"] == POLICY.timeout_seconds, "START_RETRY_BINDING")
            abandoned_previous = bool(state["attempts"] and state["attempts"][-1]["abandoned"])
            require(payload["recovery_from_abandoned"] is abandoned_previous, "ABANDONED_START_BINDING")
            state["attempts"].append({"ordinal": ordinal, "start_hash": record["entry_hash"], "progress": [], "terminal": None, "abandoned": False})
            state["outcome"] = None
            # The first A lifecycle event is persisted immediately after start.
        else:
            require(state["attempts"] and ordinal == state["attempts"][-1]["ordinal"], "EVENT_WITHOUT_CURRENT_START")
            attempt = state["attempts"][-1]
            require(attempt["terminal"] is None and not attempt["abandoned"], "DUPLICATE_TERMINAL")
            if kind == "LIFECYCLE_PROGRESS":
                exact_keys(payload, ("lifecycle_event",), "PROGRESS_FIELDS")
                edge = payload["lifecycle_event"]
                exact_keys(edge, (*t.AttemptContextV1(key, request["request_payload_sha256"], ordinal).record(), "previous_state", "state", "timestamp", "evidence_reference"), "LIFECYCLE_FIELDS")
                context = t.AttemptContextV1(key, request["request_payload_sha256"], ordinal)
                require(all(edge[k] == v for k, v in context.record().items()), "LIFECYCLE_CONTEXT")
                current = t.LifecycleState(attempt["progress"][-1]["state"]) if attempt["progress"] else t.LifecycleState.REQUEST_NOT_STARTED
                require(edge["previous_state"] == current.value, "LIFECYCLE_SEQUENCE")
                require((current, t.LifecycleState(edge["state"])) in t.ALLOWED_TRANSITIONS, "INVALID_LIFECYCLE_EDGE")
                require(type(edge["evidence_reference"]) is str and edge["evidence_reference"], "LIFECYCLE_EVIDENCE")
                if not attempt["progress"]:
                    require(edge["evidence_reference"] == attempt["start_hash"], "LIFECYCLE_START_NOT_WRITE_AHEAD_BOUND")
                attempt["progress"].append(edge)
            elif kind == "ATTEMPT_TERMINAL":
                _verify_terminal(payload, t.AttemptContextV1(key, request["request_payload_sha256"], ordinal), request, attempt["progress"], manifest.sha256,
                    manifest, [prior.record() for prior in events[:event_index]], directory)
                attempt["terminal"] = payload
                state["outcome"] = payload["outcome"]
            elif kind == "ABANDONED_ATTEMPT_CLASSIFIED":
                require(payload == {"state": ABANDONED, "restart_authority_sha256": t.MASTER_ROOT_SHA256,
                                    "attempt_consumed": True}, "ABANDONED_AUTHORITY")
                attempt["abandoned"] = True
                state["outcome"] = "RETRYABLE_FAILURE_WITH_BUDGET" if request["replay_safe"] and ordinal < POLICY.maximum_attempts else "TERMINAL_TECHNICAL_FAILURE"
            else:
                require(False, "UNKNOWN_EVENT_TYPE")
    return states, barrier, activation


class JournalIntegrityVerifierV2:
    @staticmethod
    def verify_events(events, manifest, directory):
        previous = manifest.sha256
        identity = manifest.record()
        for sequence, event in enumerate(events, 1):
            require(type(event) is JournalEventV2, "VERSIONED_JOURNAL_EVENT_REQUIRED")
            record = event.record()
            require(record["sequence_number"] == sequence and record["previous_entry_hash"] == previous, "JOURNAL_SEQUENCE_OR_LINK")
            require(all(record[k] == identity[k] for k in ("run_id", "run_epoch", "stage_id"))
                    and record["manifest_sha256"] == manifest.sha256 and record["runtime_contract_sha256"] == t.MASTER_ROOT_SHA256
                    and record["runtime_v2_implementation_manifest_sha256"] == identity["runtime_v2_implementation_manifest_sha256"]
                    and record["journal_segment_id"] == "segment-0001", "JOURNAL_IDENTITY_BINDING")
            clean, _ = o.SecretRedactorV1().tree(record)
            require(clean == record, "UNREDACTED_JOURNAL")
            previous = record["entry_hash"]
        _reduce(events, manifest, directory)
        return VerifiedJournalV2(manifest, tuple(events), str(physical(directory)))

    @classmethod
    def _read_unlocked(cls, directory, expected):
        stored = read_bytes(directory / "request_manifest.json")
        require(stored == expected.serialized, "FROZEN_REQUEST_MANIFEST_CHANGED")
        raw = read_bytes(directory / "segment-0001.jsonl")
        require(not raw or raw.endswith(b"\n"), "TORN_JOURNAL_TAIL_REQUIRES_INTEGRITY_REVIEW")
        events = tuple(JournalEventV2(line + b"\n") for line in raw.splitlines())
        return cls.verify_events(events, expected, directory)

    @classmethod
    def read(cls, directory: Path, manifest: FrozenRequestManifestV2):
        directory = physical(directory)
        fd = os.open(physical(directory / "writer.lock"), os.O_RDONLY | os.O_NOFOLLOW)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise t.TransportContractError("JOURNAL_WRITER_ACTIVE_RETRY_READ_LATER") from exc
            return cls._read_unlocked(directory, manifest)
        finally:
            os.close(fd)

    @classmethod
    def integrity_report(cls, directory, manifest):
        """Read-only diagnostics; prefix is NOT authorization after corruption."""
        raw = read_bytes(Path(directory) / "segment-0001.jsonl")
        prefix = []
        reason = None
        for line in raw.splitlines(keepends=True):
            try:
                require(line.endswith(b"\n"), "TORN_JOURNAL_TAIL_REQUIRES_INTEGRITY_REVIEW")
                candidate = JournalEventV2(line)
                cls.verify_events((*prefix, candidate), manifest, directory)
                prefix.append(candidate)
            except (ValueError, OSError, KeyError) as exc:
                reason = type(exc).__name__ + ":" + str(exc)
                break
        return {"schema_version": "JournalIntegrityReportV2", "segment_sha256": sha(raw), "segment_byte_count": len(raw),
                "verified_prefix_count": len(prefix), "verified_prefix_last_hash": prefix[-1].record()["entry_hash"] if prefix else manifest.sha256,
                "integrity_failure": reason, "recovery_authorized": False if reason else True,
                "damaged_segment_preserved": True, "historical_events_rewritten": False,
                "corrupt_tail_behavior": "FAIL_CLOSED_NO_DISPATCH_NO_NEW_SEGMENT_REQUIRES_INTEGRITY_REVIEW"}


@dataclass(frozen=True)
class DurableAttemptStartV2:
    context: t.AttemptContextV1
    entry_hash: str
    manifest_sha256: str


class AppendOnlyAttemptJournalV2:
    def __init__(self, directory, manifest, *, create=False, redactor=None):
        require(type(manifest) is FrozenRequestManifestV2 and type(create) is bool, "FROZEN_MANIFEST_REQUIRED")
        self.directory, self.manifest = physical(directory), manifest
        self.redactor = redactor if redactor is not None else o.SecretRedactorV1()
        require(type(self.redactor) is o.SecretRedactorV1, "VERSIONED_REDACTOR_REQUIRED")
        self._lock_fd = self._fd = None
        self._poisoned = False
        if create:
            require(not self.directory.exists(), "NEW_JOURNAL_DIRECTORY_REQUIRED")
            self.directory.mkdir()
            sync_directory(self.directory.parent)
            fd = os.open(self.directory / "writer.lock", os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            os.fsync(fd)
            os.close(fd)
            sync_directory(self.directory)
        try:
            self._lock_fd = os.open(physical(self.directory / "writer.lock"), os.O_RDWR | os.O_NOFOLLOW)
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise t.TransportContractError("EXCLUSIVE_JOURNAL_WRITER_ALREADY_OWNED") from exc
            if create:
                atomic_freeze(self.directory / "request_manifest.json", manifest.serialized)
                atomic_freeze(self.directory / "segment-0001.jsonl", b"")
            self._verified = JournalIntegrityVerifierV2._read_unlocked(self.directory, manifest)
            self._fd = os.open(physical(self.directory / "segment-0001.jsonl"), os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
        except BaseException:
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        for key in ("_fd", "_lock_fd"):
            fd = getattr(self, key, None)
            if fd is not None:
                os.close(fd)
                setattr(self, key, None)

    def verified(self):
        require(self._fd is not None and not self._poisoned, "CLOSED_OR_UNCERTAIN_JOURNAL_WRITER")
        current = JournalIntegrityVerifierV2._read_unlocked(self.directory, self.manifest)
        require(current.events == self._verified.events, "EXTERNAL_JOURNAL_MUTATION")
        return current

    def _append(self, kind, key, ordinal, payload, timestamp):
        verified = self.verified()
        require(type(timestamp) is str and bool(timestamp), "EXPLICIT_EVENT_TIMESTAMP_REQUIRED")
        identity = self.manifest.record()
        base = {"schema_version": "JournalEventV2", **{k: identity[k] for k in ("run_id", "run_epoch", "stage_id")},
                "journal_segment_id": "segment-0001", "sequence_number": len(verified.events) + 1,
                "event_type": kind, "logical_request_id": key,
                "frozen_request_hash": self.manifest.request(key)["request_payload_sha256"] if key is not None else None,
                "attempt_ordinal": ordinal, "timestamp": timestamp, "manifest_sha256": self.manifest.sha256,
                "runtime_v2_implementation_manifest_sha256": identity["runtime_v2_implementation_manifest_sha256"],
                "runtime_contract_sha256": t.MASTER_ROOT_SHA256, "event_payload": payload, "previous_entry_hash": verified.last_hash}
        clean, _ = self.redactor.tree(base)
        event = JournalEventV2(canonical({**clean, "entry_hash": sha(canonical(clean))}))
        pending = JournalIntegrityVerifierV2.verify_events((*verified.events, event), self.manifest, self.directory)
        try:
            raw = event.serialized
            written = 0
            while written < len(raw):
                amount = os.write(self._fd, raw[written:])
                require(amount > 0, "SHORT_JOURNAL_APPEND")
                written += amount
            os.fsync(self._fd)
        except BaseException as exc:
            self._poisoned = True
            if kind == "ATTEMPT_TERMINAL" and isinstance(exc, OSError):
                raise t.TransportContractError("UNCERTAIN_DURABILITY_FAIL_CLOSED") from exc
            raise
        self._verified = pending
        return event

    def start_attempt(self, request_id, *, timestamp):
        from .deterministic_resume_planner_v2 import DeterministicResumePlannerV2
        plan = DeterministicResumePlannerV2().build(self.verified()).record()
        require(plan["next_executable_request_id"] == request_id and plan["blocking_reason"] is None, "NOT_FIRST_AUTHORIZED_UNRESOLVED_REQUEST")
        item = next(r for r in plan["requests"] if r["request_id"] == request_id)
        ordinal = item["next_authorized_ordinal"]
        request = self.manifest.request(request_id)
        event = self._append("ATTEMPT_STARTED", request_id, ordinal,
            {"replay_safe": request["replay_safe"], "authority": AUTHORITY, "maximum_attempts": POLICY.maximum_attempts,
             "timeout_seconds": POLICY.timeout_seconds, "recovery_from_abandoned": item["current_derived_state"] == ABANDONED}, timestamp)
        context = t.AttemptContextV1(request_id, request["request_payload_sha256"], ordinal)
        return DurableAttemptStartV2(context, event.record()["entry_hash"], self.manifest.sha256)

    def dispatch_authorized(self, token):
        require(type(token) is DurableAttemptStartV2 and token.manifest_sha256 == self.manifest.sha256, "DURABLE_DISPATCH_TOKEN_REQUIRED")
        states, _, _ = _reduce(self.verified().events, self.manifest, self.directory)
        state = states.get(token.context.logical_request_id)
        require(state is not None and state["attempts"], "DISPATCH_WITHOUT_DURABLE_START")
        attempt = state["attempts"][-1]
        require(attempt["ordinal"] == token.context.attempt_ordinal and attempt["start_hash"] == token.entry_hash
                and attempt["terminal"] is None and not attempt["abandoned"], "STALE_DISPATCH_TOKEN")
        require(token.context.request_payload_sha256 == self.manifest.request(token.context.logical_request_id)["request_payload_sha256"], "DISPATCH_PAYLOAD_CHANGED")
        return True

    def record_lifecycle(self, lifecycle, *, timestamp):
        require(type(lifecycle) is t.TransportLifecycleV2, "ALPHA322A_LIFECYCLE_REQUIRED")
        states, _, _ = _reduce(self.verified().events, self.manifest, self.directory)
        context = lifecycle.context
        require(context.logical_request_id in states and states[context.logical_request_id]["attempts"], "LIFECYCLE_WITHOUT_START")
        saved = states[context.logical_request_id]["attempts"][-1]["progress"]
        edges = [{**edge.context.record(), "previous_state": edge.previous_state.value, "state": edge.state.value,
                  "timestamp": edge.timestamp, "evidence_reference": edge.evidence_reference} for edge in lifecycle.events]
        require(edges[:len(saved)] == saved, "LIFECYCLE_PREFIX_CHANGED")
        for edge in edges[len(saved):]:
            self._append("LIFECYCLE_PROGRESS", context.logical_request_id, context.attempt_ordinal, {"lifecycle_event": edge}, timestamp)

    def classify_abandoned(self, *, timestamp):
        states, _, _ = _reduce(self.verified().events, self.manifest, self.directory)
        for request in self.manifest.record()["requests"]:
            attempts = states[request["request_id"]]["attempts"]
            if attempts and attempts[-1]["terminal"] is None and not attempts[-1]["abandoned"]:
                self._append("ABANDONED_ATTEMPT_CLASSIFIED", request["request_id"], attempts[-1]["ordinal"],
                    {"state": ABANDONED, "restart_authority_sha256": t.MASTER_ROOT_SHA256, "attempt_consumed": True}, timestamp)

    def commit_terminal(self, lifecycle, decision, mapped_observation, *, artifact=None, validation=None, eligibility=None, failure_phase_binding=None, timestamp):
        require(type(lifecycle) is t.TransportLifecycleV2 and type(decision) is b.ClassifiedRetryDecisionV2
                and type(mapped_observation) is o.FrozenObservationRecordV1, "ALPHA322A_B_TYPED_TERMINAL_INPUTS_REQUIRED")
        mapped = mapped_observation.record()
        if failure_phase_binding is not None:
            require(type(failure_phase_binding) is phase.TransportFailurePhaseBindingV2, "TYPED_FAILURE_BINDING_REQUIRED")
        require(mapped["mapping"] == decision.mapping.record(), "MAPPED_DECISION_CHANGED")
        request = self.manifest.request(lifecycle.context.logical_request_id)
        if validation is not None:
            require(lifecycle.response_valid is validation["accepted"], "VALIDATION_NOT_RECORDED_BY_ALPHA322A")
        if artifact is not None:
            require(type(artifact) is t.RawArtifactV1, "ALPHA322A_RAW_ARTIFACT_REQUIRED")
            artifact.verified_bytes()
            fd = os.open(physical(Path(artifact.artifact_path)), os.O_RDONLY | os.O_NOFOLLOW)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
            sync_directory(Path(artifact.artifact_path).parent)
        retry = decision.record()["retry"]
        outcome = ("VALID_SUCCESS" if eligibility and eligibility["eligible"] else "VALID_NONELIGIBLE_RESPONSE") if retry["semantic_failure"] == t.SemanticFailure.NO_TECHNICAL_FAILURE.value else (
            "RETRYABLE_FAILURE_WITH_BUDGET" if retry["retry_authorized"] else retry["terminal_state"])
        self.record_lifecycle(lifecycle, timestamp=timestamp)
        return self._append("ATTEMPT_TERMINAL", request["request_id"], lifecycle.context.attempt_ordinal,
            {"outcome": outcome, "mapped_observation": mapped, "retry_decision": retry,
             "raw_artifact": dict(artifact.__dict__) if artifact is not None else None,
             "validation": validation, "eligibility": eligibility,
             "failure_phase_binding": failure_phase_binding.record() if failure_phase_binding is not None else None}, timestamp)

    def commit_stage_reference(self, kind, reference, *, timestamp):
        require(kind in {"STAGE_BARRIER_COMMITTED", "ACTIVATION_MANIFEST_COMMITTED"}, "STAGE_REFERENCE_KIND")
        return self._append(kind, None, None, reference, timestamp)
