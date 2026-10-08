"""Prospective phase-aware adapter, not a transport executor or retry policy.

Only exact concrete classes and urllib.error.URLError.reason are authorized.
No exception-name/message matching, arbitrary chain search, scientific content,
network, sleeps, journal, process resume, or live-client wiring.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import urllib.error
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from types import MappingProxyType

from . import transport_lifecycle_v2 as lifecycle
from . import transport_observability_v1 as observation


MAPPING_VERSION = "TransportExceptionMappingV2"
BOUND_CLIENT_IDENTITY_SHA256 = "8ea6237d1bbb547c850b83d741adc549f36543c631121264d83e8deb2f486e24"
SEMANTIC_RETRY_CONTRACT_SHA256 = "dc145cc2eeb9d9aaa370c3529854d17834e09103bfd70a020fe362c1678c5f7d"
ALPHA322A_ROOT_SHA256 = "449c8276603e44a5f19a61071dc68762361771cfc4d9a26463d30d6313f50b82"
BACKEND_VALIDATOR_SOURCE_SHA256 = "2abfdd4bad858bbfcf67a624aacf318b62435cf11992388de8fa8e0c18ec826b"
MAPPING_TABLE_SHA256 = "de61dd8f230bf1dd5b9f59da4a930848f1bb03f5941b998b7031bc2cf01b6b26"
RUNTIME_ACTIVATION_ALLOWED = False

S, F = lifecycle.LifecycleState, lifecycle.SemanticFailure
PRE_PHASES = (S.REQUEST_ATTEMPT_STARTED,)
BODY_PHASES = (S.RESPONSE_BODY_READING,)
VALIDATION_PHASES = (S.RAW_RESPONSE_FROZEN, S.RESPONSE_VALIDATION_COMPLETE)
STATUS_PHASES = (S.REQUEST_ATTEMPT_STARTED, S.RESPONSE_HEADERS_RECEIVED, S.RESPONSE_BODY_COMPLETE,
                 S.RAW_RESPONSE_FROZEN, S.RESPONSE_VALIDATION_COMPLETE)
CONCRETE_CLASSES = MappingProxyType({
    "timeout": TimeoutError,
    "reset": ConnectionResetError,
    "incomplete_read": http.client.IncompleteRead,
    "remote_disconnected": http.client.RemoteDisconnected,
    "url_error": urllib.error.URLError,
    "http_error": urllib.error.HTTPError,
    "xml_parse": ET.ParseError,
    "json_parse": json.JSONDecodeError,
})


def qualified(kind: type) -> str:
    return kind.__module__ + "." + kind.__qualname__


def table_record() -> dict:
    """Deterministic table data; no runtime IO or library source guessing."""
    def rule(rule_id, key, phases, semantic, evidence, *, wrapper=None, requirements=()):
        kind = CONCRETE_CLASSES[key]
        return {"rule_id": rule_id, "exception_module": kind.__module__, "exception_qualified_class": qualified(kind),
            "class_binding_key": key, "match_mode": "EXACT_CLASS", "allowed_lifecycle_phases": [s.value for s in phases],
            "semantic_transport_class": semantic.value, "wrapper_requirements": wrapper,
            "structured_field_requirements": list(requirements), "authority_evidence_ids": list(evidence),
            "notes": "Classification only; retry authority remains alpha3.22A."}
    rules = []
    for key in ("timeout", "reset"):
        rules.append(rule(key + "_pre_headers", key, PRE_PHASES, F.PRE_RESPONSE_TRANSPORT_INTERRUPTION,
            ("repository_open_read_sites", "urllib_do_open", "actual_client_synthetic_" + key), requirements=("trusted headers absent", "BODY_COMPLETE absent")))
        rules.append(rule(key + "_body_read", key, BODY_PHASES, F.RESPONSE_BODY_TRANSPORT_INTERRUPTION,
            ("repository_open_read_sites", "http_response_read", "actual_client_synthetic_" + key), requirements=("trusted headers present", "BODY_COMPLETE absent")))
    rules.extend((
        rule("incomplete_read_body", "incomplete_read", BODY_PHASES, F.RESPONSE_BODY_TRANSPORT_INTERRUPTION,
            ("http_safe_read", "actual_client_synthetic_incomplete_read"), requirements=("trusted headers present", "partial is bytes", "expected is null or nonnegative integer", "BODY_COMPLETE absent")),
        rule("remote_disconnected_pre_headers", "remote_disconnected", PRE_PHASES, F.PRE_RESPONSE_TRANSPORT_INTERRUPTION,
            ("http_read_status", "actual_client_synthetic_remote_disconnected"), requirements=("trusted headers absent", "BODY_COMPLETE absent")),
        rule("url_error_reason_pre_headers", "url_error", PRE_PHASES, F.PRE_RESPONSE_TRANSPORT_INTERRUPTION,
            ("urllib_do_open", "url_error_constructor", "actual_client_synthetic_wrapped_timeout"),
            wrapper={"field_path": ["reason"], "maximum_depth": 1, "inner_exact_class_keys": ["timeout", "reset"],
                "cause_authorized": False, "context_authorized": False}, requirements=("trusted headers absent", "BODY_COMPLETE absent")),
        rule("http_error_status", "http_error", (S.REQUEST_ATTEMPT_STARTED, S.RESPONSE_HEADERS_RECEIVED), F.NONRETRYABLE_HTTP_STATUS,
            ("repository_http_error_sites", "http_error_constructor", "legacy_http_status_policy"),
            requirements=("trusted structured HTTP origin", "code integer 100..599", "supplied status agrees with code")),
        rule("complete_xml_parse_failure", "xml_parse", VALIDATION_PHASES, F.COMPLETE_BODY_RESPONSE_VALIDITY_FAILURE,
            ("repository_validator_sites", "complete_parser_synthetic"), requirements=("trusted HTTP 200", "BODY_COMPLETE")),
        rule("complete_json_parse_failure", "json_parse", VALIDATION_PHASES, F.COMPLETE_BODY_RESPONSE_VALIDITY_FAILURE,
            ("backend_validator_source", "complete_parser_synthetic"), requirements=("trusted HTTP 200", "BODY_COMPLETE")),
    ))
    for entry in rules:
        if entry["class_binding_key"] == "http_error":
            entry["semantic_transport_class"] = [F.RETRYABLE_HTTP_STATUS.value, F.NONRETRYABLE_HTTP_STATUS.value]
            entry["semantic_output_owner"] = "http_status_adapter"
    return {"schema_version": MAPPING_VERSION, "mapping_authority_version": MAPPING_VERSION,
        "bound_client_identity_sha256": BOUND_CLIENT_IDENTITY_SHA256,
        "alpha322a_root_sha256": ALPHA322A_ROOT_SHA256, "semantic_retry_contract_sha256": SEMANTIC_RETRY_CONTRACT_SHA256,
        "rules": rules, "http_status_adapter": {"rule_id": "structured_http_status", "accepted_status": 200,
            "retryable_statuses": [408, 429, 500, 502, 503, 504], "policy_authority": lifecycle.MASTER_ROOT_SHA256,
            "allowed_lifecycle_phases": [s.value for s in STATUS_PHASES]},
        "body_completion_adapter": {"rule_id": "structured_body_completion", "owner": "alpha3.22A.assess_body_completion",
            "allowed_lifecycle_phases": [s.value for s in (S.RESPONSE_BODY_READING, S.RESPONSE_BODY_COMPLETE, S.RESPONSE_BODY_INTERRUPTED, S.RAW_RESPONSE_FROZEN)]},
        "backend_adapter": {"rule_id": "frozen_esearch_backend_outcome", "authority_sha256": lifecycle.BACKEND_AUTHORITY_SHA256,
            "validator_source_sha256": BACKEND_VALIDATOR_SOURCE_SHA256, "schema_version": "PubMedESearchResponseValidityV2_1",
            "accepted_structured_state": "NCBI_ESearch_BACKEND_ERROR", "body_complete_required": True,
            "allowed_lifecycle_phases": [s.value for s in VALIDATION_PHASES]},
        "precedence": ["invalid table/client/context -> UNKNOWN", "known outer HTTPError owns structured status",
            "exact exception and authorized phase; URLError delegates only reason one hop",
            "unmapped exception -> UNKNOWN, never fish through its chain",
            "structured alpha322A body interruption/mismatch before status",
            "trusted HTTP status", "frozen backend validator outcome", "complete body -> no technical failure"],
        "default_semantic_class": F.UNKNOWN_RUNTIME_FAILURE.value,
        "scientific_eligibility_fields": False, "runtime_activation_allowed": False}


@dataclass(frozen=True)
class FrozenMappingTableV2:
    serialized: bytes

    def __post_init__(self):
        lifecycle.require(type(self.serialized) is bytes, "MAPPING_TABLE_CANONICAL_BYTES_REQUIRED")

    @property
    def sha256(self):
        return hashlib.sha256(self.serialized).hexdigest()

    def record(self):
        return json.loads(self.serialized)


def default_mapping_table_v2() -> FrozenMappingTableV2:
    return FrozenMappingTableV2(observation.canonical_bytes(table_record()))


@dataclass(frozen=True)
class BackendValidatorOutcomeV2:
    schema_version: str
    state: str
    technical_retryable: bool
    valid_page: bool
    authority_sha256: str
    validator_source_sha256: str

    def __post_init__(self):
        lifecycle.require(all(type(v) is str for v in (self.schema_version, self.state, self.authority_sha256,
            self.validator_source_sha256)) and type(self.technical_retryable) is bool and type(self.valid_page) is bool,
            "INVALID_STRUCTURED_BACKEND_OUTCOME")

    @classmethod
    def from_frozen_validator_result(cls, result: dict, *, authority_sha256: str, validator_source_sha256: str):
        # Only an already-produced structured outcome is projected. No raw body,
        # backend message, prefix predicate or scientific content is inspected.
        return cls(result["schema_version"], result["state"], result["technical_retryable"], result["valid_page"],
                   authority_sha256, validator_source_sha256)


@dataclass(frozen=True)
class TransportMappingFactsV2:
    phase: lifecycle.LifecycleState
    client_identity_sha256: str
    headers_trusted: bool = False
    http_status: int | None = None
    http_status_origin: str | None = None
    body_completion: lifecycle.BodyCompletionResultV2 | None = None
    backend_outcome: BackendValidatorOutcomeV2 | None = None

    def __post_init__(self):
        lifecycle.require(isinstance(self.phase, lifecycle.LifecycleState) and type(self.client_identity_sha256) is str, "MAPPING_CONTEXT_REQUIRED")
        lifecycle.require(type(self.headers_trusted) is bool and
            (self.http_status is None or type(self.http_status) is int and 100 <= self.http_status <= 599), "INVALID_STRUCTURED_HTTP_FACT")
        lifecycle.require(self.http_status_origin is None or type(self.http_status_origin) is str, "INVALID_HTTP_STATUS_ORIGIN")
        lifecycle.require(self.body_completion is None or isinstance(self.body_completion, lifecycle.BodyCompletionResultV2), "INVALID_STRUCTURED_BODY_FACT")
        lifecycle.require(self.backend_outcome is None or isinstance(self.backend_outcome, BackendValidatorOutcomeV2), "INVALID_BACKEND_OUTCOME")


@dataclass(frozen=True)
class TransportMappingResultV2:
    semantic_failure_class: lifecycle.SemanticFailure
    mapping_rule_id: str | None
    mapping_authority_version: str
    mapping_table_sha256: str
    matched_exception_class: str | None
    matched_wrapper_path: tuple[str, ...]
    phase: lifecycle.LifecycleState
    mapping_confidence: str
    diagnostic_state: str
    semantic_retry_contract_sha256: str = SEMANTIC_RETRY_CONTRACT_SHA256

    def record(self):
        return {**self.__dict__, "semantic_failure_class": self.semantic_failure_class.value,
                "phase": self.phase.value, "matched_wrapper_path": list(self.matched_wrapper_path)}


class TransportExceptionMappingV2:
    def __init__(self, table: FrozenMappingTableV2 | None = None):
        self._table = table if table is not None else default_mapping_table_v2()
        lifecycle.require(type(self._table) is FrozenMappingTableV2, "VERSIONED_MAPPING_TABLE_REQUIRED")

    @property
    def table(self):
        return self._table

    def classify(self, exception: BaseException | None, facts: TransportMappingFactsV2) -> TransportMappingResultV2:
        """Pure facts -> semantic class. Does not mutate/capture the exception."""
        lifecycle.require(exception is None or isinstance(exception, BaseException), "ACTUAL_EXCEPTION_OBJECT_REQUIRED_NO_NAME_MAPPING")
        lifecycle.require(isinstance(facts, TransportMappingFactsV2), "STRUCTURED_MAPPING_FACTS_REQUIRED")
        def result(semantic=F.UNKNOWN_RUNTIME_FAILURE, rule=None, matched=None, path=(), confidence="NO_RULE_MATCH", diagnostic="UNMAPPED_RUNTIME_FACTS"):
            return TransportMappingResultV2(semantic, rule, MAPPING_VERSION, self.table.sha256, matched, path, facts.phase, confidence, diagnostic)
        if not isinstance(self.table, FrozenMappingTableV2) or self.table.sha256 != MAPPING_TABLE_SHA256:
            return result(confidence="AMBIGUOUS_MAPPING", diagnostic="MAPPING_AUTHORITY_CONFLICT")
        table = self.table.record()
        if table != table_record() or facts.client_identity_sha256 != BOUND_CLIENT_IDENTITY_SHA256:
            return result(confidence="AMBIGUOUS_MAPPING", diagnostic="UNBOUND_TABLE_OR_CLIENT_IDENTITY")
        completion = facts.body_completion
        complete = completion is not None and completion.body_completion_state == lifecycle.BodyState.COMPLETE
        trusted_status = facts.headers_trusted and facts.http_status_origin in {"BOUND_HTTP_RESPONSE", "BOUND_HTTP_ERROR"}
        if facts.phase == S.REQUEST_NOT_STARTED or facts.phase == S.REQUEST_ATTEMPT_STARTED and (facts.headers_trusted and type(exception) is not urllib.error.HTTPError or completion is not None):
            return result(diagnostic="CONTRADICTORY_PHASE_EVIDENCE")
        if complete and facts.phase not in {S.RESPONSE_BODY_COMPLETE, *VALIDATION_PHASES}:
            return result(diagnostic="CONTRADICTORY_COMPLETION_PHASE")
        if not complete and facts.phase in {S.RESPONSE_BODY_COMPLETE, *VALIDATION_PHASES}:
            # Partial RAW_RESPONSE_FROZEN is an allowed audit lifecycle state,
            # but never accepted as a validation context.
            if not (facts.phase == S.RAW_RESPONSE_FROZEN and completion is not None and completion.body_completion_state != lifecycle.BodyState.COMPLETE):
                return result(diagnostic="COMPLETE_BODY_EVIDENCE_REQUIRED")
        if exception is not None:
            key = next((k for k, kind in CONCRETE_CLASSES.items() if type(exception) is kind), None)
            if key is None:
                return result(diagnostic="EXACT_CONCRETE_CLASS_NOT_AUTHORIZED")
            candidates = [r for r in table["rules"] if r["class_binding_key"] == key and facts.phase.value in r["allowed_lifecycle_phases"]]
            if not candidates:
                return result(matched=qualified(type(exception)), confidence="PHASE_MISMATCH", diagnostic="KNOWN_CLASS_UNAUTHORIZED_PHASE")
            if len(candidates) != 1:
                return result(confidence="AMBIGUOUS_MAPPING", diagnostic="CONFLICTING_MAPPING_RULES")
            rule = candidates[0]
            matched, path = qualified(type(exception)), ()
            semantic = F.UNKNOWN_RUNTIME_FAILURE if key == "http_error" else F(rule["semantic_transport_class"])
            if key == "http_error":
                # Known outer HTTPError owns status; its reason/cause/context
                # can never smuggle in retry authority from an inner error.
                code = vars(exception).get("code")
                if not trusted_status or facts.http_status_origin != "BOUND_HTTP_ERROR" or type(code) is not int or not 100 <= code <= 599 or facts.http_status != code or code == 200:
                    return result(diagnostic="HTTP_ERROR_STRUCTURED_STATUS_UNTRUSTED_OR_CONFLICTING")
                semantic = F.RETRYABLE_HTTP_STATUS if code in table["http_status_adapter"]["retryable_statuses"] else F.NONRETRYABLE_HTTP_STATUS
            elif key in {"xml_parse", "json_parse"}:
                if not complete or not trusted_status or facts.http_status != 200:
                    return result(diagnostic="PARSER_EXCEPTION_WITHOUT_AUTHORITATIVE_COMPLETE_CONTEXT")
            else:
                if facts.phase in PRE_PHASES and facts.headers_trusted or facts.phase in BODY_PHASES and not facts.headers_trusted or complete:
                    return result(diagnostic="MISSING_OR_CONTRADICTORY_PHASE_EVIDENCE")
                if completion is not None and completion.semantic_failure == F.UNKNOWN_RUNTIME_FAILURE:
                    return result(diagnostic="UNKNOWN_BODY_EVIDENCE_DOMINATES")
                if key == "incomplete_read":
                    fields = vars(exception)
                    if not {"partial", "expected"} <= set(fields) or type(fields["partial"]) is not bytes or not (fields["expected"] is None or type(fields["expected"]) is int and fields["expected"] >= 0):
                        return result(diagnostic="INCOMPLETE_READ_FIELDS_NOT_TRUSTWORTHY")
                if key == "url_error":
                    # Exactly one authorized structured edge. No recursion and
                    # no __cause__/__context__ authority, even when present.
                    inner = vars(exception).get("reason")
                    if inner is exception or type(inner) not in {TimeoutError, ConnectionResetError}:
                        return result(diagnostic="URL_ERROR_REASON_UNAUTHORIZED_OR_CYCLIC")
                    if exception.__cause__ is exception or exception.__context__ is exception or inner.__cause__ in (exception, inner) or inner.__context__ in (exception, inner):
                        # urllib's real wrapper points outer.__context__ to
                        # inner, not the reverse. A reverse edge is a cycle.
                        return result(diagnostic="AUTHORIZED_WRAPPER_CYCLE")
                    matched, path = qualified(type(inner)), ("reason",)
            confidence = "AUTHORIZED_WRAPPED_CAUSE_MATCH" if path else "EXACT_RULE_MATCH"
            return result(semantic, rule["rule_id"], matched, path, confidence, "AUTHORIZED_CONCRETE_RULE")
        if completion is not None and completion.body_completion_state != lifecycle.BodyState.COMPLETE:
            if facts.phase.value not in table["body_completion_adapter"]["allowed_lifecycle_phases"] or not facts.headers_trusted:
                return result(diagnostic="BODY_COMPLETION_SIGNAL_PHASE_MISMATCH")
            return result(completion.semantic_failure, "structured_body_completion", confidence="EXACT_RULE_MATCH", diagnostic="ALPHA322A_BODY_COMPLETION_OUTCOME")
        if facts.http_status is not None:
            if not trusted_status or facts.phase not in STATUS_PHASES:
                return result(diagnostic="UNTRUSTED_HTTP_STATUS_OR_PHASE")
            if facts.http_status != 200:
                semantic = F.RETRYABLE_HTTP_STATUS if facts.http_status in table["http_status_adapter"]["retryable_statuses"] else F.NONRETRYABLE_HTTP_STATUS
                return result(semantic, "structured_http_status", confidence="EXACT_RULE_MATCH", diagnostic="UNCHANGED_BOUND_STATUS_PREDICATE")
        if facts.backend_outcome is not None:
            backend = facts.backend_outcome
            if not complete or not trusted_status or facts.http_status != 200 or facts.phase not in VALIDATION_PHASES:
                return result(diagnostic="BACKEND_OUTCOME_WITHOUT_COMPLETE_VALIDATION_CONTEXT")
            if (backend.authority_sha256, backend.validator_source_sha256, backend.schema_version, backend.state,
                backend.technical_retryable, backend.valid_page) != (lifecycle.BACKEND_AUTHORITY_SHA256,
                BACKEND_VALIDATOR_SOURCE_SHA256, "PubMedESearchResponseValidityV2_1", "NCBI_ESearch_BACKEND_ERROR", True, False):
                return result(diagnostic="BACKEND_OUTCOME_UNBOUND_OR_NOT_AUTHORIZED")
            return result(F.RETRYABLE_PROVIDER_BACKEND_FAILURE, "frozen_esearch_backend_outcome", confidence="EXACT_RULE_MATCH", diagnostic="FROZEN_VALIDATOR_STRUCTURED_OUTCOME")
        if complete and trusted_status and facts.http_status == 200:
            return result(F.NO_TECHNICAL_FAILURE, "complete_body_no_technical_failure", confidence="EXACT_RULE_MATCH", diagnostic="SCIENTIFIC_VALIDITY_NOT_IMPLIED")
        return result()


@dataclass(frozen=True)
class ClassifiedRetryDecisionV2:
    mapping: TransportMappingResultV2
    retry: lifecycle.SemanticRetryDecisionV2

    def record(self):
        return {"schema_version": "ClassifiedRetryDecisionV2", "mapping": self.mapping.record(),
            "retry": {k: v.value if isinstance(v, F) else v for k, v in self.retry.__dict__.items()},
            "semantic_retry_contract_sha256": SEMANTIC_RETRY_CONTRACT_SHA256}


def classify_transport_failure_and_decide_retry_v2(exception: BaseException | None, facts: TransportMappingFactsV2, *,
        request_replay_safe: bool, attempt_ordinal: int, mapper: TransportExceptionMappingV2 | None = None) -> ClassifiedRetryDecisionV2:
    active_mapper = mapper if mapper is not None else TransportExceptionMappingV2()
    lifecycle.require(type(active_mapper) is TransportExceptionMappingV2, "EXACT_VERSIONED_MAPPER_REQUIRED")
    mapping = active_mapper.classify(exception, facts)
    backend_authority = lifecycle.BACKEND_AUTHORITY_SHA256 if mapping.mapping_rule_id == "frozen_esearch_backend_outcome" else None
    # The ONLY retry decision owner. No duplicate exception->retry matrix.
    retry = lifecycle.semantic_retry_decision(mapping.semantic_failure_class, request_replay_safe=request_replay_safe,
        attempt_ordinal=attempt_ordinal, policy=lifecycle.SemanticRetryPolicyV2(provider_backend_authority=backend_authority))
    return ClassifiedRetryDecisionV2(mapping, retry)


def mapped_observation_v2(decision: ClassifiedRetryDecisionV2, attempt: lifecycle.TransportLifecycleV2,
        redactor: observation.SecretRedactorV1, *, original_exception: BaseException | None = None,
        http: observation.HttpResponseProvenanceV1 | None = None, body: observation.BodyReadProvenanceV1 | None = None,
        replay_safety_authority: dict | None = None, runtime_identity: dict | None = None) -> observation.FrozenObservationRecordV1:
    """Additional controller record wrapping, never editing, 22A provenance."""
    captured = observation.ExceptionProvenanceV1.capture(original_exception, attempt.context, redactor,
        runtime_identity=runtime_identity) if original_exception is not None else None
    if captured is not None and captured.provenance is None:
        captured.reraise_original()  # no logging failure may create a new attempt
    retry = observation.RetryDecisionProvenanceV1.capture(attempt.context, redactor, decision.retry,
        replay_safety_authority=replay_safety_authority)
    aggregate = observation.TransportAttemptObservationV1.capture(attempt, redactor,
        exception=captured.provenance if captured is not None else None, http=http, body=body, retry=retry)
    return observation.FrozenObservationRecordV1.from_record({"schema_version": "MappedTransportObservationV2",
        "mapping": decision.mapping.record(), "observation": aggregate.record()}, redactor)
