import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260902_single_source_provider_extraction_smoke_pmc10515557_v1"
ART = RUN / "artifacts"
GENERATOR = ROOT / "tools/generate_single_source_provider_extraction_smoke_pmc10515557_v1.py"


def load(name):
    return json.loads((ART / name).read_text())


def lines(name):
    return [json.loads(line) for line in (ART / name).read_text().splitlines() if line]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_offline_generator_cannot_import_a_provider_client():
    source = GENERATOR.read_text()
    assert "deepseek_client" not in source
    assert "build_json_client" not in source
    assert "extract_json_result" not in source


def test_offline_replay_preserves_paid_boundary_assets():
    protected = [ART / "raw_provider_response.txt", ART / "provider_attempt_ledger.json",
                 ART / "provider_request_manifest.json", ART / "provider_call_result.json"]
    before = {path: sha(path) for path in protected}
    subprocess.run([sys.executable, str(GENERATOR)], cwd=ROOT, check=True, capture_output=True, text=True)
    assert {path: sha(path) for path in protected} == before
    billing = load("billing_safety_audit.json")
    assert (billing["provider_calls"], billing["provider_attempts"], billing["provider_retries"]) == (1, 1, 0)


def test_raw_response_was_persisted_before_scientific_parser():
    manifest = load("raw_provider_response_manifest.json")
    assert manifest["persisted_before_scientific_parser_or_validator"] is True
    assert sha(ART / "raw_provider_response.txt") == manifest["raw_response_sha256"]


def test_all_six_candidates_preserve_separate_states_and_hydrate():
    parsed = lines("parsed_extraction_candidates.jsonl")
    validated = lines("validated_observations.jsonl")
    assert len(parsed) == len(validated) == 6
    assert all(set(("raw_state", "extracted_state", "validated_state", "normalized_state")) <= row.keys() for row in parsed)
    assert all(row["silent_normalization_performed"] is False for row in parsed)
    assert all(row["eligibility"]["formal_validity"] == "valid" for row in validated)


def test_observational_projection_does_not_invent_intervention():
    core = load("experimental_core_validation.json")
    assert core["structurally_eligible_count"] == 6
    assert "without_intervention" in core["projection_policy"]
    for row in core["observations"]:
        assert row["revision"]["observation_type"] == "observational_comparison"
        assert {factor["role"] for factor in row["factors"]} == {"experimental_group", "comparator"}
        assert row["integrity"]["status"] == "structurally_complete"


def test_entity_and_minimum_proposition_gates_are_satisfied():
    entity = lines("entity_authority_results.jsonl")
    sufficient = lines("minimum_proposition_sufficiency.jsonl")
    assert len(entity) == len(sufficient) == 6
    assert all(row["gate_result"]["authoritative_for_scientific_promotion"] for row in entity)
    assert all(row["minimum_profile_satisfied"] for row in sufficient)
    assert all(row["recovered_structured_semantics"]["intervention_proposition"] == "not_applicable" for row in sufficient)


def test_target_replay_is_direction_blind_and_independent():
    comparisons = lines("target_proposition_compatibility.jsonl")
    assert len(comparisons) == 6
    assert all(row["target_compatible"] for row in comparisons)
    assert all(not row["direction_or_polarity_used"] for row in comparisons)
    assert all(not row["contradiction_evaluation_executed"] for row in comparisons)
    assert load("cross_publication_independence_audit.json")["independence_state"] == "independent"


def test_level_accounting_and_safety_are_fail_closed():
    ledger = load("level_0_to_6_ledger.json")
    assert ledger["level_5_cross_publication_compatible_peers"] == 6
    assert ledger["level_6_source_independent_compatible_pairs"] == 18
    assert ledger["level_7_contradiction_evaluation_executed"] is False
    leakage = load("production_leakage_audit.json")
    assert all(leakage[key] is False for key in (
        "contradiction_evaluation_executed", "candidate_qualification_executed",
        "l4_or_formal_adjudication_executed", "atlas_activated", "active_pointer_changed",
        "variational_em_called",
    ))


def test_required_artifact_manifest_hashes_validate():
    manifest = load("manifest.json")
    assert manifest["self_excluded_to_avoid_recursive_hash"] is True
    for row in manifest["artifacts"]:
        path = ROOT / row["path"]
        assert path.stat().st_size == row["bytes"]
        assert sha(path) == row["sha256"]
    assert load("final_validation.json")["required_artifacts_present"] is True
