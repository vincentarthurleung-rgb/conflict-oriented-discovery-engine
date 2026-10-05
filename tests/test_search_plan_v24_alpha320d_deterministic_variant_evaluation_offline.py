"""Offline authority and deterministic evaluator checks for alpha3.20D."""

from scripts import run_search_plan_v24_alpha320d_deterministic_variant_evaluation_offline as d


def test_frozen_126_candidate_preflight(monkeypatch, tmp_path):
    monkeypatch.setattr(d, "OUT", tmp_path / "not_created")
    state = d.preflight()
    assert len(state["candidate_rows"]) == 126
    assert len(state["complete_rows"]) == 14
    assert not d.OUT.exists()


def test_independent_leakage_reference_agrees_on_triggers():
    cases = [
        ("alpha beta gamma delta epsilon zeta eta theta", "alpha beta gamma delta epsilon zeta eta theta", ""),
        ("one two three four five six seven eight", "unrelated title", "one two three four five six seven eight"),
        ("actor increases response in context", "unrelated title", "unrelated evidence sentence"),
    ]
    for proposition, title, sentence in cases:
        assert d.production_leakage_metrics(proposition, title, sentence) == (
            d.independent_reference_leakage(proposition, title, sentence))


def test_structure_is_representation_only():
    schema = d.obj(d.B / "builder_output_schema_v4.json")["schema"]
    candidate = {
        "actor_or_intervention": "A", "action": "affects",
        "relation_direction": "INCREASES", "response_or_endpoint": "B",
        "biological_unit": "cells", "species": None,
        "intrinsic_conditioning": None, "intrinsic_therapy_context": None,
        "intrinsic_disease_or_genotype_context": None,
    }
    result = d.structural_result(candidate, schema)
    assert result["structural_state"] == "STRUCTURALLY_COMPLETE"
    assert result["semantic_scientific_fidelity_established"] is False
