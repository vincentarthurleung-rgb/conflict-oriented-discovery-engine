"""Unwired transport semantics: no network, exception mapper or resume engine.

Semantic evidence is supplied by an adapter. Concrete library exception
classification belongs to alpha3.22B; durable attempt journals to alpha3.22C.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, TypeVar


MASTER_ROOT_SHA256 = "0766425a2d007f5ce6e988a8404a410271b2954fb4f968aec68615ff7a8585db"
BACKEND_AUTHORITY_SHA256 = "4a77d09cc623b7d3739fe1efdebead512556e123c733353d069a22e87743efb4"
RUNTIME_ACTIVATION_ALLOWED = False


class TransportContractError(ValueError):
    pass


def require(value: bool, reason: str) -> None:
    if not value:
        raise TransportContractError(reason)


class LifecycleState(str, Enum):
    REQUEST_NOT_STARTED = "REQUEST_NOT_STARTED"
    REQUEST_ATTEMPT_STARTED = "REQUEST_ATTEMPT_STARTED"
    RESPONSE_HEADERS_RECEIVED = "RESPONSE_HEADERS_RECEIVED"
    RESPONSE_BODY_READING = "RESPONSE_BODY_READING"
    RESPONSE_BODY_COMPLETE = "RESPONSE_BODY_COMPLETE"
    RESPONSE_BODY_INTERRUPTED = "RESPONSE_BODY_INTERRUPTED"
    RAW_RESPONSE_FROZEN = "RAW_RESPONSE_FROZEN"
    RESPONSE_VALIDATION_COMPLETE = "RESPONSE_VALIDATION_COMPLETE"
    TERMINAL_TECHNICAL_FAILURE = "TERMINAL_TECHNICAL_FAILURE"


class SemanticFailure(str, Enum):
    NO_TECHNICAL_FAILURE = "NO_TECHNICAL_FAILURE"
    PRE_RESPONSE_TRANSPORT_INTERRUPTION = "PRE_RESPONSE_TRANSPORT_INTERRUPTION"
    RESPONSE_BODY_TRANSPORT_INTERRUPTION = "RESPONSE_BODY_TRANSPORT_INTERRUPTION"
    RESPONSE_BODY_LENGTH_MISMATCH = "RESPONSE_BODY_LENGTH_MISMATCH"
    RETRYABLE_HTTP_STATUS = "RETRYABLE_HTTP_STATUS"
    RETRYABLE_PROVIDER_BACKEND_FAILURE = "RETRYABLE_PROVIDER_BACKEND_FAILURE"
    COMPLETE_BODY_RESPONSE_VALIDITY_FAILURE = "COMPLETE_BODY_RESPONSE_VALIDITY_FAILURE"
    NONRETRYABLE_HTTP_STATUS = "NONRETRYABLE_HTTP_STATUS"
    UNKNOWN_RUNTIME_FAILURE = "UNKNOWN_RUNTIME_FAILURE"


class BodyState(str, Enum):
    COMPLETE = "BODY_COMPLETE"
    INTERRUPTED = "BODY_INTERRUPTED"
    UNKNOWN = "BODY_COMPLETION_UNKNOWN"


class ByteRepresentation(str, Enum):
    WIRE = "wire"
    DECODED = "decoded"
    DECOMPRESSED = "decompressed"
    UNKNOWN = "unknown"


_NORMAL_EDGES = (
    (LifecycleState.REQUEST_NOT_STARTED, LifecycleState.REQUEST_ATTEMPT_STARTED),
    (LifecycleState.REQUEST_ATTEMPT_STARTED, LifecycleState.RESPONSE_HEADERS_RECEIVED),
    (LifecycleState.RESPONSE_HEADERS_RECEIVED, LifecycleState.RESPONSE_BODY_READING),
    (LifecycleState.RESPONSE_BODY_READING, LifecycleState.RESPONSE_BODY_COMPLETE),
    (LifecycleState.RESPONSE_BODY_READING, LifecycleState.RESPONSE_BODY_INTERRUPTED),
    (LifecycleState.RESPONSE_BODY_COMPLETE, LifecycleState.RAW_RESPONSE_FROZEN),
    (LifecycleState.RESPONSE_BODY_INTERRUPTED, LifecycleState.RAW_RESPONSE_FROZEN),
    (LifecycleState.RAW_RESPONSE_FROZEN, LifecycleState.RESPONSE_VALIDATION_COMPLETE),
)
ALLOWED_TRANSITIONS = frozenset(_NORMAL_EDGES) | frozenset(
    (state, LifecycleState.TERMINAL_TECHNICAL_FAILURE) for state in LifecycleState
    if state not in {LifecycleState.REQUEST_NOT_STARTED, LifecycleState.TERMINAL_TECHNICAL_FAILURE})


def validate_transition(current: LifecycleState, target: LifecycleState) -> None:
    require(isinstance(current, LifecycleState) and isinstance(target, LifecycleState), "INVALID_STATE_TYPE")
    require((current, target) in ALLOWED_TRANSITIONS, "INVALID_LIFECYCLE_TRANSITION")


@dataclass(frozen=True)
class AttemptContextV1:
    logical_request_id: str
    request_payload_sha256: str
    attempt_ordinal: int
    runtime_contract_sha256: str = MASTER_ROOT_SHA256

    def __post_init__(self):
        require(isinstance(self.logical_request_id, str) and bool(self.logical_request_id), "MISSING_LOGICAL_ID")
        require(isinstance(self.request_payload_sha256, str) and re.fullmatch(r"[0-9a-f]{64}", self.request_payload_sha256) is not None,
                "INVALID_PAYLOAD_HASH")
        require(type(self.attempt_ordinal) is int and 1 <= self.attempt_ordinal <= 4, "INVALID_CONSUMED_ATTEMPT_ORDINAL")
        require(self.runtime_contract_sha256 == MASTER_ROOT_SHA256, "UNBOUND_RUNTIME_CONTRACT")

    def record(self):
        return dict(self.__dict__)


@dataclass(frozen=True)
class FramingEvidenceV1:
    check_name: str
    passed: bool | None
    authoritative: bool
    failure_class: SemanticFailure = SemanticFailure.UNKNOWN_RUNTIME_FAILURE
    evidence_reference: str | None = None

    def __post_init__(self):
        require(type(self.check_name) is str and bool(self.check_name) and type(self.authoritative) is bool, "INVALID_FRAMING_EVIDENCE")
        require(self.passed is None or type(self.passed) is bool, "INVALID_FRAMING_VERDICT")
        require(isinstance(self.failure_class, SemanticFailure), "INVALID_SEMANTIC_EVIDENCE")
        require(self.evidence_reference is None or type(self.evidence_reference) is str, "INVALID_FRAMING_REFERENCE")


@dataclass(frozen=True)
class BodyCompletionResultV2:
    body_completion_state: BodyState
    bytes_read: int
    expected_content_length: int | None
    actual_content_length: int
    content_length_match: str
    byte_representation: ByteRepresentation
    expected_length_representation: ByteRepresentation | None
    framing_integrity_evidence: tuple[FramingEvidenceV1, ...]
    read_returned_normally: bool
    semantic_failure: SemanticFailure
    body_sha256: str | None
    observed_bytes_sha256: str
    completion_timestamp: str | None
    interruption_timestamp: str | None
    interruption_reason: str | None
    exception_provenance_reference: str | None

    def __post_init__(self):
        require(isinstance(self.body_completion_state, BodyState) and isinstance(self.semantic_failure, SemanticFailure), "INVALID_BODY_STATE")
        require(type(self.bytes_read) is int and self.bytes_read >= 0 and type(self.actual_content_length) is int and self.actual_content_length == self.bytes_read,
                "INVALID_ACTUAL_LENGTH")
        require(self.expected_content_length is None or type(self.expected_content_length) is int and self.expected_content_length >= 0,
                "INVALID_EXPECTED_LENGTH")
        require(type(self.read_returned_normally) is bool and self.content_length_match in {"MATCH", "MISMATCH", "UNAVAILABLE"}, "INVALID_READ_RESULT")
        require(isinstance(self.byte_representation, ByteRepresentation) and
                (self.expected_length_representation is None or isinstance(self.expected_length_representation, ByteRepresentation)), "INVALID_BYTE_REPRESENTATION")
        require(type(self.framing_integrity_evidence) is tuple and all(isinstance(e, FramingEvidenceV1) for e in self.framing_integrity_evidence), "INVALID_FRAMING_EVIDENCE")
        require(re.fullmatch(r"[0-9a-f]{64}", self.observed_bytes_sha256) is not None, "INVALID_OBSERVED_HASH")
        complete = self.body_completion_state == BodyState.COMPLETE
        require(complete == (self.semantic_failure == SemanticFailure.NO_TECHNICAL_FAILURE), "CONTRADICTORY_COMPLETION_CLASS")
        require(not complete or self.read_returned_normally and self.content_length_match != "MISMATCH"
                and not any(e.authoritative and e.passed is not True for e in self.framing_integrity_evidence), "UNPROVEN_BODY_COMPLETION")
        require(self.body_sha256 == (self.observed_bytes_sha256 if complete else None), "PARTIAL_BODY_COMPLETE_HASH_FORBIDDEN")
        require(self.content_length_match == "UNAVAILABLE" or self.expected_content_length is not None and
                self.expected_length_representation == self.byte_representation != ByteRepresentation.UNKNOWN and
                (self.content_length_match == "MATCH") == (self.bytes_read == self.expected_content_length), "CONTRADICTORY_LENGTH_EVIDENCE")
        require((self.body_completion_state == BodyState.UNKNOWN) == (self.semantic_failure == SemanticFailure.UNKNOWN_RUNTIME_FAILURE), "CONTRADICTORY_UNKNOWN_CLASS")
        require(complete or self.semantic_failure in {SemanticFailure.RESPONSE_BODY_TRANSPORT_INTERRUPTION,
                SemanticFailure.RESPONSE_BODY_LENGTH_MISMATCH, SemanticFailure.UNKNOWN_RUNTIME_FAILURE}, "NON_BODY_FAILURE_CLASS")
        require(complete or self.completion_timestamp is None, "PARTIAL_COMPLETION_TIMESTAMP_FORBIDDEN")


def assess_body_completion(
    raw: bytes, *, read_returned_normally: bool,
    expected_content_length: int | None = None, expected_length_trustworthy: bool = False,
    byte_representation: ByteRepresentation = ByteRepresentation.WIRE,
    expected_length_representation: ByteRepresentation | None = None,
    framing_evidence: tuple[FramingEvidenceV1, ...] = (),
    interruption_class: SemanticFailure | None = None, interruption_reason: str | None = None,
    timestamp: str | None = None, exception_provenance_reference: str | None = None,
) -> BodyCompletionResultV2:
    """No stream/exception inspection. Use explicitly supplied semantic facts."""
    require(type(raw) is bytes and type(read_returned_normally) is bool, "INVALID_BODY_EVIDENCE")
    require(type(expected_length_trustworthy) is bool, "INVALID_LENGTH_AUTHORITY")
    require(expected_content_length is None or type(expected_content_length) is int and expected_content_length >= 0,
            "INVALID_EXPECTED_LENGTH")
    require(isinstance(byte_representation, ByteRepresentation) and
            (expected_length_representation is None or isinstance(expected_length_representation, ByteRepresentation)), "INVALID_BYTE_REPRESENTATION")
    require(isinstance(framing_evidence, tuple) and all(isinstance(e, FramingEvidenceV1) for e in framing_evidence), "INVALID_FRAMING_EVIDENCE_LIST")
    body_classes = {SemanticFailure.RESPONSE_BODY_TRANSPORT_INTERRUPTION, SemanticFailure.RESPONSE_BODY_LENGTH_MISMATCH,
                    SemanticFailure.UNKNOWN_RUNTIME_FAILURE}
    require(interruption_class is None or interruption_class in body_classes, "NON_BODY_SEMANTIC_INPUT")
    require(not read_returned_normally or interruption_class is None, "CONTRADICTORY_READ_EVIDENCE")
    length_available = (expected_length_trustworthy and expected_content_length is not None
                        and expected_length_representation is not None
                        and expected_length_representation == byte_representation != ByteRepresentation.UNKNOWN)
    match = "MATCH" if length_available and len(raw) == expected_content_length else "MISMATCH" if length_available else "UNAVAILABLE"
    failed = [e for e in framing_evidence if e.authoritative and e.passed is False]
    uncertain = [e for e in framing_evidence if e.authoritative and e.passed is None]
    failure = SemanticFailure.NO_TECHNICAL_FAILURE
    if not read_returned_normally:
        failure = interruption_class or SemanticFailure.UNKNOWN_RUNTIME_FAILURE
    elif match == "MISMATCH":
        failure = SemanticFailure.RESPONSE_BODY_LENGTH_MISMATCH
    elif failed:
        classes = {e.failure_class for e in failed}
        failure = next(iter(classes)) if len(classes) == 1 and classes <= body_classes else SemanticFailure.UNKNOWN_RUNTIME_FAILURE
    elif uncertain:
        failure = SemanticFailure.UNKNOWN_RUNTIME_FAILURE
    complete = failure == SemanticFailure.NO_TECHNICAL_FAILURE
    state = BodyState.COMPLETE if complete else BodyState.UNKNOWN if failure == SemanticFailure.UNKNOWN_RUNTIME_FAILURE else BodyState.INTERRUPTED
    value = hashlib.sha256(raw).hexdigest()
    return BodyCompletionResultV2(state, len(raw), expected_content_length if expected_length_trustworthy else None,
        len(raw), match, byte_representation, expected_length_representation, framing_evidence,
        read_returned_normally, failure, value if complete else None, value,
        timestamp if complete else None, timestamp if not complete else None,
        interruption_reason if not complete else None, exception_provenance_reference)


@dataclass(frozen=True)
class RawArtifactV1:
    artifact_path: str
    sha256: str
    byte_count: int

    def __post_init__(self):
        require(type(self.artifact_path) is str and bool(self.artifact_path), "INVALID_ARTIFACT_PATH")
        require(type(self.sha256) is str and re.fullmatch(r"[0-9a-f]{64}", self.sha256) is not None, "INVALID_ARTIFACT_HASH")
        require(type(self.byte_count) is int and self.byte_count >= 0, "INVALID_ARTIFACT_LENGTH")

    def verified_bytes(self) -> bytes:
        path = Path(self.artifact_path)
        require(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)), "ARTIFACT_SYMLINK_OR_MISSING")
        raw = path.read_bytes()
        require(len(raw) == self.byte_count and hashlib.sha256(raw).hexdigest() == self.sha256, "FROZEN_RAW_ARTIFACT_MISMATCH")
        return raw


class RawArtifactStoreV1:
    """Own a new directory; exclusive byte freezes, never an attempt journal."""

    def __init__(self, directory: Path):
        directory = Path(directory).absolute()
        require(not directory.exists() and not any(p.is_symlink() for p in (directory, *directory.parents)), "AUDIT_DIRECTORY_MUST_BE_NEW_PHYSICAL_PATH")
        directory.mkdir()
        self.directory = directory

    def freeze_bytes(self, name: str, raw: bytes) -> RawArtifactV1:
        require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name) is not None and name not in {".", ".."}, "UNSAFE_ARTIFACT_NAME")
        require(type(raw) is bytes, "RAW_BYTES_REQUIRED")
        path = self.directory / name
        require(not self.directory.is_symlink() and not path.is_symlink(), "ARTIFACT_SYMLINK_FORBIDDEN")
        with path.open("xb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        result = RawArtifactV1(str(path), hashlib.sha256(raw).hexdigest(), len(raw))
        result.verified_bytes()
        return result


@dataclass(frozen=True)
class FrozenTransportResponseV2:
    """Transport admission only, never OA/license/scientific eligibility.

    Consumer eligibility properties are necessary transport guards. All
    unchanged downstream validators still have to accept a complete response.
    """

    context: AttemptContextV1
    completion: BodyCompletionResultV2
    artifact: RawArtifactV1
    accepted_HTTP_status: bool

    def __post_init__(self):
        require(isinstance(self.context, AttemptContextV1) and isinstance(self.completion, BodyCompletionResultV2)
                and isinstance(self.artifact, RawArtifactV1) and type(self.accepted_HTTP_status) is bool, "INVALID_FROZEN_RESPONSE")

    @property
    def authoritative(self):
        return (self.completion.body_completion_state == BodyState.COMPLETE and self.accepted_HTTP_status is True
                and self.completion.body_sha256 == self.artifact.sha256
                and self.completion.bytes_read == self.artifact.byte_count)

    @property
    def parser_eligible(self):
        return self.authoritative

    @property
    def identity_parser_eligible(self):
        return self.parser_eligible

    @property
    def license_parser_eligible(self):
        return self.parser_eligible

    @property
    def body_normalizer_eligible(self):
        return self.parser_eligible

    @property
    def scientific_extraction_eligible(self):
        return self.parser_eligible


T = TypeVar("T")


def guarded_parse(response: FrozenTransportResponseV2, parser: Callable[[bytes], T]) -> T:
    require(isinstance(response, FrozenTransportResponseV2) and response.parser_eligible, "PARTIAL_OR_UNAUTHORITATIVE_RESPONSE_QUARANTINED")
    # Reverify frozen bytes immediately before admission. No parser is called
    # for a partial, untrusted HTTP status, or corrupted artifact.
    raw = response.artifact.verified_bytes()
    return parser(raw)


@dataclass(frozen=True)
class LifecycleEventV2:
    context: AttemptContextV1
    previous_state: LifecycleState
    state: LifecycleState
    timestamp: str | None
    evidence_reference: str


class TransportLifecycleV2:
    def __init__(self, context: AttemptContextV1):
        require(isinstance(context, AttemptContextV1), "INVALID_ATTEMPT_CONTEXT")
        self._context = context
        self._state = LifecycleState.REQUEST_NOT_STARTED
        self._events: list[LifecycleEventV2] = []
        self._completion: BodyCompletionResultV2 | None = None
        self._response: FrozenTransportResponseV2 | None = None
        self._HTTP_accepted = False
        self._validation_valid: bool | None = None

    @property
    def context(self):
        return self._context

    @property
    def state(self):
        return self._state

    @property
    def events(self):
        return tuple(self._events)

    @property
    def completion(self):
        return self._completion

    @property
    def response_valid(self):
        return self._validation_valid

    def _advance(self, target, evidence_reference, timestamp=None):
        validate_transition(self.state, target)
        require(isinstance(evidence_reference, str) and bool(evidence_reference), "STATE_EVIDENCE_REQUIRED")
        self._events.append(LifecycleEventV2(self.context, self.state, target, timestamp, evidence_reference))
        self._state = target

    def start_attempt(self, start_evidence_reference: str, *, timestamp=None):
        # This event is in-memory only. A future live caller must supply 22C's
        # durable write-ahead commit reference; A never implements that commit.
        self._advance(LifecycleState.REQUEST_ATTEMPT_STARTED, start_evidence_reference, timestamp)

    def receive_headers(self, status: int | None, *, trustworthy: bool, evidence_reference: str, timestamp=None):
        require(status is None or type(status) is int and 100 <= status <= 599, "INVALID_HTTP_STATUS")
        require(type(trustworthy) is bool, "HTTP_TRUST_FLAG_REQUIRED")
        require(trustworthy, "UNTRUSTED_HEADERS_CANNOT_PROMOTE_LIFECYCLE")
        self._advance(LifecycleState.RESPONSE_HEADERS_RECEIVED, evidence_reference, timestamp)
        self._HTTP_accepted = trustworthy and status == 200  # unchanged bound acceptance, not a retry mapper

    def start_body(self, evidence_reference: str, *, timestamp=None):
        self._advance(LifecycleState.RESPONSE_BODY_READING, evidence_reference, timestamp)

    def record_body(self, completion: BodyCompletionResultV2, evidence_reference: str, *, timestamp=None):
        require(isinstance(completion, BodyCompletionResultV2), "BODY_COMPLETION_RESULT_REQUIRED")
        require(self.state == LifecycleState.RESPONSE_BODY_READING, "BODY_READ_PHASE_REQUIRED")
        target = (LifecycleState.RESPONSE_BODY_COMPLETE if completion.body_completion_state == BodyState.COMPLETE else
                  LifecycleState.RESPONSE_BODY_INTERRUPTED if completion.body_completion_state == BodyState.INTERRUPTED else
                  LifecycleState.TERMINAL_TECHNICAL_FAILURE)
        self._advance(target, evidence_reference, timestamp)
        self._completion = completion

    def freeze_response(self, artifact: RawArtifactV1, *, timestamp=None):
        require(self._completion is not None, "BODY_STATE_NOT_RECORDED")
        require(isinstance(artifact, RawArtifactV1), "FROZEN_ARTIFACT_REQUIRED")
        artifact.verified_bytes()
        require(artifact.sha256 == self._completion.observed_bytes_sha256 and artifact.byte_count == self._completion.bytes_read,
                "ARTIFACT_NOT_BOUND_TO_BODY_RESULT")
        self._advance(LifecycleState.RAW_RESPONSE_FROZEN, artifact.sha256, timestamp)
        self._response = FrozenTransportResponseV2(self.context, self._completion, artifact, self._HTTP_accepted)
        return self._response

    def record_validation(self, *, valid: bool, evidence_reference: str, timestamp=None):
        require(type(valid) is bool and self._response is not None and self._response.parser_eligible, "VALIDATION_REQUIRES_AUTHORITATIVE_COMPLETE_RESPONSE")
        self._response.artifact.verified_bytes()
        self._advance(LifecycleState.RESPONSE_VALIDATION_COMPLETE, evidence_reference, timestamp)
        self._validation_valid = valid
        return SemanticFailure.NO_TECHNICAL_FAILURE if valid else SemanticFailure.COMPLETE_BODY_RESPONSE_VALIDITY_FAILURE

    def terminate(self, evidence_reference: str, *, timestamp=None):
        self._advance(LifecycleState.TERMINAL_TECHNICAL_FAILURE, evidence_reference, timestamp)


@dataclass(frozen=True)
class SemanticRetryPolicyV2:
    maximum_attempts: int = 4
    timeout_seconds: int = 60
    backoff_seconds: tuple[int, ...] = (2, 4, 8)
    authority_id: str = MASTER_ROOT_SHA256
    provider_backend_authority: str | None = None

    def __post_init__(self):
        require(type(self.maximum_attempts) is int and type(self.timeout_seconds) is int and
                (self.maximum_attempts, self.timeout_seconds, self.backoff_seconds) == (4, 60, (2, 4, 8)), "NUMERIC_RETRY_POLICY_NOT_FROZEN_DEFAULT")
        require(self.authority_id == MASTER_ROOT_SHA256, "RETRY_AUTHORITY_UNBOUND")
        require(self.provider_backend_authority in {None, BACKEND_AUTHORITY_SHA256}, "BACKEND_POLICY_AUTHORITY_UNBOUND")


@dataclass(frozen=True)
class SemanticRetryDecisionV2:
    semantic_failure: SemanticFailure
    retryable_semantic_class: bool
    retry_authorized: bool
    request_replay_safe: bool
    attempt_ordinal: int
    max_attempts: int
    remaining_attempts_before_decision: int
    remaining_attempts_after_decision: int
    next_attempt_ordinal: int | None
    backoff_selected_seconds: int
    decision: str
    terminal_state: str | None
    decision_authority_identifier: str
    denial_reason: str | None


def semantic_retry_decision(failure: SemanticFailure, *, request_replay_safe: bool, attempt_ordinal: int,
                            policy: SemanticRetryPolicyV2 = SemanticRetryPolicyV2()) -> SemanticRetryDecisionV2:
    """Pure semantic input -> decision. No catch, exception class, sleep or IO."""
    require(isinstance(failure, SemanticFailure), "SEMANTIC_CLASS_REQUIRED_NO_EXCEPTION_NAME_MAPPING")
    require(type(request_replay_safe) is bool and isinstance(policy, SemanticRetryPolicyV2), "INVALID_RETRY_POLICY_INPUT")
    require(type(attempt_ordinal) is int and 1 <= attempt_ordinal <= policy.maximum_attempts, "INVALID_CONSUMED_ATTEMPT_ORDINAL")
    remaining = policy.maximum_attempts - attempt_ordinal
    candidate = failure in {SemanticFailure.PRE_RESPONSE_TRANSPORT_INTERRUPTION, SemanticFailure.RESPONSE_BODY_TRANSPORT_INTERRUPTION,
        SemanticFailure.RESPONSE_BODY_LENGTH_MISMATCH, SemanticFailure.RETRYABLE_HTTP_STATUS, SemanticFailure.RETRYABLE_PROVIDER_BACKEND_FAILURE}
    backend_ok = failure != SemanticFailure.RETRYABLE_PROVIDER_BACKEND_FAILURE or policy.provider_backend_authority == BACKEND_AUTHORITY_SHA256
    retry = candidate and backend_ok and request_replay_safe and remaining > 0
    terminal = None if retry or failure == SemanticFailure.NO_TECHNICAL_FAILURE else (
        "TERMINAL_RESPONSE_VALIDITY_FAILURE" if failure == SemanticFailure.COMPLETE_BODY_RESPONSE_VALIDITY_FAILURE else "TERMINAL_TECHNICAL_FAILURE")
    denial = None if retry or failure == SemanticFailure.NO_TECHNICAL_FAILURE else (
        "SEMANTIC_CLASS_NONRETRYABLE" if not candidate else "BACKEND_AUTHORITY_REQUIRED" if not backend_ok else
        "REQUEST_NOT_REPLAY_SAFE" if not request_replay_safe else "ATTEMPT_BUDGET_EXHAUSTED")
    return SemanticRetryDecisionV2(failure, candidate, retry, request_replay_safe, attempt_ordinal, policy.maximum_attempts,
        remaining, remaining, attempt_ordinal + 1 if retry else None, policy.backoff_seconds[attempt_ordinal - 1] if retry else 0,
        "CONTINUE_WITH_NEXT_ORDINAL" if retry else "VALID_SUCCESS" if failure == SemanticFailure.NO_TECHNICAL_FAILURE else
        "TERMINAL_VALIDITY_FAILURE" if failure == SemanticFailure.COMPLETE_BODY_RESPONSE_VALIDITY_FAILURE else terminal,
        terminal, policy.authority_id, denial)
