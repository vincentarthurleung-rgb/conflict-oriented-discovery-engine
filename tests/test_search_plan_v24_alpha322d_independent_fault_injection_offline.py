"""Structural preflight only. Primary D fault scenarios run ONCE after freeze.

These tests do not call A/B/C policies to manufacture expected outcomes or
execute primary fault scenarios before their oracle is frozen.
"""

import ast
import copy
from pathlib import Path

import pytest

from scripts import search_plan_v24_alpha322d_independent_scenarios as oracle
from scripts import run_search_plan_v24_alpha322d_independent_fault_injection_offline as d


def test_independent_oracle_has_no_imports_or_SUT_calls():
    audit = d.independent_oracle_audit()
    assert audit["independent_test_oracle_established"]
    assert audit["SUT_calls"] == audit["SUT_imports"] == 0


def test_matrix_complete_unique_and_prospectively_declared():
    cases = oracle.scenarios()
    assert len(cases) == len({r["scenario_id"] for r in cases}) == 59
    assert sum(r["category"] == "TRANSPORT" for r in cases) == 23
    assert sum(r["category"] == "CRASH" for r in cases) == 20
    assert sum(r["category"] == "INTEGRATED" for r in cases) == 1
    assert len(oracle.MUTATIONS) == 6
    assert {f"T{i:02d}" for i in range(1, 24)} <= {r["scenario_id"] for r in cases}
    assert {f"C{i:02d}" for i in range(1, 21)} <= {r["scenario_id"] for r in cases}


@pytest.mark.parametrize("scenario", oracle.scenarios(), ids=lambda r: r["scenario_id"])
def test_each_declaration_includes_initial_conditions_checkpoint_and_expectation(scenario):
    assert {"scenario_id", "category", "initial_conditions", "injected_failure", "injection_point", "expected", "oracle_authority"} <= set(scenario)
    assert scenario["expected"] and scenario["oracle_authority"]
    if scenario["category"] == "TRANSPORT":
        required = {"semantic_failure_class", "retry_authorized", "attempts_consumed", "next_attempt_ordinal",
                    "parser_invocation_counts", "journal_integrity", "terminal_logical_state", "resume_executable_ids",
                    "stage_barrier_state", "raw_artifact_trust", "durable_terminal_committed"}
        assert required <= set(scenario["expected"])


@pytest.mark.parametrize("identifier", ["T01", "T02", "T05", "T06", "T07", "T08", "T12", "T14", "T15", "T16"])
def test_transport_quarantine_expected_counts_are_independent_zeros(identifier):
    expected = next(r["expected"] for r in oracle.scenarios() if r["scenario_id"] == identifier)
    assert len(expected["parser_invocation_counts"]) == 6
    assert all(value == 0 for value in expected["parser_invocation_counts"].values())


def test_retry_backoff_budget_literals_and_unknown_nonretryable_expectations():
    cases = {r["scenario_id"]: r for r in oracle.scenarios()}
    assert [cases[key]["expected"]["backoff_seconds"] for key in ("T02", "T21", "T22", "T23")] == [2, 4, 8, 0]
    assert cases["T23"]["expected"]["next_attempt_ordinal"] is None
    for key in ("T12", "T13", "T15", "T16", "T20"):
        assert cases[key]["expected"]["retry_authorized"] is False


def test_compare_is_independent_keywise_and_never_infers_outcomes_from_SUT():
    expected = next(r["expected"] for r in oracle.scenarios() if r["scenario_id"] == "T05")
    actual = copy.deepcopy(expected)
    assert d.compare(expected, actual) == []
    actual["durable_terminal_committed"] = False
    actual["terminal_logical_state"] = "ABANDONED_ATTEMPT_UNKNOWN_TERMINATION"
    assert {row["field"] for row in d.compare(expected, actual)} == {"durable_terminal_committed", "terminal_logical_state"}


def test_harness_observes_concrete_fault_before_raw_audit_phase_advancement():
    tree = ast.parse(Path(d.__file__).read_text())
    source = Path(d.__file__).read_text()
    assert "concrete_fault_classified" in source
    assert "partial_or_complete_raw_preserved" in source
    assert "mapping_fault_phase_preserved" in source
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {"fixtures", "crash_matrix", "two_phase", "synthetic_fixtures", "sleep", "urlopen", "create_connection", "connect"}


def test_no_component_edits_and_no_release_gate_completion_in_preflight():
    assert all("alpha322d" in str(path) for path in d.SOURCES)
    assert d.FAIL_CLASS == "ALPHA3_22D_FAILED_INDEPENDENT_FAULT_INJECTION"
    assert len(d.REQUIRED_JSON) == 39
