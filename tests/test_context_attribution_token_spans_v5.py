import copy
import hashlib
import json

import pytest
from pydantic import ValidationError

from code_engine.context_attribution.composition import (
    load_composition_policy, validate_registry_policy_consistency,
)
from code_engine.context_attribution.engine import (
    build_abstract_input, extraction_cache_identity, extraction_prompt,
)
from code_engine.context_attribution.models import ContextExtraction
from code_engine.context_attribution.registry import load_registry, resolve_registry
from code_engine.context_attribution.token_spans import (
    ANCHOR_TOKENIZER_VERSION, attach_token_catalog, tokenize_anchor,
)
from code_engine.context_attribution.validation import validate_context_extraction


def _contract(text="Human A549 cells used CRC and β-catenin-like signaling."):
    return attach_token_catalog({
        "contract_version": "fulltext_context_input_v1",
        "input_mode": "fulltext_evidence_chain",
        "observation_id": "o1",
        "domain_profiles": ["generic", "biomedical"],
        "evidence_anchors": [{
            "anchor_id": "A1", "text": text, "source_role": "current",
            "source_section": "Results", "char_start": 0, "char_end": len(text),
        }],
        "experimental_logic_chain": {},
    })


def _payload(factor):
    return {
        "schema_version": "observation_context_extraction_v5",
        "observation_id": "o1",
        "domain_profiles": ["generic", "biomedical"],
        "input_mode": "fulltext_evidence_chain",
        "context_factors": [factor],
    }


def _explicit(factor_id, start, end, candidate=None):
    return {
        "factor_id": factor_id, "status": "explicit", "raw_value": None,
        "normalized_value": None, "normalized_candidate": candidate,
        "explicit_span": {
            "evidence_anchor_id": "A1",
            "start_token_id": f"A1:T{start}", "end_token_id": f"A1:T{end}",
        },
        "evidence_anchor_ids": ["A1"], "confidence": .9,
    }


def test_tokenizer_is_stable_unicode_aware_and_exactly_sliceable():
    text = "β-catenin–like, A549."
    first = tokenize_anchor("A", text)
    assert first == tokenize_anchor("A", text)
    assert [token["token_id"] for token in first] == [f"A:T{i}" for i in range(len(first))]
    assert "".join(text[x["char_start"]:x["char_end"]] for x in first) == "β-catenin–like,A549."
    assert all(x["char_end"] > x["char_start"] for x in first)


def test_single_and_multi_token_spans_hydrate_original_characters():
    contract = _contract()
    human, errors = validate_context_extraction(
        _payload(_explicit("species", 0, 0, "Homo sapiens")),
        contract, ["generic", "biomedical"],
    )
    assert not errors
    assert human.context_factors[0].raw_value == "Human"
    assert human.context_factors[0].normalized_value == "Homo sapiens"
    crc, errors = validate_context_extraction(
        _payload(_explicit("disease", 4, 4)), contract, ["generic", "biomedical"]
    )
    assert not errors
    assert crc.context_factors[0].raw_value == "CRC"
    assert crc.context_factors[0].normalized_value is None
    beta, errors = validate_context_extraction(
        _payload(_explicit("measurement_endpoint", 6, 10)),
        contract, ["generic", "biomedical"],
    )
    assert not errors
    assert beta.context_factors[0].raw_value == "β-catenin-like"


@pytest.mark.parametrize(
    ("mutation", "fragment"),
    [
        (lambda f: f["explicit_span"].update(start_token_id="A1:T3", end_token_id="A1:T1"), "reversed"),
        (lambda f: f["explicit_span"].update(start_token_id="A1:T999"), "unknown_start"),
        (lambda f: f["explicit_span"].update(end_token_id="A2:T0"), "unknown_end"),
        (lambda f: f["explicit_span"].update(evidence_anchor_id="A2"), "anchor_not_in_observation"),
    ],
)
def test_invalid_spans_fail_closed(mutation, fragment):
    factor = _explicit("cell_line", 1, 1)
    mutation(factor)
    _, errors = validate_context_extraction(
        _payload(factor), _contract(), ["generic", "biomedical"]
    )
    assert any(fragment in error for error in errors)


def test_provider_cannot_supply_raw_or_hydrated_authority():
    raw = _explicit("cell_line", 1, 1)
    raw["raw_value"] = "A549"
    with pytest.raises(ValidationError, match="provider_explicit_raw_value_must_be_null"):
        ContextExtraction.model_validate(_payload(raw))
    hydrated = _explicit("cell_line", 1, 1)
    hydrated["explicit_span_resolution"] = {"raw_value": "A549"}
    with pytest.raises(ValidationError, match="provider_explicit_hydration_fields_forbidden"):
        ContextExtraction.model_validate(_payload(hydrated))


def test_a549_cannot_prove_species_and_unknown_species_is_valid():
    _, errors = validate_context_extraction(
        _payload(_explicit("species", 1, 1, "Homo sapiens")),
        _contract(), ["generic", "biomedical"],
    )
    assert "normalization_unresolved:species" in errors
    unknown = {
        "factor_id": "species", "status": "unknown", "raw_value": None,
        "normalized_value": None, "evidence_anchor_ids": [], "confidence": 1,
    }
    value, errors = validate_context_extraction(
        _payload(unknown), _contract(), ["generic", "biomedical"]
    )
    assert not errors and value.context_factors[0].raw_value is None


@pytest.mark.parametrize("surface", [
    "control", "control cells", "TXNIP-nonspecific siRNA and mock specific siRNA",
])
def test_comparator_accepts_exact_authoritative_raw_field_without_short_allowlist(surface):
    contract = _contract(f"{surface} were measured.")
    contract["experimental_logic_chain"] = {
        "comparator_or_control": {
            "value": {"control_arm_raw": surface},
            "authoritative_evidence_anchor_ids": ["A1"],
        },
    }
    factor = {
        "factor_id": "comparator", "status": "inferred_from_local_chain",
        "raw_value": None, "normalized_value": None,
        "evidence_anchor_ids": ["A1"],
        "source_chain_node_ids": ["comparator_or_control"],
        "inference_rule": "project_comparator_control_surface",
        "raw_components": [{
            "chain_node_id": "comparator_or_control", "field_path": "control_arm_raw",
            "surface": surface, "evidence_anchor_ids": ["A1"],
        }],
        "confidence": .9,
    }
    value, errors = validate_context_extraction(
        _payload(factor), contract, ["generic", "biomedical"]
    )
    assert not errors
    assert value.context_factors[0].composed_value == surface
    if surface != "control":
        assert value.context_factors[0].normalized_value is None


def test_registry_policy_consistency_and_prompt_hide_unsupported_rule():
    registry = load_registry()
    policy, _ = load_composition_policy()
    assert validate_registry_policy_consistency(registry, policy) == []
    broken = copy.deepcopy(registry)
    broken["factor_overrides"]["species"]["allowed_local_inference_rules"] = ["missing"]
    assert "registry_rule_without_policy:species:missing" in validate_registry_policy_consistency(
        broken, policy
    )
    prompt = json.loads(extraction_prompt(_contract(), ["generic", "biomedical"], registry))
    assert "cell_system_to_in_vitro" not in json.dumps(prompt)


def test_token_catalog_and_anchor_text_change_cache_identity():
    contract = build_abstract_input({
        "observation_id": "o", "evidence_sentence": "Human cells.", "polarity": "positive",
    }, ["generic", "biomedical"])
    resolution = resolve_registry()
    kwargs = {
        "profiles": ["generic", "biomedical"], "provider": "offline", "model": "fixture",
        "registry": load_registry(resolution=resolution), "registry_resolution": resolution,
    }
    first = extraction_cache_identity(contract, **kwargs)
    changed = build_abstract_input({
        "observation_id": "o", "evidence_sentence": "Mouse cells.", "polarity": "positive",
    }, ["generic", "biomedical"])
    assert extraction_cache_identity(changed, **kwargs) != first
    assert contract["anchor_tokenizer_version"] == ANCHOR_TOKENIZER_VERSION


def test_v4_explicit_is_readable_but_never_promoted_to_v5_span():
    legacy = _payload(_explicit("cell_line", 1, 1))
    legacy["schema_version"] = "observation_context_extraction_v4"
    legacy["context_factors"][0].pop("explicit_span")
    legacy["context_factors"][0]["raw_value"] = "A549"
    value, errors = validate_context_extraction(
        legacy, _contract(), ["generic", "biomedical"]
    )
    assert "legacy_explicit_span_unverifiable:cell_line" in errors
    assert value.context_factors[0].explicit_span is None
