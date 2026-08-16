from __future__ import annotations

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/20260816_context_readiness_semantics_signal_fulltext_bridge_forensics_v1_offline/artifacts"


def load(name: str):
    return json.loads((ART / name).read_text(encoding="utf-8"))


def rows(name: str):
    return [json.loads(line) for line in (ART / name).read_text(encoding="utf-8").splitlines() if line]


@pytest.mark.parametrize("name", [
    "context_requirement_profiles.jsonl", "context_field_requirement_assignments.jsonl",
    "context_unresolved_reclassification.jsonl", "context_required_blocker_inventory.jsonl",
    "context_readiness_v2_v3_comparison.json", "context_readiness_v3_candidates.jsonl",
    "context_readiness_semantics_audit.json", "pi3k_signal_inventory.json",
    "pi3k_signal_source_identity_map.json", "pi3k_local_fulltext_coverage.json",
    "pi3k_signal_fulltext_bridge_forensics.jsonl", "pi3k_bridge_candidate_inventory.jsonl",
    "pi3k_bridge_forensic_summary.json", "bridge_next_action_decision_v1.json",
    "reference_regression_recheck.json", "scientific_state_safety_audit.json",
    "forensics_manifest.json", "forensics_summary.json",
])
def test_required_artifact_exists(name):
    assert (ART / name).is_file()


def test_readiness_v3_exposes_over_permissive_v2_without_replacing_it():
    audit = load("context_readiness_semantics_audit.json")
    assert audit["observation_count"] == audit["v2_ready_count"] == 418
    assert audit["v3_ready_count"] == 0
    assert audit["v3_reviewable_count"] == 418
    assert audit["readiness_semantic_conclusion"] == "over_permissive"
    assert audit["v2_candidate_preserved_read_only"] is True


def test_requirement_assignments_are_evidence_conservative():
    audit = load("context_readiness_semantics_audit.json")
    assert audit["field_requirement_assignment_count"] == 418 * 19
    assert audit["required_context_assignment_count"] == 0
    assert audit["optional_context_assignment_count"] == 0
    assert audit["unknown_requirement_assignment_count"] == 418 * 19
    assert audit["unknown_requirement_unresolved_count"] == 3824
    assert audit["source_not_reported_count"] == audit["ambiguous_context_count"] == 0


def test_both_signal_identities_are_scanned_and_not_assumed():
    source = rows("pi3k_signal_fulltext_bridge_forensics.jsonl")
    original = [json.loads(line)["candidate_id"] for line in (
        ROOT / "runs/20260723_183417_pi3k_akt_mtor_cancer_resistance_discovery_v1_fulltext_v3_native_reentry/artifacts/abstract_conflict_candidates.jsonl"
    ).read_text(encoding="utf-8").splitlines() if line]
    assert [x["signal_id"] for x in source] == original


def test_forensics_fails_closed_on_identity_mismatch():
    records = rows("pi3k_signal_fulltext_bridge_forensics.jsonl")
    assert {x["forensic_classification"] for x in records} == {"provenance_identity_mismatch"}
    assert all(x["provenance_bridge_status"] == "identity_mismatch" for x in records)
    assert all(x["scientific_bridge_created"] is False for x in records)


def test_paid_smoke_is_not_recommended_when_source_is_local():
    decision = load("bridge_next_action_decision_v1.json")
    assert decision["paid_smoke_recommended"] is False
    assert decision["estimated_extraction_units"] == 0
    assert decision["execution_authorized"] is False


def test_historical_scientific_state_hashes_are_unchanged():
    audit = load("scientific_state_safety_audit.json")
    assert audit["protected_hashes_before"] == audit["protected_hashes_after"]
    assert (audit["candidate_count_before"], audit["candidate_count_after"]) == (11, 11)
    assert (audit["formal_conflict_count_before"], audit["formal_conflict_count_after"]) == (0, 0)
    assert audit["historical_assets_modified"] is False
