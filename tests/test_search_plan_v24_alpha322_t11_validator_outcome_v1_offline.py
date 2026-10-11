"""Focused development tests, not the independent 59-scenario release run."""

import ast
import copy
from pathlib import Path

import pytest

from scripts import search_plan_v24_alpha322_t11_validator_outcome_fixtures_v1 as fixtures

h, j, t = fixtures.h, fixtures.j, fixtures.t


@pytest.fixture(autouse=True)
def offline():
    with h.dr.master.prior.offline_guard():
        yield


@pytest.mark.parametrize("key", list(fixtures.SPEC))
def test_named_A_through_L_exact_outcomes(tmp_path, key):
    result = fixtures.execute(key, tmp_path / key)
    assert result["passed"], result


def test_original_T11_complete_path_and_unchanged_oracle(tmp_path):
    result = h.t11(tmp_path / "T11")
    assert result["passed"], result
    assert result["actual_validator_result"]["source_identity_allows_progression"] is False
    assert result["preserved_outcome"]["transport_body_state"] == "BODY_COMPLETE"
    assert result["terminal_payload"]["validation"]["accepted"] is False
    assert result["terminal_payload"]["mapped_observation"]["observation"]["exception_provenance"] is None
    assert result["transport_mapping"]["semantic_failure_class"] == "NO_TECHNICAL_FAILURE"
    assert result["terminal_payload"]["retry_decision"]["semantic_failure"] == "COMPLETE_BODY_RESPONSE_VALIDITY_FAILURE"
    assert result["terminal_payload"]["eligibility"] is None
    assert result["fresh_reader_is_read_only"]


def test_T05_unchanged_transport_binding_through_new_entrypoint(tmp_path):
    result = h.t05(tmp_path / "T05")
    assert result["passed"], result


@pytest.mark.parametrize("value", [None, 0, 1, "", "False", [], {}, (), b"", object()])
def test_no_python_truthiness_or_type_conflation(value):
    with pytest.raises(t.TransportContractError, match="^UNSUPPORTED_VALIDATOR_RESULT$"):
        h.validity.accepted_result(value, "literal_boolean")


@pytest.mark.parametrize("value", [None, 0, 1, "", [], {}])
def test_identity_contract_projection_must_be_literal_bool(value):
    with pytest.raises(t.TransportContractError, match="^UNSUPPORTED_VALIDATOR_RESULT$"):
        h.validity.accepted_result({"schema_version": "JATSPrimarySourceIdentityContractV2", "source_identity_allows_progression": value},
                                  "jats_primary_identity_v2")


def test_old_R2_reader_cannot_silently_admit_new_adapter_manifest():
    with pytest.raises(t.TransportContractError, match="^MANIFEST_AUTHORITY$"):
        h.r2.j.FrozenRequestManifestV2(h.manifest().serialized)


def test_journal_mechanics_and_existing_terminal_rules_are_unchanged():
    old = ast.parse(Path(h.r2.j.__file__).read_text())
    new = ast.parse(Path(j.__file__).read_text())
    old_classes = {node.name: node for node in old.body if isinstance(node, ast.ClassDef)}
    new_classes = {node.name: node for node in new.body if isinstance(node, ast.ClassDef)}
    for key in old_classes:
        original = copy.deepcopy(old_classes[key])
        candidate = copy.deepcopy(new_classes[key])
        if key == "AppendOnlyAttemptJournalV2":
            candidate.body = [node for node in candidate.body if not isinstance(node, ast.FunctionDef) or node.name != "commit_validator_outcome"]
            # Only explicit module dependencies differ for the versioned reader.
            for node in ast.walk(candidate):
                if isinstance(node, ast.ImportFrom) and node.module == "deterministic_resume_planner_v2_validator_outcome_v1":
                    node.module = "deterministic_resume_planner_v2_r2"
        assert ast.dump(original, include_attributes=False) == ast.dump(candidate, include_attributes=False), key
    originals = {node.name: node for node in old.body if isinstance(node, ast.FunctionDef)}
    candidates = {node.name: node for node in new.body if isinstance(node, ast.FunctionDef)}
    terminal = copy.deepcopy(candidates["_verify_transport_terminal"])
    terminal.name = "_verify_terminal"
    assert ast.dump(terminal, include_attributes=False) == ast.dump(originals["_verify_terminal"], include_attributes=False)
    for key in originals.keys() - {"_verify_terminal", "_reduce"}:
        assert ast.dump(originals[key], include_attributes=False) == ast.dump(candidates[key], include_attributes=False), key
    original_reduce = ast.unparse(originals["_reduce"])
    new_reduce = ast.unparse(candidates["_reduce"]).replace("stage_barrier_snapshot_v2_validator_outcome_v1", "stage_barrier_snapshot_v2_r2")
    assert original_reduce == new_reduce


def test_reader_and_barrier_are_dependency_only_mechanical_forks():
    for original, versioned in (("deterministic_resume_planner_v2_r2", "deterministic_resume_planner_v2_validator_outcome_v1"),
                                ("stage_barrier_snapshot_v2_r2", "stage_barrier_snapshot_v2_validator_outcome_v1")):
        expected = (h.ROOT / "src/code_engine" / (original + ".py")).read_text().replace(
            "append_only_attempt_journal_v2_r2", "append_only_attempt_journal_v2_validator_outcome_v1")
        actual = (h.ROOT / "src/code_engine" / (versioned + ".py")).read_text()
        assert actual == "# Development-only mechanical fork; frozen R2 source remains unchanged.\n" + expected
