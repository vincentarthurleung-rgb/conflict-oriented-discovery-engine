"""The final completion archive must disclose its non-repairable timing gap."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/20260926_search_plan_v24_dev_alpha3_14e_harmonized_review_continuation"
ARCHIVE = ROOT / "runs/20260926_search_plan_v24_dev_alpha3_14e_final_harmonized_review_completion"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def load(name: str) -> dict:
    return json.loads((ARCHIVE / name).read_text(encoding="utf-8"))


def test_archive_roots_and_byte_identical_scientific_artifacts() -> None:
    result_manifest = load("harmonized_deepseek_review_results_manifest.json")
    pairs = result_manifest["aggregate_components"]
    assert all(sha(ARCHIVE / name) == checksum for name, checksum in pairs)
    assert digest(pairs) == (ARCHIVE / "harmonized_deepseek_review_results_sha256").read_text().strip()
    root_pairs = [[path.name, sha(path)] for path in sorted(ARCHIVE.iterdir())
                  if path.is_file() and path.name != "search_plan_v24_dev_alpha3_14e_sha256"]
    assert digest(root_pairs) == (ARCHIVE / "search_plan_v24_dev_alpha3_14e_sha256").read_text().strip()
    for name in (
        "complete_blinded_review_unit_results.jsonl", "unblinding_barrier_audit.json",
        "harmonized_arm_results.jsonl", "harmonized_v23_metrics.json",
        "harmonized_lexical_v2_metrics.json", "original_v23_vs_harmonized_v23_comparison.json",
        "harmonized_v23_vs_lexical_v2_comparison.json",
    ):
        assert sha(ARCHIVE / name) == sha(SOURCE / name)
    assert sha(ARCHIVE / "pass_b_batch3_replacement_raw_response.json") == sha(SOURCE / "raw_responses/pass_b_batch_03.json")


def test_fail_closed_temporal_disclosure_and_inference_accounting() -> None:
    assert load("validation.json")["status"] == "FAILED_PROTOCOL_CHRONOLOGY"
    assert load("summary.json")["status"] == "failed"
    assert load("remaining_five_batch_derivation.json")["strict_post_gate_request_derivation_satisfied"] is False
    accounting = load("complete_model_inference_accounting.json")
    assert accounting["historical_inference_events"] == 11
    assert accounting["replacement_batch3_call_count"] == 1
    assert accounting["remaining_never_inferred_calls"] == 5
    assert accounting["cumulative_provider_inference_events"] == 17
    assert accounting["new_calls_in_this_archival_turn"] == 0
    assert accounting["invalid_superseded_inference_events"] == 1
    assert load("complete_pass_b_summary.json")["valid_review_units"] == 71
    assert load("post_failure_protocol_amendment_disclosure.json")["post_failure_identity_binding_amendment_disclosed"] is True
    assert load("post_failure_protocol_amendment_disclosure.json")["post_failure_output_contract_amendment_disclosed"] is True

