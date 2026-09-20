"""Offline, fail-closed alpha2 contract and prospective provider tests."""

from copy import deepcopy
import os
from unittest.mock import patch

import pytest

from code_engine.extraction.client_factory import (
    build_json_client_from_config, diagnose_json_provider, resolve_l1_provider_settings,
)
from code_engine.search.alpha2_linked_relation_v1 import (
    Alpha2ContractError, assess_linked_relation_v1_1, search_anchor_compatibility,
    search_only_eligibility_v1_1, linked_relation_search_only_eligibility,
    validate_planner_proposal_v2,
)
from code_engine.search.deepseek_planner_transport_v1 import (
    DeepSeekPlannerTransportV1, DEFAULT_CONFIG, DEEPSEEK_PROVIDER_SCHEMA, PROMPT_TEXT, planner_cache_identity,
    rehydrate_provider_response, static_schema_preflight,
)
from code_engine.search.proposition_aware_query_planner_v1 import DEFAULT_DEVELOPMENT_CONFIG


TARGET = {
    "artifact_schema_version": "ScientificPropositionTargetV1",
    "subject": "IL-10", "object": "TNF-alpha", "relation_family": "suppresses secretion",
    "measurement_property_endpoint": "secretion", "canonical_relation_family": "suppresses secretion",
    "context_qualifier_dimensions": {"treatment": "LPS", "biological_unit": "macrophages"},
}


def proposal():
    def concept(cid, ctype, anchor):
        return {"concept_id": cid, "concept_type": ctype, "canonical_anchor": anchor,
                "proposed_terms": [{"term_id": cid + "_term", "term": anchor}]}

    link = {"subject_concept_ref": "s", "response_concept_ref": "r",
            "relation_family": "suppresses secretion", "direction": "DECREASE",
            "subject_surface_candidate": "IL-10", "relation_surface_candidate": "suppresses",
            "response_surface_candidate": "TNF-alpha", "endpoint_property_surface_candidate": "secretion",
            "linked_relation_phrase": "IL-10 suppresses LPS-induced TNF-alpha secretion in macrophages",
            "conditioning_context_refs": ["n"], "therapy_context_refs": [],
            "biological_unit_context_ref": "u", "planner_rationale": "linked retrieval language"}
    return {"retrieval_intents": [{
        "intent_id": "i", "intent_type": "DIRECT_PERTURBATION", "applicability": "APPLICABLE",
        "applicability_rationale": "direct effect", "scientific_rationale": "candidate only",
        "required_dimensions": ["subject", "relation", "object_measurement_target", "endpoint_property",
                                "direction", "evidence_mode"],
        "optional_dimensions": ["biological_unit", "nested_treatment"],
        "biological_unit_context": {"target_value": "macrophages", "planning_state": "PRESENT",
                                    "separate_from_entity_identity": True},
        "search_concepts": [concept("s", "subject", "IL-10"),
                            concept("r", "object_measurement_target", "TNF-alpha"),
                            concept("e", "endpoint_property", "secretion"),
                            concept("n", "nested_treatment", "LPS"),
                            concept("u", "biological_unit", "macrophages")],
        "candidate_query_blueprints": [{"blueprint_id": "b", "concept_ids": ["s", "r", "e", "n", "u"],
                                        "linked_relation_candidates": [link]}],
    }]}


def link():
    return proposal()["retrieval_intents"][0]["candidate_query_blueprints"][0]["linked_relation_candidates"][0]


def test_valid_proposal_and_binding():
    assert validate_planner_proposal_v2(proposal(), target=TARGET)
    assert assess_linked_relation_v1_1(link(), TARGET)["state"] == "STRUCTURALLY_BOUND"
    assert linked_relation_search_only_eligibility(link(), TARGET)[0] == "SEARCH_ONLY_EXPANSION"


def test_missing_link_and_keyword_bags_fail():
    value = proposal()
    value["retrieval_intents"][0]["candidate_query_blueprints"][0]["linked_relation_candidates"] = []
    with pytest.raises(Alpha2ContractError):
        validate_planner_proposal_v2(value, target=TARGET)
    value = link()
    value["linked_relation_phrase"] = "IL-10 TNF-alpha secretion LPS"
    assert assess_linked_relation_v1_1(value, TARGET)["state"] != "STRUCTURALLY_BOUND"


@pytest.mark.parametrize("field", ["proposal_class", "authority_reference"])
def test_model_cannot_assert_authority(field):
    value = proposal()
    value["retrieval_intents"][0][field] = "AUTHORIZED_EQUIVALENT"
    with pytest.raises(Alpha2ContractError):
        validate_planner_proposal_v2(value, target=TARGET)


@pytest.mark.parametrize("field", ["subject_concept_ref", "response_concept_ref"])
def test_unknown_refs_fail(field):
    value = proposal()
    value["retrieval_intents"][0]["candidate_query_blueprints"][0]["linked_relation_candidates"][0][field] = "invented"
    with pytest.raises(Alpha2ContractError):
        validate_planner_proposal_v2(value, target=TARGET)


@pytest.mark.parametrize("change", [
    {"direction": "INCREASE"},
    {"endpoint_property_surface_candidate": "abundance"},
    {"conditioning_context_refs": []},
    {"linked_relation_phrase": "IL-10 suppresses TNF-alpha secretion in macrophages"},
    {"response_surface_candidate": "TNF"},
])
def test_binding_fails_on_missing_roles(change):
    value = link()
    value.update(change)
    assert assess_linked_relation_v1_1(value, TARGET)["state"] == "UNDERREPRESENTED"
    assert linked_relation_search_only_eligibility(value, TARGET)[0] == "UNRESOLVED"


def test_relation_surface_cannot_contradict_direction():
    value = link()
    value["relation_surface_candidate"] = "increases"
    value["linked_relation_phrase"] = "IL-10 increases LPS-induced TNF-alpha secretion in macrophages"
    assert not assess_linked_relation_v1_1(value, TARGET)["checks"]["direction"]


def test_therapy_loss_fails():
    target = {**TARGET, "therapy": "trametinib", "context_qualifier_dimensions": {}}
    value = link()
    value["linked_relation_phrase"] = "IL-10 suppresses TNF-alpha secretion"
    assert not assess_linked_relation_v1_1(value, target)["checks"]["therapy"]


def test_canonical_target_unchanged_and_local_rehydration():
    original = deepcopy(TARGET)
    result = rehydrate_provider_response(proposal(), target_id="demo", target=TARGET)
    assert TARGET == original
    assert result["target_id"] == "demo"
    assert result["planner_proposal_payload"] == proposal()


def test_anchor_does_not_promote_identity_or_short_form():
    assert search_anchor_compatibility("TNF", ["TNF-alpha"]) not in {
        "EXACT_CANONICAL_SURFACE", "AUTHORIZED_ALIAS_SURFACE", "SAFE_ORTHOGRAPHIC_VARIANT"}
    assert search_anchor_compatibility("TNFα", ["TNF-alpha"]) == "SAFE_ORTHOGRAPHIC_VARIANT"
    assert assess_linked_relation_v1_1(link(), TARGET)["canonical_identity_promoted"] is False


def test_default_deny_search_only():
    assert search_only_eligibility_v1_1("unverified proxy", "subject", TARGET)[0] == "UNRESOLVED"
    assert search_only_eligibility_v1_1("TNF", "object_measurement_target", TARGET)[0] == "UNRESOLVED"


def test_deepseek_preflight_and_prompt():
    assert static_schema_preflight()["passed"]
    assert not static_schema_preflight()["remote_api_acceptance_verified"]
    assert "independent keyword bags" in PROMPT_TEXT
    assert DEFAULT_CONFIG.model == "deepseek-v4-pro"
    tampered = deepcopy(DEEPSEEK_PROVIDER_SCHEMA)
    tampered["properties"]["target_id"] = {"type": "string"}
    assert not static_schema_preflight(tampered)["passed"]


def test_cache_separated_from_historical_openai():
    identity = planner_cache_identity(TARGET)
    assert identity != planner_cache_identity({**TARGET, "subject": "other"})
    assert DEFAULT_DEVELOPMENT_CONFIG.provider == "OpenAI"  # frozen historical provenance
    assert DEFAULT_CONFIG.provider == "deepseek"


def test_missing_deepseek_key_fails_closed_no_openai_fallback():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "fake", "L1_PROVIDER": "deepseek"}, clear=True):
        assert build_json_client_from_config() is None
        assert not diagnose_json_provider(model_name="deepseek-v4-pro")["provider_available"]
        assert build_json_client_from_config("openai", "gpt-test") is None
        with pytest.raises(ValueError):
            resolve_l1_provider_settings(provider="openai")
        with pytest.raises(ValueError):
            DeepSeekPlannerTransportV1().execute(target_id="x", target=TARGET, api_key=None,
                                                 explicitly_authorized=True)


def test_no_provider_call_without_explicit_authorization():
    with patch("code_engine.search.deepseek_planner_transport_v1.DeepSeekClient") as client:
        with pytest.raises(PermissionError):
            DeepSeekPlannerTransportV1().execute(target_id="x", target=TARGET, api_key="fake")
        client.assert_not_called()
