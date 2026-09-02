import hashlib
import json
from pathlib import Path
import subprocess
import sys

from code_engine.context_attribution.conflict_candidate.cross_publication_replay_v1_candidate import (
    compare_observational_outcomes_v1,
    normalize_observational_contrast_v1,
    orient_observational_outcome_v1,
    qualify_scientific_candidate_v2,
)


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260902_cross_publication_contradiction_replay_trib3_survival_v1_offline"
ART = RUN / "artifacts"
GEN = ROOT / "tools/generate_cross_publication_contradiction_replay_trib3_survival_v1.py"
MODULE = ROOT / "src/code_engine/context_attribution/conflict_candidate/cross_publication_replay_v1_candidate.py"


def jl(name):
    return [json.loads(line) for line in (ART / name).read_text().splitlines() if line]


def js(name):
    return json.loads((ART / name).read_text())


def exact(oid="a", a="high TRIB3", b="low TRIB3"):
    return normalize_observational_contrast_v1(
        observation_id=oid, group_a=a, group_b=b, structured_group_a_state="higher",
        structured_group_b_state="lower", explicit_authority_refs=["structured arms"],
    )


def outcome(oid, direction, contrast=None, representation="survival", inverse=None):
    return orient_observational_outcome_v1(
        observation_id=oid, endpoint_family="clinical_outcome", result_representation=representation,
        structured_direction=direction, contrast=contrast or exact(oid), evidence_span_ids=["anchor"],
        hazard_survival_inverse_authority=inverse,
    )


def qualify(**updates):
    args = dict(
        pair_id="pair", observation_a_id="a", observation_b_id="b", evidence_unit_a_id="ua",
        evidence_unit_b_id="ub", proposition_compatible=True, entity_integrity_eligible=True,
        publication_independent=True, evidence_unit_independence_state="resolved_distinct_unit",
        contrast_orientation_state="contrast_orientation_exact",
        result_orientation_state_a="result_orientation_resolved",
        result_orientation_state_b="result_orientation_resolved", contradiction_state="opposing_direction",
        representative_evidence_pair=True,
    )
    args.update(updates)
    return qualify_scientific_candidate_v2(**args)


def test_reversed_group_order_cannot_manufacture_contradiction():
    forward = outcome("forward", "positive")
    reverse_contrast = normalize_observational_contrast_v1(
        observation_id="reverse", group_a="low TRIB3", group_b="high TRIB3",
        structured_group_a_state="lower", structured_group_b_state="higher",
        explicit_authority_refs=["structured arms"],
    )
    reverse = outcome("reverse", "negative", reverse_contrast)
    assert reverse_contrast.source_order_reversed_for_canonical_orientation is True
    assert forward.result_orientation == reverse.result_orientation == "supports_higher_outcome"
    assert compare_observational_outcomes_v1(forward, reverse) == "same_direction"


def test_high_low_and_low_high_require_explicit_authority():
    unresolved = normalize_observational_contrast_v1(
        observation_id="x", group_a="low", group_b="high", structured_group_a_state="lower",
        structured_group_b_state="higher", explicit_authority_refs=[],
    )
    resolved = normalize_observational_contrast_v1(
        observation_id="x", group_a="low", group_b="high", structured_group_a_state="lower",
        structured_group_b_state="higher", explicit_authority_refs=["structured arms"],
    )
    assert unresolved.orientation_state == "contrast_orientation_unresolved"
    assert resolved.orientation_state == "contrast_orientation_normalized_deterministically"


def test_survival_and_hazard_are_not_naively_compared():
    survival = outcome("s", "negative")
    hazard = outcome("h", "positive", representation="hazard_or_risk")
    assert hazard.orientation_state == "result_orientation_unresolved"
    assert compare_observational_outcomes_v1(survival, hazard) == "result_relation_unresolved"
    authorized = outcome("h2", "positive", representation="hazard_or_risk", inverse="explicit hazard-survival inverse contract")
    assert authorized.result_orientation == "supports_lower_outcome"


def test_same_evidence_unit_does_not_count_as_independent_candidate():
    q = qualify(evidence_unit_independence_state="same_unit")
    assert q.qualification_state == "blocked_duplicate_or_same_unit"
    assert q.qualified_for_l4_entry is False


def test_multiple_observations_do_not_become_publications():
    units = jl("evidence_unit_inventory.jsonl")
    assert len({x["publication_id"] for x in units}) == 2
    old = [x for x in units if x["publication_id"] == "pmid:33380827"]
    assert len(old) == 3 and len({x["evidence_unit_id"] for x in old}) == 1
    audit = js("duplicate_pseudoreplication_audit.json")
    assert audit["new_parent_study_count"] == audit["new_parent_cohort_count"] == 1


def test_same_direction_is_agreement_not_candidate():
    a, b = outcome("a", "negative"), outcome("b", "negative")
    assert compare_observational_outcomes_v1(a, b) == "same_direction"
    assert qualify(contradiction_state="same_direction").qualification_state == "blocked_not_contradictory"


def test_opposite_resolved_direction_enters_candidate_qualification():
    a, b = outcome("a", "positive"), outcome("b", "negative")
    assert compare_observational_outcomes_v1(a, b) == "opposing_direction"
    q = qualify()
    assert q.qualification_state == "qualified_scientific_candidate"
    assert q.qualified_for_l4_entry is True


def test_unresolved_result_direction_remains_reviewable():
    assert outcome("a", None).orientation_state == "result_orientation_unresolved"
    q = qualify(result_orientation_state_a="result_orientation_unresolved",
                contradiction_state="result_relation_unresolved")
    assert q.qualification_state == "reviewable_result_orientation"


def test_proposition_compatibility_is_an_upstream_gate():
    q = qualify(proposition_compatible=False)
    assert q.qualification_state == "blocked_proposition"


def test_replay_counts_clusters_before_candidate_qualification():
    summary = js("summary.json")
    assert summary["raw_cross_publication_pair_count"] == 18
    assert summary["independent_evidence_pair_count"] == 6
    assert summary["unique_study_cohort_comparison_count"] == 1
    assert summary["opposing_direction_observation_pair_count"] == 6
    assert summary["unique_opposing_evidence_unit_pair_count"] == 2
    assert summary["qualified_scientific_candidate_count"] == 2


def test_historical_candidates_unchanged_and_no_l4_execution():
    safety = js("scientific_state_safety_audit.json")
    assert safety["historical_candidate_object_count_before"] == safety["historical_candidate_object_count_after"] == 11
    assert safety["protected_hashes_unchanged"] is True
    assert all(not row["l4_executed"] for row in jl("l4_entry_readiness_candidate.jsonl"))
    assert not any(js("production_leakage_audit.json")[key] for key in (
        "l4a_executed", "l4b_executed", "divergence_executed", "l4c_formal_executed",
    ))


def test_no_provider_network_calls_and_no_source_specific_production_rule():
    code = GEN.read_text() + MODULE.read_text()
    for token in ("deepseek_client", "build_json_client", "requests.", "urllib", "httpx", "PMC10515557"):
        assert token not in code
    leakage = js("production_leakage_audit.json")
    assert all(leakage[key] == 0 for key in ("provider_calls", "llm_calls", "api_calls", "network_calls", "downloads"))


def test_offline_generator_is_idempotent_and_preserves_inputs():
    protected = [ROOT / path for path in js("scientific_state_safety_audit.json")["protected_input_sha256_before"]]
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in protected}
    subprocess.run([sys.executable, str(GEN)], cwd=ROOT, check=True, capture_output=True, text=True)
    assert {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in protected} == before
    manifest = js("manifest.json")
    for row in manifest["artifacts"]:
        path = ROOT / row["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]
