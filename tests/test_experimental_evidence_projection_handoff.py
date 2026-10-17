"""Actual frozen draft integration and generic fail-closed handoff regressions."""
import copy
import json
from pathlib import Path

import pytest

from code_engine.fulltext.evidence_projection import project_fulltext_run
from code_engine.fulltext.experimental_projection_handoff import prepare_experimental_handoff

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "runs/20261014_code_first_source_grounded_figure1c_experimental_record_offline/record.json"


@pytest.fixture
def draft():
    return json.loads(FROZEN.read_text())


def project(tmp_path, draft):
    source = tmp_path / "input"
    artifacts = source / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "l35_fulltext_l1_claims.jsonl").write_text(json.dumps(draft) + "\n")
    summary = project_fulltext_run(source, tmp_path / "outputs")
    out = Path(summary["output_run"]) / "artifacts"
    row = json.loads((out / "fulltext_projected_observations.jsonl").read_text())
    chain = json.loads((out / "evidence_reasoning_chains.jsonl").read_text())
    return summary, row, chain


def test_frozen_experiment_is_consumed_without_scientific_promotion(tmp_path, draft):
    before = copy.deepcopy(draft)
    summary, row, chain = project(tmp_path, draft)
    formal, core = draft["ExperimentalObservationV3"], draft["ExperimentalCore"]
    assert row["experimental_core"] == core
    assert chain["experiment_id"] == formal["experiment"]["experiment_id"]
    assert chain["evidence_family_id"] == formal["experiment"]["evidence_family_id"]
    assert chain["experimental_design"] == formal["experiment"]
    assert chain["interventions"] == formal["interventions"]
    assert chain["comparison_arm"] == [
        {"role": key, "description": formal["experiment"][key]}
        for key in ("comparison_arm_raw", "control_arm_raw")]
    assert chain["experimental_factors"] == core["factors"]
    assert chain["measurements"] == core["measurements"]
    assert chain["observed_results"] == core["results"]
    assert chain["experimental_linkages"] == core["linkages"]
    assert chain["provenance"] == formal["provenance"]["evidence_spans"]
    projection = chain["experimental_core_projection"]
    assert projection["lossless_by_reference"] and not projection["summary_is_authoritative"]
    assert projection["linkage_refs"] == core["revision"]["linkage_record_ids"]
    audit = row["experimental_core_handoff_audit"]
    assert audit["structural_integrity"] == "structurally_complete"
    assert audit["linkage"]["full_machine_reuse_linkage"] == "complete"
    assert audit["readiness"]["status"] == "machine_reusable_with_method_limitations"
    assert row["direction"] == chain["lexical_direction"] == "negative"
    assert row["observed_outcome_sign"] == chain["observed_outcome_sign"] == -1
    assert chain["observed_direction_provenance"]["evidence_span_ids"] == formal["observation"]["evidence_span_ids"]
    assert chain["observed_direction_provenance"]["causal_authority"] is False
    assert row["relation_raw"] == row["formal_relation"] == "observed_decrease_after"
    assert row["measurement_dimension"] == "unknown" and chain["measurement_dimension"] is None
    assert row["derived_causal_sign"] is chain["derived_causal_sign"] is None
    assert chain["derived_relation"] is None and chain["direction_provenance"] == "unresolved"
    assert row["final_formal_polarity"] == "unknown"
    assert not chain["chain_complete"]
    assert row["primary_layer"] == "intervention_observation"
    assert not row["formal_core_graph_eligible"] and not row["conflict_eligible"] and not row["hypothesis_eligible"]
    assert not row["scientific_authorization"] and not row["human_gold"]
    assert row["annotation_class"] == draft["annotation_class"]
    assert not row["subject_canonical_id"] and not row["object_canonical_id"]
    assert "experimental_design_not_authorized_for_causal_projection" in row["core_gate"]["reasons"]
    assert "non_causal_evidence_design" not in row["core_gate"]["reasons"]
    assert summary["strict_core_observations_after"] == summary["unique_canonical_edges_after"] == 0
    assert summary["evidence_records_after"] == summary["reviewable_evidence_after"] == 1
    assert draft == before


@pytest.mark.parametrize("native", ["bare", "claim"])
def test_native_v3_without_core_does_not_require_a_legacy_chain(tmp_path, draft, native):
    formal = draft["ExperimentalObservationV3"]
    record = formal if native == "bare" else {
        "schema_version": formal["schema_version"], "claim_id": formal["observation_id"],
        "fulltext_l1_v2_observation": formal}
    _, row, chain = project(tmp_path, record)
    assert chain["interventions"] == formal["interventions"]
    assert chain["measurements"] == [formal["measurement"]]
    assert chain["observed_results"] == [formal["observation"]]
    assert not row["formal_core_graph_eligible"]


@pytest.mark.parametrize("mutation", ["dangling", "wrong_type", "cross_observation", "wrong_source", "missing_component", "evidence", "duplicate"])
def test_invalid_core_handoff_fails_closed(draft, mutation):
    core = draft["ExperimentalCore"]
    if mutation == "dangling": core["linkages"][0]["target_ref"] = "missing"
    if mutation == "wrong_type": core["linkages"][0]["target_ref"] = core["results"][0]["observed_result_id"]
    if mutation == "cross_observation": core["measurements"][0]["observation_revision_identity"] = "other"
    if mutation == "wrong_source": core["revision"]["source_observation_identity"] = "other"
    if mutation == "missing_component": core["measurements"].clear()
    if mutation == "evidence": core["results"][0]["evidence_anchor_ids"] = ["fabricated"]
    if mutation == "duplicate": core["factors"].append(copy.deepcopy(core["factors"][0]))
    with pytest.raises(ValueError):
        prepare_experimental_handoff(draft, Path("source"))


def test_missing_factor_application_is_not_reconstructed(tmp_path, draft):
    core = draft["ExperimentalCore"]
    core["linkages"] = [l for l in core["linkages"] if l["relation_type"] != "factor_applies_to_measurement"]
    core["revision"]["linkage_record_ids"] = [l["linkage_id"] for l in core["linkages"]]
    _, row, chain = project(tmp_path, draft)
    assert row["experimental_core_handoff_audit"]["linkage"]["full_machine_reuse_linkage"] == "blocked_missing_factor_application"
    assert "blocked_missing_factor_application" in row["core_gate"]["reasons"]
    assert chain["experimental_linkages"] == core["linkages"]
    assert not row["formal_core_graph_eligible"]


def test_no_lexical_or_scalar_fields_can_promote_a_native_draft(tmp_path, draft):
    draft.update(direction="positive", direct_relation_sign=1, derived_causal_sign=1,
        causal_direction_provenance="injected", conflict_eligible=True, hypothesis_eligible=True)
    # A tempting legacy sentence must not trigger knockout sign inversion.
    draft["evidence_sentence"] = "Knockout of Ar decreases CSA."
    _, row, chain = project(tmp_path, draft)
    assert row["direction"] == "negative" and row["derived_causal_sign"] is None
    assert not row["formal_core_graph_eligible"] and chain["derived_relation"] is None


def test_content_changed_under_same_observation_id_creates_new_projection(tmp_path, draft):
    first, _, _ = project(tmp_path, draft)
    repeated, _, _ = project(tmp_path, draft)
    assert repeated["reused_completed_projection"]
    draft["context"]["measurement_quantification_method"] = "UNRESOLVED_REVIEW_NOTE"
    changed, _, _ = project(tmp_path, draft)
    assert changed["output_run"] != first["output_run"]


def test_another_endpoint_and_multiple_interventions_remain_lossless(tmp_path, draft):
    # Generic data transport, with no approved classification or canonical ID.
    formal = draft["ExperimentalObservationV3"]
    draft.pop("ExperimentalCore")
    formal["candidate_relation"].update(subject_mention="other target", object_mention="other tissue area")
    formal["measurement"].update(measurement_dimension_raw="other tissue area", endpoint_raw="other tissue area")
    formal["interventions"].append(copy.deepcopy(formal["interventions"][0]))
    formal["interventions"][1].update(intervention_id="second", target_mention="second target")
    _, row, chain = project(tmp_path, draft)
    assert len(chain["interventions"]) == 2 and row["intervention_target"] is None
    assert chain["measurements"][0]["endpoint_raw"] == "other tissue area"
    assert row["subject_raw"] == "other target" and row["object_raw"] == "other tissue area"
    assert row["derived_causal_sign"] is None and not row["formal_core_graph_eligible"]
