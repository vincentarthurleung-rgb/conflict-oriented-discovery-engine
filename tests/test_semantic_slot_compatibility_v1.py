"""Generic offline regressions for alpha2.2 semantic-slot separation."""

from copy import deepcopy

import pytest

from code_engine.search.semantic_slot_compatibility_v1 import (
    SemanticSlotCompatibilityError, audit_linked_relation_candidate,
    search_anchor_compatibility_v1_1, semantic_slot_compatibility,
    validate_v2_structure_and_slots,
)


TARGET = {
    "artifact_schema_version": "ScientificPropositionTargetV1",
    "subject": "TNF-alpha", "object": "ERK1/2", "relation_family": "increases",
    "canonical_relation_family": "increases",
    "measurement_property_endpoint": "phosphorylation",
    "required_evidence_mode": "current-study perturbational evidence linking intervention to endpoint",
    "context_qualifier_dimensions": {"biological_unit": "macrophage"},
}


def test_exact_relation_semantic_match_needs_no_entity_alias_table():
    row = semantic_slot_compatibility("relation", "increases", TARGET)
    assert row["state"] == "EXACT_SEMANTIC_MATCH"
    assert row["canonical_identity_promoted"] is False


def test_direction_opposite_is_incompatible():
    row = semantic_slot_compatibility("direction", "DECREASE", TARGET)
    assert row["state"] == "INCOMPATIBLE"


def test_endpoint_exact_match():
    assert semantic_slot_compatibility("endpoint_property", "phosphorylation", TARGET)["state"] == "EXACT_SEMANTIC_MATCH"


def test_dynamic_flux_not_generic_autophagy():
    target = {**TARGET, "measurement_property_endpoint": "autophagic flux"}
    assert semantic_slot_compatibility("endpoint_property", "autophagy", target)["state"] not in {
        "EXACT_SEMANTIC_MATCH", "AUTHORIZED_SEMANTIC_VARIANT"}


def test_short_entity_not_promoted_by_semantic_slot():
    with pytest.raises(SemanticSlotCompatibilityError):
        semantic_slot_compatibility("subject", "TNF", TARGET)
    assert not search_anchor_compatibility_v1_1("TNF", TARGET, "subject")["sufficient_for_search_anchor"]


def test_unrelated_biological_unit_not_promoted():
    row = search_anchor_compatibility_v1_1("monocyte", TARGET, "biological_unit")
    assert row["sufficient_for_search_anchor"] is False
    assert row["canonical_identity_promoted"] is False


def test_evidence_mode_exact_without_entity_registry():
    value = TARGET["required_evidence_mode"]
    assert semantic_slot_compatibility("evidence_mode", value, TARGET)["state"] == "EXACT_SEMANTIC_MATCH"


def test_evidence_mode_core_retains_mode_but_not_scientific_truth():
    target = {**TARGET, "required_evidence_mode": "current-study perturbational evidence linking A to B"}
    row = semantic_slot_compatibility("evidence_mode", "current-study perturbational evidence", target)
    assert row["state"] == "AUTHORIZED_SEMANTIC_VARIANT"
    assert row["scientific_truth_established"] is False


def test_semantic_slots_cannot_use_entity_anchor_lookup():
    with pytest.raises(SemanticSlotCompatibilityError):
        search_anchor_compatibility_v1_1("increases", TARGET, "relation")


def test_full_entity_anchor_allowed_inside_composite_search_surface_only():
    row = search_anchor_compatibility_v1_1("TNF-alpha stimulation", TARGET, "subject")
    assert row["sufficient_for_search_anchor"] is True
    assert row["canonical_identity_promoted"] is False
    assert not search_anchor_compatibility_v1_1("TNF stimulation", TARGET, "subject")["sufficient_for_search_anchor"]
