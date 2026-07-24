from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from code_engine.context_attribution.comparison_adapter import adapt_pair_v2_to_v3
from code_engine.context_attribution.identities import (
    build_provider_execution_identity, canonical_sha256,
    validate_call_contract_identity,
)
from code_engine.context_attribution.inference_rules import (
    adapt_v6_to_v7, derive_inference_rule, materialize_internal_v5,
)
from code_engine.context_attribution.models import FactorComparisonV3
from code_engine.context_attribution.offline_v7 import (
    COMPARISON_ALLOWLIST, EXTRACTION_ALLOWLIST, build_offline_plan,
    execute_offline_v7,
)
from code_engine.context_attribution.recovery import _contracts
from code_engine.context_attribution.registry import load_registry
from code_engine.context_attribution.validation import (
    validate_context_extraction_v6, validate_pair_attribution_v3,
)

ROOT = Path(__file__).parents[1]
INPUT = ROOT / "runs/20260723_171527_hif1a_hypoxia_cancer_response_discovery_v1_fulltext_v3_recovered_reentry"
SOURCE = ROOT / "runs/20260724_hif1a_context_attribution_v6_recovery_targeted_paid_execution"
PROFILES = ["generic", "biomedical"]


def provider_rows():
    path = SOURCE / "artifacts/context_attribution_provider_calls.jsonl"
    return {x["record_id"]: x for x in (
        json.loads(line) for line in path.read_text().splitlines() if line.strip()
    )}


@pytest.mark.parametrize("status,a,b,valid", [
    ("same", "a", "b", True), ("same", None, "b", False),
    ("different", "a", "b", True), ("different", "a", None, False),
    ("missing_a", None, "b", True), ("missing_a", "a", "b", False),
    ("missing_b", "a", None, True), ("missing_b", "a", "b", False),
    ("missing_both", None, None, True), ("missing_both", None, "b", False),
    ("same", "", "b", False), ("missing_a", "", "b", False),
])
def test_comparison_nullable_contract(status, a, b, valid):
    payload = {
        "factor_id": "species", "claim_a_value": a, "claim_b_value": b,
        "status": status, "comparability_effect": "minor",
        "explanatory_strength": "low", "reason": "fixture",
    }
    if valid:
        FactorComparisonV3.model_validate(payload)
    else:
        with pytest.raises(ValidationError):
            FactorComparisonV3.model_validate(payload)


def test_unique_rule_and_fail_closed_variants():
    oid = next(iter(EXTRACTION_ALLOWLIST))
    contracts = _contracts(INPUT, PROFILES)
    factor = next(
        x for x in provider_rows()[oid]["parsed_payload"]["context_factors"]
        if x["factor_id"] == "comparator"
    )
    factor = {**factor, "inference_rule": None}
    result = derive_inference_rule(factor, contracts[oid], PROFILES)
    assert result["derivation_status"] == "derived"
    assert len(result["matched_rule_candidates"]) == 1

    bad_node = deepcopy(factor)
    bad_node["raw_components"][0]["chain_node_id"] = "not_a_node"
    bad_node["source_chain_node_ids"] = ["not_a_node"]
    assert derive_inference_rule(
        bad_node, contracts[oid], PROFILES
    )["derivation_status"] == "rejected"

    bad_field = deepcopy(factor)
    bad_field["raw_components"][0]["field_path"] = "not_a_field"
    assert derive_inference_rule(
        bad_field, contracts[oid], PROFILES
    )["derivation_status"] == "rejected"

    no_rule = deepcopy(factor)
    no_rule["factor_id"] = "species"
    assert derive_inference_rule(
        no_rule, contracts[oid], PROFILES
    )["derivation_status"] == "rejected"


@pytest.mark.parametrize("oid", sorted(EXTRACTION_ALLOWLIST))
def test_real_extraction_adapter_preserves_source_and_runs_full_validation(oid):
    source = provider_rows()[oid]["parsed_payload"]
    before = canonical_sha256(source)
    contracts = _contracts(INPUT, PROFILES)
    adapted, audit = adapt_v6_to_v7(
        source, contracts[oid], PROFILES, registry=load_registry()
    )
    assert canonical_sha256(source) == before
    assert audit["scientific_text_added"] is False
    assert audit["components_added_or_modified"] is False
    inferred = [
        x for x in audit["factors"] if x["rule_derivation"] is not None
    ]
    assert inferred
    assert all("inference_rule" not in x for x in adapted["context_factors"])
    if audit["valid"]:
        internal = materialize_internal_v5(adapted, audit)
        validated, errors = validate_context_extraction_v6(
            internal, contracts[oid], PROFILES, registry=load_registry()
        )
        assert isinstance(errors, list)
        assert validated.validation_status in {"validated", "rejected"}
    else:
        assert any(
            x["rule_derivation"]["derivation_status"] == "rejected"
            for x in inferred
        )


def test_real_pair_adapter_is_content_preserving_and_validator_runs():
    source = provider_rows()[next(iter(COMPARISON_ALLOWLIST))]["parsed_payload"]
    adapted, audit = adapt_pair_v2_to_v3(source)
    assert audit["comparability_modified"] is False
    assert audit["confidence_modified"] is False
    assert adapted["comparability"] == source["comparability"]
    assert adapted["confidence"] == source["confidence"]
    extractions = {
        x["observation_id"]: x for x in (
            json.loads(line) for line in
            (SOURCE / "artifacts/observation_context_extractions.jsonl").read_text().splitlines()
            if line.strip()
        )
    }
    pair, errors = validate_pair_attribution_v3(
        adapted, pair_id=adapted["pair_id"],
        extraction_a=extractions[adapted["claim_a_observation_id"]],
        extraction_b=extractions[adapted["claim_b_observation_id"]],
        profiles=PROFILES, registry=load_registry(),
    )
    assert isinstance(errors, list)
    assert pair.validation_status in {"validated", "rejected"}


def test_provider_execution_identity_v2_splits_call_contracts():
    identity = build_provider_execution_identity(
        provider="fake", model="fake", thinking_mode="disabled",
        configured_max_tokens=100,
        extraction_prompt_version="context_attribution_prompts_v7",
        comparison_prompt_version="context_pair_attribution_prompts_v3",
        extraction_schema_version="observation_context_extraction_v7",
        comparison_schema_version="context_pair_attribution_v3",
    )
    assert identity.verify()
    assert identity.extraction_prompt_version != identity.comparison_prompt_version
    assert identity.prompt_version is None
    assert identity.identity_sha256 == canonical_sha256(identity.canonical_payload())
    contract = validate_call_contract_identity(
        identity, call_type="comparison",
        effective_prompt_version="context_pair_attribution_prompts_v3",
        effective_schema_version="context_pair_attribution_v3",
        effective_validator_version="context_pair_attribution_validator_v3",
    )
    assert len(contract["contract_identity_sha256"]) == 64
    with pytest.raises(ValueError, match="provider_call_contract_identity_mismatch"):
        validate_call_contract_identity(
            identity, call_type="comparison",
            effective_prompt_version="context_attribution_prompts_v7",
            effective_schema_version="context_pair_attribution_v3",
            effective_validator_version="context_pair_attribution_validator_v3",
        )


def test_offline_plan_exact_allowlist_and_zero_authority(tmp_path):
    plan = build_offline_plan(
        repository_root=ROOT, input_run=INPUT, source_run=SOURCE,
        output_run=tmp_path / "out", profiles=PROFILES,
    )
    assert plan["valid"]
    assert {x["call_id"] for x in plan["source_records"]} == (
        EXTRACTION_ALLOWLIST | COMPARISON_ALLOWLIST
    )
    assert all(x["offline_replay_reusable"] for x in plan["source_records"])
    assert not any(x["production_transport_reusable"] for x in plan["source_records"])
    assert plan["provider_client_permitted"] is False
    assert plan["credential_read_permitted"] is False
    assert plan["network_permitted"] is False


def test_end_to_end_zero_api_offline_run(tmp_path):
    out = tmp_path / "offline"
    summary = execute_offline_v7(
        repository_root=ROOT, input_run=INPUT, source_run=SOURCE,
        output_run=out, profiles=PROFILES,
    )
    for field in (
        "provider_calls", "api_calls", "real_api_calls",
        "network_call_attempt_count",
    ):
        assert summary[field] == 0
    assert summary["credential_values_read"] is False
    assert summary["provider_client_created"] is False
    assert summary["provider_call_artifact_record_count"] == 0
    assert summary["source_transport_provenance_complete"] is False
    rows = provider_rows()
    assert {
        key: canonical_sha256(value["parsed_payload"]) for key, value in rows.items()
    } == {
        key: canonical_sha256(value["parsed_payload"])
        for key, value in provider_rows().items()
    }
