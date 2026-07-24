import json
from pathlib import Path

import pytest

from code_engine.context_attribution.fake_provider import FakeRecoveryProvider
from code_engine.context_attribution.identities import (
    PROVIDER_EXECUTION_IDENTITY_VERSION, build_provider_execution_identity,
    canonical_sha256, resolve_provider_execution_identity,
)
from code_engine.context_attribution.models import PAIR_SCHEMA_VERSION
from code_engine.context_attribution.recovery import (
    EXTRACTION_SCHEMA_VERSION_V6, PROMPT_VERSION_V6, build_recovery_plan,
)
from code_engine.context_attribution.recovery_execution import (
    execute_targeted_recovery, validate_targeted_recovery_execution_plan,
)


ROOT = Path(__file__).parents[1]
INPUT = ROOT / "runs/20260723_171527_hif1a_hypoxia_cancer_response_discovery_v1_fulltext_v3_recovered_reentry"
SOURCE = ROOT / "runs/20260724_hif1a_context_attribution_v5_identity_complete_smoke_execution"


def identity(**changes):
    values = {
        "provider": "deepseek", "model": "deepseek-v4-pro",
        "thinking_mode": "disabled", "configured_max_tokens": 32768,
        "prompt_version": PROMPT_VERSION_V6,
        "extraction_schema_version": EXTRACTION_SCHEMA_VERSION_V6,
        "comparison_schema_version": PAIR_SCHEMA_VERSION,
        "configuration_source": {
            "provider": "cli", "model": "cli", "thinking_mode": "cli",
            "configured_max_tokens": "built_in_default",
        },
    }
    values.update(changes)
    return build_provider_execution_identity(**values)


def fake_identity():
    return resolve_provider_execution_identity(
        provider="fake", model="fake-recovery-v1", thinking_mode="disabled",
        configured_max_tokens=32768, prompt_version=PROMPT_VERSION_V6,
        extraction_schema_version=EXTRACTION_SCHEMA_VERSION_V6,
        comparison_schema_version=PAIR_SCHEMA_VERSION, fake_test=True,
    )


def fake_plan(target):
    return build_recovery_plan(
        input_run=INPUT, source_run=SOURCE, target_run=target,
        mode="targeted_provider", provider_execution_identity=fake_identity(),
    )


def test_canonical_identity_is_stable_and_provenance_does_not_hash():
    first = identity()
    second = identity(configuration_source={
        "provider": "production_config", "model": "environment_name_only",
        "thinking_mode": "built_in_default",
        "configured_max_tokens": "production_config",
    })
    assert first.identity_sha256 == second.identity_sha256
    assert first.identity_sha256 == canonical_sha256(first.canonical_payload())
    assert len(first.identity_sha256) == 64
    assert json.loads(json.dumps(first.canonical_payload(), indent=4)) == \
        first.canonical_payload()


@pytest.mark.parametrize("field,value", [
    ("provider", "openai"), ("model", "other-model"),
    ("thinking_mode", "enabled"), ("configured_max_tokens", 16384),
    ("prompt_version", "changed-prompt"),
    ("extraction_schema_version", "changed-extraction"),
    ("comparison_schema_version", "changed-comparison"),
])
def test_every_effective_field_changes_hash(field, value):
    assert identity(**{field: value}).identity_sha256 != identity().identity_sha256


def test_exact_plan_persists_effective_configuration_and_sources(monkeypatch, tmp_path):
    for name in (
        "L1_PROVIDER", "MODEL_NAME", "FULLTEXT_L1_V2_THINKING_MODE",
        "FULLTEXT_L1_V2_MAX_TOKENS",
    ):
        monkeypatch.delenv(name, raising=False)
    plan = build_recovery_plan(
        input_run=INPUT, source_run=SOURCE, target_run=tmp_path / "run",
        mode="targeted_provider", provider="deepseek",
        model="deepseek-v4-pro", thinking_mode="disabled",
    )
    assert plan["schema_version"] == "context_attribution_recovery_plan_v2"
    assert (plan["provider"], plan["model"], plan["thinking_mode"]) == (
        "deepseek", "deepseek-v4-pro", "disabled",
    )
    assert plan["configured_max_tokens"] == 32768
    assert plan["provider_configuration_source"] == {
        "provider": "cli", "model": "cli", "thinking_mode": "cli",
        "configured_max_tokens": "built_in_default",
    }
    assert plan["provider_execution_identity_version"] == \
        PROVIDER_EXECUTION_IDENTITY_VERSION
    assert plan["provider_execution_identity_verified"] is True
    assert plan["provider_calls"] == plan["api_calls"] == plan["network_calls"] == 0
    assert plan["provider_client_created"] is False


@pytest.mark.parametrize("field,value,error", [
    ("provider", "openai", "plan_provider_identity_mismatch"),
    ("model", "changed", "plan_model_identity_mismatch"),
    ("thinking_mode", "enabled", "plan_thinking_mode_identity_mismatch"),
    ("configured_max_tokens", 1, "plan_max_tokens_identity_mismatch"),
    ("provider_execution_identity_sha256", "0" * 64,
     "plan_provider_identity_hash_mismatch"),
])
def test_plan_top_level_drift_fails_before_factory(tmp_path, field, value, error):
    target = tmp_path / "run"
    plan = build_recovery_plan(
        input_run=INPUT, source_run=SOURCE, target_run=target,
        mode="targeted_provider", provider_execution_identity=identity(),
    )
    plan[field] = value
    created = []
    with pytest.raises(RuntimeError, match=error):
        execute_targeted_recovery(
            plan=plan, input_run=INPUT, source_run=SOURCE, target_run=target,
            profiles=["generic", "biomedical"],
            client_factory=lambda: created.append(True),
            actual_provider_execution_identity=identity(),
        )
    assert created == []
    assert not target.exists()


@pytest.mark.parametrize("path,value,error", [
    (("provider_execution_identity", "identity_sha256"), "0" * 64,
     "provider_execution_identity_hash_mismatch"),
    (("scientific_contract_versions", "prompt"), "changed",
     "plan_prompt_identity_mismatch"),
    (("scientific_contract_versions", "extraction_schema"), "changed",
     "plan_extraction_schema_identity_mismatch"),
    (("comparison_schema_version",), "changed",
     "plan_comparison_schema_identity_mismatch"),
])
def test_internal_hash_and_scientific_version_drift_fail_closed(
    tmp_path, path, value, error,
):
    target = tmp_path / "run"
    plan = build_recovery_plan(
        input_run=INPUT, source_run=SOURCE, target_run=target,
        mode="targeted_provider", provider_execution_identity=identity(),
    )
    parent = plan
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = value
    created = []
    with pytest.raises(RuntimeError, match=error):
        execute_targeted_recovery(
            plan=plan, input_run=INPUT, source_run=SOURCE, target_run=target,
            profiles=["generic", "biomedical"],
            client_factory=lambda: created.append(True),
            actual_provider_execution_identity=identity(),
        )
    assert created == []


def test_legacy_v1_plan_is_readable_but_not_executable(tmp_path):
    target = tmp_path / "run"
    plan = build_recovery_plan(
        input_run=INPUT, source_run=SOURCE, target_run=target,
        mode="targeted_provider", provider_execution_identity=identity(),
    )
    plan["schema_version"] = plan["recovery_plan_version"] = \
        "context_attribution_recovery_plan_v1"
    plan.pop("provider_execution_identity")
    errors = validate_targeted_recovery_execution_plan(
        plan, input_run=INPUT, source_run=SOURCE, target_run=target,
        actual_provider_execution_identity=identity(),
    )
    assert "recovery_plan_schema_mismatch" in errors
    assert "provider_execution_identity_missing" in errors


def test_request_audit_checkpoint_summary_and_cache_propagation(tmp_path):
    target = tmp_path / "run"
    fake = FakeRecoveryProvider()
    execution_id = fake_identity()
    summary = execute_targeted_recovery(
        plan=fake_plan(target), input_run=INPUT, source_run=SOURCE,
        target_run=target, profiles=["generic", "biomedical"],
        client_factory=lambda: fake, provider_mode="fake_test", test_only=True,
        actual_provider_execution_identity=execution_id,
    )
    artifacts = target / "artifacts"
    providers = [
        json.loads(line) for line in
        (artifacts / "context_attribution_provider_calls.jsonl").read_text().splitlines()
    ]
    ledger = [
        json.loads(line) for line in
        (artifacts / "context_attribution_execution_ledger.jsonl").read_text().splitlines()
    ]
    cache = json.loads(
        (artifacts / "context_attribution_cache.json").read_text()
    )
    expected = execution_id.identity_sha256
    assert summary["provider_execution_identity_sha256"] == expected
    assert all(row["provider_execution_identity_sha256"] == expected
               for row in providers)
    assert all(
        (row.get("identity_bundle") or row.get("request_identity_bundle"))
        ["provider_execution_identity_sha256"] == expected
        for row in providers
    )
    assert all(row["effective_model"] == "fake-recovery-v1" for row in providers)
    assert all(row["planned_provider_execution_identity_sha256"] == expected
               and row["actual_provider_execution_identity_sha256"] == expected
               and row["identity_match"] is True
               for row in ledger if row.get("provider_call"))
    fresh = [entry for entry in cache["entries"].values()
             if entry.get("provenance") == "fresh_provider_v6"]
    assert len(fresh) == 2
    assert all(entry["provider_execution_identity_sha256"] == expected
               for entry in fresh)
    offline = [entry for entry in cache["entries"].values()
               if entry.get("provenance") == "offline_adapted_from_v5"]
    assert offline[0]["current_offline_validation_provider_calls"] == 0
    assert fake.calls[0]["request_identity"] != identity().identity_sha256


def test_retry_attempt_records_execution_identity(tmp_path):
    target = tmp_path / "run"
    execution_id = fake_identity()
    fake = FakeRecoveryProvider(extraction_scenarios={
        "ftl1v3_17b7314297cabac677007b35": "schema_invalid",
    })
    execute_targeted_recovery(
        plan=fake_plan(target), input_run=INPUT, source_run=SOURCE,
        target_run=target, profiles=["generic", "biomedical"],
        client_factory=lambda: fake, provider_mode="fake_test", test_only=True,
        actual_provider_execution_identity=execution_id,
    )
    retry = [
        json.loads(line) for line in
        (target / "artifacts/context_attribution_retry_queue.jsonl")
        .read_text().splitlines()
    ]
    assert retry[0]["provider_execution_identity_sha256"] == \
        execution_id.identity_sha256


@pytest.mark.parametrize("change", [
    {"provider": "openai"}, {"model": "changed"},
    {"thinking_mode": "enabled"}, {"configured_max_tokens": 16384},
    {"prompt_version": "changed"}, {"extraction_schema_version": "changed"},
    {"comparison_schema_version": "changed"},
])
def test_resume_effective_configuration_drift_fails_before_factory(
    tmp_path, change,
):
    target = tmp_path / "run"
    original = fake_identity()
    with pytest.raises(InterruptedError):
        execute_targeted_recovery(
            plan=fake_plan(target), input_run=INPUT, source_run=SOURCE,
            target_run=target, profiles=["generic", "biomedical"],
            client_factory=lambda: FakeRecoveryProvider(),
            provider_mode="fake_test", test_only=True,
            actual_provider_execution_identity=original,
            interrupt_after_persist=(
                "extraction", "ftl1v3_17b7314297cabac677007b35",
            ),
        )
    changed_values = {
        **original.canonical_payload(),
        "configuration_source": original.configuration_source, **change,
    }
    changed_values.pop("provider_execution_identity_version")
    changed = build_provider_execution_identity(**changed_values)
    created = []
    plan = json.loads(
        (target / "artifacts/context_attribution_recovery_plan.json").read_text()
    )
    before = (
        target / "artifacts/context_attribution_provider_calls.jsonl"
    ).read_bytes()
    with pytest.raises(RuntimeError, match="actual_provider_execution_identity_mismatch"):
        execute_targeted_recovery(
            plan=plan, input_run=INPUT, source_run=SOURCE, target_run=target,
            profiles=["generic", "biomedical"],
            client_factory=lambda: created.append(True), resume=True,
            provider_mode="fake_test", test_only=True,
            actual_provider_execution_identity=changed,
        )
    assert created == []
    assert (target / "artifacts/context_attribution_provider_calls.jsonl").read_bytes() == before


def test_fake_identity_cannot_be_used_for_production_execution(tmp_path):
    target = tmp_path / "run"
    created = []
    with pytest.raises(RuntimeError, match="fake_provider_identity_for_production"):
        execute_targeted_recovery(
            plan=fake_plan(target), input_run=INPUT, source_run=SOURCE,
            target_run=target, profiles=["generic", "biomedical"],
            client_factory=lambda: created.append(True),
            actual_provider_execution_identity=fake_identity(),
            test_only=False,
        )
    assert created == []
