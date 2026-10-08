"""Offline-capable provenance records; capture is never retry authority.

No concrete exception mapping, network adapter, journal or process recovery.
Callers must supply known credential values, client identity and trusted facts.
Records are immutable canonical bytes, redacted before any artifact persistence.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import re
import traceback
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .transport_lifecycle_v2 import (
    AttemptContextV1, BodyCompletionResultV2, BodyState, RawArtifactV1,
    RawArtifactStoreV1, SemanticFailure, SemanticRetryDecisionV2,
    TransportLifecycleV2, require,
)


REDACTED = "[REDACTED]"
SENSITIVE_KEYS = frozenset({"authorization", "proxyauthorization", "cookie", "setcookie", "apikey",
    "xapikey", "accesskey", "accesstoken", "refreshtoken", "password", "passwd", "clientsecret",
    "privatekey", "credentials", "credential", "secret", "token", "key", "signature"})
TIMESTAMP_FIELDS = frozenset({"timestamp", "response_started_at", "headers_received_at", "body_read_started_at",
    "body_read_ended_at", "body_read_failed_at", "completion_timestamp", "interruption_timestamp"})


def sensitive_key(value: str) -> bool:
    return re.sub(r"[^a-z0-9]", "", value.casefold()) in SENSITIVE_KEYS


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"


class SecretRedactorV1:
    def __init__(self, known_secret_values: tuple[str, ...] = ()):
        require(type(known_secret_values) is tuple and all(type(s) is str and s for s in known_secret_values), "INVALID_SECRET_SET")
        self._values = tuple(sorted(set(known_secret_values), key=lambda s: (-len(s), s)))

    def _known(self, value: str) -> str:
        for secret in self._values:
            value = value.replace(secret, REDACTED)
        return value

    def url(self, value: str) -> str:
        try:
            parts = urlsplit(value)
            require(parts.scheme in {"http", "https"} and parts.hostname is not None, "UNSUPPORTED_OBSERVABILITY_URL")
            # Never persist userinfo. A malformed port also fails closed here.
            hostname = parts.hostname
            hostname = "[" + hostname + "]" if ":" in hostname else hostname
            netloc = hostname + (":" + str(parts.port) if parts.port is not None else "")
            if parts.username is not None or parts.password is not None:
                netloc = "REDACTED@" + netloc
            query = [(self._known(k), REDACTED if sensitive_key(k) else self._known(v)) for k, v in parse_qsl(parts.query, keep_blank_values=True)]
            return self._known(urlunsplit((parts.scheme, netloc, parts.path, urlencode(query), REDACTED if parts.fragment else "")))
        except Exception:
            # Observability-only catch. No classification, retry or raw fallback.
            return "[UNAVAILABLE_SANITIZED_URL]"

    def text(self, value: str) -> str:
        urls = []
        def replace_url(match):
            urls.append(self.url(match.group(0)))
            return f"<SANITIZED_URL_{len(urls) - 1}>"
        value = re.sub(r"https?://[^\s<>\"']+", replace_url, value)
        value = re.sub(r"(?i)\bBearer\s+[^\s,;\"']+", "Bearer " + REDACTED, value)
        value = re.sub(r"(?im)^(\s*(?:authorization|proxy-authorization|cookie|set-cookie)\s*:)\s*[^\n]*",
                       lambda m: m.group(1) + REDACTED, value)
        # Also mask embedded header text in exception repr/tracebacks, including
        # multi-value cookies and Basic credentials whose value contains spaces.
        value = re.sub(r"(?i)(\b(?:authorization|proxy[-_]authorization|cookie|set[-_]cookie)[\"']?\s*[:=]\s*)(?:\"[^\"\n]*\"|'[^'\n]*'|[^\n\"']+)",
                       lambda m: m.group(1) + REDACTED, value)
        keys = r"authorization|proxy[-_ ]?authorization|set[-_ ]?cookie|cookie|api[-_ ]?key|x[-_ ]?api[-_ ]?key|access[-_ ]?token|refresh[-_ ]?token|password|passwd|client[-_ ]?secret|private[-_ ]?key|credentials?|secret|token|key|signature"
        def replace_credential(match):
            original = match.group(2)
            quote = original[0] if original.startswith(("'", '"')) else ""
            return match.group(1) + quote + REDACTED + quote
        value = re.sub(r"(?im)(\b(?:" + keys + r")[\"']?\s*[:=]\s*)(\[REDACTED\]|\"[^\"]*\"|'[^']*'|[^\s\n,;)}\]]+)",
                       replace_credential, value)
        value = re.sub(r"0x[0-9a-fA-F]+", "0x[ADDRESS]", value)
        value = self._known(value)
        for i, url in enumerate(urls):
            value = value.replace(f"<SANITIZED_URL_{i}>", url)
        return value

    def tree(self, value: Any, path: str = "$") -> tuple[Any, tuple[str, ...]]:
        paths: list[str] = []

        def walk(item, here):
            if isinstance(item, dict):
                result = {}
                header_secret = isinstance(item.get("name"), str) and sensitive_key(item["name"]) and "value" in item
                for key in sorted(item):
                    require(type(key) is str, "JSON_OBJECT_STRING_KEY_REQUIRED")
                    clean_key = self.text(key)
                    require(clean_key not in result, "REDACTION_KEY_COLLISION")
                    child = here + "." + clean_key
                    if sensitive_key(key) or header_secret and key == "value":
                        result[clean_key] = REDACTED
                        paths.append(child)
                    else:
                        result[clean_key] = walk(item[key], child)
                    if clean_key != key:
                        paths.append(child)
                return result
            if isinstance(item, list):
                return [walk(v, f"{here}[{i}]") for i, v in enumerate(item)]
            if isinstance(item, str):
                cleaned = self.text(item)
                if cleaned != item:
                    paths.append(here)
                return cleaned
            require(item is None or type(item) in {bool, int, float}, "NON_JSON_OBSERVABILITY_VALUE")
            return item

        return walk(value, path), tuple(sorted(set(paths)))


def semantic_payload(record: dict) -> dict:
    """Exclude only named clocks; never erase scientific/request identity."""
    def walk(value):
        if isinstance(value, dict):
            return {k: walk(v) for k, v in value.items() if k not in TIMESTAMP_FIELDS}
        if isinstance(value, list):
            return [walk(v) for v in value]
        return value
    return walk(record)


def validate_schema(value: Any, schema: dict, path: str = "$") -> None:
    """Strict local validator for the keywords used by the frozen master schemas.

    This is not a general JSON Schema implementation. Unknown validation
    keywords fail closed instead of silently being ignored.
    """
    require(not (set(schema) - {"$schema", "$id", "title", "description", "type", "const", "enum", "properties",
        "required", "additionalProperties", "items", "minimum", "maximum", "pattern"}), "UNSUPPORTED_SCHEMA_KEYWORD:" + path)
    if "const" in schema:
        require(value == schema["const"] and type(value) is type(schema["const"]), "SCHEMA_CONST:" + path)
    if "enum" in schema:
        require(any(type(value) is type(v) and value == v for v in schema["enum"]), "SCHEMA_ENUM:" + path)
    types = schema.get("type")
    if types:
        types = [types] if isinstance(types, str) else types
        valid = {"null": value is None, "string": type(value) is str, "integer": type(value) is int,
                 "number": type(value) in {int, float} and math.isfinite(value), "boolean": type(value) is bool,
                 "array": type(value) is list, "object": type(value) is dict}
        require(all(t in valid for t in types) and any(valid[t] for t in types), "SCHEMA_TYPE:" + path)
    if type(value) in {int, float}:
        require(math.isfinite(value), "NONFINITE_JSON_NUMBER")
        require("minimum" not in schema or value >= schema["minimum"], "SCHEMA_MINIMUM:" + path)
        require("maximum" not in schema or value <= schema["maximum"], "SCHEMA_MAXIMUM:" + path)
    if type(value) is str and "pattern" in schema:
        require(re.search(schema["pattern"], value) is not None, "SCHEMA_PATTERN:" + path)
    if type(value) is dict:
        require(all(type(k) is str for k in value), "NON_STRING_JSON_KEY")
        require(set(schema.get("required", [])) <= set(value), "SCHEMA_REQUIRED:" + path)
        properties = schema.get("properties", {})
        extra = set(value) - set(properties)
        additional = schema.get("additionalProperties", True)
        require(additional is not False or not extra, "SCHEMA_ADDITIONAL_PROPERTIES:" + path)
        for key in sorted(value):
            subschema = properties.get(key, additional if isinstance(additional, dict) else {})
            validate_schema(value[key], subschema, path + "." + key)
    if type(value) is list and "items" in schema:
        for i, child in enumerate(value):
            validate_schema(child, schema["items"], f"{path}[{i}]")


@dataclass(frozen=True)
class FrozenObservationRecordV1:
    _serialized: bytes

    def __post_init__(self):
        require(type(self._serialized) is bytes, "CANONICAL_OBSERVATION_BYTES_REQUIRED")
        record = json.loads(self._serialized)
        require(type(record) is dict, "OBSERVATION_RECORD_OBJECT_REQUIRED")
        sanitized, _ = SecretRedactorV1().tree(record)
        require(canonical_bytes(sanitized) == self._serialized, "OBSERVATION_NOT_CANONICAL_OR_NOT_REDACTED")

    @classmethod
    def from_record(cls, record: dict, redactor: SecretRedactorV1):
        clean, _ = redactor.tree(record)
        return cls(canonical_bytes(clean))

    def record(self) -> dict:
        return json.loads(self._serialized)

    def freeze(self, store: RawArtifactStoreV1, name: str) -> RawArtifactV1:
        return store.freeze_bytes(name, self._serialized)


def envelope(version: str, context: AttemptContextV1, fields: dict) -> dict:
    require(isinstance(context, AttemptContextV1), "PROVENANCE_CONTEXT_REQUIRED")
    unavailable = {k: "NOT_AVAILABLE_FROM_SUPPLIED_EVIDENCE" for k, v in fields.items() if v is None}
    return {"schema_version": version, **context.record(), **fields, "unavailable_fields": unavailable}


def tagged_arg(value: Any, active: set[int] | None = None) -> dict:
    active = set() if active is None else active
    kind = type(value).__module__ + "." + type(value).__qualname__
    if value is None or type(value) in {str, bool, int}:
        return {"type": kind, "value": value}
    if type(value) is float and math.isfinite(value):
        return {"type": kind, "value": value}
    if type(value) is bytes:
        return {"type": kind, "length": len(value), "sha256": hashlib.sha256(value).hexdigest()}
    if type(value) in {list, tuple, dict}:
        if id(value) in active:
            return {"type": kind, "unavailable_reason": "CYCLIC_ARGUMENT"}
        active.add(id(value))
        try:
            if type(value) is dict:
                if not all(type(k) is str for k in value):
                    return {"type": kind, "unavailable_reason": "NON_STRING_DICTIONARY_KEYS"}
                result = {k: tagged_arg(value[k], active) for k in sorted(value)}
            else:
                result = [tagged_arg(v, active) for v in value]
            return {"type": kind, "value": result}
        finally:
            active.remove(id(value))
    return {"type": kind, "unavailable_reason": "UNSUPPORTED_VALUE_NO_OBJECT_REPR"}


@dataclass(frozen=True)
class CaptureOutcomeV1:
    original_exception: BaseException
    provenance: ExceptionProvenanceV1 | None
    secondary_observability_failure: dict | None

    def reraise_original(self):
        raise self.original_exception.with_traceback(self.original_exception.__traceback__)


class ExceptionProvenanceV1(FrozenObservationRecordV1):
    @classmethod
    def capture(cls, exception: BaseException, context: AttemptContextV1, redactor: SecretRedactorV1,
                *, runtime_identity: dict | None = None) -> CaptureOutcomeV1:
        require(isinstance(exception, BaseException), "EXCEPTION_OBJECT_REQUIRED_NO_NAME_RECONSTRUCTION")
        try:
            nodes: list[dict] = []
            seen: dict[int, str] = {}
            active: set[int] = set()

            def visit(exc):
                if exc is None:
                    return None
                if id(exc) in seen:
                    if id(exc) in active:
                        for node in nodes:
                            if node["node_id"] == seen[id(exc)]:
                                node["chain_cycle_detected"] = True
                    return seen[id(exc)]
                node_id = "exception_" + str(len(nodes) + 1)
                seen[id(exc)] = node_id
                active.add(id(exc))
                kind = type(exc)
                fields = {"node_id": node_id, "module": kind.__module__, "class_name": kind.__name__,
                    "qualified_class_name": kind.__module__ + "." + kind.__qualname__, "message": str(exc), "repr": repr(exc),
                    "args": [tagged_arg(v) for v in exc.args],
                    "traceback": "".join(traceback.format_exception(kind, exc, exc.__traceback__, chain=False)) if exc.__traceback__ is not None else None,
                    "cause_node_id": None, "context_node_id": None, "suppress_context": exc.__suppress_context__,
                    "chain_cycle_detected": False, "unavailable_fields": {}}
                nodes.append(fields)
                fields["cause_node_id"] = visit(exc.__cause__)
                fields["context_node_id"] = visit(exc.__context__)
                fields["unavailable_fields"] = {k: "NOT_PRESENT_ON_EXCEPTION_OBJECT" for k, v in fields.items() if v is None}
                active.remove(id(exc))
                return node_id

            root = visit(exception)
            identity = runtime_identity if runtime_identity is not None else {
                "python_version": platform.python_version(), "client_module": "UNAVAILABLE", "client_version": None,
                "client_code_sha256": "UNAVAILABLE"}
            record = envelope("TransportExceptionProvenanceV1", context, {
                "root_exception_node_id": root, "exception_nodes": nodes, "runtime_identity": identity,
                "redaction_applied": True, "redaction_paths": []})
            record["unavailable_fields"].update({"runtime_identity." + k: "CLIENT_IDENTITY_NOT_SUPPLIED" for k, v in identity.items() if v is None or v == "UNAVAILABLE"})
            clean, paths = redactor.tree(record)
            clean["redaction_paths"] = list(paths)
            provenance = cls(canonical_bytes(clean))
            return CaptureOutcomeV1(exception, provenance, None)
        except Exception as secondary:
            # Retain the actual original object; never convert logging failure
            # into retry eligibility or replace it with an opaque wrapper.
            kind = type(secondary)
            return CaptureOutcomeV1(exception, None, {"state": "OBSERVABILITY_CAPTURE_FAILED_NO_NEW_ATTEMPT",
                "qualified_class_name": kind.__module__ + "." + kind.__qualname__})


class HttpResponseProvenanceV1(FrozenObservationRecordV1):
    @classmethod
    def capture(cls, context: AttemptContextV1, redactor: SecretRedactorV1, *, method: str,
                request_url: str | None = None, status: int | None = None, reason: str | None = None,
                headers: tuple[tuple[str, str], ...] | None = None, expected_length: int | None = None,
                body_byte_representation: str | None = None, connection_state: str | None = None,
                headers_received_at: str | None = None, trusted: bool = False, status_origin: str | None = None):
        require(type(trusted) is bool and type(method) is str and bool(method), "INVALID_HTTP_FACTS")
        require(status is None or type(status) is int and status >= 0, "INVALID_HTTP_STATUS")
        require(expected_length is None or type(expected_length) is int and expected_length >= 0, "INVALID_HTTP_LENGTH")
        require(headers is None or type(headers) is tuple and all(type(h) is tuple and len(h) == 2 and all(type(v) is str for v in h) for h in headers), "INVALID_HEADERS")
        # Preserve header multiplicity; do not silently pick one conflicting CL.
        pairs = None if headers is None else [{"name": k, "value": v} for k, v in headers]
        def single(name):
            values = [v for k, v in headers or () if k.casefold() == name]
            return values[0] if len(values) == 1 else None
        return cls.from_record(envelope("HTTPResponseProvenanceV1", context, {
            "request_method": method, "request_url_without_secrets": redactor.url(request_url) if request_url is not None else None,
            "request_identity_sha256": context.request_payload_sha256, "status": status, "reason": reason,
            "response_headers": pairs, "content_length_raw": single("content-length"),
            "expected_content_length_bytes": expected_length, "transfer_encoding": single("transfer-encoding"),
            "content_encoding": single("content-encoding"), "body_byte_representation": body_byte_representation,
            "connection_state": connection_state, "headers_received_at": headers_received_at,
            "HTTP_provenance_trusted": trusted, "status_origin": status_origin}), redactor)


class BodyReadProvenanceV1(FrozenObservationRecordV1):
    @classmethod
    def capture(cls, context: AttemptContextV1, redactor: SecretRedactorV1, completion: BodyCompletionResultV2,
                artifact: RawArtifactV1, *, started_at: str | None = None, parser_invoked: bool = False):
        artifact.verified_bytes()
        require(artifact.sha256 == completion.observed_bytes_sha256 and artifact.byte_count == completion.bytes_read, "BODY_ARTIFACT_BINDING_FAILED")
        require(type(parser_invoked) is bool and (not parser_invoked or completion.body_completion_state == BodyState.COMPLETE), "PARTIAL_PARSER_INVOCATION_FORBIDDEN")
        complete = completion.body_completion_state == BodyState.COMPLETE
        return cls.from_record(envelope("BodyReadProvenanceV1", context, {
            "body_read_started_at": started_at, "body_read_ended_at": completion.completion_timestamp,
            "body_read_failed_at": completion.interruption_timestamp, "bytes_read": completion.bytes_read,
            "partial_body_artifact_path": None if complete else artifact.artifact_path,
            "partial_body_sha256": None if complete else artifact.sha256,
            "complete_body_artifact_path": artifact.artifact_path if complete else None,
            "complete_body_sha256": completion.body_sha256, "expected_content_length_bytes": completion.expected_content_length,
            "read_returned_normally": completion.read_returned_normally,
            "framing_integrity_checks": [{"check_name": e.check_name, "passed": e.passed, "authoritative": e.authoritative,
                "failure_class": e.failure_class.value, "evidence_reference": e.evidence_reference} for e in completion.framing_integrity_evidence],
            "completion_state": completion.body_completion_state.value,
            "semantic_failure_state": None if complete else completion.semantic_failure.value, "parser_invoked": parser_invoked}), redactor)


class RetryDecisionProvenanceV1(FrozenObservationRecordV1):
    @classmethod
    def capture(cls, context: AttemptContextV1, redactor: SecretRedactorV1, decision: SemanticRetryDecisionV2,
                *, replay_safety_authority: dict | None = None):
        require(decision.attempt_ordinal == context.attempt_ordinal and decision.decision_authority_identifier == context.runtime_contract_sha256,
                "RETRY_DECISION_CONTEXT_MISMATCH")
        require(not decision.request_replay_safe or bool(replay_safety_authority), "REPLAY_SAFETY_AUTHORITY_REQUIRED")
        return cls.from_record(envelope("TransportRetryDecisionProvenanceV2", context, {
            "semantic_transport_classification": decision.semantic_failure.value, "retryable": decision.retryable_semantic_class,
            "retry_decision_authority": {"runtime_contract_sha256": decision.decision_authority_identifier,
                "maximum_attempts": decision.max_attempts, "retry_authorized": decision.retry_authorized,
                "next_attempt_ordinal": decision.next_attempt_ordinal, "terminal_state": decision.terminal_state,
                "denial_reason": decision.denial_reason}, "request_replay_safe": decision.request_replay_safe,
            "replay_safety_authority": replay_safety_authority,
            "remaining_attempts_before_decision": decision.remaining_attempts_before_decision,
            "remaining_attempts_after_decision": decision.remaining_attempts_after_decision,
            "backoff_selected_seconds": decision.backoff_selected_seconds, "decision": decision.decision}), redactor)


class TransportAttemptObservationV1(FrozenObservationRecordV1):
    @classmethod
    def capture(cls, lifecycle: TransportLifecycleV2, redactor: SecretRedactorV1, *, response_started_at: str | None = None,
                exception: ExceptionProvenanceV1 | None = None, http: HttpResponseProvenanceV1 | None = None,
                body: BodyReadProvenanceV1 | None = None, retry: RetryDecisionProvenanceV1 | None = None):
        records = {"exception_provenance": exception, "http_response_provenance": http,
                   "body_read_provenance": body, "retry_decision_provenance": retry}
        for record in records.values():
            if record is not None:
                require(all(record.record()[k] == v for k, v in lifecycle.context.record().items()), "OBSERVATION_CONTEXT_MISMATCH")
        fields = {key: value.record() if value is not None else None for key, value in records.items()}
        fields.update({"response_started_at": response_started_at, "actual_length_bytes": lifecycle.completion.actual_content_length if lifecycle.completion else None,
            "lifecycle_state": lifecycle.state.value,
            "lifecycle_events": [{**e.context.record(), "previous_state": e.previous_state.value, "state": e.state.value,
                "timestamp": e.timestamp, "evidence_reference": e.evidence_reference} for e in lifecycle.events],
            "journal_persistence_implemented": False, "process_resume_implemented": False})
        return cls.from_record(envelope("TransportAttemptObservationV1", lifecycle.context, fields), redactor)
