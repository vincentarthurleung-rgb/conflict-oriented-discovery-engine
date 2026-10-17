"""Adversarial synthetic fixtures only; never scientific source records."""
import copy
import json
from pathlib import Path

import pytest

from code_engine.fulltext.evidence_projection import project_fulltext_run
from code_engine.fulltext.experimental_projection_handoff import prepare_experimental_handoff
from code_engine.normalization.core_eligibility import core_graph_eligibility
from code_engine.normalization.experimental_admission import experimental_admission_blocks

FROZEN = Path(__file__).resolve().parents[1] / "runs/20261014_code_first_source_grounded_figure1c_experimental_record_offline/record.json"


@pytest.fixture
def tempting():
    """Synthetic authority claims must not be mistaken for real approvals."""
    row = json.loads(FROZEN.read_text())
    formal = row["ExperimentalObservationV3"]
    formal["candidate_relation"].update(subject_mention="TargetX", object_mention="cell proliferation", relation_raw="decreases")
    formal["measurement"].update(measurement_dimension="proliferation", normalization_status="resolved")
    formal["eligibility"].update(strict_core_eligible=True, conflict_eligible=True, hypothesis_eligible=True, exclusion_reasons=[])
    formal["interventions"][0]["target_mention"] = "TargetX"
    row.update(evidence_sentence="Knockout of TargetX decreases cell proliferation.",
        subject_canonical_id="TEST:TARGET", object_canonical_id="TEST:ENDPOINT",
        subject_normalization_status="resolved", object_normalization_status="resolved",
        subject_entity_type="gene", object_entity_type="phenotype")
    return row


def project(tmp_path, row, lane="l35_fulltext_l1_claims.jsonl"):
    artifacts = tmp_path / "source/artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / lane).write_text(json.dumps(row) + "\n")
    summary = project_fulltext_run(artifacts.parent, tmp_path / "outputs")
    out = Path(summary["output_run"]) / "artifacts"
    return summary, json.loads((out / "fulltext_projected_observations.jsonl").read_text()), json.loads((out / "evidence_reasoning_chains.jsonl").read_text())


@pytest.mark.parametrize("auth", ["MISSING", None, False, True, 0, 1, "false", "true", [], {}, {"approved": True}])
@pytest.mark.parametrize("human", ["MISSING", False, True])
def test_unverified_authorization_cannot_admit(tmp_path, tempting, auth, human):
    if auth == "MISSING": tempting.pop("scientific_authorization")
    else: tempting["scientific_authorization"] = auth
    if human == "MISSING": tempting.pop("human_gold")
    else: tempting["human_gold"] = human
    tempting["scientific_review"] = {"approved": True, "reviewer": "UNVERIFIED_TEST_ASSERTION", "source_hash": "unbound"}
    summary, row, chain = project(tmp_path, tempting)
    assert summary["strict_core_observations_after"] == 0
    assert not row["formal_core_graph_eligible"] and not row["conflict_eligible"] and not row["hypothesis_eligible"]
    assert row["derived_causal_sign"] is None and chain["derived_relation"] is None
    assert "scientific_authorization" in " ".join(row["core_exclusion_reasons"])


@pytest.mark.parametrize("lane", ["l35_fulltext_l1_claims.jsonl", "l2_fulltext_observations.jsonl"])
@pytest.mark.parametrize("boundary", ["complete", "no_core", "no_application", "no_measurement_result", "no_comparator", "forged_audit", "limited_readiness"])
def test_linkage_or_readiness_cannot_bypass_authorization(tmp_path, tempting, lane, boundary):
    tempting.pop("scientific_authorization")
    core = tempting["ExperimentalCore"]
    if boundary == "no_core": tempting.pop("ExperimentalCore")
    if boundary in {"no_application", "no_measurement_result"}:
        relation = "factor_applies_to_measurement" if boundary == "no_application" else "measurement_produces_result"
        core["linkages"] = [l for l in core["linkages"] if l["relation_type"] != relation]
        core["revision"]["linkage_record_ids"] = [l["linkage_id"] for l in core["linkages"]]
        if boundary == "no_measurement_result":
            core["results"][0]["measurement_ref"] = None
    if boundary == "no_comparator":
        for r in core["results"]: r.update(comparison_factor_refs=[], baseline_ref=None)
        core["linkages"] = [l for l in core["linkages"] if l["relation_type"] not in {"result_compared_against_factor", "result_uses_baseline"}]
        core["revision"]["linkage_record_ids"] = [l["linkage_id"] for l in core["linkages"]]
    if boundary == "forged_audit":
        tempting.pop("ExperimentalCore")
        tempting["experimental_core_handoff_audit"] = {"readiness": {"status": "machine_reusable_candidate"}, "linkage": {"full_machine_reuse_linkage": "complete"}}
    if boundary == "no_measurement_result":
        with pytest.raises(ValueError, match="experimental_core_invalid_references"):
            project(tmp_path, tempting, lane)
        return
    summary, row, _ = project(tmp_path, tempting, lane)
    assert summary["strict_core_observations_after"] == 0
    assert not row["formal_core_graph_eligible"]
    if boundary in {"no_core", "forged_audit"}:
        assert "experimental_core_handoff_audit" not in row
        assert "experimental_core_audit_missing" in row["core_exclusion_reasons"]
    if boundary in {"complete", "limited_readiness"}:
        assert row["experimental_core_handoff_audit"]["readiness"]["status"] == "machine_reusable_with_method_limitations"
        assert "experimental_core_readiness_not_complete" in row["core_exclusion_reasons"]
    if boundary == "no_application":
        assert "blocked_missing_factor_application" in row["core_exclusion_reasons"]
    if boundary == "no_comparator":
        assert row["experimental_core_handoff_audit"]["linkage"]["comparative_reference_linkage"] == "unresolved"


@pytest.mark.parametrize("direction,kind,count", [("negative","knockout",1),("positive","knockout",1),("negative","drug_treatment",1),("negative","knockout",2)])
@pytest.mark.parametrize("provenance", [None,"injected_inconsistent_causal_direction"])
def test_observed_outcome_never_implies_authorized_causal_sign(tmp_path, tempting, direction, kind, count, provenance):
    tempting.pop("scientific_authorization")
    formal = tempting["ExperimentalObservationV3"]
    formal["candidate_relation"]["lexical_direction"] = direction
    # Use an existing intervention enum, no scientific category extension.
    formal["interventions"][0]["intervention_type"] = kind
    if count == 2:
        formal["interventions"].append(copy.deepcopy(formal["interventions"][0]))
        formal["interventions"][1]["intervention_id"] = "TEST_SECOND_INTERVENTION"
    tempting["causal_direction_provenance"] = provenance
    tempting["derived_causal_sign"] = 1
    _, row, chain = project(tmp_path, tempting)
    assert row["direction"] == direction and row["observed_outcome_sign"] == (-1 if direction == "negative" else 1)
    assert row["derived_causal_sign"] is None and chain["derived_relation"] is None
    assert not row["formal_core_graph_eligible"]


def test_direct_core_gate_does_not_trust_native_flags_or_supplied_semantics(tempting):
    tempting.pop("scientific_authorization")
    row = prepare_experimental_handoff(tempting, Path("source"))
    row["evidence_semantics"] = {
        "derived_causal_sign": -1, "retained_layer": "strict_causal_core", "endpoint_semantics_eligible": True,
        "relation_semantics_eligible": True, "causal_direction_eligible": True, "direction_provenance_consistent": True,
        "evidence_design_eligible": True, "species_projection_valid": True, "granularity_projection_valid": True,
        "measurement_projection_valid": True, "conflict_eligible": True,
    }
    gate = core_graph_eligibility(row)
    assert not gate["eligible"] and not gate["conflict_eligible"]
    assert "scientific_authorization" in " ".join(gate["reasons"])


def test_unknown_measurement_cannot_use_legacy_keyword_fallback(tmp_path, tempting):
    formal = tempting["ExperimentalObservationV3"]
    formal["measurement"].update(measurement_dimension="unknown", normalization_status="reviewable_unknown")
    _, row, chain = project(tmp_path, tempting)
    assert row["measurement_dimension"] == "unknown" and chain["measurement_dimension"] is None
    assert row["derived_causal_sign"] is None and not row["formal_core_graph_eligible"]


def test_native_marker_without_formal_payload_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="native_experimental_payload_missing"):
        project(tmp_path, {"adapter_mode": "formal_v3_native", "claim_id": "TEST_ONLY"})


@pytest.mark.parametrize("container", ["ExperimentalObservationV3", "fulltext_l1_v2_observation", "formal_v3_native_payload"])
def test_existing_native_container_shapes_have_the_same_boundary(tmp_path, tempting, container):
    formal = tempting.pop("ExperimentalObservationV3")
    tempting[container] = formal
    tempting.pop("scientific_authorization")
    _, row, _ = project(tmp_path, tempting, "l2_fulltext_observations.jsonl")
    assert not row["formal_core_graph_eligible"] and row["derived_causal_sign"] is None


def test_native_admission_checks_do_not_reclassify_legacy_v2():
    assert experimental_admission_blocks({"schema_version": "fulltext_l1_experimental_observation_schema_v2",
        "fulltext_l1_v2_observation": {"schema_version": "fulltext_l1_experimental_observation_schema_v2"}}) == []
