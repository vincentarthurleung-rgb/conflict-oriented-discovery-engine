import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

import code_engine.context_attribution.engine as context_engine
import code_engine.context_attribution.registry as registry_module
from code_engine.context_attribution.engine import (
    build_abstract_input, extraction_cache_identity, pair_cache_identity,
)
from code_engine.context_attribution.readiness import (
    calculate_scientific_status, scientific_readiness,
)
from code_engine.context_attribution.registry import (
    LEGACY_REGISTRY_VERSION, PROJECT_ROOT, load_registry, resolve_registry,
)


HISTORICAL_V1_SHA256 = "db0acb543603d0d1ffe06d29e101cd61eed2582e69a845b7df1d3eb21c40f7b9"


def _contract():
    return build_abstract_input(
        {
            "observation_id": "o1",
            "evidence_sentence": "Human cells changed the endpoint.",
            "polarity": "positive",
        },
        ["generic", "biomedical"],
    )


def test_registry_v1_is_immutable_and_v2_is_independent():
    v1 = PROJECT_ROOT / "configs/context_attribution/context_registry_v1.json"
    v2 = PROJECT_ROOT / "configs/context_attribution/context_registry_v2.json"
    assert hashlib.sha256(v1.read_bytes()).hexdigest() == HISTORICAL_V1_SHA256
    assert hashlib.sha256(v2.read_bytes()).hexdigest() != HISTORICAL_V1_SHA256
    assert load_registry(v1)["registry_version"] == "context_factor_registry_v1"
    assert load_registry(v2)["schema_version"] == "context_factor_registry_v2"


def test_registry_resolution_is_explicit_compatible_and_fail_closed(monkeypatch):
    current = resolve_registry(
        prompt_version="context_attribution_prompts_v5",
        extraction_schema_version="observation_context_extraction_v5",
    )
    assert current.registry_version == "context_factor_registry_v3"
    assert current.registry_path.endswith("context_registry_v3.json")
    assert len(current.registry_content_sha256) == 64
    legacy = resolve_registry(
        prompt_version="context_attribution_prompts_v2",
        extraction_schema_version="observation_context_extraction_v2",
    )
    assert legacy.registry_version == LEGACY_REGISTRY_VERSION
    assert legacy.registry_resolution_source == "prompt_compatibility"
    artifact = resolve_registry(artifact_identity={
        "registry_version": LEGACY_REGISTRY_VERSION,
        "registry_path": "configs/context_attribution/context_registry_v1.json",
        "registry_content_sha256": HISTORICAL_V1_SHA256,
    })
    assert artifact.registry_resolution_source == "artifact_registry_identity"

    with pytest.raises(ValueError, match="version_path_mismatch"):
        resolve_registry(
            requested_registry_version=LEGACY_REGISTRY_VERSION,
            explicit_path="configs/context_attribution/context_registry_v2.json",
        )
    with pytest.raises(ValueError, match="hash_mismatch"):
        resolve_registry(
            requested_registry_version=LEGACY_REGISTRY_VERSION,
            expected_content_sha256="0" * 64,
        )
    with pytest.raises(ValueError, match="unknown_context_registry_version"):
        resolve_registry(requested_registry_version="context_factor_registry_v99")

    monkeypatch.setitem(
        registry_module.REGISTRY_PATHS,
        LEGACY_REGISTRY_VERSION,
        Path("configs/context_attribution/missing_registry_v1.json"),
    )
    with pytest.raises(FileNotFoundError, match="context_registry_not_found"):
        resolve_registry(requested_registry_version=LEGACY_REGISTRY_VERSION)


def test_cache_identity_isolated_by_registry_validator_hydrator_and_local_policy(monkeypatch):
    resolution = resolve_registry()
    registry = load_registry(resolution=resolution)
    common = dict(
        profiles=["generic", "biomedical"], provider="offline", model="fixture",
        thinking_mode="disabled", registry=registry,
    )
    baseline = extraction_cache_identity(
        _contract(), registry_resolution=resolution, **common
    )
    changed_hash = extraction_cache_identity(
        _contract(),
        registry_resolution=replace(resolution, registry_content_sha256="f" * 64),
        **common,
    )
    assert changed_hash != baseline

    monkeypatch.setattr(context_engine, "VALIDATOR_VERSION", "validator_changed")
    validator_changed = extraction_cache_identity(
        _contract(), registry_resolution=resolution, **common
    )
    assert validator_changed != baseline
    monkeypatch.setattr(context_engine, "VALIDATOR_VERSION", "context_attribution_validator_v4")
    monkeypatch.setattr(context_engine, "HYDRATOR_VERSION", "hydrator_changed")
    hydrator_changed = extraction_cache_identity(
        _contract(), registry_resolution=resolution, **common
    )
    assert hydrator_changed != baseline
    monkeypatch.setattr(context_engine, "HYDRATOR_VERSION", "context_attribution_anchor_hydrator_v3")
    monkeypatch.setattr(context_engine, "LOCAL_CHAIN_INFERENCE_POLICY_VERSION", "local_chain_changed")
    local_changed = extraction_cache_identity(
        _contract(), registry_resolution=resolution, **common
    )
    assert local_changed != baseline
    monkeypatch.setattr(
        context_engine,
        "composition_identity",
        lambda: {
            "composer_version": "composer_changed",
            "composition_policy_version": "policy_changed",
            "composition_policy_path": "changed.json",
            "composition_policy_content_sha256": "e" * 64,
        },
    )
    composition_changed = extraction_cache_identity(
        _contract(), registry_resolution=resolution, **common
    )
    assert composition_changed != baseline

    pair_a = pair_cache_identity(
        "validated-a", "validated-b", ["generic"], pair_id="p1",
        registry_resolution=resolution,
    )
    pair_b = pair_cache_identity(
        "validated-a-changed", "validated-b", ["generic"], pair_id="p1",
        registry_resolution=resolution,
    )
    assert pair_a != pair_b


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"transport_complete": False}, "incomplete"),
        ({"validated_extraction_count": 0, "rejected_extraction_count": 2,
          "validated_pair_count": 0, "blocked_pair_count": 1}, "all_extractions_rejected"),
        ({"validated_extraction_count": 1, "rejected_extraction_count": 1,
          "validated_pair_count": 0, "blocked_pair_count": 1}, "partial_validation_failure"),
        ({"validated_pair_count": 0}, "no_pairs_attributed"),
        ({}, "validated_partial"),
        ({"purpose": "complete", "planned_coverage_complete": True}, "validated_complete"),
    ],
)
def test_scientific_status_priority(overrides, expected):
    values = {
        "purpose": "smoke",
        "selected_extraction_count": 2,
        "validated_extraction_count": 2,
        "rejected_extraction_count": 0,
        "selected_pair_count": 1,
        "validated_pair_count": 1,
        "blocked_pair_count": 0,
        "pending_pair_count": 0,
        "transport_complete": True,
        "planned_coverage_complete": False,
    }
    values.update(overrides)
    assert calculate_scientific_status(**values) == expected


def test_legacy_transport_completed_does_not_bypass_scientific_readiness():
    readiness = scientific_readiness({
        "status": "completed",
        "execution_status": "completed",
        "scientific_status": "all_extractions_rejected",
        "validated_pair_count": 0,
        "coverage_complete": False,
    })
    assert readiness["scientifically_ready"] is False
    assert readiness["handoff_allowed"] is False
    assert readiness["atlas_activation_allowed"] is False
