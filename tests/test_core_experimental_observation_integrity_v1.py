from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from code_engine.extraction_assets.experimental_core.atomicity import assess_atomicity
from code_engine.extraction_assets.experimental_core.factors import (
    explicit_factor_candidates,
)
from code_engine.extraction_assets.experimental_core.identities import (
    CONTRACT_NAMES, contract_identity,
)
from code_engine.extraction_assets.experimental_core.integrity import evaluate_integrity
from code_engine.extraction_assets.experimental_core.linkage import (
    duplicate_local_ids, reference_audit, resolve_explicit_links,
)
from code_engine.extraction_assets.experimental_core.loss_diagnosis import first_loss
from code_engine.extraction_assets.experimental_core.models import (
    CoreProvenance, ExperimentalCoreRemediationRequirement,
    StructuredExperimentalObservationRevision,
)
from code_engine.extraction_assets.experimental_core.readiness import evaluate_readiness
from code_engine.extraction_assets.experimental_core.recovery import (
    claim_text_recovery_allowed, context_result_recovery_allowed,
    select_explicit_source,
)
from code_engine.extraction_assets.experimental_core.remediation import authorization_fields
from code_engine.extraction_assets.experimental_core.type_policy import (
    assess_observation_type, build_policy,
)


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260725_hif1a_core_experimental_observation_integrity_v1_offline"
ART = RUN / "artifacts"
PROV = CoreProvenance(producer="test", producer_version="1")


def jsonl(name: str):
    return [
        json.loads(line) for line in (ART / name).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def revision(**updates):
    base = {
        "structured_observation_revision_id": "rev",
        "source_observation_identity": "obs",
        "observation_type": "interventional_experiment",
        "observation_type_authority": "authoritative",
        "experimental_factor_ids": ["factor"],
        "measurement_ids": ["measurement"],
        "observed_result_ids": ["result"],
        "immutable": True,
        "identity": "rev",
        "provenance": PROV,
    }
    base.update(updates)
    return StructuredExperimentalObservationRevision(**base)


def factor(local_id="f", role="intervention", evidence=True):
    return {
        "factor_id": f"factor:{local_id}", "local_factor_id": local_id,
        "role": role, "order_index": 0,
        "evidence_anchor_ids": ["S1"] if evidence else [],
    }


def measurement(local_id="m", evidence=True):
    return {
        "measurement_id": f"measurement:{local_id}",
        "local_measurement_id": local_id,
        "evidence_anchor_ids": ["S2"] if evidence else [],
    }


def result(local_id="r", measurement_ref="measurement:m", comparative=False, comparator=True):
    return {
        "observed_result_id": f"result:{local_id}",
        "local_result_id": local_id,
        "measurement_ref": measurement_ref,
        "_explicit_measurement_local_ref": "m",
        "_comparative": comparative,
        "comparison_factor_refs": ["factor:c"] if comparator else [],
        "baseline_ref": None,
        "evidence_anchor_ids": ["S3"],
    }


def audit(valid=True):
    return {
        "dangling_refs": [] if valid else ["missing"],
        "duplicate_local_ids": [], "orphan_results": [],
    }


def test_observation_type_policy_has_all_five_types_and_explicit_factor_exemption():
    policy = build_policy()
    entries = {row.observation_type: row for row in policy.entries}
    assert set(entries) == {
        "interventional_experiment", "observational_comparison",
        "descriptive_measurement", "non_experimental_claim", "unresolved",
    }
    assert entries["interventional_experiment"].factor_requirement == "active_factor_required"
    assert entries["observational_comparison"].factor_requirement == "group_or_comparison_required"
    assert entries["descriptive_measurement"].factor_requirement == "not_required_by_type_policy"


@pytest.mark.parametrize("field", ["measurement_ids", "observed_result_ids"])
def test_formal_observation_rejects_empty_measurement_or_result(field):
    with pytest.raises(ValidationError):
        revision(**{field: []})


@pytest.mark.parametrize("observation_type", [
    "interventional_experiment", "observational_comparison",
])
def test_factor_required_types_reject_empty_factor(observation_type):
    with pytest.raises(ValidationError):
        revision(observation_type=observation_type, experimental_factor_ids=[])


def test_descriptive_measurement_accepts_explicit_empty_factor_policy():
    assert revision(
        observation_type="descriptive_measurement", experimental_factor_ids=[]
    ).experimental_factor_ids == []


def test_nonexperimental_claim_does_not_masquerade_as_formal_observation():
    assert revision(
        observation_type="non_experimental_claim", experimental_factor_ids=[],
        measurement_ids=[], observed_result_ids=[],
    ).observation_type == "non_experimental_claim"
    assert evaluate_readiness(
        observation_type="non_experimental_claim",
        integrity_status="non_experimental_claim", has_claim_evidence=True,
    )[0] == "non_experimental_claim"


def test_unresolved_type_cannot_pass_reuse_gate():
    assert evaluate_readiness(
        observation_type="unresolved", integrity_status="unresolved",
        has_claim_evidence=False,
    )[0] == "unassessed"


def test_type_assessment_uses_structure_not_claim_keywords():
    assert assess_observation_type(
        source={"claim": "drug strongly changed expression"},
        factor_roles=set(), measurement_count=0, result_count=0,
    )[0] == "unresolved"
    assert assess_observation_type(
        source={"experiment": {}}, factor_roles={"intervention"},
        measurement_count=1, result_count=1,
    )[0] == "interventional_experiment"


def test_intervention_migrates_to_factor_and_legacy_field_is_untouched():
    source = {"interventions": [{
        "intervention_id": "i1", "intervention_type_raw": "treatment",
        "agent_mention": "A",
    }]}
    before = json.dumps(source, sort_keys=True)
    rows = explicit_factor_candidates(source)
    assert rows[0]["intervention_id"] == "i1"
    assert json.dumps(source, sort_keys=True) == before


def test_context_fields_are_not_all_converted_to_factors():
    rows = explicit_factor_candidates({
        "experiment": {"species_raw": "mouse", "tissue_raw": "liver",
                       "model_system_raw": "cells"}
    })
    assert rows == []


def test_empty_intervention_does_not_mean_empty_experimental_factor():
    rows = explicit_factor_candidates({
        "interventions": [],
        "experiment": {"control_arm_raw": "control", "comparison_arm_raw": "disease"},
    })
    assert len(rows) == 2


def test_raw_extracted_and_canonical_factor_layers_are_distinct_in_output():
    rows = jsonl("experimental_factor_records.jsonl")
    assert rows
    assert {"raw_text", "extracted_value", "canonical_value"} <= rows[0].keys()


def test_measurement_target_endpoint_method_gaps_are_preserved_not_dropped():
    rows = jsonl("measurement_records.jsonl")
    assert len(rows) == 418
    assert all("measured_entity_raw" in row and "property_or_endpoint_raw" in row
               and "method_raw" in row for row in rows)
    assert any(row["method_raw"] is None for row in rows)


def test_result_direction_and_quantitative_layers_are_independent():
    row = jsonl("observed_result_records.jsonl")[0]
    assert "direction" in row and "quantitative_value_raw" in row
    assert "evidence_anchor_ids" in row


def test_result_must_reference_existing_measurement_at_gate():
    status = evaluate_integrity(
        observation_type="interventional_experiment", factors=[factor()],
        measurements=[measurement()], results=[result(measurement_ref=None)],
        links=[], reference_audit=audit(),
    )[0]
    assert status == "incomplete_missing_linkage"


def test_comparative_result_requires_comparator_or_baseline():
    status = evaluate_integrity(
        observation_type="interventional_experiment", factors=[factor()],
        measurements=[measurement()], results=[result(comparative=True, comparator=False)],
        links=[], reference_audit=audit(),
    )[0]
    assert status == "incomplete_missing_linkage"


def test_explicit_local_ids_and_scalar_one_to_one_recover_links():
    links = resolve_explicit_links("rev", [factor()], [measurement()], [result()])
    assert len(links) == 1
    assert links[0]["relation_type"] == "measurement_produces_result"
    implicit = result()
    implicit["_explicit_measurement_local_ref"] = None
    assert resolve_explicit_links("rev", [], [measurement()], [implicit])[0][
        "derivation_method"] == "legacy_scalar_one_to_one"


def test_same_observation_does_not_create_factor_measurement_full_connect():
    links = resolve_explicit_links(
        "rev", [factor("a"), factor("b")], [measurement()], [result()]
    )
    assert not any(row["relation_type"] == "factor_applies_to_measurement" for row in links)


def test_dangling_duplicate_and_cross_record_fail_closed():
    assert duplicate_local_ids([factor("same")], [measurement("same")], [])
    row = reference_audit(
        "rev", [], [measurement()], [result(measurement_ref="other")], [{
            "source_ref": "measurement:m", "target_ref": "missing",
        }],
    )
    assert not row["valid"]
    assert row["dangling_refs"] == ["missing"]
    assert row["orphan_results"] == ["result:r"]


def test_input_order_does_not_change_link_identity():
    f = [factor("a"), factor("b")]
    a = resolve_explicit_links("rev", f, [measurement()], [result()])
    b = resolve_explicit_links("rev", list(reversed(f)), [measurement()], [result()])
    assert [row["linkage_id"] for row in a] == [row["linkage_id"] for row in b]


@pytest.mark.parametrize(
    ("stage", "origin"),
    [(1, "parser_dropped"), (3, "scientific_validation_rejected"),
     (5, "evidence_projection_loss"), (6, "asset_migration_omission")],
)
def test_first_loss_distinguishes_pipeline_stages(stage, origin):
    traces = []
    for number in range(8):
        count = 1 if number < stage else 0
        traces.append({
            "stage_number": number, "stage_name": f"s{number}",
            "measurement_count": count, "factor_count": count,
            "intervention_count": count, "observed_result_count": count,
            "linkage_count": count,
            "field_status": {"measurements": "present" if count else "absent"},
        })
    assert first_loss(traces, "measurements")[2] == origin


def test_missing_raw_lineage_is_not_claimed_as_provider_omission():
    traces = [{
        "stage_number": 1, "stage_name": "parsed", "measurement_count": 0,
        "factor_count": 0, "intervention_count": 0, "observed_result_count": 0,
        "linkage_count": 0, "field_status": {"measurements": "absent"},
    }]
    assert first_loss(traces, "measurements")[2] == "raw_unavailable"


@pytest.mark.parametrize("component", ["factors", "measurements", "results"])
def test_recovery_uses_explicit_structures_in_priority_order(component):
    key = {"factors": "interventions", "measurements": "measurement",
           "results": "observation"}[component]
    stage, found_key, rows = select_explicit_source({
        "parsed_payload": {key: {"value": "x"}},
        "validated_observation": {key: {"value": "later"}},
    }, component)
    assert stage == "parsed_payload" and found_key == key and len(rows) == 1


def test_claim_and_context_never_generate_core_records():
    assert not claim_text_recovery_allowed()
    assert not context_result_recovery_allowed()


def test_recovery_creates_new_revisions_and_historical_hashes_are_stable():
    recoveries = jsonl("experimental_core_recovery_revisions.jsonl")
    assert len(recoveries) == 418
    assert all(row["immutable"] and row["recovery_revision_id"] for row in recoveries)
    safety = json.loads((ART / "experimental_core_safety_audit.json").read_text())
    for ref, digest in safety["historical_hashes"].items():
        assert sha256_file(ROOT / ref) == digest


def sha256_file(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_atomicity_preserves_explicit_compound_and_blocks_unmapped_split():
    explicit = [
        result("a"), {**result("b"), "_explicit_measurement_local_ref": "m2"},
    ]
    assert assess_atomicity([measurement(), measurement("m2")], explicit)[0] == (
        "compound_but_explicitly_linked"
    )
    status, issues = assess_atomicity(
        [measurement(), measurement("m2")],
        [{**result("a"), "_explicit_measurement_local_ref": None},
         {**result("b"), "_explicit_measurement_local_ref": None}],
    )
    assert status == "merged_unrecoverable" and issues


@pytest.mark.parametrize(
    ("updates", "expected"),
    [
        ({"factors": []}, "incomplete_missing_factor"),
        ({"measurements": []}, "incomplete_missing_measurement"),
        ({"results": []}, "incomplete_missing_result"),
        ({"reference_audit": audit(False)}, "invalid_dangling_reference"),
    ],
)
def test_integrity_gate_core_failures(updates, expected):
    args = {
        "observation_type": "interventional_experiment",
        "factors": [factor()], "measurements": [measurement()],
        "results": [result()], "links": [], "reference_audit": audit(),
    }
    args.update(updates)
    assert evaluate_integrity(**args)[0] == expected


def test_missing_noncore_metadata_can_pass_with_limitations_but_no_evidence_cannot_complete():
    status = evaluate_integrity(
        observation_type="interventional_experiment", factors=[factor(evidence=False)],
        measurements=[measurement()], results=[result()], links=[],
        reference_audit=audit(),
    )[0]
    assert status == "structurally_complete_with_limitations"


@pytest.mark.parametrize(
    ("integrity", "evidence", "expected"),
    [
        ("structurally_complete", True, "machine_reusable_candidate"),
        ("structurally_complete_with_limitations", True, "usable_with_major_limitations"),
        ("incomplete_missing_measurement", True, "text_evidence_only"),
        ("invalid_dangling_reference", False, "unusable"),
    ],
)
def test_machine_reuse_gate_is_fail_closed(integrity, evidence, expected):
    assert evaluate_readiness(
        observation_type="interventional_experiment",
        integrity_status=integrity, has_claim_evidence=evidence,
    )[0] == expected


def test_readiness_is_not_human_gold_or_formal_conflict_authority():
    rows = jsonl("experimental_observation_machine_reuse_readiness.jsonl")
    assert all(not row["human_gold"] and not row["formal_conflict_authority"] for row in rows)


def test_remediation_authorizations_are_strict_false():
    assert not any(authorization_fields().values())
    with pytest.raises(ValidationError):
        ExperimentalCoreRemediationRequirement(
            observation_identity="o", observation_type="unresolved",
            missing_components=["measurement"], raw_lineage_status="unavailable",
            parsed_payload_status="unavailable", evidence_status="unavailable",
            provider_reextraction_required=True, minimal_source_scope="block",
            dedup_group_identity="d", provider_call_authorized=True,
            identity="x", provenance=PROV,
        )


def test_all_required_offline_artifacts_exist_and_json_parse():
    required = {
        "experimental_core_asset_inventory.jsonl",
        "observation_stage_traces.jsonl",
        "experimental_core_first_loss_diagnoses.jsonl",
        "observation_type_assessments.jsonl",
        "experimental_factor_records.jsonl", "measurement_records.jsonl",
        "observed_result_records.jsonl", "experimental_observation_linkages.jsonl",
        "experimental_observation_atomicity_audit.jsonl",
        "experimental_observation_reference_integrity_audit.jsonl",
        "experimental_core_recovery_revisions.jsonl",
        "structured_experimental_observation_revisions.jsonl",
        "experimental_observation_structural_integrity.jsonl",
        "experimental_observation_machine_reuse_readiness.jsonl",
        "experimental_core_remediation_requirements.jsonl",
        "core_experimental_observation_integrity_summary.json",
        "core_experimental_observation_integrity_manifest.json",
    }
    assert all((ART / name).is_file() for name in required)
    for path in ART.glob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))
    for path in ART.glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            json.loads(line)


def test_generated_schemas_are_strict_and_contract_identities_recompute():
    schema_paths = list((RUN / "schemas").glob("*.schema.json"))
    assert len(schema_paths) >= 14
    assert all(json.loads(path.read_text()).get("additionalProperties") is False
               for path in schema_paths)
    for name in CONTRACT_NAMES:
        identity = contract_identity(name)
        assert identity["identity_match"]
        assert identity["identity_sha256"] == identity["recomputed_sha256"]


def test_joint_v2_has_ids_refs_scopes_and_remains_inactive():
    contract = json.loads((ART / "candidate_joint_contract_v2.json").read_text())
    status = json.loads((ART / "candidate_joint_contract_v2_status.json").read_text())
    fields = set(contract["output_fields"])
    assert {"experiment_scopes[]", "observations[]", "experimental_factors[]",
            "measurements[]", "observed_results[]"} <= fields
    assert "result.measurement_ref" in contract["local_reference_requirements"]
    assert {"formal_conflict", "comparability", "divergence_explanation"} <= set(
        contract["forbidden_outputs"]
    )
    assert status["validation_status"] == "pending_smoke_validation"
    assert status["production_status"] == "not_activated"


def test_existing_scientific_state_is_unchanged_and_fail_closed():
    manifest = json.loads((ART / "core_experimental_observation_integrity_manifest.json").read_text())
    assert manifest["candidate_count_before"] == manifest["candidate_count_after"] == 11
    assert not manifest["candidate_identity_changed"]
    assert not manifest["candidate_order_changed"]
    assert not manifest["scientific_pair_set_changed"]
    assert manifest["formal_conflict_count_before"] == manifest["formal_conflict_count_after"] == 0
    assert json.loads((ART / "weak_3ca_core_observation_audit.json").read_text())[
        "difference_authority_status"] == "ready_not_materialized"
    assert json.loads((ART / "weak_256_core_observation_audit.json").read_text())[
        "context_entry_status"] == "blocked_context_b_unavailable"
    assert json.loads((ART / "ebd5_core_observation_audit.json").read_text())[
        "candidate_qualification_status"] == "blocked_alignment"
    assert json.loads((ART / "context_17b_core_observation_audit.json").read_text())[
        "status"] == "fail_closed_policy_coverage_failure"
    assert json.loads((ART / "context_41f_core_observation_audit.json").read_text())[
        "status"] == "fail_closed_policy_coverage_failure"


def test_safety_zero_external_activity_and_no_forbidden_side_effects():
    safety = json.loads((ART / "experimental_core_safety_audit.json").read_text())
    for key in ("provider_calls", "api_calls", "real_api_calls", "network_calls", "downloads"):
        assert safety[key] == 0
    for key in (
        "credential_values_read", "provider_client_created", "historical_runs_modified",
        "historical_raw_files_modified", "historical_parsed_payloads_modified",
        "historical_validated_observations_modified", "formal_v3_modified",
        "projection_historical_content_modified", "candidate_pairs_modified",
        "dataset_release_pipeline_created", "method_paper_narrative_changed",
        "handoff_created", "atlas_activated", "active_pointer_changed",
        "variational_em_called",
    ):
        assert not safety[key]


def test_dependency_boundary_has_no_provider_network_or_conflict_authority_imports():
    package = ROOT / "src/code_engine/extraction_assets/experimental_core"
    forbidden = (
        "requests", "httpx", "deepseek_client", "conflict_candidate",
        "context_difference", "comparability", "divergence_explanation",
    )
    for path in package.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not any(f"import {token}" in text or f"from {token}" in text
                       for token in forbidden)

