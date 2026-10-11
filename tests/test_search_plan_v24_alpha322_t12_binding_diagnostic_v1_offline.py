"""Test the documented contradiction, not a fabricated original T12 PASS."""

import json
import os
from pathlib import Path

import pytest

from scripts import search_plan_v24_alpha322_t12_binding_diagnostic_v1 as d


@pytest.fixture(scope="module")
def evidence():
    path = Path(os.environ["ALPHA322_T12_DIAGNOSTIC_EVIDENCE_DIR"])
    return json.loads((path / "t12_focused_results.json").read_bytes())


@pytest.fixture(autouse=True)
def offline():
    with d.release.master.prior.offline_guard():
        yield


def test_original_fixture_really_contains_content_length_50():
    result = d.source_findings()
    assert result["actual_frozen_header_bytes"] == "HTTP/1.1 200 OK\r\nContent-Length: 50"
    assert result["original_definition"]["injected_failure"] == "RuntimeError"
    assert result["original_definition"]["injection_point"] == "RESPONSE_BODY_READING"
    assert result["original_expected"]["content_length_match"] == "UNAVAILABLE"
    assert result["scenario_definition_explicit_headers"] is None
    assert result["scenario_does_not_require_absent_or_untrusted_length"] is True


def test_actual_read_raised_before_return_not_normal_eof(evidence):
    trace = evidence["actual_frozen_read_trace"]
    assert trace["headers"] == {"Content-Length": "50"}
    assert trace["expected_content_length"] == 50
    assert trace["read_returned_normally"] is False
    assert trace["exception_class"] == "builtins.RuntimeError"
    assert trace["exception_before_body_completion"] is True
    assert trace["read_return_value"] is None
    assert trace["zero_bytes_mean_valid_eof"] is False
    assert trace["recoverable_bytes"] == 0
    assert trace["exception_has_partial"] is False


def test_interruption_preserves_comparable_wire_length(evidence):
    trace = evidence["actual_frozen_read_trace"]
    assert trace["byte_representation"] == trace["expected_length_representation"] == "wire"
    assert trace["decoded_or_decompressed_transform_applied"] is False
    assert trace["content_length_match"] == "MISMATCH"
    assert trace["body_state"] == "BODY_COMPLETION_UNKNOWN"
    assert trace["semantic_failure"] == "UNKNOWN_RUNTIME_FAILURE"


def test_original_oracle_failure_is_explicit_not_relabeled(evidence):
    assert evidence["original_T12_oracle_passed"] is False
    assert evidence["T12"]["status"] == "FAIL"
    assert evidence["T12"]["mismatches"] == [
        {"field": "content_length_match", "expected": "UNAVAILABLE", "actual": "MISMATCH"}]
    assert evidence["diagnosis_consistency_passed"] is True


def test_unknown_read_is_durable_terminal_without_retry_or_parser(evidence):
    result = evidence["T12"]
    actual = result["actual"]
    assert actual["semantic_failure_class"] == "UNKNOWN_RUNTIME_FAILURE"
    assert actual["body_complete"] is False
    assert actual["raw_artifact_trust"] == "NONAUTHORITATIVE_PARTIAL"
    assert not any(actual["parser_invocation_counts"].values())
    assert actual["retry_authorized"] is False
    assert actual["durable_terminal_committed"] is True
    assert actual["terminal_logical_state"] == "TERMINAL_TECHNICAL_FAILURE"
    assert actual["next_attempt_ordinal"] is None
    assert actual["resume_executable_ids"] == []
    assert result["durable_terminal_error"] is None
    assert result["fresh_reader_read_only"] is True


def test_normal_empty_read_must_remain_length_mismatch(evidence):
    result = evidence["normal_empty_counterexample"]
    assert result["read_returned_normally"] is True
    assert result["actual_body_length"] == 0 and result["expected_content_length"] == 50
    assert result["expected_length_trustworthy"] is True
    assert result["content_length_match"] == "MISMATCH"
    assert result["semantic_failure"] == "RESPONSE_BODY_LENGTH_MISMATCH"
    assert result["body_state"] == "BODY_INTERRUPTED"
    assert result["parser_invocations"] == 0
    assert result["passed"] is True


@pytest.mark.parametrize("key", ["T05", "T11"])
def test_full_frozen_regressions(evidence, key):
    assert evidence[key]["status"] == "PASS"
    assert evidence[key]["mismatches"] == []
    assert evidence[key + "_full_path_passed"] is True


def test_recovery_reporting_uses_exact_frozen_ids():
    rows = [{"fixture_id": "R0_REC01", "passed": True}, {"fixture_id": "R0_REC02", "passed": False}]
    original = json.dumps(rows, sort_keys=True)
    assert d.project_recovery(rows) == {"rec01_passed": True, "rec02_passed": False}
    assert json.dumps(rows, sort_keys=True) == original


@pytest.mark.parametrize("rows,reason", [
    ([], "REC_REPORT_EXACT_IDENTITIES_REQUIRED"),
    ([{"fixture_id": "REC01", "passed": True}, {"fixture_id": "REC02", "passed": True}], "REC_REPORT_EXACT_IDENTITIES_REQUIRED"),
    ([{"fixture_id": "R0_REC01", "passed": True}, {"fixture_id": "R0_REC01", "passed": True}], "REC_REPORT_DUPLICATE_ID"),
    ([{"fixture_id": "R0_REC01", "passed": 1}, {"fixture_id": "R0_REC02", "passed": True}], "REC_REPORT_BOOLEAN_REQUIRED"),
])
def test_reporting_projection_fails_closed_on_invalid_identity_or_boolean(rows, reason):
    with pytest.raises(d.t.TransportContractError, match="^" + reason + "$"):
        d.project_recovery(rows)
