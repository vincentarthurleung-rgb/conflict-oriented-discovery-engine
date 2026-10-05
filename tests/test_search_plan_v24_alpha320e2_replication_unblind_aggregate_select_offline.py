"""Frozen E2 derivation and comparison rules, without model or network calls."""

import pytest

from scripts import run_search_plan_v24_alpha320e2_replication_unblind_aggregate_select_offline as e2


def test_preflight_only_reads_blinded_replication_material(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(e2, "OUT", tmp_path / "not-created")
    state = e2.preflight()
    assert len(state["judgments"]) == 84
    assert len(state["attempts"]) == 28
    assert state["validation"]["unblinding_performed"] is False
    assert not e2.OUT.exists()


@pytest.mark.parametrize("values,expected", [
    (["PASS"] * 6, "SEMANTIC_FIDELITY_PASS"),
    (["PASS"] * 5 + ["UNRESOLVED"], "SEMANTIC_FIDELITY_UNRESOLVED"),
    (["UNRESOLVED", "PASS", "PASS", "FAIL", "PASS", "PASS"],
     "SEMANTIC_FIDELITY_FAIL"),
])
def test_controller_overall_state_priority(values, expected) -> None:
    criteria = dict(zip(e2.r.e.CRITERIA, values))
    assert e2.state_from_six(criteria) == expected


@pytest.mark.parametrize("v1,v2,expected", [
    ((2, 1), (3, 1), "V1_SEMANTICALLY_DOMINATES"),
    ((3, 1), (2, 1), "V2_SEMANTICALLY_DOMINATES"),
    ((2, 1), (2, 1), "SEMANTIC_TIE"),
    ((2, 3), (3, 2), "SEMANTIC_INCOMPARABLE"),
])
def test_frozen_dominance_branches(v1, v2, expected) -> None:
    assert e2.comparison(v1, v2) == expected


def test_blinded_derivation_is_repeatable_without_mapping(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(e2, "OUT", tmp_path / "not-created")
    state = e2.preflight()
    one = e2.derive_blinded(state["judgments"])
    two = e2.derive_blinded(state["judgments"])
    assert e2.r.canonical(one) == e2.r.canonical(two)
    assert len(one) == len({row["blinded_candidate_token"] for row in one}) == 84
    assert all("private_variant_id" not in row for row in one)
