"""D-R2 structural preflight; never execute original faults or infer expectations."""

import ast
import copy
import json
from pathlib import Path

import pytest

from scripts import search_plan_v24_alpha322dr2_independent_harness as h


MANIFEST_RAW = (h.ORIGINAL / "frozen_fault_scenario_manifest.json").read_bytes()
ORACLE_RAW = (h.ORIGINAL / "independent_expected_outcomes.jsonl").read_bytes()
MANIFEST = json.loads(MANIFEST_RAW)
EXPECTED = [json.loads(line) for line in ORACLE_RAW.splitlines()]


def test_exact_original_bytes_and_order():
    assert h.j.sha(MANIFEST_RAW) == "aed33640b5a88badd5a785b41019158ca369b656f20a5a150713b2e8f8eba23b"
    assert h.j.sha(ORACLE_RAW) == "b1d452438341fd2a01262f09a75649169dd726da119371b30388c4a464d6d817"
    assert len(MANIFEST["scenarios"]) == len(EXPECTED) == 59
    assert MANIFEST["order"] == [row["scenario_id"] for row in EXPECTED]
    assert MANIFEST["order"] == [row["scenario_id"] for row in MANIFEST["scenarios"]]
    assert len(set(MANIFEST["order"])) == 59


def test_independent_literal_oracle_has_no_SUT_imports():
    tree = ast.parse(Path(h.oracle.__file__).read_bytes())
    assert not any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(tree))
    forbidden = {"classify", "capture_failure", "semantic_retry_decision", "TransportLifecycleV2", "_reduce"}
    assert not any(isinstance(node, ast.Name) and node.id in forbidden for node in ast.walk(tree))


@pytest.mark.parametrize("scenario", MANIFEST["scenarios"], ids=lambda row: row["scenario_id"])
def test_preserved_scenario_contract(scenario):
    assert "expected" not in scenario
    assert {"initial_conditions", "injected_failure", "injection_point", "category"} <= set(scenario)
    assert next(row for row in EXPECTED if row["scenario_id"] == scenario["scenario_id"])["expected"]


def test_category_and_mutation_counts():
    assert {key: sum(row["category"] == key for row in MANIFEST["scenarios"]) for key in
            ("TRANSPORT", "CRASH", "JOURNAL_INTEGRITY", "ACTIVATION_INTEGRITY", "INTEGRATED")} == {
                "TRANSPORT": 23, "CRASH": 20, "JOURNAL_INTEGRITY": 9, "ACTIVATION_INTEGRITY": 6, "INTEGRATED": 1}
    assert MANIFEST["mutation_ids"] == list(h.oracle.MUTATIONS)


def test_actual_R2_dependencies_and_explicit_child_entrypoint():
    assert Path(h.j.__file__).name == "append_only_attempt_journal_v2_validator_outcome_v1.py"
    assert Path(h.p.__file__).name == "deterministic_resume_planner_v2_validator_outcome_v1.py"
    assert Path(h.s.__file__).name == "stage_barrier_snapshot_v2_validator_outcome_v1.py"
    assert Path(h.f.__file__).name == "transport_failure_phase_binding_v2_r2.py"
    source = Path(h.__file__).read_text()
    assert "scripts.search_plan_v24_alpha322dr2_independent_harness" in source
    assert "FrozenRequestManifestV1" not in source
    assert "JournalIntegrityVerifierV1" not in source
    assert "DeterministicResumePlannerV1" not in source


def test_handlers_never_read_expected_values_or_repair_components():
    tree = ast.parse(Path(h.__file__).read_text())
    handlers = {"transport_scenario", "crash_scenario", "integrity_scenario", "integrated_scenario",
                "success_unit", "partial_unit", "request_manifest", "crash_child"}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in handlers:
            assert not any(isinstance(child, ast.Name) and child.id in {"expected", "EXPECTED"} for child in ast.walk(node))
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
                    assert child.func.attr not in {"scenarios", "fixtures", "synthetic_fixtures", "urlopen", "connect", "sleep"}


def test_comparison_detects_safety_differences_without_normalization():
    expected = next(row["expected"] for row in EXPECTED if row["scenario_id"] == "T05")
    actual = copy.deepcopy(expected)
    assert h.compare(expected, actual) == []
    actual["durable_terminal_committed"] = False
    actual["terminal_logical_state"] = "ABANDONED_ATTEMPT_UNKNOWN_TERMINATION"
    assert [row["field"] for row in h.compare(expected, actual)] == [
        key for key in expected if key in {"durable_terminal_committed", "terminal_logical_state"}]


def test_r2_capture_occurs_before_partial_lifecycle_progression():
    tree = ast.parse(Path(h.__file__).read_text())
    transport = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "transport_scenario")
    source = ast.unparse(transport)
    assert source.index("capture_for_decision(writer, lifecycle") < source.index("lifecycle.record_body")
    assert "failure_phase_binding=binding" in source
    assert "capture.record()['occurrence']['sha256']" in source

def test_latest_entrypoint_and_validator_route_are_bound_not_reimplemented():
    assert h.integration.j is h.j
    assert h.integration.p is h.p
    assert h.integration.RUNTIME_ACTIVATION_ALLOWED is False
    assert h.RUNTIME_ACTIVATION_ALLOWED is False
    source = Path(h.__file__).read_text()
    assert "integration.prepare_result(writer, lifecycle, validator_results[-1]" in source
    assert "integration.commit(writer, validator_item)" in source
    assert 'decision.retry.semantic_failure.value if validator_item is not None' in source
    assert "terminal_event" in source and "refetch_rejection" in source


def test_unchanged_non_validator_handlers():
    from scripts import search_plan_v24_alpha322dr_r2_independent_harness as previous
    new = ast.parse(Path(h.__file__).read_text())
    old = ast.parse(Path(previous.__file__).read_text())
    for name in ("begin", "mapping_facts", "classify", "capture_for_decision",
                 "observation_and_binding", "success_unit", "partial_unit",
                 "crash_child", "crash_scenario", "integrity_scenario"):
        a = ast.unparse(next(n for n in new.body if isinstance(n, ast.FunctionDef) and n.name == name))
        b = ast.unparse(next(n for n in old.body if isinstance(n, ast.FunctionDef) and n.name == name))
        assert a == b.replace("scripts.search_plan_v24_alpha322dr_r2_independent_harness",
                              "scripts.search_plan_v24_alpha322dr2_independent_harness")


def test_integrated_fault_uses_real_process_termination():
    source = Path(h.__file__).read_text()
    tree = ast.parse(source)
    child = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "integrated_child")
    assert "os._exit(73)" in ast.unparse(child)
    assert '"--integrated-child"' in source
