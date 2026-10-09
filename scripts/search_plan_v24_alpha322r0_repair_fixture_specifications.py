"""Independent, descriptive R0 fixtures only; no runtime or SUT imports.

These literal expectations must be frozen before any R1 implementation.
They are NOT executed by R0 and do not claim that a repair already works.
"""


def positive():
    return {
        "fixture_id": "R0_P01", "execution_status": "SPECIFICATION_ONLY_NOT_EXECUTED",
        "environment": "fresh isolated offline synthetic run; no sockets",
        "identity": {"run_id": "synthetic:repair-validation", "run_epoch": "epoch-1",
                     "stage_id": "synthetic:OA-JATS", "logical_request_id": "repair:OA:0",
                     "attempt_ordinal": 1},
        "request_hash_source": "canonical immutable synthetic request payload; compute before execution",
        "signal": "actual exact builtins.ConnectionResetError raised by bound local HTTPResponse body read",
        "failure_occurrence_phase": "RESPONSE_BODY_READING",
        "mapping_evidence_phase": "RESPONSE_BODY_READING",
        "mapping_rule_id": "reset_body_read",
        "mapping_table_sha256": "de61dd8f230bf1dd5b9f59da4a930848f1bb03f5941b998b7031bc2cf01b6b26",
        "required_event_order": ["durable ATTEMPT_STARTED", "RESPONSE_HEADERS_RECEIVED",
            "RESPONSE_BODY_READING", "immutable occurrence capture and unchanged 22B/22A decision",
            "RESPONSE_BODY_INTERRUPTED", "quarantined raw bytes physically frozen",
            "RAW_RESPONSE_FROZEN", "validated failure terminal append and fsync"],
        "required_lifecycle_suffix": ["RESPONSE_BODY_READING", "RESPONSE_BODY_INTERRUPTED", "RAW_RESPONSE_FROZEN"],
        "persistence_phase": "RAW_RESPONSE_FROZEN",
        "raw_fixture_hex": "", "raw_byte_count": 0,
        "raw_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "nonempty_partial_supplement": "independent IncompleteRead with literal prefix; not a replacement for original T06",
        "request_replay_safe": True,
        "expected": {"semantic_failure_class": "RESPONSE_BODY_TRANSPORT_INTERRUPTION",
            "retry_authorized": True, "durable_terminal_committed": True,
            "terminal_logical_state": "RETRYABLE_FAILURE_WITH_BUDGET", "attempts_consumed": 1,
            "remaining_attempts": 3, "next_attempt_ordinal": 2, "backoff_seconds": 2,
            "raw_artifact_frozen": True, "body_complete": False, "authoritative": False,
            "parser_eligible": False, "parser_invocations": 0, "network_calls": 0},
        "expected_source": "R0 user requirements and frozen master; independent literals, not SUT answers",
    }


def negatives():
    declarations = (
        ("N01", "Occurrence is AFTER BODY_COMPLETE but mapping claims BODY_READING", "OCCURRENCE_MAPPING_PHASE_MISMATCH"),
        ("N02", "Mapping phase is absent", "MISSING_MAPPING_PHASE"),
        ("N03", "Explicit lifecycle trace or its journal anchors are absent", "MISSING_LIFECYCLE_TRACE"),
        ("N04", "Trace jumps BODY_READING directly to RAW_RESPONSE_FROZEN", "INVALID_LIFECYCLE_EDGE"),
        ("N05", "Persistence phase cannot be reached from occurrence via the supplied valid trace", "PERSISTENCE_TRACE_MISMATCH"),
        ("N06", "Mapping evidence belongs to attempt ordinal 2, terminal belongs to ordinal 1", "ATTEMPT_IDENTITY_MISMATCH"),
        ("N07", "Mapping evidence belongs to a different logical request", "REQUEST_IDENTITY_MISMATCH"),
        ("N08", "Mapping rule ID or mapping table hash differs from frozen 22B", "MAPPING_AUTHORITY_MISMATCH"),
        ("N09", "Occurrence phase or mapping snapshot is edited after its immutable capture", "IMMUTABLE_EVIDENCE_HASH_MISMATCH"),
        ("N10", "Partial artifact bytes do not match saved hash", "RAW_ARTIFACT_HASH_MISMATCH"),
        ("N11", "Partial bytes claim authoritative=true or parser_eligible=true", "PARTIAL_QUARANTINE_VIOLATION"),
        ("N12", "UNKNOWN_RUNTIME_FAILURE claims retry_authorized=true", "RETRY_AUTHORITY_MISMATCH"),
        ("N13", "Replay-unsafe request claims retry_authorized=true", "REPLAY_SAFETY_MISMATCH"),
        ("N14", "Consumed ordinal 4 claims a next retry", "EXHAUSTED_RETRY_BUDGET"),
        ("N15", "A rehashed trace/occurrence envelope belongs to a different run or epoch", "RUN_IDENTITY_MISMATCH"),
        ("N16", "Evidence has a different stage or frozen request payload hash", "STAGE_OR_PAYLOAD_IDENTITY_MISMATCH"),
        ("N17", "A second terminal event is proposed for the same started attempt", "DUPLICATE_TERMINAL"),
        ("N18", "Only monotonic timestamps are supplied instead of ordered trace/anchors", "MISSING_LIFECYCLE_TRACE"),
        ("N19", "Valid enum strings and rehashed record but no controller-captured occurrence evidence", "UNBOUND_OCCURRENCE_EVIDENCE"),
        ("N20", "Mapping facts lose bound client identity or trusted-header evidence", "MAPPING_FACTS_AUTHORITY_MISMATCH"),
        ("N21", "Terminal append/fsync is uncertain and caller claims committed success", "UNCERTAIN_DURABILITY_FAIL_CLOSED"),
        ("N22", "Body-interruption trace progresses through BODY_COMPLETE/validation before failure persistence", "CONTRADICTORY_INTERRUPTION_TRACE"),
    )
    return [{"fixture_id": key, "base_fixture": "R0_P01", "independent_perturbation": description,
             "expected": {"accept_invalid_record": False, "retry_dispatches": 0, "parser_invocations": 0,
                          "failure": "FAIL_CLOSED", "proposed_reason_code": reason},
             "execution_status": "SPECIFICATION_ONLY_NOT_EXECUTED"}
            for key, description, reason in declarations]


def recovery():
    return {
        "fixture_id": "R0_REC01", "execution_status": "SPECIFICATION_ONLY_NOT_EXECUTED",
        "environment": "fresh subprocess reads only new synthetic V2 journal; no live sources",
        "frozen_request_order": ["repair:OA:success", "repair:OA:0", "repair:OA:later"],
        "precrash_records": ["success has valid complete raw/validation/eligibility + durable terminal",
            "repair:OA:0 has ordinal 1 interrupted raw + fully validated/fsynced failure terminal",
            "repair:OA:later has no ATTEMPT_STARTED"],
        "expected": {"success_state": "VALID_SUCCESS", "success_skipped": True,
            "failure_state": "RETRYABLE_FAILURE_WITH_BUDGET", "failure_is_abandoned": False,
            "failure_attempts_consumed": 1, "failure_remaining_attempts": 3,
            "failure_next_ordinal": 2, "failure_backoff_seconds": 2,
            "executable_request_ids": ["repair:OA:0", "repair:OA:later"],
            "next_executable_request_id": "repair:OA:0", "later_next_ordinal": 1,
            "journal_bytes_changed_by_planning": False, "dispatches": 0},
        "crash_before_terminal_variant": {"fixture_id": "R0_REC02",
            "cut_point": "after occurrence/quarantine/progress, before fully durable terminal commit",
            "expected": {"state": "ABANDONED_ATTEMPT_UNKNOWN_TERMINATION", "attempts_consumed": 1,
                "next_ordinal": 2, "backoff_seconds": 2, "replay_safe_required": True,
                "classification_append_required_before_next_start": True,
                "infer_terminal_from_memory_or_orphan_occurrence": False}},
        "expected_source": "frozen master restart/ordering rules and user R0 requirements; no resume SUT calls",
    }
