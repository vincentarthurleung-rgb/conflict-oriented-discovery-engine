import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from code_engine.fulltext.evidence_anchors import generate_evidence_anchors, render_anchored_block, resolve_anchor
from code_engine.fulltext.experimental_semantics_registry import REGISTRY_VERSION, normalize_semantics
from code_engine.fulltext.fulltext_l1_draft_hydration_v3 import (
    TrustedDraftContextV3, hydrate_draft_response_v3,
)
from code_engine.fulltext.fulltext_observation_v3 import adapt_v2_observation_to_v3, legacy_lossy_projection
from code_engine.fulltext.reasoning_trace import evidence_chains_from_v2_observations
from code_engine.schemas.fulltext_observation import (
    ExperimentalObservationV3, FulltextL1V2Response, FulltextL1V3Response, fulltext_l1_v2_prompt_examples,
)
from code_engine.schemas.fulltext_observation_draft import DRAFT_SCHEMA_VERSION, FulltextL1DraftResponse


def context(text, block_id="block"):
    return TrustedDraftContextV3(
        run_id="run", block_id=block_id, parent_block_id=block_id, child_block_id=None,
        block_text=f"CURRENT_RESULTS: {text}", source_block_hash="block-hash",
        source_document_id="doc", paper_id="paper", pmid=None, pmcid=None,
        fulltext_source_hash="source-hash", source_artifact="article_text.json", section="Results",
    )


def payload(text, interventions, *, design="unknown", measurement="unknown", direction="positive",
            combination="unknown", endpoint="endpoint", comparison="versus comparator"):
    anchor = generate_evidence_anchors(block_id="block", source_document_id="doc",
                                       block_text=f"CURRENT_RESULTS: {text}", section="Results")[0]
    evidence = {"text": text, "evidence_anchor_ids": [anchor.anchor_id], "span_type": "observation"}
    rows = []
    for index, item in enumerate(interventions):
        rows.append({
            "role_raw": item[0], "intervention_type_raw": item[1],
            "intervention_target_mention": item[2], "agent_or_drug_mention": item[2],
            "intervention_method_raw": None, "dose_raw": None, "duration_raw": None,
            "route_raw": None, "condition_raw": item[2],
            "evidence_text": {**evidence, "span_type": "intervention"},
        })
    return {
        "schema_version": DRAFT_SCHEMA_VERSION,
        "experimental_observations": [{
            "experiment": {"experiment_label_raw": "experiment", "evidence_family_label_raw": "family",
                "experimental_design_raw": text, "design_type_raw": design, "species_raw": None,
                "model_system_raw": None, "cell_line_or_type_raw": None, "tissue_raw": None,
                "disease_model_raw": None, "genotype_raw": None, "cohort_raw": None,
                "sample_raw": None, "comparison_arm_raw": "experimental arm", "control_arm_raw": "comparator"},
            "interventions": rows, "combination_mode_raw": combination,
            "measurement": {"measurement_dimension_raw": measurement, "measured_entity_mention": endpoint,
                "outcome_mention": endpoint, "assay_or_readout_raw": None, "endpoint_raw": endpoint,
                "evidence_text": {**evidence, "span_type": "measurement"}},
            "observation": {"observed_result": text, "lexical_direction_raw": direction,
                "quantitative_result_raw": None, "statistical_support_raw": None,
                "uncertainty_raw": None, "comparison_raw": comparison, "negation": False,
                "evidence_text": evidence},
            "interpretation_raw": None, "interpretation_evidence_text": None,
            "candidate_relation": {"subject_mention": interventions[0][2] if interventions else "cohort",
                "object_mention": endpoint, "relation_wording_raw": "changed",
                "lexical_direction_raw": direction, "evidence_design_raw": design,
                "confidence_or_qualification_raw": None},
            "statement_role": "current_study_experiment", "evidence_texts": [evidence],
            "extraction_warnings_raw": []
        }],
    }


def hydrate(value, text):
    draft = FulltextL1DraftResponse.model_validate(value)
    result = hydrate_draft_response_v3(draft, context(text))
    assert not result.rejected
    return FulltextL1V3Response.model_validate(result.formal_response).experimental_observations[0]


@pytest.mark.parametrize(("text", "interventions", "design", "measurement", "combination"), [
    ("Gene knockdown followed by drug rescue changed protein abundance.",
     [("primary", "knockdown", "gene"), ("rescue", "drug_treatment", "rescue agent")], "in_vitro", "abundance_expression", "rescue_design"),
    ("A clinical cohort showed higher biomarker levels without an assigned intervention.",
     [], "clinical", "abundance_expression", "unknown"),
    ("Catalyst A with promoter B increased conversion at 500 K.",
     [("primary", "unknown", "Catalyst A"), ("co_treatment", "unknown", "promoter B")], "unknown", "conversion", "concurrent"),
    ("Annealing followed by surface treatment increased conductivity.",
     [("primary", "unknown", "annealing"), ("secondary", "unknown", "surface treatment")], "unknown", "conductivity", "sequential"),
    ("Changing solvent and adding ligand increased yield.",
     [("primary", "unknown", "solvent"), ("co_treatment", "unknown", "ligand")], "unknown", "yield", "factorial"),
])
def test_same_formal_pipeline_is_domain_portable(text, interventions, design, measurement, combination):
    row = hydrate(payload(text, interventions, design=design, measurement=measurement,
                          combination=combination), text)
    assert row.provenance.evidence_spans[0].anchor_id == "block:S0001"
    assert len(row.interventions) == len(interventions)
    assert row.measurement.measurement_dimension_raw == measurement
    assert row.eligibility.graph_eligible is True
    if len(interventions) > 1:
        assert row.combination_mode == combination


def test_formal_v3_multi_intervention_is_strict_and_preserves_order_roles():
    text = "Annealing followed by surface treatment increased conductivity."
    row = hydrate(payload(text, [("primary", "unknown", "annealing"),
                                 ("secondary", "unknown", "surface treatment")],
                          combination="sequential", endpoint="conductivity"), text)
    assert [x.role for x in row.interventions] == ["primary", "secondary"]
    assert row.combination_mode == "sequential"
    assert row.eligibility.strict_core_eligible is False
    bad = row.model_dump(mode="json"); bad["extra"] = True
    with pytest.raises(ValidationError): ExperimentalObservationV3.model_validate(bad)


def test_v2_adapter_preserves_unstructured_secondary_without_guessing():
    _, nonempty = fulltext_l1_v2_prompt_examples()
    row = nonempty["experimental_observations"][0]
    row["intervention"]["secondary_intervention"] = "unstructured secondary condition"
    v2 = FulltextL1V2Response.model_validate(nonempty).experimental_observations[0]
    v3 = adapt_v2_observation_to_v3(v2)
    assert len(v3.interventions) == 2
    assert v3.interventions[1].intervention_type == "unknown"
    assert v3.interventions[1].intervention_type_raw == "unstructured secondary condition"
    assert v3.interventions[1].target_mention is None
    assert "intervention.secondary_intervention" in v3.lossy_fields
    lossy = legacy_lossy_projection(v3)
    assert lossy["discarded_intervention_ids"] == [v3.interventions[1].intervention_id]


def test_reviewable_unknown_and_mixed_are_formal_valid_but_core_conflict_ineligible():
    text = "The treatment increased endpoint A but decreased endpoint B."
    row = hydrate(payload(text, [("primary", "stabilization", "treatment")],
                          design="clinical", measurement="unknown", direction="mixed"), text)
    assert row.interventions[0].intervention_type == "unknown"
    assert row.interventions[0].intervention_type_raw == "stabilization"
    assert row.experiment.design_type == "unknown" and row.experiment.design_type_raw == "clinical"
    assert row.candidate_relation.lexical_direction == "mixed"
    assert row.eligibility.graph_eligible is True
    assert row.eligibility.strict_core_eligible is False
    assert row.eligibility.conflict_eligible is False


def test_endpoint_split_preferred_over_mixed_when_draft_provides_two_observations():
    text = "The treatment increased endpoint A but decreased endpoint B."
    first = payload(text, [("primary", "drug_treatment", "treatment")], measurement="unknown", direction="positive", endpoint="endpoint A")
    second = copy.deepcopy(first["experimental_observations"][0])
    second["measurement"]["endpoint_raw"] = second["measurement"]["measured_entity_mention"] = "endpoint B"
    second["candidate_relation"]["object_mention"] = "endpoint B"
    second["candidate_relation"]["lexical_direction_raw"] = "negative"
    first["experimental_observations"].append(second)
    result = hydrate_draft_response_v3(FulltextL1DraftResponse.model_validate(first), context(text))
    assert len(result.formal_response["experimental_observations"]) == 2
    assert {x["candidate_relation"]["lexical_direction"] for x in result.formal_response["experimental_observations"]} == {"positive", "negative"}


def test_anchor_generation_hash_offsets_cross_block_and_methods_guard():
    block = "CURRENT_RESULTS: Result increased.\nLINKED_METHODS: Assay was performed."
    anchors = generate_evidence_anchors(block_id="b", source_document_id="d", block_text=block, section="Results")
    assert [x.anchor_id for x in anchors] == ["b:S0001", "b:S0002"]
    assert all(block[x.char_start:x.char_end] == x.text for x in anchors)
    assert render_anchored_block(anchors).startswith("[b:S0001]")
    assert resolve_anchor("b:S0001", anchors, expected_block_id="b").text == "Result increased."
    with pytest.raises(ValueError, match="not_found"): resolve_anchor("other:S0001", anchors, expected_block_id="b")
    with pytest.raises(ValueError, match="cross_block"):
        resolve_anchor("b:S0001", [copy.copy(anchors[0]).__class__(**{**anchors[0].as_dict(), "block_id": "other"})], expected_block_id="b")


def test_reasoning_keeps_multi_intervention_as_one_reviewable_chain():
    text = "Catalyst A with promoter B increased conversion at 500 K."
    row = hydrate(payload(text, [("primary", "unknown", "Catalyst A"),
                                 ("co_treatment", "unknown", "promoter B")],
                          measurement="conversion", combination="concurrent", endpoint="conversion"), text)
    chains = evidence_chains_from_v2_observations([row.model_dump(mode="json")])
    assert len(chains) == 1 and len(chains[0]["interventions"]) == 2
    assert chains[0]["intervention_sign"] is None
    assert chains[0]["causal_design"]["evidence_type"] == "association"


def test_registry_is_configuration_driven_and_preserves_unmapped_raw():
    assert REGISTRY_VERSION == "experimental_semantics_registry_v1"
    value = normalize_semantics("intervention_type", "new experimental factor", domain_profile="materials")
    assert value.normalized_value == "unknown" and value.status == "reviewable_unknown"
    assert value.raw_value == "new experimental factor"
    engine = Path("src/code_engine/fulltext/experimental_semantics_registry.py").read_text()
    for forbidden in ("HIF1A", "cancer", "hypoxia", "ketamine", "TGFB1"):
        assert forbidden not in engine
