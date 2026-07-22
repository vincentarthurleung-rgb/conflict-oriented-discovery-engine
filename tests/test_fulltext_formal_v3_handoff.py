import json
from pathlib import Path

import pytest

from code_engine.fulltext.projection_handoff import ProjectionHandoffError, stage_projection_handoff
from code_engine.fulltext.reentry import _fulltext_record_from_claim


def test_formal_v3_adapter_preserves_group_and_provenance():
    formal = {
        "schema_version": "fulltext_l1_experimental_observation_schema_v3",
        "observation_id": "o1", "normalization_status": "reviewable", "review_reasons": ["mixed"],
        "provenance": {"pmid": "1", "pmcid": "PMC1", "source_document_id": "PMC1", "parent_block_id": "b0", "child_block_id": "b1", "evidence_spans": [{"evidence_span_id": "s1", "anchor_id": "b1:S1", "text": "evidence"}]},
        "experiment": {"experiment_id": "e1", "evidence_family_id": "f1", "design_type": "in_vitro", "species_raw": "human", "comparison_arm_raw": "combo", "control_arm_raw": "vehicle"},
        "interventions": [
            {"intervention_id": "i1", "role": "primary", "intervention_type": "knockdown", "target_mention": "A", "intervention_sign": "negative"},
            {"intervention_id": "i2", "role": "co_intervention", "intervention_type": "drug", "agent_mention": "B", "dose_raw": "1 uM"},
        ],
        "combination_mode": "joint", "measurement": {"measurement_dimension": "activity", "measured_entity_mention": "C"},
        "observation": {"observed_result": "decreased", "comparison_raw": "versus vehicle"},
        "candidate_relation": {"subject_mention": "A+B", "object_mention": "C", "relation_raw": "decreased", "lexical_direction": "negative", "evidence_design_raw": "controlled perturbation"},
        "eligibility": {"strict_core_eligible": False, "graph_eligible": True}, "extraction_warnings": ["review"],
    }
    claim = {"schema_version": formal["schema_version"], "claim_id": "o1", "fulltext_l1_v2_observation": formal, "intervention_target": "WRONG"}
    row = _fulltext_record_from_claim(claim, Path("source"))
    assert row["adapter_mode"] == "formal_v3_native"
    assert len(row["interventions"]) == 2
    assert [x["role"] for x in row["interventions"]] == ["primary", "co_intervention"]
    assert row["combination_mode"] == "joint"
    assert row["measurement_dimension"] == "activity"
    assert row["evidence_design"] == "controlled perturbation"
    assert row["evidence_anchor_ids"] == ["b1:S1"]
    assert row["source_block_id"] == "b1" and row["experiment_id"] == "e1"
    assert row["normalization_status"] == "reviewable"
    assert row["formal_v3_eligibility"]["strict_core_eligible"] is False


def test_legacy_adapter_is_explicit():
    row = _fulltext_record_from_claim({"schema_version": "fulltext_l1_claim_v2", "claim_id": "c", "subject": "A", "object": "B"}, Path("source"))
    assert row["adapter_mode"] == "legacy_compatibility"


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value) + "\n")


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text("".join(json.dumps(x) + "\n" for x in rows))


def test_projection_handoff_uses_projected_core_and_never_activates(tmp_path):
    fulltext, reentry, projection, base = [tmp_path / x for x in ("fulltext", "reentry", "projection", "base")]
    formal = {"schema_version": "fulltext_l1_experimental_observation_schema_v3", "observation_id": "o", "provenance": {"evidence_spans": [{"anchor_id": "b:S"}]}, "experiment": {"experiment_id": "e"}, "interventions": [], "measurement": {}, "observation": {}, "candidate_relation": {}, "eligibility": {}}
    _write_jsonl(fulltext / "artifacts/l35_fulltext_l1_claims.jsonl", [{"schema_version": formal["schema_version"], "claim_id": "o", "fulltext_l1_v2_observation": formal}])
    _write_json(fulltext / "artifacts/fulltext_l1_v2_summary.json", {"scientific_input_complete": False, "partial_block_failures": True, "consistency_report": {"publication_allowed": False}})
    _write_json(reentry / "artifacts/fulltext_reentry_summary.json", {"normalized_fulltext_claim_count": 1})
    for name, rows in (("fulltext_seed_neighborhood_observations.jsonl", [{"claim_id": "ctx", "exploratory_graph_eligible": True}]), ("fulltext_reviewable_relations.jsonl", []), ("fulltext_off_seed_relations.jsonl", [])):
        _write_jsonl(reentry / "artifacts" / name, rows)
    core = {"claim_id": "o", "formal_core_graph_eligible": True, "subject_canonical_id": "EntrezGene:10920", "object_canonical_id": "GO:0001837", "final_formal_polarity": "positive"}
    edge = {"canonical_edge_id": "ce", "subject_canonical_id": "EntrezGene:10920", "object_canonical_id": "GO:0001837", "polarity": "positive"}
    _write_json(projection / "projection_manifest.json", {"status": "completed", "api_used": False, "network_used": False, "content_identity": "x"})
    _write_jsonl(projection / "artifacts/fulltext_projected_observations.jsonl", [core])
    _write_jsonl(projection / "artifacts/canonical_edge_evidence_families.jsonl", [edge])
    _write_json(projection / "artifacts/fulltext_l2_readjudication_summary.json", {"schema_version": "fulltext_l2_readjudication_summary_v1"})
    _write_json(projection / "artifacts/fulltext_core_projection_summary.json", {"schema_version": "fulltext_core_projection_summary_v1", "formal_core_observation_count": 1, "canonical_edge_count": 1, "safety_violations": {}})
    _write_jsonl(base / "artifacts/l2_graph_observations.jsonl", [{"observation_id": "prior"}])
    result = stage_projection_handoff(fulltext_run=fulltext, reentry_run=reentry, projection_run=projection, base_abstract_run=base, output_root=tmp_path / "out")
    assert result["formal_core_observation_count"] == 1 and result["staging_canonical_edge_count"] == 1
    assert result["staging_contains_cops8_emt"] is True
    assert result["atlas_activated"] is False and result["active_projection_unchanged"] is True
    assert result["publication_allowed"] is False


def test_projection_handoff_missing_projection_fails_closed(tmp_path):
    with pytest.raises(ProjectionHandoffError):
        stage_projection_handoff(fulltext_run=tmp_path / "f", reentry_run=tmp_path / "r", projection_run=tmp_path / "p")
