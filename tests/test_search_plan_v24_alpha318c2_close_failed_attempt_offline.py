"""Read-only checks of the incomplete Quality attempt closure."""
from __future__ import annotations

import pytest

from scripts import search_plan_v24_alpha318c2_close_failed_attempt_offline as closure


def test_frozen_history_and_closure_root() -> None:
    with pytest.raises(RuntimeError, match="ALPHA3_18C2_ALREADY_EXISTS"):
        closure.preflight()
    assert closure.prior.root(closure.OUT, closure.ROOT_MARKER) == (
        closure.OUT / closure.ROOT_MARKER).read_text().strip()
    assert closure.prior.root(closure.FAILED, closure.failed_run.ROOT_MARKER) == closure.FAILED_SHA
    assert closure.prior.root(closure.C1, closure.audit.ROOT_MARKER) == closure.C1_SHA


def test_undefined_outcomes_are_not_serialized_as_zero() -> None:
    outcome = closure.load(closure.OUT / "quality_candidate_outcome_claim_boundary.json")
    pool = closure.load(closure.OUT / "eligible_pool_state.json")
    assert outcome["quality_pass_candidate_count"] is None
    assert outcome["quality_fail_candidate_count"] is None
    assert outcome["quality_unresolved_candidate_count"] is None
    assert outcome["zero_pass_claim_allowed"] is False
    assert pool["eligible_proposition_pool_state"] == "NOT_DERIVED"
    assert pool["final_pool_size"] is None


def test_unattempted_groups_and_no_post_quality_outputs() -> None:
    groups = closure.load(closure.OUT / "quality_group_terminal_state_summary.json")["groups"]
    assert len(groups) == 3
    assert groups[0]["terminal_state"] == "QUALITY_RESPONSE_INVALID"
    assert all(row["terminal_state"] == "UNATTEMPTED_DUE_TO_PREREGISTERED_STAGE_STOP"
               for row in groups[1:])
    assert closure.load(closure.OUT / "scientific_state_safety_audit.json")["provider_calls"] == 0
    assert closure.load(closure.OUT / "fresh_heldout_state.json")["fresh_heldout_v3_selected"] is False
