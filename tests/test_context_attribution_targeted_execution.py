import json
from copy import deepcopy
from pathlib import Path

import pytest

from code_engine.context_attribution.fake_provider import FakeRecoveryProvider
from code_engine.context_attribution.recovery import build_recovery_plan
from code_engine.context_attribution.recovery_execution import (
    EXPECTED_ALLOWLIST, execute_targeted_recovery,
    validate_targeted_recovery_execution_plan,
)


ROOT = Path(__file__).parents[1]
INPUT = ROOT / "runs/20260723_171527_hif1a_hypoxia_cancer_response_discovery_v1_fulltext_v3_recovered_reentry"
SOURCE = ROOT / "runs/20260724_hif1a_context_attribution_v5_identity_complete_smoke_execution"
OID17 = "ftl1v3_17b7314297cabac677007b35"
OID41 = "ftl1v3_41f0090d726e6e8591a58574"


def plan_for(target):
    return build_recovery_plan(
        input_run=INPUT, source_run=SOURCE, target_run=target,
        mode="targeted_provider",
    )


def execute(target, scenarios=None, *, interrupt=None, resume=False, fake=None):
    fake = fake or FakeRecoveryProvider(extraction_scenarios=scenarios)
    summary = execute_targeted_recovery(
        plan=(json.loads((target / "artifacts/context_attribution_recovery_plan.json")
                         .read_text()) if resume else plan_for(target)),
        input_run=INPUT, source_run=SOURCE, target_run=target,
        profiles=["generic", "biomedical"], client_factory=lambda: fake,
        resume=resume, provider_mode="fake_test", test_only=True,
        interrupt_after_persist=interrupt,
    )
    return summary, fake


def test_plan_support_flags_exact_allowlist_and_bounds(tmp_path):
    target = tmp_path / "run"
    plan = plan_for(target)
    assert plan["recovery_execution_supported"] is True
    assert plan["provider_allowlist_enforced"] is True
    assert plan["dynamic_pair_execution"] is True
    assert plan["resume_checkpoint_enabled"] is True
    assert set(plan["provider_recall_required_observation_ids"]) == EXPECTED_ALLOWLIST
    assert "ftl1v3_71023211dcfb3d430a918e17" not in EXPECTED_ALLOWLIST
    assert "ftl1v3_f530298f2b2955bfe9988710" not in EXPECTED_ALLOWLIST
    assert plan["extraction_provider_calls_hard_bound"] == 2
    assert plan["comparison_provider_calls_hard_bound"] == 3
    assert plan["provider_calls_hard_bound"] == 5
    assert plan["provider_calls"] == plan["network_calls"] == 0
    assert plan["credential_values_read"] is False
    assert plan["provider_client_created"] is False


@pytest.mark.parametrize("mutation,error", [
    (lambda p: p["provider_recall_required_observation_ids"].append(
        "ftl1v3_f530298f2b2955bfe9988710"), "provider_allowlist_not_exact"),
    (lambda p: p.__setitem__("activation", True), "activation_not_false"),
    (lambda p: p["source_artifact_sha256"].__setitem__(
        "context_attribution_plan.json", "0" * 64), "source_artifact_hash_drift"),
])
def test_fail_closed_before_client_factory(tmp_path, mutation, error):
    target = tmp_path / "run"
    plan = plan_for(target)
    mutation(plan)
    created = []
    with pytest.raises(RuntimeError, match=error):
        execute_targeted_recovery(
            plan=plan, input_run=INPUT, source_run=SOURCE, target_run=target,
            profiles=["generic", "biomedical"],
            client_factory=lambda: created.append(True),
        )
    assert created == []
    assert not target.exists()


def test_target_equals_source_is_rejected_before_client():
    plan = plan_for(SOURCE)
    errors = validate_targeted_recovery_execution_plan(
        plan, input_run=INPUT, source_run=SOURCE, target_run=SOURCE,
    )
    assert "target_run_equals_source_run" in errors


def test_both_success_exact_calls_reuse_offline_dynamic_pairs_and_isolation(tmp_path):
    before = {name: digest for name, digest in plan_for(tmp_path / "unused")
              ["source_artifact_sha256"].items()}
    summary, fake = execute(tmp_path / "run")
    calls = [(row["call_type"], row["record_id"]) for row in fake.calls]
    assert calls == [
        ("extraction", OID17), ("extraction", OID41),
        ("comparison", "weak-ebd5deb14f4f39dfffe6"),
        ("comparison", "weak-88595372e74db34331a2"),
        ("comparison", "weak-cbfed6a3bdc9f49e9d60"),
    ]
    assert [row["attempt_number"] for row in fake.calls[:2]] == [2, 2]
    assert summary["source_reused_count"] == 4
    assert summary["offline_validated_count"] == 1
    assert summary["fresh_provider_validated_count"] == 2
    assert summary["provider_calls"] == 5
    assert summary["comparison_executed_count"] == 3
    assert summary["comparison_blocked_count"] == 2
    assert summary["network_calls"] == summary["real_api_calls"] == 0
    assert summary["credential_values_read"] is False
    assert summary["scientific_result_test_only"] is True
    assert summary["not_reusable_as_production_scientific_artifact"] is True
    assert {name: digest for name, digest in plan_for(tmp_path / "unused2")
            ["source_artifact_sha256"].items()} == before


@pytest.mark.parametrize("scenarios,expected_pairs", [
    ({OID41: "deterministic_invalid"},
     {"weak-ebd5deb14f4f39dfffe6", "weak-cbfed6a3bdc9f49e9d60"}),
    ({OID17: "schema_invalid"},
     {"weak-ebd5deb14f4f39dfffe6", "weak-88595372e74db34331a2"}),
    ({OID17: "provider_failure", OID41: "provider_failure"},
     {"weak-ebd5deb14f4f39dfffe6"}),
])
def test_dynamic_comparison_counts_follow_actual_validation(tmp_path, scenarios, expected_pairs):
    summary, fake = execute(tmp_path / "run", scenarios)
    extraction = [x for x in fake.calls if x["call_type"] == "extraction"]
    comparisons = {x["record_id"] for x in fake.calls if x["call_type"] == "comparison"}
    assert {x["record_id"] for x in extraction} == EXPECTED_ALLOWLIST
    assert comparisons == expected_pairs
    assert summary["provider_calls"] == 2 + len(expected_pairs)
    assert "ftl1v3_f530298f2b2955bfe9988710" not in {
        x["record_id"] for x in fake.calls
    }


def test_invalid_fresh_payload_never_enters_cache_and_retry_layer_is_exact(tmp_path):
    target = tmp_path / "run"
    execute(target, {OID17: "schema_invalid", OID41: "deterministic_invalid"})
    cache = json.loads((target / "artifacts/context_attribution_cache.json").read_text())
    cached_oids = {(entry.get("payload") or {}).get("observation_id")
                   for entry in cache["entries"].values()}
    assert OID17 not in cached_oids
    assert OID41 not in cached_oids
    queue = {row["observation_id"]: row for row in [
        json.loads(line) for line in
        (target / "artifacts/context_attribution_retry_queue.jsonl").read_text().splitlines()
    ]}
    assert queue[OID17]["failure_layer"] == "schema"
    assert queue[OID41]["failure_layer"] == "deterministic_validation"


@pytest.mark.parametrize("scenario", ["provider_failure", "schema_invalid"])
def test_comparison_failures_are_persisted_without_unlocking_artifact(tmp_path, scenario):
    target = tmp_path / "run"
    pair = "weak-ebd5deb14f4f39dfffe6"
    fake = FakeRecoveryProvider(comparison_scenarios={pair: scenario})
    summary, _ = execute(target, fake=fake)
    cache = json.loads((target / "artifacts/context_attribution_cache.json").read_text())
    assert pair not in {(entry.get("payload") or {}).get("pair_id")
                        for entry in cache["entries"].values()}
    assert summary["comparison_executed_count"] == 3


def test_resume_after_first_extraction_persist_does_not_repeat_paid_call(tmp_path):
    target = tmp_path / "run"
    first = FakeRecoveryProvider()
    with pytest.raises(InterruptedError):
        execute(target, fake=first, interrupt=("extraction", OID17))
    assert [(x["call_type"], x["record_id"]) for x in first.calls] == [
        ("extraction", OID17)
    ]
    second = FakeRecoveryProvider()
    summary, second = execute(target, resume=True, fake=second)
    assert [x["record_id"] for x in second.calls if x["call_type"] == "extraction"] == [OID41]
    assert summary["extraction_provider_calls"] == 1


def test_resume_after_comparison_persist_replays_exact_artifact(tmp_path):
    target = tmp_path / "run"
    first = FakeRecoveryProvider()
    with pytest.raises(InterruptedError):
        execute(target, fake=first,
                interrupt=("comparison", "weak-ebd5deb14f4f39dfffe6"))
    second = FakeRecoveryProvider()
    summary, second = execute(target, resume=True, fake=second)
    assert "weak-ebd5deb14f4f39dfffe6" not in {
        x["record_id"] for x in second.calls
    }
    assert summary["extraction_provider_calls"] == 0
    assert summary["comparison_provider_calls"] == 2


def test_resume_identity_mismatch_fails_closed_without_new_call(tmp_path):
    target = tmp_path / "run"
    first = FakeRecoveryProvider()
    with pytest.raises(InterruptedError):
        execute(target, fake=first, interrupt=("extraction", OID17))
    path = target / "artifacts/context_attribution_provider_calls.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[0]["request_identity"] = "0" * 64
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    second = FakeRecoveryProvider()
    with pytest.raises(RuntimeError, match="resume_provider_identity_mismatch"):
        execute(target, resume=True, fake=second)
    assert second.calls == []


def test_tampered_bounds_fail_before_call(tmp_path):
    target = tmp_path / "run"
    plan = plan_for(target)
    plan["provider_calls_hard_bound"] = 6
    fake = FakeRecoveryProvider()
    with pytest.raises(RuntimeError, match="provider_bound_exceeds_five"):
        execute_targeted_recovery(
            plan=plan, input_run=INPUT, source_run=SOURCE, target_run=target,
            profiles=["generic", "biomedical"], client_factory=lambda: fake,
        )
    assert fake.calls == []
