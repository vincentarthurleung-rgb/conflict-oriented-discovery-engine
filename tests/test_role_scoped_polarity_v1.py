from copy import deepcopy

import pytest

from code_engine.search.role_scoped_polarity_v1 import (
    assess_relation_binding_v3_1, intervention_action_polarity_v1,
    rehydrate_and_compile_alpha3_3, response_orientation_evidence_v1,
    role_scoped_polarity_parser_v1,
)


def target(endpoint="autophagic flux", direction="inhibition increases"):
    return {
        "artifact_schema_version": "ScientificPropositionTargetV1",
        "scientific_proposition_target_id": "fixture:role-scope:v1",
        "subject": "TARGET", "canonical_subject": "TARGET",
        "subject_intervention": "TARGET inhibition",
        "relation_family": direction, "canonical_relation_family": direction,
        "canonical_proposition_orientation": f"reduced TARGET function -> increased {endpoint}",
        "object": endpoint, "measurement_target": endpoint,
        "measurement_property_endpoint": endpoint,
        "required_evidence_mode": "current-study perturbational evidence",
        "acceptable_endpoint_evidence": [endpoint],
        "context_qualifier_dimensions": {"biological_unit": ["test cell"]},
        "therapy": None,
    }


def link(action="inhibition", relation="increases", direction="INCREASE",
         endpoint="autophagic flux"):
    return {
        "subject_surface": f"TARGET {action}", "subject_action_surface": action,
        "relation_surface": relation, "direction": direction,
        "response_surface": endpoint, "endpoint_property_surface": endpoint,
        "linked_relation_phrase": f"TARGET {action} {relation} {endpoint} in test cells",
        "biological_unit_surface": "test cells", "conditioning_treatment_surface": None,
        "therapy_surface": None, "disease_surface": None, "genotype_surface": None,
        "evidence_mode_surface": None, "planner_rationale": "fixture",
    }


def payload(value=None):
    return {"retrieval_intents": [{"intent_type": "DIRECT_PERTURBATION",
        "retrieval_rationale": "fixture", "linked_relation_proposals": [value or link()],
        "search_concept_proposals": [{"semantic_role": "PRIMARY_INTERVENTION",
                                      "proposed_terms": ["TARGET"]}]}]}


@pytest.mark.parametrize(("action", "expected"), [
    ("inhibition", "INHIBIT"), ("activation", "ACTIVATE"),
    ("loss", "DELETE_OR_LOSS"), ("overexpression", "OVEREXPRESS_OR_INCREASE"),
])
def test_actor_polarity_never_controls_response(action, expected):
    result = intervention_action_polarity_v1(link(action=action))
    assert result["state"] == expected
    assert result["controls_response_orientation"] is False


def test_explicit_response_increase_controls_up():
    row = response_orientation_evidence_v1(
        link=link(action="inhibition", relation="increases", direction="INCREASE"),
        target=target(), intent_type="DIRECT_PERTURBATION")
    assert row["state"] == "COMPATIBLE"
    assert row["expected_response_orientation"]["orientation"] == "FLUX_UP"
    assert not row["actor_action_polarity_used"]


def test_explicit_response_decrease_controls_down():
    value = link(action="activation", relation="decreases", direction="DECREASE")
    row = response_orientation_evidence_v1(
        link=value, target=target(), intent_type="INVERSE_PERTURBATION")
    assert row["state"] == "COMPATIBLE"
    assert row["expected_response_orientation"]["orientation"] == "FLUX_DOWN"


def test_inhibit_actor_plus_sensitivity_up_is_valid():
    value = link(action="inhibition", relation="sensitizes", direction="SENSITIZE",
                 endpoint="sensitivity")
    value["therapy_surface"] = "DRUG"
    value["response_surface"] = "DRUG"
    value["linked_relation_phrase"] = "TARGET inhibition sensitizes test cells to DRUG"
    t = target(endpoint="increased sensitivity")
    t["therapy"] = "DRUG"
    t["measurement_target"] = t["object"] = "DRUG treatment response"
    t["context_qualifier_dimensions"]["therapy"] = ["DRUG"]
    binding = assess_relation_binding_v3_1(
        link=value, target=t, intent_type="THERAPY_SENSITIZATION")
    assert binding["relation_core"]["intervention_action_polarity"]["state"] == "INHIBIT"
    assert binding["compositional_response_semantics"]["response_orientation"]["orientation"] == "SENSITIVITY_UP"


def test_inhibit_actor_plus_flux_up_is_valid():
    binding = assess_relation_binding_v3_1(
        link=link(), target=target(), intent_type="DIRECT_PERTURBATION")
    assert binding["state"] == "STRUCTURALLY_BOUND"
    assert binding["relation_core"]["intervention_action_polarity"]["state"] == "INHIBIT"


def test_inhibit_actor_plus_response_down_is_possible():
    value = link(action="inhibition", relation="decreases", direction="DECREASE")
    row = response_orientation_evidence_v1(
        link=value, target=target(), intent_type="INVERSE_PERTURBATION")
    assert row["state"] == "COMPATIBLE"
    assert row["expected_response_orientation"]["orientation"] == "FLUX_DOWN"


def test_nested_suppression_uses_relation_not_lps_stimulation():
    t = target(endpoint="secretion", direction="decreases / suppresses")
    t.update({"subject": "IL-10", "canonical_subject": "IL-10",
              "subject_intervention": "IL-10 treatment",
              "measurement_target": "TNF-alpha", "object": "TNF-alpha",
              "canonical_proposition_orientation": "increased IL-10 -> decreased TNF-alpha secretion"})
    t["context_qualifier_dimensions"] = {"biological_unit": ["macrophage"],
                                         "treatment_context": ["LPS stimulation"]}
    value = link(action="treatment", relation="suppresses", direction="DECREASE", endpoint="secretion")
    value.update({"subject_surface": "IL-10", "subject_action_surface": "treatment",
                  "response_surface": "TNF-alpha", "biological_unit_surface": "macrophage",
                  "conditioning_treatment_surface": "LPS stimulation",
                  "linked_relation_phrase": "IL-10 suppresses LPS-induced TNF-alpha secretion in macrophages"})
    binding = assess_relation_binding_v3_1(link=value, target=t, intent_type="DIRECT_PERTURBATION")
    assert binding["state"] == "STRUCTURALLY_BOUND"
    assert binding["compositional_response_semantics"]["response_orientation"]["orientation"] == "SECRETION_DOWN"


def test_therapy_composition_remains_internal():
    value = link(action="inhibition", relation="sensitizes", direction="SENSITIZE", endpoint="sensitivity")
    value.update({"therapy_surface": "DRUG", "response_surface": "DRUG",
                  "linked_relation_phrase": "TARGET inhibition sensitizes test cells to DRUG"})
    t = target(endpoint="increased sensitivity")
    t.update({"therapy": "DRUG", "measurement_target": "DRUG treatment response",
              "object": "DRUG treatment response"})
    t["context_qualifier_dimensions"]["therapy"] = ["DRUG"]
    binding = assess_relation_binding_v3_1(link=value, target=t, intent_type="THERAPY_SENSITIZATION")
    assert binding["relation_core"]["checks"]["therapy_internal_when_required"]


def test_autophagic_flux_does_not_collapse_to_generic_autophagy():
    value = link(endpoint="autophagy")
    value["response_surface"] = "autophagy"
    value["linked_relation_phrase"] = "TARGET inhibition increases autophagy in test cells"
    binding = assess_relation_binding_v3_1(link=value, target=target(), intent_type="DIRECT_PERTURBATION")
    assert binding["state"] == "UNDERREPRESENTED"


def test_role_scope_does_not_change_identity():
    parsed = role_scoped_polarity_parser_v1(link())
    assert parsed["intervention_polarity_distinct_from_response_orientation"]
    assert not parsed["global_polarity_bag_active"]
    assert all("identity" not in row for row in parsed["field_scoped_evidence"])


def test_no_global_lexical_polarity_bag_in_active_path():
    parsed = role_scoped_polarity_parser_v1(link(action="inhibition", relation="increases"))
    scoped = {(row["normalized_semantic"], row["scope"]) for row in parsed["field_scoped_evidence"]}
    assert ("INHIBIT", "PRIMARY_INTERVENTION_ACTION_SCOPE") in scoped
    assert ("UP", "RELATION_SCOPE") in scoped
    assert not parsed["global_polarity_bag_active"]


def test_core_direct_definition_is_not_part_of_parser():
    parsed = role_scoped_polarity_parser_v1(link())
    assert "core_direct" not in repr(parsed).casefold()


def test_compiler_still_requires_valid_relation_core_and_coverage():
    result = rehydrate_and_compile_alpha3_3(payload(), target=target())
    assert result["compiled_query_count"] == 1
    assert result["compiler_requires_valid_relation_core"]
    broken = payload()
    broken["retrieval_intents"][0]["linked_relation_proposals"][0]["endpoint_property_surface"] = "autophagy"
    broken["retrieval_intents"][0]["linked_relation_proposals"][0]["response_surface"] = "autophagy"
    broken["retrieval_intents"][0]["linked_relation_proposals"][0]["linked_relation_phrase"] = \
        "TARGET inhibition increases autophagy in test cells"
    assert rehydrate_and_compile_alpha3_3(broken, target=target())["compiled_query_count"] == 0


def test_no_case_specific_rule():
    assert "heldout_v2" not in repr(role_scoped_polarity_parser_v1(link()))


def test_actor_state_modifier_does_not_override_response():
    value = link(action="depletion", relation="increases", direction="INCREASE")
    evidence = response_orientation_evidence_v1(
        link=value, target=target(), intent_type="DIRECT_PERTURBATION")
    assert evidence["state"] == "COMPATIBLE"
    assert evidence["expected_response_orientation"]["orientation"] == "FLUX_UP"


def test_missing_explicit_response_relation_fails_closed():
    value = link(action="inhibition", relation="associated with", direction="INCREASE")
    evidence = response_orientation_evidence_v1(
        link=value, target=target(), intent_type="DIRECT_PERTURBATION")
    assert evidence["state"] == "UNDERREPRESENTED"
