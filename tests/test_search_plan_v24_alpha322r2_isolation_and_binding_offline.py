"""Additional R2 binding/isolation regressions; unchanged R0 oracles."""

import ast
import copy
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts import search_plan_v24_alpha322r2_runtime_identity_fixtures as ri
from scripts import search_plan_v24_alpha322r1_versioned_phase_binding_integration as historical

h, j, f = ri.h, ri.j, ri.fixtures.f


@pytest.fixture(autouse=True)
def offline():
    with h.r0.d.master.prior.offline_guard():
        yield


def test_one_identity_capture_reused_in_both_exception_paths(tmp_path):
    with j.AppendOnlyAttemptJournalV2(tmp_path / "journal", h.manifest(), create=True) as writer:
        lifecycle = h.start(writer)
        with patch.object(f, "capture_runtime_identity", wraps=f.capture_runtime_identity) as capture:
            item = h.failed_attempt(writer, lifecycle)
        assert capture.call_count == 1
        frozen = item["capture"].runtime_identity.record()
        occurrence = f.read_evidence(item["capture"].record()["occurrence"], writer.directory)
        signal = f.read_evidence(occurrence["signal"], writer.directory)
        assert frozen == signal["runtime_identity"] == item["observation"].record()["observation"]["exception_provenance"]["runtime_identity"]
        assert occurrence["capture_source_sha256"] == j.sha(j.read_bytes(Path(f.__file__)))
        assert occurrence["capture_implementation_manifest_sha256"] == f.implementation_identity()


@pytest.mark.parametrize("mode", ["reset", "partial"])
def test_local_http_response_is_explicitly_closed_after_failure_capture(tmp_path, mode):
    original_response = h.http.client.HTTPResponse
    observed = []
    def response(socket):
        result = original_response(socket)
        observed.append((result, socket.file))
        return result
    with j.AppendOnlyAttemptJournalV2(tmp_path / "journal", h.manifest(), create=True) as writer:
        with patch.object(h.http.client, "HTTPResponse", side_effect=response):
            h.failed_attempt(writer, h.start(writer), mode=mode)
    assert len(observed) == 1
    response, source = observed[0]
    assert response.closed and response.fp is None and source.closed


@pytest.mark.parametrize("drop", ["parent", "python_version"])
def test_full_terminal_verifier_rejects_malformed_identity_without_repair(tmp_path, drop):
    with j.AppendOnlyAttemptJournalV2(tmp_path / "journal", h.manifest(), create=True) as writer:
        item = h.failed_attempt(writer, h.start(writer), commit=False)
        data = ri.fixtures.payload(item)
        signal = data["mapped_observation"]["observation"]["exception_provenance"]
        if drop == "parent":
            signal.pop("runtime_identity")
        else:
            signal["runtime_identity"].pop("python_version")
        malformed = copy.deepcopy(data)
        before = ri.fixtures.snapshot(writer.directory)
        with patch.object(f, "capture_runtime_identity", side_effect=AssertionError("VERIFIER_MUST_NOT_CAPTURE_OR_REPAIR")):
            # Existing full-terminal order verifies signal equality first. The
            # six RI fixtures independently test their frozen admission stages.
            with pytest.raises(ri.t.TransportContractError, match="IMMUTABLE_EVIDENCE_HASH_MISMATCH"):
                ri.fixtures.candidate(writer, data)
        assert data == malformed and ri.fixtures.snapshot(writer.directory) == before


def test_r1_r2_implementation_manifests_and_typed_readers_are_isolated(tmp_path):
    old = historical.manifest()
    new = h.manifest()
    assert old.record()["runtime_v2_implementation_manifest_sha256"] != new.record()["runtime_v2_implementation_manifest_sha256"]
    with pytest.raises(ri.t.TransportContractError, match="RUNTIME_IMPLEMENTATION_BINDING"):
        j.FrozenRequestManifestV2(old.serialized)
    with pytest.raises(ri.t.TransportContractError, match="RUNTIME_IMPLEMENTATION_BINDING"):
        historical.j.FrozenRequestManifestV2(new.serialized)
    with j.AppendOnlyAttemptJournalV2(tmp_path / "r2", new, create=True) as writer:
        h.start(writer)
        with pytest.raises(ri.t.TransportContractError, match="VERIFIED_JOURNAL_REQUIRED"):
            historical.p.DeterministicResumePlannerV2().build(writer.verified())


def test_journal_reader_barrier_and_fixture_forks_are_dependency_only():
    root = h.ROOT
    pairs = [
        ("src/code_engine/append_only_attempt_journal_v2.py", "src/code_engine/append_only_attempt_journal_v2_r2.py"),
        ("src/code_engine/deterministic_resume_planner_v2.py", "src/code_engine/deterministic_resume_planner_v2_r2.py"),
        ("src/code_engine/stage_barrier_snapshot_v2.py", "src/code_engine/stage_barrier_snapshot_v2_r2.py"),
        ("scripts/search_plan_v24_alpha322r1_repair_fixtures.py", "scripts/search_plan_v24_alpha322r2_repair_fixtures.py"),
    ]
    for original, versioned in pairs:
        expected = (root / original).read_text()
        for before, after in (("transport_failure_phase_binding_v2", "transport_failure_phase_binding_v2_r2"),
            ("append_only_attempt_journal_v2", "append_only_attempt_journal_v2_r2"),
            ("deterministic_resume_planner_v2", "deterministic_resume_planner_v2_r2"),
            ("stage_barrier_snapshot_v2", "stage_barrier_snapshot_v2_r2"),
            ("search_plan_v24_alpha322r1_versioned_phase_binding_integration", "search_plan_v24_alpha322r2_versioned_runtime_identity_integration")):
            expected = expected.replace(before, after)
        actual = (root / versioned).read_text()
        assert actual == "# R2 mechanical version fork; original R1 remains byte-frozen.\n" + expected
    # Phase verification itself has no functional changes, only new source and
    # manifest identities through the module's explicit R2 bindings.
    old_tree = ast.parse(Path(historical.f.__file__).read_bytes())
    new_tree = ast.parse(Path(f.__file__).read_bytes())
    old_functions = {node.name: ast.dump(node, include_attributes=False) for node in old_tree.body if isinstance(node, ast.FunctionDef)}
    new_functions = {node.name: ast.dump(node, include_attributes=False) for node in new_tree.body if isinstance(node, ast.FunctionDef)}
    for name in old_functions.keys() - {"implementation_identity", "capture_failure"}:
        assert old_functions[name] == new_functions[name]
