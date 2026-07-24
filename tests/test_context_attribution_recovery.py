import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from code_engine.context_attribution.engine import extraction_prompt_v6
from code_engine.context_attribution.models import ProviderContextExtractionV6
from code_engine.context_attribution.recovery import (
    OFFLINE_ADAPTER_VERSION,
    adapt_v5_payload_to_v6,
    build_recovery_plan,
    classify_recovery,
    create_recovery_run,
    derive_factor_anchors,
    recovery_counts,
    retry_queue_v2,
    truncation_audit,
)


ROOT = Path(__file__).parents[1]
INPUT = ROOT / "runs/20260723_171527_hif1a_hypoxia_cancer_response_discovery_v1_fulltext_v3_recovered_reentry"
SOURCE = ROOT / "runs/20260724_hif1a_context_attribution_v5_identity_complete_smoke_execution"


def provider_payload(observation_id):
    rows = [
        json.loads(line)
        for line in (SOURCE / "artifacts/context_attribution_provider_calls.jsonl")
        .read_text(encoding="utf-8").splitlines()
    ]
    return next(row["parsed_payload"] for row in rows if row["record_id"] == observation_id)


def test_real_recovery_classification_is_exclusive_and_complete():
    rows = classify_recovery(SOURCE)
    by_id = {row["observation_id"]: row for row in rows}
    assert len(rows) == len(by_id) == 8
    assert sum(row["classification"] == "validated_cached" for row in rows) == 4
    assert by_id["ftl1v3_71023211dcfb3d430a918e17"]["recovery_action"] == "offline_revalidate"
    assert by_id["ftl1v3_f530298f2b2955bfe9988710"]["recovery_action"] == \
        "provider_regeneration_explicit_opt_in"
    for oid in (
        "ftl1v3_17b7314297cabac677007b35",
        "ftl1v3_41f0090d726e6e8591a58574",
    ):
        assert by_id[oid]["recovery_action"] == "provider_regeneration_required"


def test_v6_schema_forbids_provider_factor_anchor_authority():
    payload, _ = adapt_v5_payload_to_v6(
        provider_payload("ftl1v3_71023211dcfb3d430a918e17")
    )
    payload["context_factors"][0]["evidence_anchor_ids"] = ["invented"]
    with pytest.raises(ValidationError):
        ProviderContextExtractionV6.model_validate(payload)


def test_v6_prompt_removes_system_derived_provider_fields():
    prompt = extraction_prompt_v6(
        {"observation_id": "x", "evidence_anchors": [], "experimental_logic_chain": {}},
        ["generic"],
    )
    value = json.loads(prompt)
    factor_properties = value["output_schema"]["$defs"]["ProviderContextFactorV6"]["properties"]
    assert "evidence_anchor_ids" not in factor_properties
    assert "raw_value" not in factor_properties
    assert "composed_value" not in factor_properties


def test_anchor_derivation_is_stable_and_adapter_is_immutable():
    source = provider_payload("ftl1v3_71023211dcfb3d430a918e17")
    original = deepcopy(source)
    adapted, audit = adapt_v5_payload_to_v6(source)
    internal, provenance = derive_factor_anchors(adapted)
    assert source == original
    assert audit["adapter_version"] == OFFLINE_ADAPTER_VERSION
    assert audit["new_scientific_information_added"] is False
    factors = {row["factor_id"]: row for row in internal["context_factors"]}
    assert factors["cell_line"]["evidence_anchor_ids"] == [
        factors["cell_line"]["explicit_span"]["evidence_anchor_id"]
    ]
    assert factors["comparator"]["evidence_anchor_ids"] == [
        "PMC7689016_35_0:S0002"
    ]
    assert factors["species"]["evidence_anchor_ids"] == []
    assert provenance["provider_factor_level_anchor_authority"] is False


def test_adapter_fails_closed_for_schema_rejected_and_truncated_payload():
    with pytest.raises(ValueError, match="adapter_missing_explicit_span"):
        adapt_v5_payload_to_v6(
            provider_payload("ftl1v3_f530298f2b2955bfe9988710")
        )
    with pytest.raises(ValueError, match="adapter_requires_schema_v5"):
        adapt_v5_payload_to_v6({})


def test_resume_billing_plan_only_allowlists_and_bounds(tmp_path):
    default = build_recovery_plan(
        input_run=INPUT, source_run=SOURCE, target_run=tmp_path / "default",
        mode="targeted_provider",
    )
    assert default["provider_recall_required_observation_ids"] == [
        "ftl1v3_17b7314297cabac677007b35",
        "ftl1v3_41f0090d726e6e8591a58574",
    ]
    assert default["extraction_provider_calls_planned"] == 2
    assert default["provider_calls_hard_bound"] <= 7
    assert default["provider_calls"] == default["network_calls"] == 0
    assert default["credential_values_read"] is False
    opted = build_recovery_plan(
        input_run=INPUT, source_run=SOURCE, target_run=tmp_path / "opted",
        mode="targeted_provider", include_schema_regeneration=True,
    )
    assert opted["extraction_provider_calls_planned"] == 3
    assert opted["provider_calls_hard_bound"] <= 8


def test_offline_real_fixture_validates_without_provider(tmp_path):
    plan = create_recovery_run(
        input_run=INPUT, source_run=SOURCE, output_run=tmp_path / "offline",
        mode="offline_only", profiles=["generic", "biomedical"],
    )
    assert plan["offline_revalidation_results"][0]["valid"] is True
    assert plan["offline_revalidation_validated_count"] == 1
    assert plan["provider_calls"] == plan["network_calls"] == plan["downloads"] == 0
    assert not (tmp_path / "offline/artifacts/context_attribution_provider_calls.jsonl").exists()


def test_retry_queue_v2_separates_layers_and_bounds_attempts():
    classifications = classify_recovery(SOURCE)
    queue = retry_queue_v2(classifications)
    by_id = {row["observation_id"]: row for row in queue}
    assert by_id["ftl1v3_71023211dcfb3d430a918e17"]["failure_layer"] == \
        "deterministic_validation"
    assert by_id["ftl1v3_f530298f2b2955bfe9988710"]["failure_layer"] == "schema"
    for oid in (
        "ftl1v3_17b7314297cabac677007b35",
        "ftl1v3_41f0090d726e6e8591a58574",
    ):
        assert by_id[oid]["failure_layer"] == "provider"
        assert by_id[oid]["max_attempts"] == 2
        assert by_id[oid]["attempt_count"] == 1
    counts = recovery_counts(classifications)
    assert counts["validated_extraction_count"] == 4
    assert counts["provider_failed_observation_count"] == 2
    assert counts["schema_rejected_observation_count"] == 1
    assert counts["deterministic_rejected_observation_count"] == 1
    assert counts["nonvalidated_observation_count"] == 4


def test_real_truncation_evidence_reaches_recorded_output_limit():
    audits = truncation_audit(SOURCE)
    assert len(audits) == 2
    assert all(row["raw_response_byte_count"] == 16384 for row in audits)
    assert all(row["completion_tokens"] == row["configured_max_tokens"] == 32768 for row in audits)
    assert all(row["finish_reason"] == "length" for row in audits)
    assert all(row["http_status"] is None for row in audits)
    assert all(row["recorded_token_limit_reached"] for row in audits)
