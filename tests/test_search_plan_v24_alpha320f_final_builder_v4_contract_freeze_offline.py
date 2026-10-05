"""Offline checks for the alpha3.20F contract freeze."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts import run_search_plan_v24_alpha320f_final_builder_v4_contract_freeze_offline as f


def test_preflight_reads_authoritative_frozen_state_only(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(f, "OUT", tmp_path / "not_created")
    state = f.preflight()
    assert state["e2_validation"]["semantic_comparison_state"] == "SEMANTIC_TIE"
    assert state["e2_validation"]["deterministic_selection_recommendation"] == "V1"
    assert not f.OUT.exists()


def test_temp_freeze_keeps_prompt_byte_identical_and_runtime_separate(
    monkeypatch,
) -> None:
    with TemporaryDirectory(prefix="alpha320f_test_", dir=f.RUNS) as temporary:
        output = Path(temporary) / "freeze"
        monkeypatch.setattr(f, "OUT", output)
        result = f.run()
        source = f.B / "prompt_variant_1_full_template.txt"
        assert (output / "final_selected_builder_v4_prompt.txt").read_bytes() == source.read_bytes()
        assert result["final_selected_builder_v4_prompt_sha256"] == f.PROMPT_SHA
        assert f.e2.r.e.d.c.root_hash(output, f.ROOT_MARKER) == result[
            "search_plan_v24_dev_alpha3_20f_sha256"
        ]
        contract = json.loads((output / "search_plan_builder_v4_final_contract.json").read_text())
        bundle = json.loads((output / "builder_v4_reproducibility_bundle.json").read_text())
        assert len(contract["components"]) == len({
            item["artifact_role"] for item in contract["components"]
        })
        assert contract["fresh_primary_attempt_started"] is False
        assert bundle["model_visible_development_results"] is False
        assert "semantic_comparison" not in bundle
        assert result["provider_calls"] == result["network_calls"] == 0
