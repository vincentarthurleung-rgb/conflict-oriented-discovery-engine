import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.replay_test_support import fixture


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_replay_separates_historical_l1_from_current_l2_calls():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        profile, plan, source = fixture(root)
        artifacts = source / "artifacts"
        (artifacts / "abstract_l1_summary.json").write_text(json.dumps({"api_calls_made": 39, "paper_count": 40}))
        _write_jsonl(artifacts / "pubmed_query_diagnostics.jsonl", [
            {"downloaded_count": 5, "reused_existing_record_count": 10},
            {"downloaded_count": 7, "reused_existing_record_count": 2},
        ])
        _write_jsonl(artifacts / "run_paper_manifest.jsonl", [{"paper_id": f"P{i}"} for i in range(12)])

        from code_engine.cli.replay_case_from_stage import replay

        result = replay(
            profile, plan, source, "l2", root / "runs", "replay", "r2",
            network=False, api=False, bundle_root=root / "bundles",
        )

        accounting = json.loads((Path(result["new_run"]) / "artifacts" / "replay_stage_call_accounting.json").read_text())
        assert accounting["historical_abstract_l1_calls"] == 39
        assert accounting["historical_abstract_documents_downloaded"] == 12
        assert accounting["current_run_calls"]["abstract_l1_provider_calls"] == 0
        assert accounting["current_run_calls"]["abstract_retrieval_http_calls"] == 0
        assert accounting["current_run_calls"]["abstract_documents_downloaded"] == 0
        assert accounting["current_run_calls"]["abstract_documents_reused_from_source"] == 12


def test_replay_records_current_l2_entity_network_calls_by_provider():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        profile, plan, source = fixture(root)
        artifacts = source / "artifacts"
        _write_jsonl(artifacts / "entity_resolution_decisions.jsonl", [])

        def fake_l2(run_dir, **_):
            target_artifacts = Path(run_dir) / "artifacts"
            _write_jsonl(target_artifacts / "entity_resolution_decisions.jsonl", [
                {
                    "request": {"surface": "Snail"},
                    "normalization_status": "resolved_external_grounded",
                    "provider_trace": [
                        {"provider_name": "MyGeneCandidateProvider", "status": "candidates_returned", "network_calls_made": 1},
                        {"provider_name": "UniProtCandidateProvider", "status": "candidates_returned", "network_calls_made": 2},
                    ],
                }
            ])
            (target_artifacts / "entity_resolution_audit.json").write_text(json.dumps({"network_calls_made": 3}))
            for name in ("l2_graph_observations.jsonl", "l2_core_graph_observations.jsonl"):
                (target_artifacts / name).write_text("")

        from code_engine.cli.replay_case_from_stage import replay

        with patch("code_engine.workflow.steps.run_l2_abstract_step", side_effect=fake_l2):
            result = replay(
                profile, plan, source, "l2", root / "runs", "replay", "r2",
                network=True, api=False, entity_network_lookup=True, bundle_root=root / "bundles",
            )

        accounting = json.loads((Path(result["new_run"]) / "artifacts" / "replay_stage_call_accounting.json").read_text())
        calls = accounting["current_run_calls"]
        assert calls["abstract_retrieval_http_calls"] == 0
        assert calls["abstract_l1_provider_calls"] == 0
        assert calls["entity_network_calls"]["mygene"] == 1
        assert calls["entity_network_calls"]["uniprot"] == 2
        ledger = json.loads((Path(result["new_run"]) / "artifacts" / "replay_external_call_ledger.json").read_text())
        assert len(ledger["records"]) == 2
        assert {row["component"] for row in ledger["records"]} == {"entity_network_provider"}


def test_replay_entity_llm_cleaner_builds_and_injects_l2_client_without_l1_api_flag():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        profile, plan, source = fixture(root)
        client = object()

        def fake_l2(run_dir, **kwargs):
            assert kwargs["api"] is False
            assert kwargs["entity_llm_cleaner"] is True
            assert kwargs["entity_llm_client"] is client
            target_artifacts = Path(run_dir) / "artifacts"
            (target_artifacts / "entity_llm_cleaner_summary.json").write_text(json.dumps({
                "entity_llm_cleaner_calls_made": 2,
                "cleaner_actual_calls": 2,
                "cleaner_eligible_mentions": 3,
                "cleaner_cache_hits": 1,
            }))
            (target_artifacts / "entity_resolution_audit.json").write_text(json.dumps({"network_calls_made": 0}))
            for name in ("l2_graph_observations.jsonl", "l2_core_graph_observations.jsonl"):
                (target_artifacts / name).write_text("")

        from code_engine.cli.replay_case_from_stage import replay

        with patch("code_engine.extraction.client_factory.diagnose_entity_cleaner_provider", return_value={"provider_available": True}), \
             patch("code_engine.extraction.client_factory.build_entity_cleaner_client_from_config", return_value=client), \
             patch("code_engine.workflow.steps.run_l2_abstract_step", side_effect=fake_l2):
            result = replay(
                profile, plan, source, "l2", root / "runs", "replay", "r2",
                network=True, api=False, entity_llm_cleaner=True, bundle_root=root / "bundles",
            )

        accounting = json.loads((Path(result["new_run"]) / "artifacts" / "replay_stage_call_accounting.json").read_text())
        assert accounting["current_run_calls"]["abstract_l1_provider_calls"] == 0
        assert accounting["current_run_calls"]["l2_entity_llm_cleaner_calls"] == 2
        assert result["llm_used"] is True
        assert result["api_used"] is True


def test_replay_entity_llm_cleaner_fail_fast_when_client_unavailable():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        profile, plan, source = fixture(root)

        from code_engine.cli.replay_case_from_stage import replay

        with patch("code_engine.extraction.client_factory.diagnose_entity_cleaner_provider", return_value={"provider_available": False, "provider_error": "credential_missing"}), \
             patch("code_engine.workflow.steps.run_l2_abstract_step") as l2:
            with pytest.raises(RuntimeError, match="entity_llm_cleaner_requested_but_unavailable:credential_missing"):
                replay(
                    profile, plan, source, "l2", root / "runs", "replay", "r2",
                    network=True, api=False, entity_llm_cleaner=True, bundle_root=root / "bundles",
                )
            l2.assert_not_called()


def test_replay_source_l1_missing_fails_before_l2_initialization():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        profile, plan, source = fixture(root)
        (source / "artifacts" / "abstract_l1_claims.jsonl").unlink()

        from code_engine.cli.replay_case_from_stage import replay

        with patch("code_engine.workflow.steps.run_l2_abstract_step") as l2:
            with pytest.raises(FileNotFoundError):
                replay(profile, plan, source, "l2", root / "runs", "replay", "r2", bundle_root=root / "bundles")
            l2.assert_not_called()


def test_replay_terminal_state_audit_marks_completed_exit_zero():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        profile, plan, source = fixture(root)

        from code_engine.cli.replay_case_from_stage import replay

        result = replay(profile, plan, source, "l2", root / "runs", "replay", "r2", bundle_root=root / "bundles")
        run = Path(result["new_run"])
        terminal = json.loads((run / "artifacts" / "replay_terminal_state_audit.json").read_text())
        state = json.loads((run / "run_state.json").read_text())
        assert terminal["final_status"] == "completed"
        assert terminal["exit_code"] == 0
        assert terminal["no_stage_started_after_terminal"] is True
        assert state["final_status"] == "completed"
        assert state["current_step"] is None
