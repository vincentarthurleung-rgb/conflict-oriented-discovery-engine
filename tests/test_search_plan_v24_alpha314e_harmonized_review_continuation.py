"""Offline integrity checks for the completed alpha3.14e continuation."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260926_search_plan_v24_dev_alpha3_14e_harmonized_review_continuation"
SCRIPT = ROOT / "scripts/run_search_plan_v24_alpha314e_harmonized_review_continuation.py"
SPEC = importlib.util.spec_from_file_location("alpha314e_continuation", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def load(name: str) -> dict:
    return json.loads((RUN / name).read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_manifest(manifest_name: str, root_name: str, field_name: str) -> None:
    manifest = load(manifest_name)
    for relative_path, checksum in manifest["aggregate_components"]:
        assert sha(RUN / relative_path) == checksum
    expected = MODULE.digest(manifest["aggregate_components"])
    assert expected == manifest[field_name]
    assert expected == (RUN / root_name).read_text(encoding="utf-8").strip()


def test_authoritative_roots_and_historical_preservation() -> None:
    MODULE.verify_upstreams()
    snapshot = load("historical_preservation_snapshot.json")
    for root, field in (
        (MODULE.FAILED_313, "failed_alpha3_13_inventory_sha256"),
        (MODULE.FAILED_314B, "failed_alpha3_14b_inventory_sha256"),
        (MODULE.AUTOPSY, "alpha3_14c_inventory_sha256"),
    ):
        assert MODULE.digest(MODULE.inventory(root)) == snapshot[field]
    invalid = load("invalid_superseded_inference_preservation_audit.json")
    assert invalid["old_inference_status"] == "INVALID_SUPERSEDED_INFERENCE"
    assert sha(ROOT / invalid["old_raw_preserved_at"]) == invalid["old_batch3_raw_sha256"]
    assert invalid["old_scientific_labels_not_compared_to_replacement"] is True


def test_sequential_six_call_gate_and_accounting() -> None:
    attempts = [load(f"attempts/pass_b_batch_{index:02d}.json") for index in range(3, 9)]
    assert [attempt["batch_index"] for attempt in attempts] == list(range(3, 9))
    assert all(attempt["single_attempt_committed_before_network"] for attempt in attempts)
    assert [attempt["started_unix_time"] for attempt in attempts] == sorted(
        attempt["started_unix_time"] for attempt in attempts
    )
    gate = load("gate/replacement_batch3_validation.json")
    assert gate["status"] == "VALID"
    assert gate["full_schema_valid"] and gate["identity_binding_valid"]
    assert gate["next_batches_permitted"] == [4, 5, 6, 7, 8]
    assert gate["old_invalid_inference_reused"] is False
    accounting = load("model_call_accounting.json")
    assert accounting["new_inference_events"] == 6
    assert accounting["cumulative_provider_inference_events"] == 17
    assert accounting["planned_batch_identities"] == 16
    assert accounting["valid_final_batch_adjudications"] == 16
    assert accounting["invalid_superseded_inference_events"] == 1
    assert accounting["reinferred_batch_identities"] == 1
    assert all(accounting[key] == 0 for key in (
        "pass_a_reinference_calls", "pass_b_batch1_reinference_calls",
        "pass_b_batch2_reinference_calls", "unplanned_scientific_adjudication_calls",
    ))


def test_blinded_freeze_precedes_unblinding_and_results_are_frozen() -> None:
    verify_manifest(
        "harmonized_deepseek_blinded_adjudication_corpus_manifest.json",
        "harmonized_deepseek_blinded_adjudication_corpus_sha256",
        "harmonized_deepseek_blinded_adjudication_corpus_sha256",
    )
    barrier = load("unblinding_barrier_audit.json")
    assert barrier["all_component_hashes_verified_before_map_open"] is True
    assert barrier["blinded_adjudication_freeze_verified"] is True
    assert barrier["arm_map_accessed_before_blinded_freeze"] is False
    assert barrier["metrics_computed_before_blinded_freeze"] is False
    verify_manifest(
        "harmonized_deepseek_review_results_manifest.json",
        "harmonized_deepseek_review_results_sha256",
        "harmonized_deepseek_review_results_sha256",
    )
    assert load("validation.json")["status"] == "PASS"
    assert load("summary.json")["status"] == "completed"

