import copy
from dataclasses import replace

import pytest

import code_engine.context_attribution.engine as engine
from code_engine.context_attribution.composition import (
    composition_identity, load_composition_policy,
)
from code_engine.context_attribution.engine import extraction_cache_identity
from code_engine.context_attribution.identities import (
    COMPARATOR_NORMALIZATION_POLICY_SCHEMA_VERSION,
    IDENTITY_BUNDLE_VERSION,
    NORMALIZATION_POLICY_SCHEMA_VERSION,
    PolicyIdentity,
    canonical_sha256,
    comparator_normalization_policy_payload,
    normalization_policy_payload,
    resolve_policy_identities,
    validate_policy_identity,
)
from code_engine.context_attribution.registry import load_registry, resolve_registry
from code_engine.context_attribution.runner import _plan_identity_errors
from code_engine.context_attribution.token_spans import (
    ANCHOR_TOKENIZER_VERSION, TOKEN_CATALOG_IDENTITY_VERSION,
    anchor_token_catalog_identity, attach_token_catalog,
    observation_token_catalog_identity, selected_token_catalog_identity,
    validate_selected_token_catalog_identity,
)


def _resolved():
    resolution = resolve_registry()
    registry = load_registry(resolution=resolution)
    composition, _ = load_composition_policy()
    composition_id = composition_identity()
    policies = resolve_policy_identities(
        registry=registry,
        registry_path=resolution.registry_path,
        registry_sha256=resolution.registry_content_sha256,
        composition_policy=composition,
        composition_path=composition_id["composition_policy_path"],
        composition_sha256=composition_id["composition_policy_content_sha256"],
    )
    return resolution, registry, composition, policies


def _contract(observation_id="o1", text="Human β-catenin-like cells."):
    return attach_token_catalog({
        "observation_id": observation_id,
        "input_mode": "abstract_sentence_only",
        "evidence_anchors": [{
            "anchor_id": f"{observation_id}:A1", "text": text,
            "source_section": "abstract", "source_role": "abstract",
            "char_start": 0, "char_end": len(text),
        }],
    })


def test_embedded_policy_identities_are_complete_and_bound_to_parents():
    resolution, registry, composition, (normalization, comparator) = _resolved()
    assert normalization.schema_version == NORMALIZATION_POLICY_SCHEMA_VERSION
    assert normalization.resolution_source == "embedded_in_registry"
    assert normalization.path is None
    assert normalization.parent_path == resolution.registry_path
    assert normalization.parent_sha256 == resolution.registry_content_sha256
    assert comparator.schema_version == COMPARATOR_NORMALIZATION_POLICY_SCHEMA_VERSION
    assert comparator.resolution_source == "embedded_in_composition_policy"
    assert comparator.path is None and comparator.active is True
    assert validate_policy_identity(normalization) == []
    assert validate_policy_identity(comparator) == []
    assert len(normalization.content_sha256) == len(comparator.identity_sha256) == 64
    assert comparator_normalization_policy_payload(composition)["rules"]


def test_policy_canonical_hash_is_format_independent_and_content_sensitive():
    left = {"b": [2, 1], "a": {"x": "β"}}
    right = {"a": {"x": "β"}, "b": [2, 1]}
    assert canonical_sha256(left) == canonical_sha256(right)
    changed = copy.deepcopy(right)
    changed["b"][0] = 3
    assert canonical_sha256(changed) != canonical_sha256(left)


def test_policy_version_and_identity_mismatch_fail_closed():
    _, registry, composition, (normalization, _) = _resolved()
    broken_registry = copy.deepcopy(registry)
    broken_registry["normalization_registry_version"] = "context_normalization_policy_v99"
    with pytest.raises(ValueError, match="normalization_policy_version_mismatch"):
        normalization_policy_payload(broken_registry)
    broken_composition = copy.deepcopy(composition)
    broken_composition["comparator_normalization_policy_version"] = "wrong"
    with pytest.raises(ValueError, match="comparator_normalization_policy_version_mismatch"):
        comparator_normalization_policy_payload(broken_composition)
    corrupted = replace(normalization, identity_sha256="0" * 64)
    assert any("identity_hash_mismatch" in error for error in validate_policy_identity(corrupted))
    inactive = PolicyIdentity.embedded(
        version="v", schema_version="s", payload={"x": 1},
        parent_path="configs/context_attribution/context_registry_v3.json",
        parent_sha256="a" * 64, active=False, inactive_reason="not_executed",
    )
    assert inactive.active is False and inactive.inactive_reason == "not_executed"


def test_anchor_observation_and_selected_token_identities_are_stable_and_layered():
    first = _contract()
    repeated = _contract()
    assert first["observation_token_catalog_identity"] == repeated[
        "observation_token_catalog_identity"
    ]
    anchor = first["evidence_anchors"][0]
    baseline = anchor_token_catalog_identity(anchor)
    token_text_changed = copy.deepcopy(anchor)
    token_text_changed["tokens"][0]["text"] = "Mouse"
    assert anchor_token_catalog_identity(token_text_changed)["token_catalog_sha256"] != baseline[
        "token_catalog_sha256"
    ]
    offset_changed = copy.deepcopy(anchor)
    offset_changed["tokens"][0]["char_end"] += 1
    assert anchor_token_catalog_identity(offset_changed)["token_catalog_sha256"] != baseline[
        "token_catalog_sha256"
    ]
    reversed_tokens = copy.deepcopy(anchor)
    reversed_tokens["tokens"].reverse()
    assert anchor_token_catalog_identity(reversed_tokens)["token_catalog_sha256"] != baseline[
        "token_catalog_sha256"
    ]
    changed_text = _contract(text="Mouse β-catenin-like cells.")
    assert changed_text["token_catalog_identity"] != first["token_catalog_identity"]
    assert (
        changed_text["observation_token_catalog_identity"][
            "observation_anchor_text_identity_sha256"
        ]
        != first["observation_token_catalog_identity"][
            "observation_anchor_text_identity_sha256"
        ]
    )


def test_observation_and_selected_aggregates_use_stable_id_order_and_scope():
    contracts = {"o2": _contract("o2"), "o1": _contract("o1"), "o3": _contract("o3")}
    forward = selected_token_catalog_identity(contracts, ["o2", "o1"])
    reverse = selected_token_catalog_identity(contracts, ["o1", "o2"])
    assert forward == reverse
    assert forward["token_catalog_identity_version"] == TOKEN_CATALOG_IDENTITY_VERSION
    assert [x["observation_id"] for x in forward[
        "selected_observation_token_catalog_identities"
    ]] == ["o1", "o2"]
    assert "o3" not in str(forward)
    assert validate_selected_token_catalog_identity(
        forward, contracts, ["o1", "o2"]
    ) == []
    corrupted = {**forward, "selected_token_catalog_identity_sha256": "0" * 64}
    assert "selected_token_catalog_aggregate_mismatch" in (
        validate_selected_token_catalog_identity(corrupted, contracts, ["o1", "o2"])
    )
    plan = {
        **forward,
        "normalization_policy_content_sha256": "a" * 64,
        "normalization_policy_identity_sha256": "b" * 64,
        "comparator_normalization_policy_content_sha256": "c" * 64,
        "comparator_normalization_policy_identity_sha256": "d" * 64,
        "comparator_normalization_policy_active": True,
    }
    assert _plan_identity_errors(plan, contracts, ["o1", "o2"]) == []
    plan["selected_anchor_text_identity_sha256"] = None
    assert any(
        "plan_identity_missing:selected_anchor_text_identity_sha256" in error
        for error in _plan_identity_errors(plan, contracts, ["o1", "o2"])
    )


def test_extraction_cache_identity_contains_policy_and_observation_content(monkeypatch):
    resolution, registry, composition, _ = _resolved()
    common = {
        "profiles": ["generic", "biomedical"], "provider": "offline",
        "model": "fixture", "registry_resolution": resolution,
    }
    contract = _contract()
    baseline = extraction_cache_identity(contract, registry=registry, **common)
    changed_registry = copy.deepcopy(registry)
    changed_registry["factor_overrides"]["species"]["controlled_normalizations"]["human"] = "X"
    assert extraction_cache_identity(contract, registry=changed_registry, **common) != baseline

    changed_composition = copy.deepcopy(composition)
    changed_composition["rules"]["project_comparator_control_surface"][
        "optional_normalized_classes"
    ]["control"] = "different"
    monkeypatch.setattr(engine, "load_composition_policy", lambda: (changed_composition, "x"))
    assert extraction_cache_identity(contract, registry=registry, **common) != baseline
    assert extraction_cache_identity(
        _contract(text="Mouse cells."), registry=registry, **common
    ) != baseline
    assert IDENTITY_BUNDLE_VERSION == "context_attribution_identity_bundle_v1"
    assert ANCHOR_TOKENIZER_VERSION == "context_attribution_anchor_tokenizer_v1"
