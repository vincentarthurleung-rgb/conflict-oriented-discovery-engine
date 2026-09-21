from copy import deepcopy

import pytest

from code_engine.search.planner_v3_contract import (
    PLANNER_PROPOSAL_PAYLOAD_V3_SCHEMA, PlannerV3ContractError,
    allocate_artifact_id_v1, compile_validated_planner_v3,
    deterministic_target_role_frame_v1, intent_semantic_transform_v1,
    planner_role_rehydrate_v1, semantic_surface_containment_v2,
    static_provider_schema_preflight, validate_planner_proposal_v3,
)


def target():
    return {
        "artifact_schema_version": "ScientificPropositionTargetV1",
        "scientific_proposition_target_id": "fixture:target:v1",
        "subject": "IL-10", "canonical_subject": "IL-10",
        "subject_intervention": "IL-10 perturbation",
        "relation_family": "decreases / suppresses",
        "canonical_relation_family": "decreases / suppresses",
        "canonical_proposition_orientation": "increased IL-10 function -> decreased LPS-induced TNF-alpha",
        "object": "TNF-alpha", "measurement_target": "TNF-alpha",
        "measurement_property_endpoint": "secretion / extracellular release",
        "required_evidence_mode": "current-study perturbational evidence",
        "acceptable_endpoint_evidence": ["extracellular TNF-alpha secretion"],
        "context_qualifier_dimensions": {
            "biological_unit": ["macrophage"], "treatment_context": ["LPS stimulation"],
        },
        "therapy": None,
    }


def payload(intent_type="DIRECT_PERTURBATION", direction="DECREASE"):
    return {"retrieval_intents": [{
        "intent_type": intent_type,
        "retrieval_rationale": "retrieve actor-to-response evidence",
        "linked_relation_proposals": [{
            "subject_surface": "IL-10", "subject_action_surface": "IL-10 perturbation",
            "relation_surface": "decreases", "direction": direction,
            "response_surface": "TNF-alpha", "endpoint_property_surface": "secretion",
            "linked_relation_phrase": "IL-10 decreases LPS-induced TNF-alpha secretion in macrophage",
            "biological_unit_surface": "macrophage",
            "conditioning_treatment_surface": "LPS stimulation",
            "therapy_surface": None, "disease_surface": None, "genotype_surface": None,
            "evidence_mode_surface": None, "planner_rationale": "direct linked language",
        }],
        "search_concept_proposals": [{
            "semantic_role": "PRIMARY_INTERVENTION", "proposed_terms": ["IL-10"],
        }],
    }]}


def test_provider_surface_has_no_ids_refs_authority_or_applicability():
    fields = set()
    def walk(node):
        if isinstance(node, dict):
            fields.update(node.get("properties", {}))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
    walk(PLANNER_PROPOSAL_PAYLOAD_V3_SCHEMA)
    assert not any(name.endswith("_id") or name.endswith("_ref") or name.endswith("_refs") for name in fields)
    assert not fields & {"authority", "applicability", "canonical_target"}
    assert static_provider_schema_preflight()["passed"]


def test_provider_cannot_add_deterministic_fields():
    broken = payload()
    broken["retrieval_intents"][0]["intent_id"] = "model-id"
    with pytest.raises(PlannerV3ContractError):
        validate_planner_proposal_v3(broken)


def test_provider_cannot_generate_canonical_refs():
    broken = payload()
    broken["retrieval_intents"][0]["linked_relation_proposals"][0]["therapy_ref"] = "x"
    with pytest.raises(PlannerV3ContractError):
        validate_planner_proposal_v3(broken)


def test_provider_cannot_assign_authority():
    broken = payload()
    broken["retrieval_intents"][0]["authority"] = "CANONICAL"
    with pytest.raises(PlannerV3ContractError):
        validate_planner_proposal_v3(broken)


def test_provider_cannot_assign_applicability():
    broken = payload()
    broken["retrieval_intents"][0]["applicability"] = "APPLICABLE"
    with pytest.raises(PlannerV3ContractError):
        validate_planner_proposal_v3(broken)


def test_role_frame_distinguishes_primary_conditioning_and_therapy():
    frame = deterministic_target_role_frame_v1(target())
    assert frame["role_surfaces"]["PRIMARY_INTERVENTION"] == ["IL-10"]
    assert frame["role_surfaces"]["CONDITIONING_TREATMENT"] == ["LPS stimulation"]
    assert frame["role_surfaces"]["THERAPY"] == []
    assert frame["conditioning_treatment_applicability"] == "REQUIRED"


def test_allocator_is_stable_and_surface_sensitive():
    kwargs = dict(target_sha256="a" * 64, intent_index=0, intent_type="DIRECT_PERTURBATION",
                  semantic_role="INTENT", normalized_surface="IL-10")
    assert allocate_artifact_id_v1(**kwargs) == allocate_artifact_id_v1(**kwargs)
    assert allocate_artifact_id_v1(**kwargs) != allocate_artifact_id_v1(**{**kwargs, "normalized_surface": "TNF"})


@pytest.mark.parametrize(("intent_type", "direction"), [
    ("DIRECT_PERTURBATION", "DECREASE"),
    ("INVERSE_PERTURBATION", "INCREASE"),
    ("NECESSITY", "REQUIRE"),
    ("RESCUE", "RESCUE"),
])
def test_intent_semantics_are_transformed(intent_type, direction):
    expected = intent_semantic_transform_v1(target(), intent_type)
    assert direction in expected["allowed_directions"]
    assert expected["response_target_preserved"]


def test_therapy_intent_requires_therapy_role():
    therapy_target = target()
    therapy_target["therapy"] = "trametinib"
    therapy_target["context_qualifier_dimensions"]["therapy"] = ["trametinib"]
    expected = intent_semantic_transform_v1(therapy_target, "THERAPY_SENSITIZATION")
    assert expected["therapy_required"]


def test_nested_conditioning_role_is_mandatory():
    broken = payload()
    broken["retrieval_intents"][0]["linked_relation_proposals"][0]["conditioning_treatment_surface"] = None
    result = planner_role_rehydrate_v1(broken, target=target())
    assert not result["has_structurally_bound_relation"]


def test_evidence_mode_is_not_required_from_model():
    proposal = payload()
    assert proposal["retrieval_intents"][0]["linked_relation_proposals"][0]["evidence_mode_surface"] is None
    validated = planner_role_rehydrate_v1(proposal, target=target())
    assert validated["has_structurally_bound_relation"]
    assert validated["intents"][0]["expected_retrieval_semantics"]["evidence_mode_injected_deterministically"]


def test_multi_alias_containment_is_role_wise():
    result = semantic_surface_containment_v2(
        "increased PGE2 secretion", "PGE2 / prostaglandin E2", ["PGE2 / prostaglandin E2"])
    assert result["state"] == "CONTAINED"
    assert not result["whole_multi_alias_string_required"]


def test_endpoint_semantics_still_mandatory():
    broken = payload()
    link = broken["retrieval_intents"][0]["linked_relation_proposals"][0]
    link["endpoint_property_surface"] = "transcript abundance"
    link["linked_relation_phrase"] = "IL-10 decreases LPS-induced TNF-alpha transcript abundance in macrophage"
    result = planner_role_rehydrate_v1(broken, target=target())
    assert not result["has_structurally_bound_relation"]


def test_rehydrator_never_promotes_identity_and_ids_are_not_cross_intent_inputs():
    result = planner_role_rehydrate_v1(payload(), target=target())
    assert result["canonical_identity_promotions"] == 0
    assert result["model_generated_opaque_id_count"] == 0


def test_cross_intent_model_id_consistency_is_not_a_contract():
    proposal = payload()
    inverse = deepcopy(proposal["retrieval_intents"][0])
    inverse["intent_type"] = "INVERSE_PERTURBATION"
    inverse["linked_relation_proposals"][0]["direction"] = "INCREASE"
    inverse["linked_relation_proposals"][0]["relation_surface"] = "increases"
    proposal["retrieval_intents"].append(inverse)
    validate_planner_proposal_v3(proposal, allowed_intent_types=[
        "DIRECT_PERTURBATION", "INVERSE_PERTURBATION"])
    assert not any(key.endswith("_id") for key in proposal["retrieval_intents"][0])


def test_compiler_boundary_rejects_raw_and_accepts_validated():
    with pytest.raises(PlannerV3ContractError):
        compile_validated_planner_v3(payload())
    validated = planner_role_rehydrate_v1(payload(), target=target())
    compiled = compile_validated_planner_v3(validated)
    assert compiled["compiled_query_count"] == 1
    assert compiled["compiler_accepts_raw_planner_v3"] is False
    assert compiled["compiler_accepts_validated_planner_v3"] is True


def test_no_case_specific_production_keys_or_openai_fallback():
    assert "heldout_v2_" not in repr(PLANNER_PROPOSAL_PAYLOAD_V3_SCHEMA)
    preflight = static_provider_schema_preflight()
    assert preflight["passed"]
    assert "openai" not in repr(PLANNER_PROPOSAL_PAYLOAD_V3_SCHEMA).casefold()


def test_openai_fallback_is_absent_from_provider_contract():
    assert "fallback" not in repr(PLANNER_PROPOSAL_PAYLOAD_V3_SCHEMA).casefold()


def test_request_applicable_intent_enum_is_enforced():
    with pytest.raises(PlannerV3ContractError):
        validate_planner_proposal_v3(payload(), allowed_intent_types=["RESCUE"])
