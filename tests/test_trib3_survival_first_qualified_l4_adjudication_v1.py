import hashlib
import json
from pathlib import Path

from code_engine.context_attribution.conflict_adjudication.first_qualified_l4_v1_candidate import (
    assess_divergence_explanatory_power_v1,
    make_formal_judgment_candidate_v1,
)
from code_engine.extraction_assets.context.pair_requirements_v2 import L4bUpstreamEligibilityV1
from code_engine.extraction_assets.context.pair_requirements_v3_candidate import (
    CONTEXT_DIMENSIONS,
    activate_pair_dimension_v3_candidate,
    evaluate_l4b_v3_candidate,
    make_requirement_authority_v1,
)


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/20260902_trib3_survival_first_qualified_l4_adjudication_v1_offline/artifacts"
PRODUCTION = ROOT / "src/code_engine/context_attribution/conflict_adjudication/first_qualified_l4_v1_candidate.py"


def _json(name):
    return json.loads((ART / name).read_text(encoding="utf-8"))


def _rows(name):
    return [json.loads(line) for line in (ART / name).read_text(encoding="utf-8").splitlines() if line]


def _unresolved_explanation():
    return assess_divergence_explanatory_power_v1(
        pair_id="generic-pair", context_dimension="disease",
        context_difference_identity="generic-difference", difference_validated=True,
        two_sided_context_resolved=True, explanation_eligible=True,
        source_refs=["structured-source#span"],
    )


def test_context_difference_does_not_automatically_imply_explanation():
    result = _unresolved_explanation()
    assert result.explanation_state == "explanatory_power_unresolved"
    assert result.sufficient_to_explain_divergence is None


def test_context_difference_does_not_automatically_imply_incomparability():
    results = _rows("l4b_comparability_results.jsonl")
    assert {row["l4b_state"] for row in results} == {"comparable_with_context_divergence"}
    assert all(row["comparable"] is True for row in results)


def test_disease_population_difference_is_not_hardcoded_as_explanatory():
    disease = [row for row in _rows("divergence_explanatory_power_results.jsonl") if row["context_dimension"] == "disease"]
    assert len(disease) == 2
    assert all(row["explanation_state"] == "explanatory_power_unresolved" for row in disease)


def test_resolved_explanation_candidate_difference_can_remain_comparable():
    l4a = _rows("l4a_context_difference_results.jsonl")
    l4b = {row["pair_id"]: row for row in _rows("l4b_comparability_results.jsonl")}
    assert all(l4b[row["pair_id"]]["comparable"] is True for row in l4a if row["difference_state"] == "different")


def test_unresolved_required_context_cannot_pass_l4b():
    pair = "generic-unresolved-pair"
    activations = []
    for dimension in CONTEXT_DIMENSIONS:
        authorities = [] if dimension == "disease" else [make_requirement_authority_v1(
            pair_id=pair, consumer="l4b_comparability", dimension=dimension,
            authority_state="not_applicable", authority="structural_inapplicability_rule",
            contract_refs=["generic-contract-v1"], reason="generic bounded test authority",
        )]
        activations.append(activate_pair_dimension_v3_candidate(
            pair_id=pair, consumer="l4b_comparability", dimension=dimension,
            trigger_facts=[], requirement_authorities=authorities,
        ))
    upstream = L4bUpstreamEligibilityV1(
        pair_id=pair, entity_integrity_eligible=True, alignment_eligible=True,
        contradiction_signal_valid=True, candidate_qualification_eligible=True,
        entity_integrity_state="eligible", alignment_state="aligned",
        contradiction_signal_state="validated", candidate_qualification_state="qualified",
    )
    result, _ = evaluate_l4b_v3_candidate(
        pair_id=pair, upstream=upstream, activations=activations, dimension_evidence=[],
    )
    assert result.comparable is None
    assert result.l4b_state == "reviewable_requirement_semantics_unresolved"


def test_unsupported_explanation_cannot_suppress_residual_disagreement():
    assessed_insufficient = assess_divergence_explanatory_power_v1(
        pair_id="generic-pair", context_dimension="disease",
        context_difference_identity="generic-difference", difference_validated=True,
        two_sided_context_resolved=True, explanation_eligible=True,
        source_refs=["structured-source#span"], explanation_policy_identity="policy-v1",
        authoritative_sufficiency=False,
    )
    formal = make_formal_judgment_candidate_v1(
        pair_id="generic-pair", upstream_valid=True, evidence_independence_valid=True,
        provenance_adequate=True, l4b_state="comparable_with_context_divergence",
        l4b_comparable=True, explanation_results=[assessed_insufficient],
    )
    assert assessed_insufficient.explanation_state == "difference_not_explanatory_under_contract"
    assert formal.formal_candidate_state == "formal_conflict_candidate_confirmed"


def test_unresolved_explanatory_power_does_not_automatically_confirm_formal():
    formal = make_formal_judgment_candidate_v1(
        pair_id="generic-pair", upstream_valid=True, evidence_independence_valid=True,
        provenance_adequate=True, l4b_state="comparable_with_context_divergence",
        l4b_comparable=True, explanation_results=[_unresolved_explanation()],
    )
    assert formal.formal_candidate_state == "reviewable_divergence_explanation_unresolved"


def test_absent_explanation_assessment_fails_closed():
    formal = make_formal_judgment_candidate_v1(
        pair_id="generic-pair", upstream_valid=True, evidence_independence_valid=True,
        provenance_adequate=True, l4b_state="comparable_all_required_context_resolved",
        l4b_comparable=True, explanation_results=[],
    )
    assert formal.formal_candidate_state == "reviewable_divergence_explanation_unresolved"


def test_supported_sufficient_explanation_prevents_formal_confirmation():
    supported = assess_divergence_explanatory_power_v1(
        pair_id="generic-pair", context_dimension="disease",
        context_difference_identity="generic-difference", difference_validated=True,
        two_sided_context_resolved=True, explanation_eligible=True,
        source_refs=["structured-source#span"], explanation_policy_identity="policy-v1",
        authoritative_sufficiency=True,
    )
    formal = make_formal_judgment_candidate_v1(
        pair_id="generic-pair", upstream_valid=True, evidence_independence_valid=True,
        provenance_adequate=True, l4b_state="comparable_with_context_divergence",
        l4b_comparable=True, explanation_results=[supported],
    )
    assert formal.formal_candidate_state == "not_confirmed_context_explained"


def test_two_subgroup_pairs_aggregate_to_one_publication_structure():
    structure = _json("publication_disagreement_structure.json")
    assert len(structure["candidate_pair_refs"]) == 2
    assert structure["analysis_level_support_count"] == 2
    assert structure["publication_level_disagreement_count"] == 1
    assert structure["independent_conflict_count_asserted"] == 0


def test_neutral_analyses_remain_outside_current_l4():
    audit = _json("neutral_analysis_preservation_audit.json")
    assert audit["reviewable_neutral_evidence_pair_count"] == 4
    assert audit["included_in_current_l4"] is False
    assert audit["states_modified"] is False


def test_no_llm_explanation_authority_and_no_provider_or_network_calls():
    assert all(row["llm_authority_used"] is False for row in _rows("divergence_explanatory_power_results.jsonl"))
    leakage = _json("production_leakage_audit.json")
    for key in ("provider_calls", "llm_calls", "api_calls", "network_calls", "downloads"):
        assert leakage[key] == 0
    assert leakage["credentials_read"] is False


def test_historical_formal_and_scientific_assets_remain_unchanged():
    safety = _json("scientific_state_safety_audit.json")
    assert safety["historical_formal_conflict_count"] == 0
    assert safety["historical_assets_modified"] is False
    assert safety["formal_v3_modified"] is False
    assert safety["protected_input_sha256_before"] == safety["protected_input_sha256_after"]


def test_no_target_specific_production_rule():
    text = PRODUCTION.read_text(encoding="utf-8").lower()
    for forbidden in ("trib3", "luad", "neuroblastoma", "pmc10515557", "pmid33380827"):
        assert forbidden not in text


def test_human_review_is_bounded_neutral_and_unanswered():
    boundary = _json("human_review_boundary.json")
    packet = _rows("human_review_packet.jsonl")
    assert boundary["task_count"] == len(packet) == 1
    assert packet[0]["answer"] is None
    for key in ("preferred_answer", "system_formal_prediction", "score_based_recommendation", "historical_answer"):
        assert packet[0][key] is None


def test_manifest_hashes_are_complete_and_valid():
    manifest = _json("manifest.json")
    indexed = {row["path"]: row for row in manifest["artifacts"]}
    expected = {path.relative_to(ROOT).as_posix() for path in ART.iterdir() if path.is_file() and path.name != "manifest.json"}
    assert set(indexed) == expected
    for relative, row in indexed.items():
        path = ROOT / relative
        assert row["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert row["bytes"] == path.stat().st_size
