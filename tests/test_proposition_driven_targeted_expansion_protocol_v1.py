import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from code_engine.context_attribution.conflict_candidate.targeted_expansion_v1_candidate import (
    BoundedTargetExpansionBudgetV1,
    EVALUATION_LEVELS_V1,
    PlannedQueryComponentsV1,
    primary_contradiction_term_count_v1,
)


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/20260826_proposition_driven_targeted_expansion_protocol_v1_offline/artifacts"
SOURCE = ROOT / "runs/20260826_cross_publication_proposition_opportunity_frontier_v1_offline/artifacts"


def read_json(name):
    return json.loads((ART / name).read_text())


def read_rows(name, root=ART):
    return [json.loads(line) for line in (root / name).read_text().splitlines() if line]


def test_exact_four_authoritative_target_semantics_are_preserved():
    source = {row["target_id"]: row for row in read_rows("proposition_driven_future_retrieval_targets.jsonl", SOURCE)}
    inventory = read_json("target_proposition_inventory.json")
    assert inventory["target_count"] == 4
    for target in inventory["targets"]:
        original = source[target["target_id"]]
        for field in ("source_proposition_block_id", "entity_proposition", "relation_family", "object_target", "measurement_targets", "measurement_properties", "result_families", "intervention_targets", "causal_mode", "evidence_family"):
            assert target[field] == original[field]
        assert target["structured_semantics_modified"] is False


def test_primary_query_components_are_direction_neutral_and_locally_bounded():
    query_rows = [PlannedQueryComponentsV1.model_validate(row) for row in read_rows("planned_query_components.jsonl")]
    assert len(query_rows) == 4
    assert primary_contradiction_term_count_v1(query_rows) == 0
    assert all(not row.fuzzy_entity_expansion and not row.external_ontology_expansion for row in query_rows)
    assert all(not row.executable_query_generated for row in query_rows)


def test_query_contract_rejects_contradiction_seeking_primary_term():
    with pytest.raises(ValidationError):
        PlannedQueryComponentsV1(
            target_id="target:1", entity_terms=["TRIB3"], relation_effect_terms=["conflicting"],
            measurement_target_terms=["tumorigenesis"], measurement_property_terms=["abundance"],
            intervention_terms=[], prohibited_primary_terms=["conflicting"],
        )


def test_budget_is_small_finite_monotone_and_globally_bounded():
    budget = read_json("bounded_expansion_budget.json")
    rows = [BoundedTargetExpansionBudgetV1.model_validate(row) for row in budget["per_target"]]
    assert len(rows) == 4
    assert budget["global_maximums"] == {
        "abstract_candidates": 24, "fulltext_extraction_calls": 8, "fulltexts": 8,
        "metadata_candidates": 48, "provider_attempts_per_source": 1,
        "provider_calls": 8, "provider_retries_per_source": 0,
    }
    assert all(row.maximum_metadata_candidates >= row.maximum_abstract_candidates >= row.maximum_fulltexts for row in rows)


def test_invalid_non_narrowing_budget_fails_closed():
    with pytest.raises(ValidationError):
        BoundedTargetExpansionBudgetV1(
            target_id="target:1", maximum_metadata_candidates=2, maximum_abstract_candidates=3,
            maximum_fulltexts=1, maximum_fulltext_extraction_calls=1, maximum_provider_calls=1,
        )


def test_duplicate_and_cache_gates_precede_paid_extraction():
    policy = read_json("extraction_activation_policy.json")
    steps = policy["required_order"]
    assert steps.index("publication_identity_check") < steps.index("duplicate_check")
    assert steps.index("duplicate_check") < steps.index("existing_cache_check")
    assert steps.index("existing_cache_check") < steps.index("asset_preservation_contract_check")
    assert policy["all_steps_must_pass_before_paid_extraction"] is True


def test_parser_schema_and_normalization_failures_never_retry_provider():
    billing = read_json("provider_billing_safety_plan.json")
    assert billing["maximum_attempts_per_source"] == 1
    assert billing["maximum_retries_per_source"] == 0
    assert billing["parser_failure_retry"] is False
    assert billing["schema_failure_retry"] is False
    assert billing["normalization_failure_retry"] is False
    assert billing["cache_required_before_every_paid_attempt"] is True


def test_level_5_is_primary_smoke_success_and_opposition_is_not_required():
    ledger = read_json("expansion_evaluation_ledger_schema.json")
    assert EVALUATION_LEVELS_V1[5] == "cross_publication_proposition_peers"
    assert ledger["planned_success_level"] == 5
    assert ledger["levels_7_or_8_required_for_smoke_success"] is False
    assert ledger["result_direction_evaluated_only_after_proposition_compatibility"] is True


def test_target_metrics_are_not_hidden_by_aggregation():
    ledger = read_json("expansion_evaluation_ledger_schema.json")
    assert len(ledger["initial_counts"]) == 4
    assert ledger["aggregation_may_not_hide_target_failure"] is True
    assert all(row["cross_publication_peer_count"] == 0 for row in ledger["initial_counts"])


def test_every_extraction_is_preserved_even_without_conflict_relevance():
    preservation = read_json("dataset_asset_preservation_recheck.json")
    assert preservation["minimum_quality_observation_enters_reusable_data_pipeline"] is True
    assert preservation["conflict_relevance_required"] is False
    assert preservation["paid_result_may_be_disposable_intermediate"] is False
    assert "raw_provider_response_before_parser" in preservation["required_assets"]
    assert "failure_artifacts" in preservation["required_assets"]


def test_execution_plan_is_unauthorized_and_nothing_executed():
    plan = read_json("network_provider_execution_plan.json")
    assert plan["execution_authorized"] is False
    assert plan["explicit_user_approval_required"] is True
    assert plan["provider_calls"] == plan["api_calls"] == plan["network_calls"] == plan["downloads"] == 0
    assert all(action["executed"] is False for action in plan["proposed_external_actions"])


def test_order_uses_local_evidence_and_keeps_unjustified_tie():
    order = read_json("target_expansion_order.json")
    assert order["targets_with_clear_priority"] == 2
    assert order["targets_equal_priority"] == 2
    assert [row["source_observation_count"] for row in order["ordered_tiers"]] == [3, 2, 1, 1]
    assert [row["priority_tier"] for row in order["ordered_tiers"]] == [1, 2, 3, 3]
    assert order["web_derived_counts_used"] is False


def test_scientific_gates_are_reused_without_relaxation():
    policy = read_json("extraction_activation_policy.json")
    assert policy["scientific_gate_relaxation_allowed"] is False
    assert "ScientificEntityIntegrityGateV1" in policy["authoritative_gates"]
    assert "MinimumScientificPropositionProfile" in policy["authoritative_gates"]
    specs = read_rows("targeted_retrieval_specifications_v1.jsonl")
    assert all(row["scientific_gates_reused_without_relaxation"] is True for row in specs)


def test_completed_or_pending_run_preserves_historical_state_and_pi3k():
    safety = read_json("scientific_state_safety_audit.json")
    assert safety["historical_assets_modified"] is False
    assert safety["candidate_pairs_modified"] is False
    assert safety["formal_v3_modified"] is False
    assert safety["historical_candidate_count_after"] == 11
    assert safety["formal_conflict_count_after"] == 0
    assert safety["entity_integrity_claims_blocked"] == 241
    assert safety["entity_integrity_signals_blocked"] == 2
    assert safety["pi3k"] == {"f389_state": "manual_scientific_review", "signal_40f_state": "historically_blocked"}
    assert safety["provider_calls"] == safety["api_calls"] == safety["network_calls"] == safety["downloads"] == 0


def test_manifest_contains_all_required_artifacts():
    manifest = read_json("manifest.json")
    assert manifest["artifact_count"] == 19
    assert manifest["all_required_artifacts_present"] is True
    assert len(manifest["artifacts"]) == 18
    assert manifest["execution_authorized"] is False
