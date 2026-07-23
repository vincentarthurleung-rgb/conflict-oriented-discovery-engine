import copy
import hashlib
import json

import pytest
from pydantic import ValidationError

from code_engine.context_attribution.composition import (
    COMPOSER_VERSION, COMPOSITION_POLICY_VERSION, composition_identity,
)
from code_engine.context_attribution.engine import extraction_prompt
from code_engine.context_attribution.models import ContextExtraction
from code_engine.context_attribution.registry import load_registry
from code_engine.context_attribution.validation import validate_context_extraction


def _anchor(anchor_id: str, text: str, role: str = "setup") -> dict:
    return {
        "anchor_id": anchor_id,
        "text": text,
        "text_hash": hashlib.sha256(text.encode()).hexdigest(),
        "char_start": 0,
        "char_end": len(text),
        "source_role": role,
        "source_section": "Results",
    }


def _contract() -> dict:
    return {
        "contract_version": "fulltext_context_input_v1",
        "input_mode": "fulltext_evidence_chain",
        "observation_id": "obs-1",
        "domain_profiles": ["generic", "biomedical"],
        "evidence_anchors": [
            _anchor("A1", "CSN8 perturbation changed the endpoint."),
            _anchor("A2", "The control arm was measured in parallel."),
        ],
        "experimental_logic_chain": {
            "intervention_or_exposure": {
                "value": [{
                    "target_mention": "CSN8",
                    "intervention_type_raw": "perturbation",
                }],
                "authoritative_evidence_anchor_ids": ["A1"],
            },
            "comparator_or_control": {
                "value": {
                    "comparison_arm_raw": "CSN8 overexpression",
                    "control_arm_raw": "control",
                },
                "authoritative_evidence_anchor_ids": ["A2"],
            },
        },
    }


def _base_factor(**updates) -> dict:
    factor = {
        "factor_id": "intervention",
        "raw_value": None,
        "normalized_value": None,
        "normalized_candidate": None,
        "status": "inferred_from_local_chain",
        "evidence_anchor_ids": ["A1"],
        "source_chain_node_ids": ["intervention_or_exposure"],
        "inference_rule": "compose_intervention_target_and_type",
        "raw_components": [
            {
                "chain_node_id": "intervention_or_exposure",
                "field_path": "target_mention",
                "surface": "CSN8",
                "evidence_anchor_ids": ["A1"],
            },
            {
                "chain_node_id": "intervention_or_exposure",
                "field_path": "intervention_type_raw",
                "surface": "perturbation",
                "evidence_anchor_ids": ["A1"],
            },
        ],
        "confidence": 0.9,
    }
    factor.update(updates)
    return factor


def _payload(factor: dict) -> dict:
    return {
        "schema_version": "observation_context_extraction_v4",
        "observation_id": "obs-1",
        "domain_profiles": ["generic", "biomedical"],
        "input_mode": "fulltext_evidence_chain",
        "context_factors": [factor],
    }


@pytest.mark.parametrize(
    ("raw", "valid"),
    [
        ("mRNA expression of CSN8", True),
        ("MRNA\u00a0EXPRESSION—OF CSN8", True),
        ("CSN8 mRNA expression", False),
        ("messenger RNA expression of CSN8", False),
        ("mRNA expression of CSN8 versus control", False),
        ("in_vitro", False),
        ("Homo sapiens", False),
    ],
)
def test_explicit_surface_copy_contract(raw, valid):
    text = "mRNA expression—of CSN8 was measured in A549 cells."
    contract = {
        **_contract(),
        "evidence_anchors": [_anchor("A1", text)],
    }
    factor_id = "species" if raw == "Homo sapiens" else (
        "in_vivo_in_vitro_ex_vivo" if raw == "in_vitro" else "measurement_endpoint"
    )
    payload = _payload({
        "factor_id": factor_id,
        "raw_value": raw,
        "normalized_value": None,
        "status": "explicit",
        "evidence_anchor_ids": ["A1"],
        "confidence": 0.9,
    })
    _, errors = validate_context_extraction(
        payload, contract, ["generic", "biomedical"]
    )
    assert (not errors) is valid
    if not valid:
        assert f"explicit_value_not_in_evidence:{factor_id}" in errors


def test_inferred_schema_requires_components_and_forbids_free_raw_value():
    no_components = _base_factor(raw_components=[])
    with pytest.raises(ValidationError, match="requires_raw_components"):
        ContextExtraction.model_validate(_payload(no_components))
    with pytest.raises(ValidationError, match="raw_value_must_be_null"):
        ContextExtraction.model_validate(_payload(_base_factor(raw_value="CSN8 perturbation")))


def test_explicit_surface_cannot_span_two_authoritative_anchors():
    contract = {
        **_contract(),
        "evidence_anchors": [_anchor("A1", "CSN8"), _anchor("A2", "expression")],
    }
    payload = _payload({
        "factor_id": "measurement_endpoint",
        "raw_value": "CSN8 expression",
        "normalized_value": None,
        "status": "explicit",
        "evidence_anchor_ids": ["A1", "A2"],
        "confidence": 0.9,
    })
    _, errors = validate_context_extraction(
        payload, contract, ["generic", "biomedical"]
    )
    assert "explicit_value_not_in_evidence:measurement_endpoint" in errors


def test_valid_components_compose_stably_and_hydrate_full_provenance():
    value, errors = validate_context_extraction(
        _payload(_base_factor()), _contract(), ["generic", "biomedical"]
    )
    assert not errors
    factor = value.context_factors[0]
    assert factor.raw_value is None
    assert factor.composed_value == "CSN8 perturbation"
    assert factor.composition_rule == "compose_intervention_target_and_type"
    assert [x["resolved_field_path"] for x in factor.composition_provenance] == [
        "value[0].target_mention", "value[0].intervention_type_raw",
    ]
    assert all(x["authoritative_evidence"][0]["text_hash"] for x in factor.composition_provenance)
    second, second_errors = validate_context_extraction(
        _payload(_base_factor()), _contract(), ["generic", "biomedical"]
    )
    assert not second_errors
    assert second.context_factors[0].composed_value == factor.composed_value
    assert composition_identity()["composer_version"] == COMPOSER_VERSION


@pytest.mark.parametrize(
    ("mutation", "error_fragment"),
    [
        (lambda f: f["raw_components"][0].update(field_path="missing"), "field_missing_or_null"),
        (lambda f: f["raw_components"][0].update(surface="HIF1A"), "surface_not_in_field"),
        (lambda f: f["raw_components"][0].update(surface="CSN8 perturbation"), "surface_not_in_field"),
        (lambda f: f["raw_components"][0].update(evidence_anchor_ids=["A2"]), "anchor_not_bound_to_node"),
        (lambda f: f.update(inference_rule="external_knowledge"), "rule_not_allowed"),
        (lambda f: f["raw_components"].reverse(), "order_or_shape_invalid"),
        (lambda f: f["raw_components"][0].update(chain_node_id="other_observation_node"), "unknown_chain_node"),
    ],
)
def test_component_validation_fails_closed(mutation, error_fragment):
    factor = copy.deepcopy(_base_factor())
    mutation(factor)
    factor["source_chain_node_ids"] = list(dict.fromkeys(
        x["chain_node_id"] for x in factor["raw_components"]
    ))
    factor["evidence_anchor_ids"] = list(dict.fromkeys(
        aid for item in factor["raw_components"] for aid in item["evidence_anchor_ids"]
    ))
    _, errors = validate_context_extraction(
        _payload(factor), _contract(), ["generic", "biomedical"]
    )
    assert any(error_fragment in error for error in errors)


def test_comparator_requires_control_surface_from_comparator_node():
    valid = _base_factor(
        factor_id="comparator",
        evidence_anchor_ids=["A2"],
        source_chain_node_ids=["comparator_or_control"],
        inference_rule="project_comparator_control_surface",
        raw_components=[{
            "chain_node_id": "comparator_or_control",
            "field_path": "control_arm_raw",
            "surface": "control",
            "evidence_anchor_ids": ["A2"],
        }],
    )
    value, errors = validate_context_extraction(
        _payload(valid), _contract(), ["generic", "biomedical"]
    )
    assert not errors
    assert value.context_factors[0].composed_value == "control"

    wrong_node = copy.deepcopy(valid)
    wrong_node["source_chain_node_ids"] = ["intervention_or_exposure"]
    wrong_node["raw_components"][0]["chain_node_id"] = "intervention_or_exposure"
    wrong_node["raw_components"][0]["evidence_anchor_ids"] = ["A1"]
    wrong_node["evidence_anchor_ids"] = ["A1"]
    _, errors = validate_context_extraction(
        _payload(wrong_node), _contract(), ["generic", "biomedical"]
    )
    assert any("order_or_shape_invalid" in error for error in errors)

    invented = copy.deepcopy(valid)
    invented["raw_components"][0]["field_path"] = "comparison_arm_raw"
    invented["raw_components"][0]["surface"] = "control"
    _, errors = validate_context_extraction(
        _payload(invented), _contract(), ["generic", "biomedical"]
    )
    assert errors


def test_a549_cell_line_explicit_species_unknown_and_no_registry_mapping():
    contract = {
        **_contract(),
        "evidence_anchors": [_anchor("A1", "A549 cells showed an increased endpoint.")],
    }
    payload = _payload({
        "factor_id": "cell_line",
        "raw_value": "A549",
        "normalized_value": None,
        "status": "explicit",
        "evidence_anchor_ids": ["A1"],
        "confidence": 0.9,
    })
    payload["context_factors"].append({
        "factor_id": "species",
        "raw_value": None,
        "normalized_value": None,
        "normalized_candidate": None,
        "status": "unknown",
        "evidence_anchor_ids": [],
        "confidence": 1.0,
    })
    value, errors = validate_context_extraction(
        payload, contract, ["generic", "biomedical"]
    )
    assert not errors
    assert value.context_factors[1].normalized_value is None
    assert "a549" not in load_registry()["factor_overrides"]["species"]["controlled_normalizations"]

    guessed = copy.deepcopy(payload)
    guessed["context_factors"][1] = {
        "factor_id": "species",
        "raw_value": "Homo sapiens",
        "normalized_value": None,
        "status": "explicit",
        "evidence_anchor_ids": ["A1"],
        "confidence": 0.9,
    }
    _, errors = validate_context_extraction(
        guessed, contract, ["generic", "biomedical"]
    )
    assert "explicit_value_not_in_evidence:species" in errors


def test_unknown_structure_and_provider_composed_value_are_rejected():
    unknown = {
        "factor_id": "species", "raw_value": None, "normalized_value": None,
        "status": "unknown", "evidence_anchor_ids": [], "confidence": 1.0,
    }
    invalid = copy.deepcopy(unknown)
    invalid["raw_components"] = [{
        "chain_node_id": "intervention_or_exposure",
        "field_path": "target_mention", "surface": "CSN8",
        "evidence_anchor_ids": ["A1"],
    }]
    with pytest.raises(ValidationError, match="unknown_factor_must_be_empty"):
        ContextExtraction.model_validate(_payload(invalid))

    provider_composed = _payload(_base_factor(composed_value="model chose this"))
    _, errors = validate_context_extraction(
        provider_composed, _contract(), ["generic", "biomedical"]
    )
    assert "provider_composed_value_forbidden" in errors


def test_prompt_contains_and_validates_all_new_examples():
    prompt = json.loads(extraction_prompt(_contract(), ["generic", "biomedical"]))
    assert prompt["prompt_version"] == "context_attribution_prompts_v4"
    assert prompt["local_chain_composition_policy"]["policy_version"] == COMPOSITION_POLICY_VERSION
    descriptions = " ".join(x["description"] for x in prompt["examples"]["extraction_examples"])
    assert "field-level components" in descriptions
    assert "Comparator provenance" in descriptions
    assert "A549" in json.dumps(prompt["examples"])
    for example in prompt["examples"]["extraction_examples"]:
        ContextExtraction.model_validate(example["output"])
        _, errors = validate_context_extraction(
            example["output"], example["input"], ["generic", "biomedical"]
        )
        assert not errors, (example["description"], errors)
