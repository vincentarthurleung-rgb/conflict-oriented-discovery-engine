"""Fail-closed fresh-heldout preregistration integrity tests."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_16_architecture_freeze_fresh_heldout_v3_preregistration_offline"


def load(name: str) -> dict:
    return json.loads((RUN / name).read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def test_architecture_and_run_roots_verify() -> None:
    manifest = load("architecture_freeze_manifest.json")
    assert all(sha(ROOT / path) == checksum for path, checksum in manifest["components"])
    expected = digest({
        "component_hashes": manifest["components"],
        "frozen_architecture_roots": manifest["frozen_architecture_roots"],
        "alpha3_15_interpretation_root": load("alpha3_15_root_verification.json")["actual_sha256"],
    })
    assert expected == manifest["architecture_freeze_sha256"]
    assert expected == (RUN / "architecture_freeze_sha256").read_text().strip()
    pairs = [[path.name, sha(path)] for path in sorted(RUN.iterdir())
             if path.is_file() and path.name != "search_plan_v24_dev_alpha3_16_sha256"]
    assert digest(pairs) == (RUN / "search_plan_v24_dev_alpha3_16_sha256").read_text().strip()


def test_no_untouched_pool_no_target_freeze() -> None:
    audit = [json.loads(line) for line in (RUN / "untouched_proposition_eligibility_audit.jsonl").read_text().splitlines()]
    assert len(audit) == 531
    assert Counter(row["eligibility_state"] for row in audit) == {
        "SEEN_CALIBRATION": 63,
        "SEEN_DEVELOPMENT": 24,
        "SEEN_DEBUGGING": 27,
        "PROVENANCE_UNRESOLVED": 417,
    }
    assert all(row["eligible_for_sampling"] is False for row in audit)
    assert (RUN / "fresh_heldout_sampling_frame.jsonl").read_bytes() == b""
    assert sha(RUN / "fresh_heldout_sampling_frame.jsonl") == (RUN / "fresh_heldout_sampling_frame_sha256").read_text().strip()
    assert (RUN / "fresh_heldout_v3_targets.jsonl").read_bytes() == b""
    assert (RUN / "fresh_heldout_v3_target_manifest_sha256").read_text().strip() == "null"
    assert load("target_freeze_barrier.json")["query_compilation_permitted"] is False
    assert load("validation.json")["status"] == "FAILED_CLOSED_INSUFFICIENT_UNTOUCHED_POOL"
    assert load("summary.json")["next_stage_recommendation"] == "CONSTRUCT_NEW_PROPOSITION_POOL_UNDER_BLINDED_PROTOCOL"


def test_seen_cases_and_zero_call_firewall() -> None:
    seen = load("seen_development_case_registry.json")["cases"]
    assert [item["case_id"] for item in seen] == [f"heldout_v2_{i}" for i in range(101, 109)]
    assert all(item["status"] == "SEEN_DEVELOPMENT_CASES" for item in seen)
    safety = load("scientific_state_safety_audit.json")
    for field in ("provider_calls", "llm_calls", "network_calls", "retrieval_calls",
                  "known_pmid_checks", "pubmed_hit_count_checks", "query_modifications",
                  "lexical_changes", "validator_changes", "selection_policy_changes"):
        assert safety[field] == 0
    assert load("development_label_nonuse_audit.json")["development_labels_used_for_case_selection"] is False

