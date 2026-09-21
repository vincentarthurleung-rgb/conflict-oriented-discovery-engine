from copy import deepcopy

from code_engine.search.compositional_relation_semantics_v1 import (
    RELATION_INTERNAL_ROLE_MATRIX, assess_relation_binding_v3,
    composite_biological_unit_compatibility_v1, direction_composition_v1,
    final_query_coverage_v1, rehydrate_and_compile_alpha3_2,
    semantic_surface_containment_v3,
)
from code_engine.search.planner_v3_contract import intent_semantic_transform_v1


def therapy_target():
    return {
        "artifact_schema_version": "ScientificPropositionTargetV1",
        "scientific_proposition_target_id": "fixture:therapy:v1",
        "subject": "PARP1", "canonical_subject": "PARP1",
        "subject_intervention": "PARP1 inhibition or loss",
        "relation_family": "inhibition increases sensitivity / sensitizes",
        "canonical_relation_family": "inhibition increases sensitivity / sensitizes",
        "canonical_proposition_orientation": "reduced PARP1 function -> increased temozolomide sensitivity",
        "object": "temozolomide treatment response",
        "measurement_target": "temozolomide treatment response",
        "measurement_property_endpoint": "increased sensitivity / decreased resistance",
        "required_evidence_mode": "current-study functional evidence linking PARP1 inhibition or loss to increased temozolomide response",
        "acceptable_endpoint_evidence": ["PARP1 depletion increasing temozolomide sensitivity"],
        "context_qualifier_dimensions": {
            "biological_unit": ["glioblastoma cell / explicitly compatible glioblastoma model"],
            "disease_context": ["glioblastoma"], "therapy": ["temozolomide"],
        },
        "therapy": "temozolomide",
    }


def therapy_link(direction="INCREASE"):
    return {
        "subject_surface": "PARP1 depletion", "subject_action_surface": "increases",
        "relation_surface": "sensitivity to", "direction": direction,
        "response_surface": "temozolomide", "endpoint_property_surface": "sensitivity",
        "linked_relation_phrase": "PARP1 depletion increases temozolomide sensitivity in glioblastoma cells",
        "biological_unit_surface": "glioblastoma cells", "conditioning_treatment_surface": None,
        "therapy_surface": "temozolomide", "disease_surface": "glioblastoma",
        "genotype_surface": None, "evidence_mode_surface": None,
        "planner_rationale": "fixture",
    }


def payload(link=None):
    return {"retrieval_intents": [{
        "intent_type": "DIRECT_PERTURBATION", "retrieval_rationale": "fixture",
        "linked_relation_proposals": [link or therapy_link()],
        "search_concept_proposals": [{"semantic_role": "PRIMARY_INTERVENTION",
                                      "proposed_terms": ["PARP1"]}],
    }]}


def nested_target():
    value = therapy_target()
    value.update({
        "scientific_proposition_target_id": "fixture:nested:v1",
        "subject": "IL-10", "canonical_subject": "IL-10",
        "subject_intervention": "IL-10 perturbation",
        "relation_family": "decreases / suppresses",
        "canonical_relation_family": "decreases / suppresses",
        "canonical_proposition_orientation": "increased IL-10 function -> decreased LPS-induced extracellular TNF-alpha",
        "object": "TNF-alpha", "measurement_target": "TNF-alpha",
        "measurement_property_endpoint": "secretion / extracellular release",
        "acceptable_endpoint_evidence": ["extracellular TNF-alpha secretion"],
        "therapy": None,
        "context_qualifier_dimensions": {"biological_unit": ["macrophage"],
                                         "treatment_context": ["LPS stimulation"]},
    })
    return value


def nested_link():
    value = therapy_link("DECREASE")
    value.update({
        "subject_surface": "IL-10", "subject_action_surface": "suppresses",
        "relation_surface": "suppresses", "response_surface": "TNF-alpha",
        "endpoint_property_surface": "secretion",
        "linked_relation_phrase": "IL-10 suppresses LPS-induced TNF-alpha secretion in macrophages",
        "biological_unit_surface": "macrophages",
        "conditioning_treatment_surface": "LPS stimulation", "therapy_surface": None,
        "disease_surface": None,
    })
    return value


def test_valid_relation_core_required_before_context_externalization():
    broken = therapy_link()
    broken["linked_relation_phrase"] = "PARP1 glioblastoma temozolomide sensitivity"
    binding = assess_relation_binding_v3(link=broken, target=therapy_target(),
                                         intent_type="DIRECT_PERTURBATION")
    assert binding["relation_core"]["state"] == "INVALID"
    assert final_query_coverage_v1(phrase=broken["linked_relation_phrase"], binding=binding)["state"] == "INVALID_RELATION_CORE"


def test_therapy_is_internal_for_therapy_response():
    assert RELATION_INTERNAL_ROLE_MATRIX["THERAPY"].startswith("INTERNAL")
    broken = therapy_link()
    broken["linked_relation_phrase"] = "PARP1 depletion increases sensitivity in glioblastoma cells"
    assert assess_relation_binding_v3(link=broken, target=therapy_target(),
                                      intent_type="DIRECT_PERTURBATION")["state"] == "UNDERREPRESENTED"


def test_nested_conditioning_and_endpoint_are_internal():
    assert RELATION_INTERNAL_ROLE_MATRIX["CONDITIONING_TREATMENT"].startswith("INTERNAL")
    assert RELATION_INTERNAL_ROLE_MATRIX["RESPONSE_PROPERTY"] == "INTERNAL"
    broken = nested_link()
    broken["linked_relation_phrase"] = "IL-10 suppresses TNF-alpha secretion in macrophages"
    assert assess_relation_binding_v3(link=broken, target=nested_target(),
                                      intent_type="DIRECT_PERTURBATION")["state"] == "UNDERREPRESENTED"
    broken = nested_link()
    broken["linked_relation_phrase"] = "IL-10 suppresses LPS-induced TNF-alpha in macrophages"
    assert assess_relation_binding_v3(link=broken, target=nested_target(),
                                      intent_type="DIRECT_PERTURBATION")["state"] == "UNDERREPRESENTED"


def test_biological_unit_can_be_external_after_valid_core():
    link = therapy_link()
    link["linked_relation_phrase"] = "PARP1 depletion increases temozolomide sensitivity"
    binding = assess_relation_binding_v3(link=link, target=therapy_target(),
                                         intent_type="DIRECT_PERTURBATION")
    assert binding["state"] == "STRUCTURALLY_BOUND"
    coverage = final_query_coverage_v1(phrase=link["linked_relation_phrase"], binding=binding)
    assert coverage["state"] == "COVERED"
    assert "BIOLOGICAL_UNIT_CONTEXT" in coverage["externalized_constraints"]


def test_endpoint_conditioned_sensitivity_direction_composition():
    expected = intent_semantic_transform_v1(therapy_target(), "DIRECT_PERTURBATION")
    row = direction_composition_v1(raw_direction="INCREASE", endpoint_property="sensitivity",
                                   intent_type="DIRECT_PERTURBATION", expected_semantics=expected)
    assert row["response_orientation"]["orientation"] == "SENSITIVITY_UP"
    lexical = direction_composition_v1(raw_direction="SENSITIZE", endpoint_property="sensitivity",
                                       intent_type="THERAPY_SENSITIZATION",
                                       expected_semantics=intent_semantic_transform_v1(
                                           therapy_target(), "THERAPY_SENSITIZATION"))
    assert lexical["response_orientation"]["orientation"] == "SENSITIVITY_UP"
    assert not row["global_lexical_equivalence_used"]


def test_increase_not_globally_equal_sensitize():
    expected = intent_semantic_transform_v1(therapy_target(), "DIRECT_PERTURBATION")
    row = direction_composition_v1(raw_direction="SENSITIZE", endpoint_property="phosphorylation",
                                   intent_type="DIRECT_PERTURBATION", expected_semantics=expected)
    assert row["state"] == "UNRESOLVED"


def test_decreased_sensitivity_is_not_canonicalized_to_resistance():
    expected = intent_semantic_transform_v1(therapy_target(), "DIRECT_PERTURBATION")
    row = direction_composition_v1(raw_direction="DECREASE", endpoint_property="sensitivity",
                                   intent_type="DIRECT_PERTURBATION", expected_semantics=expected)
    assert row["response_orientation"]["orientation"] == "SENSITIVITY_DOWN"


def test_multi_part_therapy_response_containment():
    binding = assess_relation_binding_v3(link=therapy_link(), target=therapy_target(),
                                         intent_type="DIRECT_PERTURBATION")
    response = binding["compositional_response_semantics"]
    assert response["state"] == "COMPATIBLE"
    assert response["composite_response_satisfied"]
    assert not response["monolithic_response_string_required"]


def test_whole_string_alias_not_required():
    row = semantic_surface_containment_v3(
        phrase="increased PGE2 secretion", role="RESPONSE_TARGET",
        proposed_surfaces=["PGE2"], canonical_surfaces=["PGE2 / prostaglandin E2"])
    assert row["state"] == "CONTAINED"
    assert not row["whole_composite_string_required"]


def test_composite_biological_unit_only_allows_validated_modifier():
    target = therapy_target()
    anchors = ["glioblastoma cell"]
    accepted = composite_biological_unit_compatibility_v1(
        "PARP1-depleted glioblastoma cells", anchors, target=target)
    assert accepted["state"] == "COMPATIBLE"
    assert accepted["modifier_class"] == "VALIDATED_PRIMARY_INTERVENTION_STATE"
    arbitrary = composite_biological_unit_compatibility_v1(
        "hypoxic glioblastoma cells", anchors, target=target)
    subtype = composite_biological_unit_compatibility_v1(
        "glioblastoma stem-like cells", anchors, target=target)
    assert arbitrary["state"] == subtype["state"] == "INCOMPATIBLE"
    assert not accepted["arbitrary_modifier_stripping"]


def test_nontherapy_endpoint_orientations_remain_distinct():
    expected = intent_semantic_transform_v1(nested_target(), "DIRECT_PERTURBATION")
    secretion = direction_composition_v1(raw_direction="DECREASE", endpoint_property="secretion",
                                         intent_type="DIRECT_PERTURBATION", expected_semantics=expected)
    assert secretion["response_orientation"]["orientation"] == "SECRETION_DOWN"
    flux = direction_composition_v1(raw_direction="INCREASE", endpoint_property="autophagic flux",
                                    intent_type="DIRECT_PERTURBATION", expected_semantics=expected)
    assert flux["response_orientation"]["orientation"] == "FLUX_UP"


def test_compiler_rejects_invalid_core_and_catches_missing_context():
    link = therapy_link()
    link["biological_unit_surface"] = None
    binding = assess_relation_binding_v3(link=link, target=therapy_target(),
                                         intent_type="DIRECT_PERTURBATION")
    coverage = final_query_coverage_v1(phrase=link["linked_relation_phrase"], binding=binding)
    assert coverage["state"] == "MISSING_REQUIRED_CONTEXT"
    broken = deepcopy(binding)
    broken["relation_core"]["state"] = "INVALID"
    assert final_query_coverage_v1(phrase=link["linked_relation_phrase"], binding=broken)["state"] == "INVALID_RELATION_CORE"


def test_identity_composition_never_promotes_tnf_or_rptor():
    row = semantic_surface_containment_v3(
        phrase="TNF secretion", role="RESPONSE_TARGET",
        proposed_surfaces=["TNF"], canonical_surfaces=["TNF-alpha"])
    assert row["state"] == "CONTAINED"  # proposal surface only; no authority grant
    assert not row["canonical_identity_promoted"]
    tnf_link = nested_link()
    tnf_link["response_surface"] = "TNF"
    tnf_link["linked_relation_phrase"] = "IL-10 suppresses LPS-induced TNF secretion in macrophages"
    assert assess_relation_binding_v3(
        link=tnf_link, target=nested_target(),
        intent_type="DIRECT_PERTURBATION")["state"] == "UNDERREPRESENTED"
    unit = composite_biological_unit_compatibility_v1(
        "RPTOR-depleted cardiomyocytes", ["cardiomyocyte"],
        target={**therapy_target(), "subject": "mTORC1", "canonical_subject": "mTORC1"})
    assert unit["state"] == "INCOMPATIBLE"
    assert not unit["canonical_identity_promoted"]


def test_replay_compiles_only_structurally_bound_relations():
    result = rehydrate_and_compile_alpha3_2(payload(), target=therapy_target())
    assert result["structurally_bound_intent_count"] == 1
    assert result["compiled_query_count"] == 1
    assert result["compiler_requires_valid_relation_core"]
