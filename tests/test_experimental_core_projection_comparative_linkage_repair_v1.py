from __future__ import annotations

import json
from pathlib import Path

import pytest

from code_engine.extraction_assets.experimental_core.comparator_linkage import recover_comparator
from code_engine.extraction_assets.experimental_core.comparison_semantics import classify_comparison
from code_engine.extraction_assets.experimental_core.measurement_method import recover_method
from code_engine.extraction_assets.experimental_core.projection import (
    build_compatibility_sidecar, build_projection,
)
from code_engine.extraction_assets.experimental_core.projection_validation import validate_projection_refs
from code_engine.extraction_assets.experimental_core.readiness_v2 import evaluate_readiness_v2
from code_engine.extraction_assets.experimental_core.remediation_v2 import plan_remediation_v2

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260725_hif1a_experimental_core_projection_comparative_linkage_repair_v1_offline"
ART = RUN / "artifacts"
V1 = ROOT / "runs/20260725_hif1a_core_experimental_observation_integrity_v1_offline/artifacts"


def rows(name: str):
    return [json.loads(line) for line in (ART / name).read_text().splitlines() if line]


def value(name: str):
    return json.loads((ART / name).read_text())


@pytest.fixture
def provenance():
    return {
        "producer": "test", "producer_version": "v1", "source_artifact_refs": [],
        "deterministic_rule_refs": [], "limitations": [], "offline": True,
    }


@pytest.fixture
def observation(provenance):
    return {
        "source_observation_identity": "obs", "identity": "revision",
        "observation_type": "interventional_experiment",
        "experiment_scope_identity": "scope", "experimental_factor_ids": ["factor"],
        "measurement_ids": ["measurement"], "observed_result_ids": ["result"],
        "linkage_record_ids": ["link"], "context_asset_identity": "context",
        "evidence_chain_identity": "evidence", "structural_integrity_identity": "integrity",
        "source_projection_identity": "old_projection", "provenance": provenance,
    }


def test_projection_is_lossless_by_reference(observation):
    projection = build_projection(observation, readiness_ref="ready")
    assert projection["lossless_by_reference"] is True
    assert projection["experimental_factor_refs"] == ["factor"]
    assert projection["measurement_refs"] == ["measurement"]
    assert projection["observed_result_refs"] == ["result"]
    assert projection["linkage_refs"] == ["link"]
    assert "claim" not in projection


def test_projection_sidecar_does_not_mutate_history(observation):
    projection = build_projection(observation, readiness_ref="ready")
    sidecar = build_compatibility_sidecar(
        projection, historical_projection_identity="old", missing_component_types=["measurement"]
    )
    assert sidecar["historical_content_unchanged"] is True
    assert sidecar["projection_v2_identity"] == projection["identity"]


def test_projection_validation_fails_closed(observation):
    projection = build_projection(observation, readiness_ref="ready")
    assert validate_projection_refs(projection, {"factor", "measurement", "result", "link"})[0] == (
        "ready_for_offline_consumer_validation"
    )
    assert validate_projection_refs(projection, {"factor"})[0] == "blocked_invalid_links"


@pytest.mark.parametrize(
    ("observation_type", "expected", "required"),
    [
        ("interventional_experiment", "intervention_vs_control", True),
        ("observational_comparison", "group_vs_group", True),
        ("descriptive_measurement", "absolute_descriptive_observation", False),
    ],
)
def test_comparison_type_policy(observation, observation_type, expected, required):
    observation["observation_type"] = observation_type
    result = {"identity": "result", "evidence_anchor_ids": [], "provenance": observation["provenance"]}
    semantic = classify_comparison(result, observation, {"observation": {"comparison_raw": "vs control"}})
    assert (semantic["comparison_semantics"], semantic["comparison_required"]) == (expected, required)


def test_direction_alone_cannot_require_comparison(observation):
    result = {
        "identity": "result", "direction": "positive", "comparison_factor_refs": [],
        "baseline_ref": None, "evidence_anchor_ids": [], "provenance": observation["provenance"],
    }
    semantic = classify_comparison(result, observation, {"observation": {"comparison_raw": None}})
    assert semantic["comparison_semantics"] == "unresolved"
    assert semantic["comparison_required"] is None


def test_explicit_association_is_not_intervention_comparison(observation):
    observation["observation_type"] = "observational_comparison"
    result = {"identity": "result", "evidence_anchor_ids": [], "provenance": observation["provenance"]}
    semantic = classify_comparison(
        result, observation,
        {"observation": {"comparison_raw": None, "observed_result": "associated with"},
         "candidate_relation": {"relation_raw": "associated"}},
    )
    assert semantic["comparison_semantics"] == "association_or_correlation"
    assert semantic["comparison_required"] is False


def _factor(identity, text, provenance):
    return {"identity": identity, "raw_text": text, "extracted_value": text, "provenance": provenance}


def test_exact_unique_comparator_can_recover(observation, provenance):
    result = {
        "identity": "result", "comparison_factor_refs": [], "baseline_ref": None,
        "evidence_anchor_ids": ["anchor"], "provenance": provenance,
    }
    semantic = {"identity": "semantic", "comparison_required": True}
    edges, recovery = recover_comparator(
        result, [_factor("control", "vehicle control", provenance)], semantic,
        ["response was lower compared with vehicle control"],
    )
    assert edges[0]["deterministic_uniqueness"] is True
    assert recovery["comparator_link_authority"] == "deterministic_exact_evidence_reference"
    assert recovery["creates_new_link_revision"] is True


def test_single_control_without_explicit_syntax_is_not_authority(provenance):
    result = {
        "identity": "result", "comparison_factor_refs": [], "baseline_ref": None,
        "evidence_anchor_ids": ["anchor"], "provenance": provenance,
    }
    _, recovery = recover_comparator(
        result, [_factor("control", "vehicle", provenance)],
        {"identity": "semantic", "comparison_required": True}, ["vehicle response changed"],
    )
    assert recovery["comparator_link_authority"] == "unresolved"


def test_multiple_exact_candidates_remain_unresolved(provenance):
    result = {
        "identity": "result", "comparison_factor_refs": [], "baseline_ref": None,
        "evidence_anchor_ids": ["anchor"], "provenance": provenance,
    }
    _, recovery = recover_comparator(
        result, [_factor("a", "control", provenance), _factor("b", "control", provenance)],
        {"identity": "semantic", "comparison_required": True}, ["lower versus control"],
    )
    assert recovery["comparator_link_authority"] == "unresolved"


@pytest.mark.parametrize("field_id", ["localization", "measurement_semantic_level", "sample_type"])
def test_non_method_context_fields_are_rejected(provenance, field_id):
    measurement = {
        "identity": "measurement", "observation_revision_identity": "revision",
        "_source_observation_identity": "obs", "_experiment_scope_identity": "scope",
        "method_raw": None, "method_extracted": None, "method_canonical": None,
        "evidence_anchor_ids": [], "provenance": provenance,
    }
    recovery, links = recover_method(measurement, [{
        "identity": "field", "field_id": field_id, "value_state": "present",
        "context_validation_status": "validated", "observation_candidate_identity": "obs",
    }], experiment_scope_validated=True)
    assert recovery["method_present_after"] is False
    assert links == []


def test_local_context_method_recovers_by_reference(provenance):
    measurement = {
        "identity": "measurement", "observation_revision_identity": "revision",
        "_source_observation_identity": "obs", "_experiment_scope_identity": "scope",
        "method_raw": None, "method_extracted": None, "method_canonical": None,
        "evidence_anchor_ids": [], "provenance": provenance,
    }
    recovery, links = recover_method(measurement, [{
        "identity": "field", "field_id": "measurement_method", "value_state": "present",
        "context_validation_status": "validated", "observation_candidate_identity": "obs",
    }], experiment_scope_validated=False)
    assert recovery["method_context_ref"] == "field"
    assert recovery["method_raw"] is None
    assert links[0]["authority_status"] == "validated_local_context_reference"


def test_unvalidated_shared_scope_is_candidate_only(provenance):
    measurement = {
        "identity": "measurement", "observation_revision_identity": "revision",
        "_source_observation_identity": "obs", "_experiment_scope_identity": "scope",
        "method_raw": None, "method_extracted": None, "method_canonical": None,
        "evidence_anchor_ids": [], "provenance": provenance,
    }
    recovery, _ = recover_method(measurement, [{
        "identity": "field", "field_id": "assay", "value_state": "present",
        "context_validation_status": "validated", "observation_candidate_identity": "other",
    }], experiment_scope_validated=False)
    assert recovery["method_recovery_authority"] == "candidate_non_authoritative"
    assert recovery["method_present_after"] is False


def test_missing_comparator_is_not_text_only(observation):
    linkage = {"identity": "linkage", "full_machine_reuse_linkage": "blocked_missing_comparator"}
    readiness = evaluate_readiness_v2(
        observation, linkage, [{"method_present_after": True}], context_available=True
    )
    assert readiness["status"] == "structured_core_blocked_comparative_linkage"
    assert readiness["human_gold"] is False
    assert readiness["formal_authority"] is False


def test_missing_method_is_a_limitation(observation):
    linkage = {"identity": "linkage", "full_machine_reuse_linkage": "complete"}
    readiness = evaluate_readiness_v2(
        observation, linkage, [{"method_present_after": False}], context_available=True
    )
    assert readiness["status"] == "machine_reusable_with_method_limitations"


def test_remediation_is_planning_only(observation):
    linkage = {"full_machine_reuse_linkage": "blocked_missing_comparator"}
    requirements = plan_remediation_v2(
        observation, linkage, [{"method_present_after": False}], "block"
    )
    assert {row["remediation_category"] for row in requirements} == {"core_blocking", "enrichment"}
    for row in requirements:
        assert row["automatic_execution_authorized"] is False
        assert row["provider_call_authorized"] is False
        assert row["network_call_authorized"] is False
        assert row["budget_authorization_present"] is False


def test_full_run_projection_counts_and_losses():
    summary = value("experimental_core_projection_comparative_linkage_summary.json")
    assert summary["observation_count"] == 418
    assert summary["projection_v2_count"] == 418
    assert summary["projection_v1_missing_measurement_refs_count"] == 418
    assert summary["projection_v1_missing_result_refs_count"] == 418
    assert summary["projection_v1_missing_factor_refs_count"] == 31
    assert summary["projection_v2_invalid_count"] == 0


def test_full_run_corrects_text_only_semantics():
    summary = value("experimental_core_projection_comparative_linkage_summary.json")
    assert summary["pre_recovery_missing_comparator_count"] == 88
    assert summary["true_text_evidence_only_count"] == 0
    assert summary["structured_core_blocked_comparative_linkage_count"] > 0


def test_contract_identities_recompute():
    for row in value("contract_identities.json"):
        canonical = json.dumps(
            row["canonical_payload"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
        import hashlib
        assert hashlib.sha256(canonical).hexdigest() == row["identity_sha256"]
        assert row["identity_sha256"] == row["recomputed_sha256"]
        assert row["identity_match"] is True


def test_all_json_and_jsonl_parse():
    for path in RUN.rglob("*.json"):
        json.loads(path.read_text())
    for path in RUN.rglob("*.jsonl"):
        for line in path.read_text().splitlines():
            json.loads(line)


def test_historical_projection_and_scientific_state_are_unchanged():
    safety = value("experimental_core_projection_safety_audit.json")
    assert safety["historical_projection_content_modified"] is False
    assert safety["formal_v3_modified"] is False
    assert safety["candidate_pairs_modified"] is False
    assert value("weak_3ca_projection_linkage_audit.json") == {
        "context_entry_status": "ready",
        "difference_authority_status": "ready_not_materialized",
    }
    assert value("weak_256_projection_linkage_audit.json")["context_entry_status"] == (
        "blocked_context_b_unavailable"
    )
    assert value("ebd5_projection_linkage_audit.json")["candidate_qualification_status"] == (
        "blocked_alignment"
    )


@pytest.mark.parametrize(
    "field",
    ["provider_calls", "api_calls", "real_api_calls", "network_calls", "downloads"],
)
def test_external_activity_is_zero(field):
    assert value("experimental_core_projection_safety_audit.json")[field] == 0


@pytest.mark.parametrize(
    "field",
    ["credential_values_read", "provider_client_created", "atlas_activated",
     "active_pointer_changed", "variational_em_called"],
)
def test_forbidden_activity_is_false(field):
    assert value("experimental_core_projection_safety_audit.json")[field] is False


def test_v1_assets_remain_read_only_contracts():
    assert len((V1 / "structured_experimental_observation_revisions.jsonl").read_text().splitlines()) == 418
    assert len((V1 / "measurement_records.jsonl").read_text().splitlines()) == 418
    assert len((V1 / "observed_result_records.jsonl").read_text().splitlines()) == 418


def test_generated_schemas_are_closed_and_self_consistent():
    schemas = list((RUN / "schemas").glob("*.schema.json"))
    assert len(schemas) == 14
    for path in schemas:
        schema = json.loads(path.read_text())
        assert schema["$schema"].endswith("2020-12/schema")
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])


def test_dependency_boundaries_are_fail_closed():
    package = ROOT / "src/code_engine/extraction_assets/experimental_core"
    sources = "\n".join(
        (package / name).read_text()
        for name in (
            "comparison_semantics.py", "comparator_linkage.py", "measurement_method.py",
            "linkage_completeness.py", "readiness_v2.py", "remediation_v2.py",
        )
    )
    assert "context_attribution.conflict_candidate" not in sources
    assert "comparability" not in sources
    assert "provider" not in sources.casefold().replace("provider_reextraction", "")
    assert "credential" not in sources.casefold()


def test_comparator_recovery_is_input_order_stable(provenance):
    result = {
        "identity": "result", "comparison_factor_refs": [], "baseline_ref": None,
        "evidence_anchor_ids": ["anchor"], "provenance": provenance,
    }
    factors = [_factor("b", "vehicle", provenance), _factor("a", "untreated", provenance)]
    semantic = {"identity": "semantic", "comparison_required": True}
    first = recover_comparator(result, factors, semantic, ["lower versus vehicle"])
    second = recover_comparator(result, list(reversed(factors)), semantic, ["lower versus vehicle"])
    assert first[1]["recovered_comparator_factor_ref"] == second[1]["recovered_comparator_factor_ref"]
    assert [row["edge_identity"] for row in first[0]] == [row["edge_identity"] for row in second[0]]
