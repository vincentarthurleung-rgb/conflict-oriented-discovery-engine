"""Actual Pilot cache replay and negative graph-handoff binding cases."""
import copy

import pytest

from tests.test_builder_quality_bridge import inputs, offline
from code_engine.construction.builder_quality_bridge import project_quality_accepted_builder_claims
from code_engine.construction.builder_quality_bridge_v2 import normalize_reviewable_builder_claims
from code_engine.evidence_graph.builders import normalize_observation_to_evidence_edge
from code_engine.evidence_graph.bundle_builder import build_relation_evidence_bundles


def test_actual_relations_reach_native_graph_field_without_authority(inputs):
    claims = project_quality_accepted_builder_claims(**inputs)["claims"]
    before = copy.deepcopy(claims)
    normalized = normalize_reviewable_builder_claims(claims)
    assert claims == before
    assert [r["formal_relation"] for r in normalized] == ["decreases", None, "increases"]
    edges = [normalize_observation_to_evidence_edge(r, {}, {"run_id": "TEST_ONLY", "topic_id": None, "query_id": None}) for r in normalized]
    assert [e.relation_family for e in edges] == ["decreases", "unknown", "increases"]
    assert build_relation_evidence_bundles(edges) == []
    assert all(e.claim_id and e.observation_id is None and not e.canonical_graph_eligible for e in edges)


@pytest.mark.parametrize("field,value,error", [
    ("subject_raw", "CHANGED", "CLAIM_PROJECTION_MISMATCH"),
    ("neutral_proposition", "CHANGED", "CLAIM_PROJECTION_MISMATCH"),
    ("paper_id", "TEST_ONLY:wrong", "CLAIM_SOURCE_BINDING_MISMATCH"),
    ("candidate_id", "TEST_ONLY:wrong", "CLAIM_ID_BINDING_MISMATCH"),
    ("evidence_quote", "CHANGED", "CLAIM_EVIDENCE_BINDING_MISMATCH"),
])
def test_changed_projection_rejected(inputs, field, value, error):
    claims = project_quality_accepted_builder_claims(**inputs)["claims"]
    claims[0][field] = value
    with pytest.raises(ValueError, match=error):
        normalize_reviewable_builder_claims(claims)


def test_bad_offsets_and_context_rejected(inputs):
    claims = project_quality_accepted_builder_claims(**inputs)["claims"]
    changed = copy.deepcopy(claims); changed[0]["evidence_span"]["end_offset"] += 1
    with pytest.raises(ValueError, match="CLAIM_OFFSET_BINDING_MISMATCH"):
        normalize_reviewable_builder_claims(changed)
    changed = copy.deepcopy(claims); changed[0]["context"]["species"] = "CHANGED"
    with pytest.raises(ValueError, match="CLAIM_CONTEXT_BINDING_MISMATCH"):
        normalize_reviewable_builder_claims(changed)


def test_exact_duplicate_identity_keeps_one_source_claim(inputs):
    claims = project_quality_accepted_builder_claims(**inputs)["claims"]
    assert len(normalize_reviewable_builder_claims(claims + copy.deepcopy(claims))) == 3
