"""Pure planning over verified events; no network, writes, retry or sleep."""

from dataclasses import dataclass

from . import append_only_attempt_journal_v2 as j


LOGICAL_STATES = ("NOT_STARTED", "IN_PROGRESS", "RETRYABLE_FAILURE_WITH_BUDGET", "VALID_SUCCESS",
    "VALID_NONELIGIBLE_RESPONSE", "TERMINAL_TECHNICAL_FAILURE", "TERMINAL_RESPONSE_VALIDITY_FAILURE", "NOT_REQUIRED", j.ABANDONED)
SKIPPED = {"VALID_SUCCESS", "VALID_NONELIGIBLE_RESPONSE", "NOT_REQUIRED"}


@dataclass(frozen=True)
class LogicalRequestExecutionStateV2:
    serialized: bytes

    def record(self):
        return j.strict_json(self.serialized)


@dataclass(frozen=True)
class CrashRecoveryStateV2:
    state: str
    attempts_consumed: int
    replay_safe: bool
    continuation_authorized: bool
    next_ordinal: int | None
    backoff_seconds: int
    authority_sha256: str = j.t.MASTER_ROOT_SHA256


def abandoned_recovery(request, consumed):
    """Apply ONLY the explicit master restart rule, not an exception matrix.

    ABANDONED remains unknown; it is not mapped to transport interruption.
    A's immutable policy object owns numeric budgets and backoff. Completed
    UNKNOWN_RUNTIME_FAILURE decisions never pass through this restart rule.
    """
    j.require(1 <= consumed <= j.POLICY.maximum_attempts, "ABANDONED_CONSUMPTION_INVALID")
    permitted = request["replay_safe"] and consumed < j.POLICY.maximum_attempts
    return CrashRecoveryStateV2(j.ABANDONED, consumed, request["replay_safe"], permitted,
        consumed + 1 if permitted else None, j.POLICY.backoff_seconds[consumed - 1] if permitted else 0)


def resume_plan_schema_v2():
    nullable_string = {"type": ["string", "null"]}
    request_fields = {"request_id": {"type": "string"},
        "request_payload_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "request_order_position": {"type": "integer", "minimum": 0},
        "current_derived_state": {"enum": list(LOGICAL_STATES)},
        "attempts_consumed": {"type": "integer", "minimum": 0, "maximum": j.POLICY.maximum_attempts},
        "remaining_attempts": {"type": "integer", "minimum": 0, "maximum": j.POLICY.maximum_attempts},
        "next_authorized_ordinal": {"type": ["integer", "null"], "minimum": 1, "maximum": j.POLICY.maximum_attempts},
        "backoff_seconds": {"enum": [0, *j.POLICY.backoff_seconds]},
        "retry_continuation_eligible": {"type": "boolean"}, "execution_required": {"type": "boolean"},
        "scheduled_in_resume_plan": {"type": "boolean"}, "terminal_reason": nullable_string,
        "reason_for_skipping": nullable_string, "abandoned_classification_persisted": {"type": "boolean"},
        "recovery_authority_sha256": nullable_string}
    request_schema = {"type": "object", "additionalProperties": False,
                      "properties": request_fields, "required": list(request_fields)}
    fields = {"schema_version": {"const": "ResumePlanV2"}, "manifest_sha256": {"type": "string"},
        "journal_tip_sha256": {"type": "string"}, "requests": {"type": "array", "items": request_schema},
        "executable_request_ids": {"type": "array", "items": {"type": "string"}},
        "next_executable_request_id": {"type": ["string", "null"]}, "blocking_reason": {"type": ["string", "null"]},
        "stage_complete": {"type": "boolean"}, "barrier_sha256": {"type": ["string", "null"]},
        "activation_sha256": {"type": ["string", "null"]}, "authority": {"type": "object"}}
    return {"type": "object", "additionalProperties": False, "properties": fields, "required": list(fields)}


@dataclass(frozen=True)
class ResumePlanV2:
    serialized: bytes

    def __post_init__(self):
        record = self.record()
        j.o.validate_schema(record, resume_plan_schema_v2())
        j.require(j.canonical(record) == self.serialized and record["authority"] == j.AUTHORITY, "RESUME_PLAN_BINDING")

    def record(self):
        return j.strict_json(self.serialized)


class DeterministicResumePlannerV2:
    def build(self, journal):
        j.require(type(journal) is j.VerifiedJournalV2, "VERIFIED_JOURNAL_REQUIRED")
        # Reverify immutable event bytes, chain, raw references and snapshots.
        j.JournalIntegrityVerifierV2.verify_events(journal.events, journal.manifest, journal.directory)
        states, barrier, activation = j._reduce(journal.events, journal.manifest, journal.directory)
        records, executable = [], []
        blocking = None
        for request in journal.manifest.record()["requests"]:
            key = request["request_id"]
            saved = states[key]
            consumed = len(saved["attempts"])
            state = saved["outcome"] or "NOT_STARTED"
            next_ordinal, backoff, reason, recovery = None, 0, None, None
            phase_ready = request["stage"] == "OA" or activation is not None
            if request["stage"] == "JATS" and activation is not None and key in activation.record()["not_required_request_ids"]:
                j.require(not consumed, "NOT_REQUIRED_REQUEST_WAS_DISPATCHED")
                state = "NOT_REQUIRED"
            elif consumed:
                attempt = saved["attempts"][-1]
                if attempt["terminal"] is None:
                    state = j.ABANDONED
                    recovery = abandoned_recovery(request, consumed)
                    if recovery.continuation_authorized:
                        next_ordinal, backoff = recovery.next_ordinal, recovery.backoff_seconds
                    else:
                        reason = "REQUEST_NOT_REPLAY_SAFE" if not request["replay_safe"] else "ATTEMPT_BUDGET_EXHAUSTED"
                elif state == "RETRYABLE_FAILURE_WITH_BUDGET":
                    decision = attempt["terminal"]["retry_decision"]
                    next_ordinal, backoff = decision["next_attempt_ordinal"], decision["backoff_selected_seconds"]
                elif state.startswith("TERMINAL_"):
                    reason = attempt["terminal"]["retry_decision"]["denial_reason"]
            elif phase_ready and state != "NOT_REQUIRED":
                next_ordinal = 1
            skip = "TRUSTED_TERMINAL_" + state if state in SKIPPED else None
            required = state not in SKIPPED
            eligible = required and phase_ready and next_ordinal is not None
            if blocking is None and required:
                if not phase_ready:
                    blocking = "AWAITING_FROZEN_ACTIVATION" if barrier is not None else "AWAITING_FROZEN_OA_BARRIER"
                elif not eligible:
                    blocking = "TERMINAL_OR_UNAUTHORIZED_REQUEST:" + key
            # Never cross an earlier blocking terminal request or barrier.
            scheduled = eligible and blocking is None
            if scheduled:
                executable.append(key)
            records.append(LogicalRequestExecutionStateV2(j.canonical({"request_id": key,
                "request_payload_sha256": request["request_payload_sha256"], "request_order_position": request["execution_order"],
                "current_derived_state": state, "attempts_consumed": consumed,
                "remaining_attempts": j.POLICY.maximum_attempts - consumed, "next_authorized_ordinal": next_ordinal,
                "backoff_seconds": backoff, "retry_continuation_eligible": eligible, "execution_required": required,
                "scheduled_in_resume_plan": scheduled, "terminal_reason": reason, "reason_for_skipping": skip,
                "abandoned_classification_persisted": bool(consumed and saved["attempts"][-1]["abandoned"]),
                "recovery_authority_sha256": recovery.authority_sha256 if recovery else None})).record())
        # A pending later-stage barrier does not block execution of earlier OA
        # work. Terminal failure always blocks; completed OA needs barrier freeze.
        operational_block = blocking
        if executable and blocking in {"AWAITING_FROZEN_OA_BARRIER", "AWAITING_FROZEN_ACTIVATION"}:
            operational_block = None
        record = {"schema_version": "ResumePlanV2", "manifest_sha256": journal.manifest.sha256,
            "journal_tip_sha256": journal.last_hash, "authority": j.AUTHORITY, "requests": records,
            "executable_request_ids": executable if operational_block is None else [],
            "next_executable_request_id": executable[0] if executable and operational_block is None else None,
            "blocking_reason": operational_block, "stage_complete": all(r["current_derived_state"] in SKIPPED for r in records),
            "barrier_sha256": barrier.sha256 if barrier else None, "activation_sha256": activation.sha256 if activation else None}
        return ResumePlanV2(j.canonical(record))
