import copy
import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from code_engine.cli.fulltext_l1_v2_provider_smoke_test import main as v2_main
from code_engine.cli.fulltext_l1_v3_provider_smoke_test import main as v3_main
from code_engine.extraction.deepseek_client import DeepSeekExtractionError, JSONExtractionResult
from code_engine.fulltext import fulltext_l1_v3_smoke as smoke
from code_engine.fulltext.fulltext_l1_v2 import DEFAULT_MAX_TOKENS, PROMPT_VERSION, SCHEMA_VERSION
from code_engine.fulltext.fulltext_l1_draft_hydration_v3 import HYDRATOR_VERSION
from code_engine.schemas.fulltext_observation_draft import DRAFT_SCHEMA_VERSION, fulltext_l1_draft_prompt_examples


def _plan():
    return {
        "schema_version": "fulltext_l1_v3_anchor_authoritative_provider_smoke_plan_v2", "mode": "plan_only",
        "maximum_provider_calls": 2, "planned_provider_calls": 2,
        "entries": [{"block_id": block_id, "validation_role": role,
                     "provider_call_planned": True, "provider_call_executed": False}
                    for block_id, role in smoke.FROZEN_SELECTION],
    }


def _inventory():
    return {block_id: {
        "block": {"block_id": block_id, "text": "CURRENT_RESULTS: Observed increase.",
                  "chunk_hash": f"hash-{block_id}", "section": {"section_title": "Results"}},
        "paper": {"paper_id": block_id, "pmid": block_id, "pmcid": block_id.split("_")[0]},
        "source_fulltext_hash": f"source-{block_id}", "article_path": "article_text.json",
    } for block_id, _ in smoke.FROZEN_SELECTION}


def _run(tmp_path: Path) -> Path:
    run = tmp_path / "run"; artifacts = run / "artifacts"; artifacts.mkdir(parents=True)
    (artifacts / smoke.PLAN_ARTIFACT).write_text(json.dumps(_plan()))
    (artifacts / "fulltext_l1_v2_summary.json").write_text(json.dumps({
        "scientific_input_complete": False, "partial_block_failures": True,
        "consistency_report": {"publication_allowed": False},
    }))
    return run


def _draft(block_id: str):
    _, payload = fulltext_l1_draft_prompt_examples(); row = payload["experimental_observations"][0]
    evidence = "Observed increase."
    row["experiment"].update({"experiment_label_raw": "exp", "evidence_family_label_raw": "family",
                              "design_type_raw": "in_vitro", "comparison_arm_raw": "treated",
                              "control_arm_raw": "control"})
    row["interventions"][0].update({"role_raw": "primary", "intervention_type_raw": "knockdown",
                                    "intervention_target_mention": "target"})
    row["measurement"].update({"measurement_dimension_raw": "abundance_expression",
                               "measured_entity_mention": "endpoint", "outcome_mention": "endpoint"})
    row["observation"].update({"observed_result": evidence, "lexical_direction_raw": "positive",
                               "comparison_raw": "treated versus control"})
    row["candidate_relation"].update({"subject_mention": "target", "object_mention": "endpoint",
                                      "lexical_direction_raw": "positive"})
    for item in [*row["evidence_references"], row["observation"]["evidence"],
                 row["measurement"]["evidence"], row["interventions"][0]["evidence"]]:
        item["model_selected_excerpt_raw"] = evidence; item["evidence_anchor_ids"] = [f"{block_id}:S0001"]
    if block_id == "PMC7744182_1_0":
        second = copy.deepcopy(row["interventions"][0]); second["role_raw"] = "secondary"
        second["intervention_target_mention"] = "second target"; row["interventions"].append(second)
        row["combination_mode_raw"] = "concurrent"
    if block_id == "PMC7749157_1_0": row["interventions"][0]["intervention_type_raw"] = "stabilization"
    if block_id == "PMC7708218_12_0":
        row["observation"]["lexical_direction_raw"] = "mixed"
        row["candidate_relation"]["lexical_direction_raw"] = "mixed"
    return payload


class GoodClient:
    def __init__(self): self.calls = []
    def extract_json_result(self, prompt, **kwargs):
        block_id = re.findall(r"\[(PMC[^\]]+):S0001\]", prompt)[0]
        self.calls.append((block_id, kwargs))
        payload = _draft(block_id)
        return JSONExtractionResult(payload=payload, raw_response=json.dumps(payload), finish_reason="stop", usage={})


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    run = _run(tmp_path); inventory = _inventory()
    config = {"max_sections": 12, "max_chunks_per_paper": 24, "max_chars": 6000,
              "max_total_chunks": 200, "max_tokens": 32768}
    monkeypatch.setattr(smoke, "_resolve_inventory", lambda _run: (inventory, config))
    return run, inventory


def test_profile_separation_is_explicit_and_v2_cli_is_not_switched(tmp_path, capsys):
    with patch("code_engine.cli.fulltext_l1_v2_provider_smoke_test.write_plan_artifacts",
               return_value={"planned_provider_calls": 12, "manifest_blocks": list(range(12))}):
        assert v2_main(["--run-dir", str(tmp_path)]) == 0
    old = json.loads(capsys.readouterr().out)
    assert old["planned_provider_calls"] == 12
    assert old["smoke_profile"] == "historical_fulltext_l1_v2_v4_12_block_smoke"
    assert "historical v2/v4 12-block" in old["deprecation_notice"]


def test_manifest_is_exactly_frozen_ordered_unique_and_audited(isolated):
    run, _ = isolated; manifest = smoke.build_v3_manifest(run)
    assert [x["block_id"] for x in manifest["entries"]] == [x[0] for x in smoke.FROZEN_SELECTION]
    assert len({x["block_id"] for x in manifest["entries"]}) == manifest["sample_count"] == 2
    assert manifest["maximum_calls"] == 2 and manifest["source_plan_hash"]
    assert all(x["plan_hash"] and x["block_hash"] and x["source_hash"] and x["selection_reason"] for x in manifest["entries"])


def test_invalid_plan_and_missing_source_fail_closed_without_replacement(isolated, monkeypatch):
    run, inventory = isolated; path = run / "artifacts" / smoke.PLAN_ARTIFACT
    broken = _plan(); broken["entries"].append(copy.deepcopy(broken["entries"][0])); path.write_text(json.dumps(broken))
    with pytest.raises(RuntimeError, match="duplicate"): smoke.build_v3_manifest(run)
    path.write_text(json.dumps(_plan())); inventory.pop(smoke.FROZEN_SELECTION[1][0])
    with pytest.raises(RuntimeError, match="cannot be resolved"): smoke.build_v3_manifest(run)


def test_plan_only_is_zero_call_versioned_and_preserves_state(isolated):
    run, _ = isolated; protected = (run / "artifacts/fulltext_l1_v2_summary.json").read_bytes()
    result = smoke.write_v3_plan_artifacts(run)
    assert result["planned_provider_calls"] == result["maximum_calls"] == 2
    assert result["api_calls"] == result["network_calls"] == result["downloads"] == 0
    assert result["smoke_profile"] == smoke.SMOKE_PROFILE and result["manifest_only"] is True
    assert result["prompt_version"] == PROMPT_VERSION
    assert result["draft_schema_version"] == DRAFT_SCHEMA_VERSION
    assert result["formal_schema_version"] == SCHEMA_VERSION
    assert result["hydrator_version"] == HYDRATOR_VERSION
    assert result["thinking_mode"] == "disabled" and result["thinking_parameter_sent"] is True
    assert result["protected_state_hashes_unchanged"] is True
    assert (run / "artifacts/fulltext_l1_v2_summary.json").read_bytes() == protected
    assert not (run / "artifacts" / smoke.RESULTS_ARTIFACT).exists()


def test_cli_defaults_plan_only_and_retains_double_authorization(isolated, capsys):
    run, _ = isolated
    assert v3_main(["--run-dir", str(run)]) == 0
    assert json.loads(capsys.readouterr().out)["planned_provider_calls"] == 2
    with pytest.raises(SystemExit): v3_main(["--run-dir", str(run), "--execute"])
    with pytest.raises(SystemExit): v3_main(["--run-dir", str(run), "--api"])


def test_execute_uses_v7_authoritative_anchors_v3_hydration_and_never_exceeds_two(isolated):
    run, _ = isolated; smoke.write_v3_plan_artifacts(run); client = GoodClient()
    result = smoke.execute_v3_smoke(run, api_authorized=True, client=client)
    assert result["api_calls"] == result["network_calls"] == 2
    assert result["maximum_calls"] == 2 and len(client.calls) == 2
    assert [x[0] for x in client.calls] == [x[0] for x in smoke.FROZEN_SELECTION]
    assert all(kwargs["max_tokens"] == DEFAULT_MAX_TOKENS and kwargs["thinking_mode"] == "disabled"
               and kwargs["retry_on_length"] is False for _, kwargs in client.calls)
    assert result["draft_valid_blocks"] == 2 and result["formal_valid_observation_count"] == 2
    assert result["anchor_id_valid_reference_count"] > 0 and result["formal_evidence_binding_failure_count"] == 0
    assert result["multi_intervention_count"] == 1 and result["mixed_direction_count"] == 0
    assert result["scientific_input_complete"] is False and result["publication_allowed"] is False
    assert result["atlas_publication_executed"] is False and result["protected_state_hashes_unchanged"] is True


def test_compatible_cache_reduces_calls_and_old_cache_cannot_hit(isolated):
    run, _ = isolated
    manifest = smoke.build_v3_manifest(run); first = manifest["entries"][0]
    old_root = run / "artifacts/cache/fulltext_l1_v2"; old_root.mkdir(parents=True)
    (old_root / f"{first['cache_identity']}.json").write_text(json.dumps({"prompt_version": "v4"}))
    native_root = run / "artifacts" / smoke.CACHE_DIR; native_root.mkdir(parents=True)
    (native_root / f"{first['cache_identity']}.json").write_text(json.dumps({
        "smoke_profile": smoke.SMOKE_PROFILE, "prompt_version": "fulltext_experimental_observation_prompt_v5_draft_contract",
        "draft_response": _draft(first["block_id"]), "formal_response": {"schema_version": "fulltext_l1_experimental_observation_schema_v2", "experimental_observations": []},
    }))
    assert smoke.build_v3_preflight(smoke.build_v3_manifest(run))["planned_provider_calls"] == 2
    smoke.write_v3_plan_artifacts(run); client = GoodClient(); smoke.execute_v3_smoke(run, api_authorized=True, client=client)
    smoke.write_v3_plan_artifacts(run)
    class NeverClient:
        def extract_json_result(self, *_args, **_kwargs): raise AssertionError("compatible cache must avoid provider calls")
    cached = smoke.execute_v3_smoke(run, api_authorized=True, client=NeverClient())
    assert cached["api_calls"] == 0 and cached["cache_hits"] == 2


def test_fatal_provider_error_stops_after_one_call(isolated):
    run, _ = isolated; smoke.write_v3_plan_artifacts(run)
    class Fatal:
        calls = 0
        def extract_json_result(self, *_args, **_kwargs):
            self.calls += 1
            raise DeepSeekExtractionError("fatal", "fatal", 1, error_kind="authentication", retryable=False)
    client = Fatal(); result = smoke.execute_v3_smoke(run, api_authorized=True, client=client)
    assert client.calls == result["api_calls"] == 1
    assert result["provider_errors"] == 1 and result["stopped_reason"] == "provider_fatal_error"


def test_finish_reason_length_stops_without_retry(isolated):
    run, _ = isolated; smoke.write_v3_plan_artifacts(run)
    class Length:
        calls = 0
        def extract_json_result(self, prompt, **_kwargs):
            self.calls += 1; block_id = re.findall(r"\[(PMC[^\]]+):S0001\]", prompt)[0]
            payload = _draft(block_id)
            return JSONExtractionResult(payload=payload, raw_response=json.dumps(payload), finish_reason="length")
    client = Length(); result = smoke.execute_v3_smoke(run, api_authorized=True, client=client)
    assert client.calls == result["api_calls"] == 1
    assert result["output_truncation_count"] == 1
    assert result["stopped_reason"] == "finish_reason_length_no_retry"


def test_missing_native_anchor_fails_closed_without_exact_text_fallback(isolated):
    run, _ = isolated; smoke.write_v3_plan_artifacts(run)
    class MissingAnchors:
        def extract_json_result(self, prompt, **_kwargs):
            block_id = re.findall(r"\[(PMC[^\]]+):S0001\]", prompt)[0]; payload = _draft(block_id)
            row = payload["experimental_observations"][0]
            for item in [*row["evidence_references"], row["observation"]["evidence"],
                         row["measurement"]["evidence"], *[x["evidence"] for x in row["interventions"]]]:
                item["evidence_anchor_ids"] = []
            return JSONExtractionResult(payload=payload, raw_response=json.dumps(payload), finish_reason="stop")
    result = smoke.execute_v3_smoke(run, api_authorized=True, client=MissingAnchors())
    assert result["api_calls"] == 2 and result["draft_failed_blocks"] == 2
    assert result["formal_valid_observation_count"] == 0
    assert result["formal_incomplete_blocks"] == 2 and result["formal_zero_hydrated_blocks"] == 2


def test_result_metrics_keep_raw_nonempty_formal_failure_and_partial_incomplete():
    rows = [{"block_id": "PMC7269543_4_0", "api_called": True, "draft_valid": True,
             "raw_observation_count": 2, "formal_valid_observation_count": 1,
             "formal_rejected_count": 1, "formal_reviewable_count": 1,
             "formal_block_status": "incomplete", "status": "formal_partial"}]
    result = smoke._aggregate_results(rows, calls=1, stopped_reason=None)
    assert result["raw_observation_count"] == 2 and result["formal_valid_observation_count"] == 1
    assert result["formal_rejected_count"] == 1 and result["formal_incomplete_blocks"] == 1
    assert result["legacy_empty"]["raw_nonempty"] is True
    assert result["legacy_empty"]["formal_valid_nonempty"] is True
    assert result["legacy_empty"]["false_negative_candidate_status"] == "candidate"


def test_cache_identity_includes_smoke_profile(monkeypatch):
    args = dict(source_hash="s", block_hash="b", rendered_prompt_hash="p", config_hash="c")
    first = smoke.v3_smoke_cache_key(**args)
    monkeypatch.setattr(smoke, "SMOKE_PROFILE", "different_profile")
    assert smoke.v3_smoke_cache_key(**args) != first
