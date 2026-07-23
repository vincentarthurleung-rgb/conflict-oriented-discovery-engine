import json
from pathlib import Path
from unittest.mock import patch
import pytest
import httpx

from code_engine.context_attribution.engine import (
    build_abstract_input, build_fulltext_input, candidate_pairs,
    extraction_cache_identity, extraction_prompt, pair_cache_identity, pair_prompt,
)
from code_engine.context_attribution.gate import apply_comparability_gate
from code_engine.context_attribution.models import ContextExtraction
from code_engine.context_attribution.planning import representative_smoke_selection
from code_engine.context_attribution.registry import load_registry, resolve_factors
from code_engine.context_attribution.runner import run_context_attribution
from code_engine.context_attribution.validation import validate_context_extraction, validate_pair_attribution
from code_engine.extraction.deepseek_client import (
    DeepSeekClient, DeepSeekExtractionError, JSONExtractionResult,
)
from code_engine.graph.conflict_discovery import build_conflict_graph

def _abstract(oid="a", sentence="Treatment increased the endpoint.", polarity="positive"):
    return {"observation_id": oid, "evidence_sentence": sentence, "polarity": polarity,
            "canonical_endpoint_id": "ENDPOINT:1", "fulltext_secret": {"species": "mouse"}}

def _unknown(oid, anchor):
    return {"schema_version": "observation_context_extraction_v2", "observation_id": oid,
            "domain_profiles": ["generic", "biomedical"], "input_mode": "abstract_sentence_only",
            "context_factors": [{"factor_id": "species", "raw_value": "unknown",
                                 "normalized_value": None, "status": "unknown",
                                 "evidence_anchor_ids": [], "evidence_text": None, "confidence": 1.0}],
            "missing_critical_information": ["species"], "warnings": [], "provenance": {}}

def test_abstract_contract_is_sentence_only_and_unknown_does_not_use_fulltext():
    contract = build_abstract_input(_abstract(), ["generic", "biomedical"])
    assert contract["input_mode"] == "abstract_sentence_only"
    assert "fulltext_secret" not in json.dumps(contract)
    value, errors = validate_context_extraction(_unknown("a", "a:abstract_sentence"), contract,
                                                ["generic", "biomedical"])
    assert not errors
    assert value.context_factors[0].raw_value == "unknown"

def test_abstract_rejects_fulltext_anchor_and_external_knowledge_value():
    contract = build_abstract_input(_abstract(), ["generic", "biomedical"])
    bad = _unknown("a", "")
    bad["context_factors"][0] = {"factor_id": "species", "raw_value": "mouse",
        "normalized_value": None, "status": "explicit", "evidence_anchor_ids": ["full:S1"],
        "evidence_text": "mouse", "confidence": .9}
    _, errors = validate_context_extraction(bad, contract, ["generic", "biomedical"])
    assert any("anchor_not_in_observation" in x for x in errors)
    assert any("explicit_value_not_in_evidence" in x for x in errors)

def _fulltext():
    text = "Drug A plus Drug B increased conversion to 80%."
    import hashlib
    return {
        "schema_version": "fulltext_l1_experimental_observation_schema_v3",
        "observation_id": "f1", "polarity": "positive", "canonical_endpoint_id": "ENDPOINT:1",
        "evidence_span_ids": ["s1"], "combination_mode": "concurrent",
        "provenance": {"section": "Results", "source_document_id": "doc",
            "evidence_spans": [{"evidence_span_id": "s1", "anchor_id": "A1", "text": text,
                "text_hash": hashlib.sha256(text.encode()).hexdigest(), "char_start": 0,
                "char_end": len(text), "source_role": "current", "span_type": "observation"}]},
        "experiment": {"experiment_id": "e1", "evidence_family_id": "ef1",
                       "comparison_arm_raw": "control", "species_raw": None},
        "interventions": [
            {"intervention_id": "i1", "agent_mention": "Drug A", "evidence_span_ids": ["s1"]},
            {"intervention_id": "i2", "agent_mention": "Drug B", "evidence_span_ids": ["s1"]}],
        "measurement": {"measurement_dimension": "conversion", "evidence_span_ids": ["s1"]},
        "observation": {"observed_result": "conversion increased to 80%", "evidence_span_ids": ["s1"]},
        "interpretation_raw": None, "interpretation_evidence_span_ids": [],
    }

def test_fulltext_contract_preserves_combination_measurement_and_result():
    contract = build_fulltext_input(_fulltext(), ["generic", "chemistry", "catalysis"])
    chain = contract["experimental_logic_chain"]
    assert len(chain["intervention_or_exposure"]["value"]) == 2
    assert chain["intervention_or_exposure"]["combination_mode"] == "concurrent"
    assert chain["measurement"]["value"] != chain["observed_result"]["value"]
    assert contract["input_mode"] == "fulltext_evidence_chain"


def test_final_extraction_and_pair_prompts_require_json_and_include_valid_examples():
    profiles = ["generic", "biomedical"]
    extraction = extraction_prompt(build_abstract_input(_abstract(), profiles), profiles)
    extraction_body = json.loads(extraction)
    extraction_example = extraction_body["schema_valid_json_example"]
    ContextExtraction.model_validate(extraction_example)

    extraction_a = ContextExtraction.model_validate(_unknown("a", ""))
    extraction_b = ContextExtraction.model_validate(_unknown("b", ""))
    pair = pair_prompt({
        "pair_id": "p",
        "claim_a_extraction": extraction_a.model_dump(mode="json"),
        "claim_b_extraction": extraction_b.model_dump(mode="json"),
    }, profiles)
    pair_body = json.loads(pair)
    _, pair_example_errors = validate_pair_attribution(
        pair_body["schema_valid_json_example"],
        pair_id="example_chemistry_pair",
        extraction_a=ContextExtraction.model_validate({
            **_unknown("example_chemistry_a", ""),
            "domain_profiles": ["generic", "chemistry"],
            "context_factors": [{
                "factor_id": "temperature", "raw_value": "25 C", "normalized_value": None,
                "status": "explicit", "evidence_anchor_ids": ["chem_a:A1"],
                "evidence_text": "25 C", "confidence": .9,
            }],
        }),
        extraction_b=ContextExtraction.model_validate({
            **_unknown("example_chemistry_b", ""),
            "domain_profiles": ["generic", "chemistry"],
            "context_factors": [{
                "factor_id": "temperature", "raw_value": "298.15 K", "normalized_value": None,
                "status": "explicit", "evidence_anchor_ids": ["chem_b:A1"],
                "evidence_text": "298.15 K", "confidence": .9,
            }],
        }),
        profiles=["generic", "chemistry"],
    )
    assert not pair_example_errors

    required = (
        "Return exactly one valid JSON object. "
        "Do not output Markdown or any text outside the JSON object."
    )
    for final_prompt in (extraction, pair):
        assert "json" in final_prompt.casefold()
        assert required in final_prompt
        assert json.loads(final_prompt)["prompt_version"] == "context_attribution_prompts_v2"

def test_registry_has_all_composable_profiles_and_required_metadata():
    registry = load_registry()
    assert set(registry["profiles"]) == {"generic", "biomedical", "clinical", "chemistry", "materials", "catalysis"}
    factors = resolve_factors(list(registry["profiles"]), registry)
    for required in ("species", "population", "reactants", "composition", "catalyst_composition"):
        assert required in factors
        for field in ("value_type", "criticality", "comparison_policy", "normalization_policy",
                      "evidence_requirements", "whether_difference_can_block_comparability",
                      "whether_difference_can_explain_polarity", "prompt_guidance"):
            assert field in factors[required]

def test_pair_validation_cross_anchor_missing_and_unsafe_unit_fail_closed():
    a = ContextExtraction.model_validate({**_unknown("a", ""), "context_factors": [
        {"factor_id": "temperature", "raw_value": "25 C", "normalized_value": None,
         "status": "explicit", "evidence_anchor_ids": ["a1"], "evidence_text": "25 C", "confidence": .9}]})
    b = ContextExtraction.model_validate({**_unknown("b", ""), "context_factors": [
        {"factor_id": "temperature", "raw_value": "80 psi", "normalized_value": None,
         "status": "explicit", "evidence_anchor_ids": ["b1"], "evidence_text": "80 psi", "confidence": .9}]})
    payload = {"schema_version": "context_pair_attribution_v2", "pair_id": "p",
        "claim_a_observation_id": "a", "claim_b_observation_id": "b", "comparability": "conditionally_comparable",
        "factor_comparisons": [{"factor_id": "temperature", "claim_a_value": "25 C",
            "claim_b_value": "80 psi", "status": "equivalent", "comparability_effect": "minor",
            "explanatory_strength": "low", "claim_a_anchor_ids": ["b1"],
            "claim_b_anchor_ids": ["a1"], "reason": "claimed conversion"}],
        "primary_explanatory_factors": [], "missing_critical_information": [],
        "reasoning_summary": "Short evidence summary.", "confidence": .7}
    _, errors = validate_pair_attribution(payload, pair_id="p", extraction_a=a, extraction_b=b,
                                          profiles=["generic", "chemistry"])
    assert any("cross_or_unknown_anchor" in x for x in errors)
    assert "unsafe_unit_equivalence:temperature" in errors

def test_safe_unit_conversion_and_pair_status_schema():
    a = ContextExtraction.model_validate({**_unknown("a", ""), "domain_profiles": ["generic", "chemistry"],
        "context_factors": [{"factor_id": "temperature", "raw_value": "25 C", "normalized_value": None,
        "status": "explicit", "evidence_anchor_ids": ["a1"], "evidence_text": "25 C", "confidence": .9}]})
    b = ContextExtraction.model_validate({**_unknown("b", ""), "domain_profiles": ["generic", "chemistry"],
        "context_factors": [{"factor_id": "temperature", "raw_value": "298.15 K", "normalized_value": None,
        "status": "explicit", "evidence_anchor_ids": ["b1"], "evidence_text": "298.15 K", "confidence": .9}]})
    payload = {"schema_version": "context_pair_attribution_v2", "pair_id": "p",
        "claim_a_observation_id": "a", "claim_b_observation_id": "b", "comparability": "comparable",
        "factor_comparisons": [{"factor_id": "temperature", "claim_a_value": "25 C",
            "claim_b_value": "298.15 K", "status": "equivalent", "comparability_effect": "none",
            "explanatory_strength": "none", "claim_a_anchor_ids": ["a1"],
            "claim_b_anchor_ids": ["b1"], "reason": "Safely convertible temperatures."}],
        "primary_explanatory_factors": [], "missing_critical_information": [],
        "reasoning_summary": "The temperatures are equivalent.", "confidence": .9}
    _, errors = validate_pair_attribution(payload, pair_id="p", extraction_a=a, extraction_b=b,
                                          profiles=["generic", "chemistry"])
    assert not errors

@pytest.mark.parametrize("profile,factor", [
    ("biomedical", "species"), ("clinical", "population"), ("chemistry", "reactants"),
    ("materials", "composition"), ("catalysis", "feed_composition")])
def test_cross_domain_explicit_missing_and_applicability(profile, factor):
    factors = resolve_factors(["generic", profile])
    assert factor in factors
    assert "population" not in factors if profile != "clinical" else "population" in factors

def test_methods_only_result_anchor_and_scientific_state_fields_are_rejected():
    row = _fulltext()
    row["provenance"]["evidence_spans"][0]["source_role"] = "methods"
    contract = build_fulltext_input(row, ["generic", "chemistry"])
    payload = {"schema_version": "observation_context_extraction_v2", "observation_id": "f1",
        "domain_profiles": ["generic", "chemistry"], "input_mode": "fulltext_evidence_chain",
        "context_factors": [{"factor_id": "observed_outcome", "raw_value": "conversion increased to 80%",
            "normalized_value": None, "status": "explicit", "evidence_anchor_ids": ["A1"],
            "evidence_text": row["provenance"]["evidence_spans"][0]["text"], "confidence": .9}],
        "missing_critical_information": [], "warnings": [], "provenance": {}}
    _, errors = validate_context_extraction(payload, contract, ["generic", "chemistry"])
    assert "methods_anchor_cannot_prove_result:observed_outcome" in errors
    payload["polarity"] = "negative"
    with pytest.raises(Exception):
        ContextExtraction.model_validate(payload)

def test_validated_blocking_factor_gate_and_reviewable_safety():
    payload = {"schema_version": "context_pair_attribution_v2", "pair_id": "p",
        "claim_a_observation_id": "a", "claim_b_observation_id": "b", "comparability": "non_comparable",
        "factor_comparisons": [{"factor_id": "species", "claim_a_value": "human",
            "claim_b_value": "mouse", "status": "different", "comparability_effect": "blocking",
            "explanatory_strength": "high", "claim_a_anchor_ids": [], "claim_b_anchor_ids": [],
            "reason": "Different explicitly reported species."}],
        "primary_explanatory_factors": ["species"], "missing_critical_information": [],
        "reasoning_summary": "Species differ.", "confidence": .9, "validation_status": "validated"}
    gate = apply_comparability_gate(payload, ["generic", "biomedical"], existing_formal_eligibility=True)
    assert gate["formal_conflict_eligible"] is False
    payload["validation_status"] = "reviewable"
    assert apply_comparability_gate(payload, ["generic", "biomedical"],
                                    existing_formal_eligibility=True)["formal_conflict_eligible"] is False

def test_candidate_screening_is_endpoint_polarity_bounded_and_cache_sensitive():
    rows = [_abstract("a", polarity="positive"), _abstract("b", polarity="negative"),
            {**_abstract("c", polarity="negative"), "canonical_endpoint_id": "OTHER"}]
    pairs = candidate_pairs(rows)
    assert len(pairs) == 1
    ca = build_abstract_input(rows[0], ["generic"])
    first = extraction_cache_identity(ca, profiles=["generic"], provider="x", model="m")
    ca["evidence_anchors"][0]["text_hash"] = "changed"
    second = extraction_cache_identity(ca, profiles=["generic"], provider="x", model="m")
    assert first != second
    assert pair_cache_identity(first, "b", ["generic"]) != pair_cache_identity(second, "b", ["generic"])

def test_plan_only_zero_api_and_no_variational_em(tmp_path):
    source, output = tmp_path / "source", tmp_path / "output"
    (source / "artifacts").mkdir(parents=True)
    (source / "artifacts" / "l2_graph_observations.jsonl").write_text(
        "\n".join(json.dumps(x) for x in [_abstract("a", polarity="positive"), _abstract("b", polarity="negative")]) + "\n")
    (source / "artifacts" / "weak_conflict_candidates.jsonl").write_text(json.dumps({
        "candidate_id": "existing-1", "eligible_for_weak_conflict": True,
        "supporting_observation_ids": ["a"], "opposing_or_contextual_observation_ids": ["b"]}) + "\n")
    result = run_context_attribution(input_run=source, output_run=output, mode="abstract-only",
        profiles=["generic", "biomedical"], provider="offline", model="fixture")
    assert result["plan_only"] and result["candidate_pair_count"] == 1
    summary = json.loads((output / "artifacts/context_attribution_summary.json").read_text())
    assert summary["api_calls"] == summary["network_calls"] == 0
    assert result["activation"] is False
    obs = [{"evidence_id": "1", "triple_id": "1", "source_asset": "x", "doi": "", "article_title": "",
            "evidence_sentence": "x", "relation_sign": 1, "context": {}, "subject": "s", "object": "o",
            "confidence": 1}, {"evidence_id": "2", "triple_id": "2", "source_asset": "y", "doi": "",
            "article_title": "", "evidence_sentence": "y", "relation_sign": -1, "context": {},
            "subject": "s", "object": "o", "confidence": 1}]
    with patch("code_engine.graph.context_attribution.run_variational_em_attribution") as em:
        em.return_value = ("HYPOXIA", .5, .4)
        build_conflict_graph(obs, latent_pool=[])
        em.assert_not_called()
        build_conflict_graph(obs, latent_pool=[], context_attribution_mode="variational_em_experimental")
        em.assert_called()

def test_offline_fixture_execution_is_resumable_and_reviewable_never_confirms(tmp_path):
    source, output = tmp_path / "source", tmp_path / "output"
    (source / "artifacts").mkdir(parents=True)
    rows = [_abstract("a", polarity="positive"), _abstract("b", polarity="negative")]
    (source / "artifacts/l2_graph_observations.jsonl").write_text(
        "".join(json.dumps(x) + "\n" for x in rows))
    (source / "artifacts/weak_conflict_candidates.jsonl").write_text(json.dumps({
        "candidate_id": "existing-1", "eligible_for_weak_conflict": True,
        "supporting_observation_ids": ["a"], "opposing_or_contextual_observation_ids": ["b"]}) + "\n")
    pair = {"schema_version": "context_pair_attribution_v2", "pair_id": "existing-1",
        "claim_a_observation_id": "a", "claim_b_observation_id": "b",
        "comparability": "insufficient_information",
        "factor_comparisons": [{"factor_id": "species", "claim_a_value": "unknown",
            "claim_b_value": "unknown", "status": "missing_both", "comparability_effect": "unknown",
            "explanatory_strength": "unknown", "claim_a_anchor_ids": [], "claim_b_anchor_ids": [],
            "reason": "Neither sentence reports species."}],
        "primary_explanatory_factors": [], "missing_critical_information": ["species"],
        "reasoning_summary": "Species is missing from both supplied sentences.", "confidence": .8}
    fixture = tmp_path / "fixture.json"
    fixture.write_text(json.dumps({"extractions": {"a": _unknown("a", ""), "b": _unknown("b", "")},
                                   "pairs": {"existing-1": pair}}))
    first = run_context_attribution(input_run=source, output_run=output, mode="abstract-only",
        profiles=["generic", "biomedical"], provider="offline", model="fixture",
        execute=True, fixture_responses=fixture)
    assert first["api_calls"] == first["network_calls"] == 0
    handoff = json.loads((output / "artifacts/context_attribution_handoff.jsonl").read_text())
    assert handoff["formal_conflict_eligibility"] is False
    second = run_context_attribution(input_run=source, output_run=output, mode="abstract-only",
        profiles=["generic", "biomedical"], provider="offline", model="fixture",
        execute=True, cached_only=True, resume=True)
    assert second["extraction_cache_hits"] == 2
    assert second["comparison_cache_hits"] == 1
    assert second["api_calls"] == 0

def _write_planning_run(root, count=11):
    (root / "artifacts").mkdir(parents=True)
    rows = [_abstract(f"o{i}", sentence=f"Condition {i} changed endpoint.", polarity="positive" if i % 2 == 0 else "negative")
            for i in range(count)]
    (root / "artifacts/l2_graph_observations.jsonl").write_text("".join(json.dumps(x) + "\n" for x in rows))
    candidates = []
    for i in range(count):
        candidates.append({"candidate_id": f"p{i:02d}", "eligible_for_weak_conflict": True,
                           "supporting_observation_ids": [f"o{i}"],
                           "opposing_or_contextual_observation_ids": [f"o{(i + 1) % count}"],
                           "context_match": "compatible", "context_terms_left": [], "context_terms_right": []})
    (root / "artifacts/weak_conflict_candidates.jsonl").write_text(
        "".join(json.dumps(x) + "\n" for x in candidates))

def test_smoke_selection_is_deterministic_stratified_and_not_input_prefix():
    a1, a2 = _abstract("a1"), _abstract("a2", polarity="negative")
    f1, f2, f3 = _fulltext(), _fulltext(), _fulltext()
    f1["observation_id"], f2["observation_id"], f3["observation_id"] = "f1", "f2", "f3"
    f1["experiment"]["experimental_unit_raw"] = f2["experiment"]["experimental_unit_raw"] = "A549"
    f3["experiment"]["experimental_unit_raw"] = "mouse tissue"
    f1["interventions"].append(dict(f1["interventions"][0], intervention_id="i3"))
    pairs = [
        {"pair_id": "p-redundant-1", "claim_a": f2, "claim_b": f3, "candidate_record": {}},
        {"pair_id": "p-redundant-2", "claim_a": f2, "claim_b": f3, "candidate_record": {}},
        {"pair_id": "p-redundant-3", "claim_a": f2, "claim_b": f3, "candidate_record": {}},
        {"pair_id": "p-redundant-4", "claim_a": f2, "claim_b": f3, "candidate_record": {}},
        {"pair_id": "p-redundant-5", "claim_a": f2, "claim_b": f3, "candidate_record": {}},
        {"pair_id": "p-aa", "claim_a": a1, "claim_b": a2, "candidate_record": {}},
        {"pair_id": "p-af", "claim_a": a1, "claim_b": f1, "candidate_record": {}},
        {"pair_id": "p-ff-same-multi", "claim_a": f1, "claim_b": f2, "candidate_record": {}},
    ]
    first = representative_smoke_selection(pairs, 5)
    second = representative_smoke_selection(list(reversed(pairs)), 5)
    assert first["selected_pair_ids"] == second["selected_pair_ids"]
    assert first["selected_pair_ids"] != [x["pair_id"] for x in pairs[:5]]
    coverage = first["category_coverage"]
    assert coverage["abstract_abstract"]["selected"]
    assert coverage["fulltext_fulltext"]["selected"]
    assert coverage["abstract_fulltext"]["selected"]
    assert coverage["multi_intervention"]["selected"]
    assert coverage["complex_fulltext_logic_chain"]["selected"]

def test_smoke_closure_and_call_bound_fail_closed(tmp_path):
    source, output = tmp_path / "source", tmp_path / "smoke"
    _write_planning_run(source)
    plan = run_context_attribution(input_run=source, output_run=output, mode="combined",
        profiles=["generic", "biomedical"], provider="deepseek", model="deepseek-v4-pro",
        purpose="smoke", smoke_pair_count=5, extraction_limit=50, comparison_limit=50)
    endpoints = {oid for x in plan["selected_pairs"] for oid in (x["claim_a_id"], x["claim_b_id"])}
    assert endpoints == set(plan["selected_observation_ids"])
    assert endpoints == set(plan["planned_extraction_observation_ids"])
    assert plan["extraction_calls_planned"] == len(endpoints)
    assert plan["comparison_calls_planned"] == 5
    assert plan["provider_calls_hard_bound"] == len(endpoints) + 5
    assert plan["coverage_complete"] is False
    assert plan["api_enabled"] is False
    assert plan["provider_calls"] == plan["network_calls"] == plan["downloads"] == 0
    assert plan["credential_values_read"] is False
    blocked = run_context_attribution(input_run=source, output_run=tmp_path / "blocked", mode="combined",
        profiles=["generic", "biomedical"], provider="offline", model="fixture",
        purpose="smoke", smoke_pair_count=5, extraction_limit=1, comparison_limit=5)
    assert blocked["plan_status"] == "blocked_by_call_bound"
    assert blocked["comparison_calls_planned"] == 0
    selected_pair_ids = {x["pair_id"] for x in blocked["selected_pairs"]}
    assert all(x["reason"] == "missing_extraction" for x in blocked["unprocessed_pairs"]
               if x["pair_id"] in selected_pair_ids)

def test_complete_coverage_and_insufficient_cap_status(tmp_path):
    source = tmp_path / "source"
    _write_planning_run(source)
    complete = run_context_attribution(input_run=source, output_run=tmp_path / "complete", mode="combined",
        profiles=["generic", "biomedical"], provider="deepseek", model="deepseek-v4-pro",
        purpose="complete", extraction_limit=11, comparison_limit=11)
    assert complete["observation_count"] == complete["selected_observation_count"] == 11
    assert complete["candidate_pair_count"] == complete["selected_pair_count"] == 11
    assert complete["extraction_calls_planned"] == 11
    assert complete["comparison_calls_planned"] == 11
    assert complete["provider_calls_hard_bound"] == 22
    assert complete["coverage_complete"] is True
    assert complete["plan_status"] == "ready_complete"
    blocked = run_context_attribution(input_run=source, output_run=tmp_path / "incomplete", mode="combined",
        profiles=["generic", "biomedical"], provider="deepseek", model="deepseek-v4-pro",
        purpose="complete", extraction_limit=10, comparison_limit=11)
    assert blocked["coverage_complete"] is False
    assert blocked["plan_status"] == "blocked_by_call_bound"

def test_unavailable_smoke_categories_are_explicit():
    pairs = [{"pair_id": "aa", "claim_a": _abstract("a"), "claim_b": _abstract("b"),
              "candidate_record": {"context_terms_left": [], "context_terms_right": []}}]
    result = representative_smoke_selection(pairs, 5)
    unavailable = result["category_coverage"]["fulltext_fulltext"]
    assert unavailable == {"requested_category": "fulltext_fulltext", "available": False,
                           "selected": False, "selected_pair_ids": [],
                           "reason": "category_not_present_in_current_candidate_pairs"}

def test_shared_provider_defaults_and_explicit_overrides(tmp_path, monkeypatch):
    source = tmp_path / "source"
    _write_planning_run(source, count=2)
    monkeypatch.setenv("L1_PROVIDER", "deepseek")
    monkeypatch.setenv("MODEL_NAME", "deepseek-v4-pro")
    default = run_context_attribution(input_run=source, output_run=tmp_path / "default", mode="combined",
        profiles=["generic", "biomedical"], purpose="smoke")
    assert (default["provider"], default["model"], default["thinking_mode"]) == (
        "deepseek", "deepseek-v4-pro", "disabled")
    assert default["provider_configuration_source"]["provider"] == "L1_PROVIDER"
    override = run_context_attribution(input_run=source, output_run=tmp_path / "override", mode="combined",
        profiles=["generic", "biomedical"], purpose="smoke",
        provider="openai", model="gpt-test", thinking_mode="provider_default")
    assert (override["provider"], override["model"], override["thinking_mode"]) == (
        "openai", "gpt-test", "provider_default")
    assert set(override["provider_configuration_source"].values()) >= {"override"}

class _RecordingContextClient:
    def __init__(self):
        self.calls = []
    def extract_json_result(self, prompt, **kwargs):
        self.calls.append((json.loads(prompt), kwargs))
        body = self.calls[-1][0]
        if body["task"] == "observation_context_extraction":
            oid = body["input"]["observation_id"]
            return JSONExtractionResult(payload=_unknown(oid, ""), raw_response="{}")
        pair_input = body["input"]
        a = pair_input["claim_a_extraction"]["observation_id"]
        b = pair_input["claim_b_extraction"]["observation_id"]
        return JSONExtractionResult(payload={
            "schema_version": "context_pair_attribution_v2", "pair_id": pair_input["pair_id"],
            "claim_a_observation_id": a, "claim_b_observation_id": b,
            "comparability": "insufficient_information",
            "factor_comparisons": [{"factor_id": "species", "claim_a_value": "unknown",
                "claim_b_value": "unknown", "status": "missing_both", "comparability_effect": "unknown",
                "explanatory_strength": "unknown", "claim_a_anchor_ids": [], "claim_b_anchor_ids": [],
                "reason": "Species is absent."}],
            "primary_explanatory_factors": [], "missing_critical_information": ["species"],
            "reasoning_summary": "Species is absent from both claims.", "confidence": .8,
        }, raw_response="{}")

def test_context_execution_uses_shared_l1_factory_and_fulltext_request_contract(tmp_path, monkeypatch):
    source = tmp_path / "source"
    _write_planning_run(source, count=2)
    client = _RecordingContextClient()
    factory = patch("code_engine.context_attribution.runner.build_l1_client_from_env_or_config",
                    return_value=client)
    with factory as shared:
        result = run_context_attribution(input_run=source, output_run=tmp_path / "execution",
            mode="combined", profiles=["generic", "biomedical"], purpose="smoke",
            smoke_pair_count=1,
            provider="deepseek", model="deepseek-v4-pro", thinking_mode="disabled",
            extraction_limit=2, comparison_limit=1, execute=True, api=True)
    shared.assert_called_once_with("deepseek", "deepseek-v4-pro", max_retries=0)
    assert result["status"] == "completed"
    assert len(client.calls) == 3
    for _, kwargs in client.calls:
        assert kwargs == {"model": "deepseek-v4-pro", "temperature": 0, "top_p": 1,
                          "max_tokens": 32768, "retry_on_length": False,
                          "thinking_mode": "disabled"}

class _Systemic400Client:
    def __init__(self):
        self.calls = 0
    def extract_json_result(self, prompt, **kwargs):
        self.calls += 1
        error = DeepSeekExtractionError(
            "deepseek_extraction_failed", "400", 1, error_kind="configuration",
            retryable=False, status_code=400,
            raw_response='{"error":{"message":"bad request","api_key":"SECRET","auth":"Bearer token"}}',
            provider_metadata={"request_endpoint": DeepSeekClient.endpoint,
                               "response_format": {"type": "json_object"},
                               "json_output_enabled": True},
        )
        error.error_type = "api_error"
        raise error

def test_systemic_400_is_redacted_ledgered_and_stops_immediately(tmp_path):
    source = tmp_path / "source"
    _write_planning_run(source, count=2)
    client = _Systemic400Client()
    with patch("code_engine.context_attribution.runner.build_l1_client_from_env_or_config",
               return_value=client):
        result = run_context_attribution(input_run=source, output_run=tmp_path / "failed",
            mode="combined", profiles=["generic", "biomedical"], purpose="smoke",
            smoke_pair_count=1,
            provider="deepseek", model="deepseek-v4-pro", thinking_mode="disabled",
            extraction_limit=2, comparison_limit=1, execute=True, api=True)
    assert result["status"] == "failed_systemic_provider_error"
    assert result["provider_calls"] == result["api_calls"] == result["network_calls"] == 1
    assert client.calls == 1
    ledger = [json.loads(x) for x in (tmp_path / "failed/artifacts/context_attribution_execution_ledger.jsonl").read_text().splitlines()]
    failed = [x for x in ledger if x["status"] == "failed_systemic_provider_400"]
    assert len(failed) == 1
    diagnostic = failed[0]["provider_diagnostic"]
    assert diagnostic["status_code"] == 400
    assert diagnostic["call_type"] == "extraction"
    assert diagnostic["request_endpoint"] == DeepSeekClient.endpoint
    serialized = json.dumps(ledger)
    assert "SECRET" not in serialized and "Bearer token" not in serialized
    assert sum(x["status"] == "pending" for x in ledger) == 2
    assert result["activation"] is False and result["active_pointer_unchanged"] is True

def test_shared_deepseek_preserves_safe_400_body_and_request_contract(monkeypatch):
    captured = {}
    def fake_post(url, *, content, headers, timeout):
        captured["url"] = url
        captured["payload"] = json.loads(content)
        captured["authorization_present"] = "Authorization" in headers
        return httpx.Response(400, request=httpx.Request("POST", url),
                              text='{"error":{"message":"invalid request","api_key":"TOPSECRET"}}')
    monkeypatch.setattr(httpx, "post", fake_post)
    client = DeepSeekClient("TOPSECRET", max_retries=0)
    with pytest.raises(DeepSeekExtractionError) as caught:
        client.extract_json_result("{}", model="deepseek-v4-pro", temperature=0, top_p=1,
                                   max_tokens=32768, retry_on_length=False,
                                   thinking_mode="disabled")
    assert captured["url"] == DeepSeekClient.endpoint
    assert captured["payload"] == {
        "model": "deepseek-v4-pro", "messages": [{"role": "system", "content": "{}"}],
        "response_format": {"type": "json_object"}, "temperature": 0, "top_p": 1.0,
        "max_tokens": 32768, "thinking": {"type": "disabled"},
    }
    assert captured["authorization_present"]
    assert caught.value.status_code == 400
    assert "invalid request" in caught.value.raw_response
    assert "TOPSECRET" not in caught.value.raw_response

def test_plan_only_does_not_construct_client_or_expose_credentials(tmp_path, monkeypatch):
    source = tmp_path / "source"
    _write_planning_run(source, count=2)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "DO_NOT_LOG")
    with patch("code_engine.context_attribution.runner.build_l1_client_from_env_or_config") as factory:
        plan = run_context_attribution(input_run=source, output_run=tmp_path / "plan",
            mode="combined", profiles=["generic", "biomedical"], purpose="smoke")
    factory.assert_not_called()
    assert plan["provider_calls"] == plan["network_calls"] == 0
    assert plan["credential_values_read"] is False
    assert "DO_NOT_LOG" not in json.dumps(plan)
