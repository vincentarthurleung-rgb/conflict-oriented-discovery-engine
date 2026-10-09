"""Independent 22D oracle. No SUT imports, execution, or result-derived values.

Expected outcomes are prospective literals from the frozen master and the
22D request. They are never produced by A/B/C functions. Unknown test
coverage remains unexecuted if the first critical defect stops the gate.
"""

CONSUMERS = ("generic_parser", "jats_structure", "primary_identity", "license_parser", "body_normalizer", "scientific_extractor")
STAGE_IDENTITY = "POST_ALPHA3_21_INDEPENDENT_TRANSPORT_CRASH_FAULT_VALIDATION"


def transport_spec(identifier, title, signal, phase, semantic, state, *, ordinal=1, safe=True,
                   complete=False, parser_counts=None, retry=False, next_ordinal=None, backoff=0,
                   raw_trust="NO_RESPONSE", length="UNAVAILABLE"):
    request_id = identifier + ":OA:0"
    expected = {"semantic_failure_class": semantic, "retry_authorized": retry, "attempts_consumed": ordinal,
        "next_attempt_ordinal": next_ordinal, "backoff_seconds": backoff,
        "parser_invocation_counts": dict.fromkeys(CONSUMERS, 0) if parser_counts is None else parser_counts,
        "journal_integrity": "VERIFIED", "terminal_logical_state": state,
        "resume_executable_ids": [request_id] if retry else [], "stage_barrier_state": "ABSENT",
        "raw_artifact_trust": raw_trust, "body_complete": complete, "content_length_match": length,
        "durable_terminal_committed": True, "dispatch_count": ordinal}
    return {"scenario_id": identifier, "category": "TRANSPORT", "description": title,
        "initial_conditions": {"frozen_order": [request_id], "ordinal": ordinal, "replay_safe": safe,
                               "maximum_attempts": 4, "timeout_seconds": 60},
        "injected_failure": signal, "injection_point": phase, "expected": expected,
        "oracle_authority": "master fault_injection_matrix_contract + alpha3.22D request; literals only"}


def scenarios():
    partial = dict(complete=False, raw_trust="NONAUTHORITATIVE_PARTIAL")
    success = dict(complete=True, raw_trust="AUTHORITATIVE_COMPLETE", length="MATCH")
    retry = dict(retry=True, next_ordinal=2, backoff=2)
    result = [
        transport_spec("T01", "connection failure before headers", "ConnectionResetError", "REQUEST_ATTEMPT_STARTED", "PRE_RESPONSE_TRANSPORT_INTERRUPTION", "RETRYABLE_FAILURE_WITH_BUDGET", **retry),
        transport_spec("T02", "timeout before headers", "TimeoutError", "REQUEST_ATTEMPT_STARTED", "PRE_RESPONSE_TRANSPORT_INTERRUPTION", "RETRYABLE_FAILURE_WITH_BUDGET", **retry),
        transport_spec("T03", "authorized HTTP 503", "HTTPError_503", "RESPONSE_HEADERS_RECEIVED", "RETRYABLE_HTTP_STATUS", "RETRYABLE_FAILURE_WITH_BUDGET", **retry),
        transport_spec("T04", "nonretryable HTTP 404", "HTTPError_404", "RESPONSE_HEADERS_RECEIVED", "NONRETRYABLE_HTTP_STATUS", "TERMINAL_TECHNICAL_FAILURE"),
        transport_spec("T05", "connection reset during BODY_READING; preserve fault phase through raw freeze", "ConnectionResetError", "RESPONSE_BODY_READING", "RESPONSE_BODY_TRANSPORT_INTERRUPTION", "RETRYABLE_FAILURE_WITH_BUDGET", length="MISMATCH", **partial, **retry),
        transport_spec("T06", "timeout during BODY_READING", "TimeoutError", "RESPONSE_BODY_READING", "RESPONSE_BODY_TRANSPORT_INTERRUPTION", "RETRYABLE_FAILURE_WITH_BUDGET", length="MISMATCH", **partial, **retry),
        transport_spec("T07", "actual bound HTTPResponse IncompleteRead with returned partial bytes", "IncompleteRead", "RESPONSE_BODY_READING", "RESPONSE_BODY_TRANSPORT_INTERRUPTION", "RETRYABLE_FAILURE_WITH_BUDGET", length="MISMATCH", **partial, **retry),
        transport_spec("T08", "comparable wire Content-Length mismatch", "ComparableLengthMismatch", "RAW_RESPONSE_FROZEN", "RESPONSE_BODY_LENGTH_MISMATCH", "RETRYABLE_FAILURE_WITH_BUDGET", length="MISMATCH", **partial, **retry),
        transport_spec("T09", "complete valid synthetic JATS", "NONE", "RESPONSE_VALIDATION_COMPLETE", "NO_TECHNICAL_FAILURE", "VALID_SUCCESS", parser_counts=dict.fromkeys(CONSUMERS, 1), **success),
        transport_spec("T10", "complete malformed XML", "ParseError", "RESPONSE_VALIDATION_COMPLETE", "COMPLETE_BODY_RESPONSE_VALIDITY_FAILURE", "TERMINAL_RESPONSE_VALIDITY_FAILURE", parser_counts={k: int(k == "generic_parser") for k in CONSUMERS}, **success),
        transport_spec("T11", "complete well-formed JATS with direct identity mismatch", "FrozenIdentityValidatorRejects", "RESPONSE_VALIDATION_COMPLETE", "COMPLETE_BODY_RESPONSE_VALIDITY_FAILURE", "TERMINAL_RESPONSE_VALIDITY_FAILURE", parser_counts={k: int(k in {"generic_parser", "jats_structure", "primary_identity"}) for k in CONSUMERS}, **success),
        transport_spec("T12", "unknown exception during body read", "RuntimeError", "RESPONSE_BODY_READING", "UNKNOWN_RUNTIME_FAILURE", "TERMINAL_TECHNICAL_FAILURE", **partial),
        transport_spec("T13", "known timeout in unsupported headers phase", "TimeoutError", "RESPONSE_HEADERS_RECEIVED", "UNKNOWN_RUNTIME_FAILURE", "TERMINAL_TECHNICAL_FAILURE"),
        transport_spec("T14", "authorized one-hop URLError.reason", "URLError_TimeoutReason", "REQUEST_ATTEMPT_STARTED", "PRE_RESPONSE_TRANSPORT_INTERRUPTION", "RETRYABLE_FAILURE_WITH_BUDGET", **retry),
        transport_spec("T15", "unauthorized nested/context chain", "URLError_NestedReason", "REQUEST_ATTEMPT_STARTED", "UNKNOWN_RUNTIME_FAILURE", "TERMINAL_TECHNICAL_FAILURE"),
        transport_spec("T16", "connection reset after BODY_COMPLETE not a body interruption", "ConnectionResetError", "RESPONSE_BODY_COMPLETE", "UNKNOWN_RUNTIME_FAILURE", "TERMINAL_TECHNICAL_FAILURE", complete=True, raw_trust="COMPLETE_NOT_ADMITTED_AFTER_UNKNOWN", length="MATCH"),
        transport_spec("T17", "decoded bytes are not comparable to wire length", "DecodedLengthUnavailable", "RESPONSE_VALIDATION_COMPLETE", "NO_TECHNICAL_FAILURE", "VALID_SUCCESS", complete=True, raw_trust="AUTHORITATIVE_COMPLETE", parser_counts=dict.fromkeys(CONSUMERS, 1)),
        transport_spec("T18", "decompressed bytes are not comparable to wire length", "DecompressedLengthUnavailable", "RESPONSE_VALIDATION_COMPLETE", "NO_TECHNICAL_FAILURE", "VALID_SUCCESS", complete=True, raw_trust="AUTHORITATIVE_COMPLETE", parser_counts=dict.fromkeys(CONSUMERS, 1)),
        transport_spec("T19", "frozen structured NCBI backend contract", "FrozenBackendFailure", "RESPONSE_VALIDATION_COMPLETE", "RETRYABLE_PROVIDER_BACKEND_FAILURE", "RETRYABLE_FAILURE_WITH_BUDGET", parser_counts={k: int(k == "generic_parser") for k in CONSUMERS}, **success, **retry),
        transport_spec("T20", "replay-unsafe timeout denies retry", "TimeoutError", "REQUEST_ATTEMPT_STARTED", "PRE_RESPONSE_TRANSPORT_INTERRUPTION", "TERMINAL_TECHNICAL_FAILURE", safe=False),
        transport_spec("T21", "second failed attempt selects four-second backoff", "TimeoutError", "REQUEST_ATTEMPT_STARTED", "PRE_RESPONSE_TRANSPORT_INTERRUPTION", "RETRYABLE_FAILURE_WITH_BUDGET", ordinal=2, retry=True, next_ordinal=3, backoff=4),
        transport_spec("T22", "third failed attempt selects eight-second backoff", "TimeoutError", "REQUEST_ATTEMPT_STARTED", "PRE_RESPONSE_TRANSPORT_INTERRUPTION", "RETRYABLE_FAILURE_WITH_BUDGET", ordinal=3, retry=True, next_ordinal=4, backoff=8),
        transport_spec("T23", "fourth failed attempt cannot schedule fifth", "TimeoutError", "REQUEST_ATTEMPT_STARTED", "PRE_RESPONSE_TRANSPORT_INTERRUPTION", "TERMINAL_TECHNICAL_FAILURE", ordinal=4),
    ]
    crash_conditions = [
        ("before_start_ack", "NOT_STARTED", 0, 1, "VERIFIED", False, "NO_RESPONSE", "ABSENT"),
        ("after_start_ack", "ABANDONED_ATTEMPT_UNKNOWN_TERMINATION", 1, 2, "VERIFIED", False, "NO_RESPONSE", "ABSENT"),
        ("after_headers", "ABANDONED_ATTEMPT_UNKNOWN_TERMINATION", 1, 2, "VERIFIED", False, "NO_RESPONSE", "ABSENT"),
        ("after_partial_raw", "ABANDONED_ATTEMPT_UNKNOWN_TERMINATION", 1, 2, "VERIFIED", False, "NONAUTHORITATIVE_PARTIAL", "ABSENT"),
        ("after_complete_raw_before_terminal", "ABANDONED_ATTEMPT_UNKNOWN_TERMINATION", 1, 2, "VERIFIED", False, "ORPHAN_COMPLETE_NOT_SUCCESS", "ABSENT"),
        ("after_success_terminal", "VALID_SUCCESS", 1, None, "VERIFIED", True, "AUTHORITATIVE_COMPLETE", "ABSENT"),
        ("after_noneligible_terminal", "VALID_NONELIGIBLE_RESPONSE", 1, None, "VERIFIED", True, "AUTHORITATIVE_COMPLETE", "ABSENT"),
        ("during_append", "INTEGRITY_REVIEW_REQUIRED", 0, None, "FAILED_CLOSED", False, "NO_RESPONSE", "ABSENT"),
        ("torn_jsonl_tail", "INTEGRITY_REVIEW_REQUIRED", 1, None, "FAILED_CLOSED", False, "NO_RESPONSE", "ABSENT"),
        ("hash_chain_corruption", "INTEGRITY_REVIEW_REQUIRED", 1, None, "FAILED_CLOSED", False, "NO_RESPONSE", "ABSENT"),
        ("duplicate_attempt", "INTEGRITY_REVIEW_REQUIRED", 1, None, "FAILED_CLOSED", False, "NO_RESPONSE", "ABSENT"),
        ("writer_contention", "WRITER_OWNERSHIP_DENIED", 0, None, "FAILED_CLOSED", False, "NO_RESPONSE", "ABSENT"),
        ("during_barrier_persistence", "AWAITING_FROZEN_OA_BARRIER", 8, None, "VERIFIED", False, "AUTHORITATIVE_COMPLETE", "ABSENT"),
        ("after_barrier_commit", "AWAITING_FROZEN_ACTIVATION", 8, None, "VERIFIED", False, "AUTHORITATIVE_COMPLETE", "COMMITTED"),
        ("during_activation_persistence", "AWAITING_FROZEN_ACTIVATION", 8, None, "VERIFIED", False, "AUTHORITATIVE_COMPLETE", "COMMITTED"),
        ("after_activation_commit", "NOT_STARTED", 8, 1, "VERIFIED", False, "AUTHORITATIVE_COMPLETE", "COMMITTED"),
        ("after_some_JATS_success", "ABANDONED_ATTEMPT_UNKNOWN_TERMINATION", 10, 2, "VERIFIED", False, "NONAUTHORITATIVE_PARTIAL", "COMMITTED"),
        ("unsafe_abandoned", "ABANDONED_ATTEMPT_UNKNOWN_TERMINATION", 1, None, "VERIFIED", False, "NO_RESPONSE", "ABSENT"),
        ("corrupt_success_artifact", "INTEGRITY_REVIEW_REQUIRED", 1, None, "FAILED_CLOSED", False, "CORRUPT_REJECTED", "ABSENT"),
        ("repeat_readonly_resume", "VALID_SUCCESS", 1, None, "VERIFIED", True, "AUTHORITATIVE_COMPLETE", "ABSENT"),
    ]
    for n, (checkpoint, state, consumed, next_ordinal, integrity, terminal, trust, barrier) in enumerate(crash_conditions, 1):
        identifier = f"C{n:02d}"
        pending = [identifier + ":OA:0"] if next_ordinal is not None else []
        if n == 16:
            pending = [identifier + f":JATS:{i}" for i in range(5)]
        elif n == 17:
            pending = [identifier + f":JATS:{i}" for i in range(1, 5)]
        result.append({"scenario_id": identifier, "category": "CRASH", "description": checkpoint,
            "initial_conditions": {"workflow": "8 OA -> 5 JATS" if n in range(13, 18) else "one frozen request", "replay_safe": n != 18},
            "consumer_count_scope": "RECOVERY_ONLY",
            "injected_failure": "NAMED_PROCESS_TERMINATION_OR_INTEGRITY_FAULT", "injection_point": checkpoint,
            "expected": {"semantic_failure_class": "ABANDONED_ATTEMPT_UNKNOWN_TERMINATION" if state == "ABANDONED_ATTEMPT_UNKNOWN_TERMINATION" else None,
                "retry_authorized": state == "ABANDONED_ATTEMPT_UNKNOWN_TERMINATION" and n != 18,
                "attempts_consumed": consumed, "next_attempt_ordinal": next_ordinal,
                "parser_invocation_counts": dict.fromkeys(CONSUMERS, 0), "journal_integrity": integrity,
                "terminal_logical_state": state, "durable_terminal_committed": terminal,
                "resume_executable_ids": pending,
                "stage_barrier_state": barrier, "raw_artifact_trust": trust},
            "oracle_authority": "frozen master restart/barrier rules and 22D crash requirements; literals only"})
    for n, fault in enumerate(("missing_record", "duplicate_sequence", "invalid_hash", "wrong_previous_hash", "wrong_request_identity",
                                "duplicate_terminal", "unknown_request_id", "request_hash_drift", "unsupported_schema"), 1):
        result.append(integrity_spec(f"J{n:02d}", "JOURNAL_INTEGRITY", fault))
    for n, fault in enumerate(("missing", "truncated", "hash_mismatch", "request_list_drift", "extra_request", "missing_required_request"), 1):
        result.append(integrity_spec(f"A{n:02d}", "ACTIVATION_INTEGRITY", fault))
    result.append({"scenario_id": "E01", "category": "INTEGRATED", "description": "8 OA / 5 eligible / 3 noneligible / 5 activated JATS",
        "initial_conditions": {"oa_count": 8, "eligible_count": 5, "noneligible_count": 3, "activated_jats_count": 5},
        "injected_failure": ["body reset", "successful technical retry", "complete invalid response", "terminal license ineligible", "crash after JATS success", "untouched pending JATS"],
        "injection_point": "ordered synthetic OA/JATS workflow",
        "expected": {"oa_refetch_count": 0, "activation_drift_count": 0, "attempt_ordinal_reuse_count": 0,
            "partial_parser_invocations": 0, "raw_success_durable": True, "pending_order_preserved": True,
            "terminal_validity_failure_blocks_later_dispatch": True, "license_ineligible_refetch_count": 0},
        "oracle_authority": "22D integrated scenario and frozen fail-closed continuation order"})
    return result


def integrity_spec(identifier, category, fault):
    return {"scenario_id": identifier, "category": category, "description": fault,
        "initial_conditions": {"frozen_inputs_unchanged": True}, "injected_failure": fault, "injection_point": "verified reopen before dispatch",
        "expected": {"semantic_failure_class": None, "retry_authorized": False, "attempts_consumed": None,
            "next_attempt_ordinal": None, "parser_invocation_counts": dict.fromkeys(CONSUMERS, 0),
            "journal_integrity": "FAILED_CLOSED", "terminal_logical_state": "INTEGRITY_REVIEW_REQUIRED", "resume_executable_ids": [],
            "stage_barrier_state": "NO_UNVERIFIED_ACTIVATION_ADMITTED", "raw_artifact_trust": "NOT_ADMITTED", "dispatch_count": 0},
        "oracle_authority": "22D explicit integrity negative tests; fail closed, no repair"}


MUTATIONS = ("allow_partial_parser", "reset_ordinal", "refresh_success", "ignore_activation_mismatch", "retry_unknown", "accept_corrupt_raw")
