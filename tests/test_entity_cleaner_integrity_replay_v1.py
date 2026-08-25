import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/20260825_entity_cleaner_integrity_repair_v1_offline/artifacts"


def _json(name):
    return json.loads((ART / name).read_text(encoding="utf-8"))


def _rows(name):
    return [json.loads(line) for line in (ART / name).read_text(encoding="utf-8").splitlines() if line]


def test_required_offline_replay_artifacts_exist():
    required = {
        "baseline.json", "git_head_provenance_audit.json", "entity_cleaner_rule_inventory_v1.json",
        "cleaner_transformation_inventory_v2.jsonl", "cleaner_boundary_integrity_classification_v1.jsonl",
        "cleaner_canonical_impact_replay_v1.jsonl", "entity_cleaner_affected_claims_v1.jsonl",
        "entity_cleaner_affected_signals_v1.jsonl", "entity_cleaner_revision_candidates_v1.jsonl",
        "entity_integrity_quality_state_summary.json", "scientific_state_safety_audit.json",
        "reference_regression_recheck.json", "production_leakage_audit.json",
        "autonomous_iteration_ledger.jsonl", "final_validation.json", "manifest.json", "summary.json",
    }
    assert required <= {path.name for path in ART.iterdir()}


def test_corpus_counts_and_refined_taxonomy_close_exactly():
    summary = _json("entity_integrity_quality_state_summary.json")
    assert summary["cleaner_inputs_scanned"] == 57902
    assert summary["cleaner_modified_value_count"] == 20020
    assert summary["boundary_change_total"] == 9963
    assert sum(summary[key] for key in (
        "supported_boundary_change_count", "unsupported_boundary_change_count",
        "ambiguous_boundary_change_count", "unclassified_boundary_change_count",
    )) == 9963
    assert summary["unclassified_boundary_change_count"] == 0


def test_every_boundary_event_has_one_primary_class():
    allowed = {
        "validated_semantic_normalization", "validated_formatting_normalization",
        "unsupported_boundary_change", "ambiguous_rule_authority", "unclassified",
    }
    records = _rows("cleaner_boundary_integrity_classification_v1.jsonl")
    assert len(records) == 9963
    assert all(record["primary_class"] in allowed for record in records)


def test_raw_and_historical_values_are_immutable_in_every_inventory_row():
    records = _rows("cleaner_transformation_inventory_v2.jsonl")
    assert len(records) == 57902
    assert all(record["raw_before"] == record["raw_after"] for record in records)
    assert all(record["historical_cleaned_retained"] for record in records)
    assert all(record["historical_normalized_retained"] for record in records)
    assert not any(record["historical_object_modified"] for record in records)


def test_all_historical_canonical_changes_receive_impact_replay():
    impacts = _rows("cleaner_canonical_impact_replay_v1.jsonl")
    changed = [record for record in impacts if record["historical_canonical_identity_changed"]]
    assert len(changed) == 327
    assert all(record["critical_unsupported_or_ambiguous_canonical_change"] for record in changed)
    assert all(record["identity_transition_state"] in {
        "historical_identity_still_valid", "historical_identity_invalidated_by_cleaner_corruption",
        "historical_identity_suspect_but_unresolved",
    } for record in changed)


def test_claim_blocking_requires_dependency_on_affected_entity():
    claims = _rows("entity_cleaner_affected_claims_v1.jsonl")
    blocked = [record for record in claims if record["claim_integrity_state"] == "blocked_upstream_entity_integrity"]
    assert blocked
    assert all(record["scientific_proposition_depends_on_affected_entity"] for record in blocked)


def test_both_affected_signals_are_discovered_from_lineage_and_fail_closed():
    signals = _rows("entity_cleaner_affected_signals_v1.jsonl")
    assert len(signals) == 2
    assert {record["signal_id"] for record in signals} == {"40f42ffa988cbcff", "b01a1e7d5f27cb9d"}
    assert {record["signal_scientific_eligibility"] for record in signals} == {
        "blocked_upstream_claim_integrity", "blocked_entity_identity_unresolved",
    }
    assert not any(record["new_contradiction_signal_created"] for record in signals)


def test_evaluation_case_is_generic_replay_output_and_remains_unresolved():
    case = _json("summary.json")["evaluation_case"]
    assert case["source_raw_entity"] == case["l1_raw_entity"] == "PAR1"
    assert case["historical_cleaned_entity"] == "AR1"
    assert case["historical_normalized_entity"] == "TCF20"
    assert case["repaired_cleaned_entity_candidate"] == "PAR1"
    assert case["repaired_normalized_entity_candidate"] is None
    assert case["scientific_bridge_created"] is False


def test_scientific_state_and_leakage_safety_are_closed():
    safety = _json("scientific_state_safety_audit.json")
    leakage = _json("production_leakage_audit.json")
    assert (safety["core_reference_exact_match_count"], safety["core_reference_fail_closed_match_count"], safety["core_reference_mismatch_count"]) == (33, 6, 0)
    assert safety["candidate_count_before"] == safety["candidate_count_after"] == 11
    assert safety["formal_conflict_count_before"] == safety["formal_conflict_count_after"] == 0
    assert safety["historical_assets_modified"] is False
    assert leakage["case_specific_rule_count"] == 0


def test_manifest_hashes_match_materialized_sidecars():
    manifest = _json("manifest.json")
    for record in manifest["files"]:
        path = ROOT / record["path"]
        assert path.stat().st_size == record["bytes"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]
