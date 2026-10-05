"""Offline tests for alpha3.20F.1 selected-prompt hash authority."""

from pathlib import Path
from tempfile import TemporaryDirectory

from scripts import run_search_plan_v24_alpha320f1_selected_prompt_hash_authority_audit_offline as a


def test_byte_mismatch_offset_handles_equal_and_prefix() -> None:
    assert a.first_mismatch(b"same", b"same") is None
    assert a.first_mismatch(b"abc", b"abd") == 2
    assert a.first_mismatch(b"abc", b"abcd") == 3


def test_frozen_prompt_references_are_valid(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(a, "OUT", tmp_path / "not_created")
    state = a.preflight()
    assert a.sha(state["b_prompt_bytes"]) == a.PROMPT_SHA
    assert state["b_prompt_bytes"] == state["f_prompt_bytes"]
    inventory = a.audit_references()
    assert inventory["stored_hash_reference_count"] == 9
    assert inventory["malformed_stored_hash_reference_count"] == 0
    assert inventory["incorrect_valid_length_hash_reference_count"] == 0
    assert inventory["malformed_hash_fields"] == []


def test_binding_state_rejects_malformed_and_wrong_digest() -> None:
    path = a.F / "final_selected_builder_v4_prompt.txt"
    reference = a.file_ref(path, "selected_v1_full_prompt", "alpha3.20F")
    assert a.binding_state([reference], path) == "SAFE_EXACT_BINDING"
    assert a.binding_state([{**reference, "sha256": a.REPORTED_MALFORMED_SHA}],
                           path) == "MALFORMED_HASH_BINDING"
    assert a.binding_state([{**reference, "sha256": "0" * 64}],
                           path) == "INCORRECT_PROMPT_BINDING"


def test_temp_audit_freeze_is_report_only_and_preserves_upstream(monkeypatch) -> None:
    with TemporaryDirectory(prefix="alpha320f1_test_", dir=a.RUNS) as temporary:
        output = Path(temporary) / "audit"
        monkeypatch.setattr(a, "OUT", output)
        result = a.run()
        assert result["alpha3_20f1_classification"] == a.CLASS_REPORT_ONLY
        assert result["builder_v4_contract_ready_for_fresh_attempt"] is True
        assert result["alpha3_20f_contract_correction_required"] is False
        assert not (output /
                    "prospective_builder_v4_hash_authority_correction_draft.json").exists()
        assert a.root_hash(output, a.ROOT_MARKER) == result[a.ROOT_MARKER]
        assert a.verify_root(a.F, "search_plan_v24_dev_alpha3_20f_sha256", a.F_ROOT)
        assert a.verify_root(a.B, "search_plan_v24_dev_alpha3_20b_sha256", a.B_ROOT)
