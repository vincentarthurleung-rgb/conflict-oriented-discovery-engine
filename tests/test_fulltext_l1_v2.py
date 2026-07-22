import json
from pathlib import Path

import pytest
from pydantic import ValidationError

import code_engine.fulltext.fulltext_l1_v2 as l1_v2
from code_engine.fulltext.fulltext_l1_extractor import fulltext_l1_cache_key
from code_engine.fulltext.fulltext_l1_v2 import (
    SCHEMA_VERSION, build_prompt, cache_key, observation_as_legacy_claim, parse_response,
    run_fulltext_l1_v2_extraction,
)
from code_engine.fulltext.input_preparation import execute_missing_only, prepare_fulltext_inputs
from code_engine.fulltext.reasoning_trace import evidence_chains_from_v2_observations, run_fulltext_reasoning_trace_stage
from code_engine.schemas.fulltext_observation import measurement_dimension_values


def span(text, kind="observation"):
    return {"text": text, "span_type": kind, "section": "Results", "sentence_id": "s1"}


def observation(observation_id="o1", experiment_id="e1", *, intervention_type="overexpression",
                intervention_sign=1, outcome_sign=1, species="human", design_type="in_vitro",
                dimension="morphology_marker_panel", role="current_study_experiment", outcome="EMT"):
    sentence = f"COPS8 {intervention_type} changed {outcome}."
    return {
        "schema_version": SCHEMA_VERSION, "observation_id": observation_id,
        "provenance": {"paper_id": "P1", "pmid": "1", "pmcid": "PMC1", "source_document_id": "PMC1",
                       "section": "Results", "sentence_ids": ["s1"], "evidence_spans": [span(sentence)],
                       "fulltext_source_hash": "source"},
        "experiment": {"experiment_id": experiment_id, "evidence_family_id": f"ef_{experiment_id}",
                       "design_type": design_type, "species": species, "species_source": "explicit Results text" if species else None,
                       "cell_line": "HCT116" if species == "human" else None, "comparison_arm": "vector control",
                       "context_source": ["current_evidence_span"], "binding_confidence": .95},
        "intervention": {"intervention_target_mention": "COPS8", "intervention_type": intervention_type,
                         "intervention_sign": intervention_sign, "intervention_span": span(sentence, "intervention")},
        "measurement": {"outcome_mention": outcome, "measured_entity_mention": outcome,
                        "measurement_dimension": dimension, "assay": "immunoblot",
                        "measurement_span": span(sentence, "measurement")},
        "observation": {"observed_result": sentence, "observed_outcome_sign": outcome_sign,
                        "observation_span": span(sentence)},
        "author_interpretation": {"author_interpretation": None, "author_conclusion": None},
        "candidate_relation": {"subject_mention": "COPS8", "object_mention": outcome,
                               "relation_raw": "changed", "lexical_direction": "positive" if outcome_sign == 1 else "negative",
                               "evidence_design_candidate": "gain_of_function" if intervention_sign == 1 else "loss_of_function"},
        "statement_role": role,
    }


@pytest.mark.parametrize("row", [
    observation("gof"),
    observation("lof", intervention_type="silencing", intervention_sign=-1, outcome_sign=-1),
    observation("rescue", intervention_type="rescue", intervention_sign=1),
    observation("drug", intervention_type="drug_treatment", intervention_sign=-1),
    observation("human", species="human"),
    observation("mouse", experiment_id="xeno", species="mouse", design_type="in_vivo"),
    observation("biopsy", intervention_type="observational_no_intervention", intervention_sign=0, dimension="abundance_expression", design_type="patient_sample"),
    observation("review", intervention_type="observational_no_intervention", intervention_sign=0, role="review"),
    observation("pakt", outcome="P-AKT", dimension="phosphorylation"),
    observation("endpoint2", experiment_id="e1", outcome="migration", dimension="migration"),
])
def test_prompt_parser_fixtures_are_strict_and_grounded(row):
    parsed = parse_response({"schema_version": SCHEMA_VERSION, "experimental_observations": [row]})
    assert parsed[0]["experiment"]["experiment_id"] == row["experiment"]["experiment_id"]
    assert parsed[0]["provenance"]["evidence_spans"]


def test_two_experiments_and_multiple_endpoints_retain_identity():
    rows = [observation("a", "e1"), observation("b", "e1", outcome="migration", dimension="migration"), observation("c", "e2", species="mouse", design_type="in_vivo")]
    parsed = parse_response({"schema_version": SCHEMA_VERSION, "experimental_observations": rows})
    assert len({x["experiment"]["experiment_id"] for x in parsed}) == 2
    assert parsed[0]["experiment"]["evidence_family_id"] == parsed[1]["experiment"]["evidence_family_id"]
    assert parsed[0]["experiment"]["species"] != parsed[2]["experiment"]["species"]


def test_prompt_lists_schema_measurement_dimensions_from_single_source():
    prompt = build_prompt({}, {"paper_metadata": {}, "text": "fixture"})
    for value in measurement_dimension_values():
        assert f'"{value}"' in prompt
    assert 'output "unknown"' in prompt
    assert "Never invent a new measurement_dimension label" in prompt
    assert "do not put an assay name, unit, or measured entity" in prompt


@pytest.mark.parametrize(("raw", "canonical"), [
    ("protein_level", "abundance_expression"),
    ("protein_expression", "abundance_expression"),
    ("mrna_expression", "abundance_expression"),
    ("mRNA_level", "abundance_expression"),
    ("gene_expression", "abundance_expression"),
    ("phosphorylation_level", "phosphorylation"),
    ("phospho_status", "phosphorylation"),
    ("phosphorylated", "phosphorylation"),
    ("activation_level", "activation_activity"),
    ("pathway_activation", "activation_activity"),
    ("cell_survival", "viability"),
    ("proliferative_capacity", "proliferation"),
])
def test_measurement_dimension_aliases_are_whitelist_canonicalized(raw, canonical):
    row = observation(dimension=raw); audit = []
    parsed = parse_response({"schema_version": SCHEMA_VERSION, "experimental_observations": [row]}, normalization_audit=audit)
    assert parsed[0]["measurement"]["measurement_dimension"] == canonical
    assert audit == [{
        "observation_id": "o1", "observation_index": 0, "measurement_dimension_raw": raw,
        "measurement_dimension_normalized": canonical, "status": "canonicalized",
        "mapping_rule": f"measurement_dimension_aliases_v1:{l1_v2._alias_key(raw)}", "reason": "whitelisted_alias",
    }]


def test_unknown_measurement_dimension_is_not_fuzzily_mapped_and_audit_survives():
    row = observation(dimension="protein_abundance_score"); audit = []
    with pytest.raises(ValidationError):
        parse_response({"schema_version": SCHEMA_VERSION, "experimental_observations": [row]}, normalization_audit=audit)
    assert audit[0]["measurement_dimension_raw"] == "protein_abundance_score"
    assert audit[0]["measurement_dimension_normalized"] is None
    assert audit[0]["reason"] == "measurement_dimension_alias_not_whitelisted"
    assert row["measurement"]["measurement_dimension"] == "protein_abundance_score"


def test_missing_span_and_extra_formal_decision_fail_closed():
    row = observation(); row["provenance"]["evidence_spans"] = []
    with pytest.raises(ValidationError): parse_response({"schema_version": SCHEMA_VERSION, "experimental_observations": [row]})
    row = observation(); row["strict_core_eligible"] = True
    with pytest.raises(ValidationError): parse_response({"schema_version": SCHEMA_VERSION, "experimental_observations": [row]})


def test_v1_and_v2_cache_keys_are_isolated_and_prompt_config_sensitive():
    v1 = fulltext_l1_cache_key({"pmcid": "PMC1"}, {"section_index": 1}, "chunk", provider="p", model="m", chunker_config_hash="c")
    base = dict(source_fulltext_hash="source", chunk_hash="chunk", provider="p", model="m", config_hash="c", candidate_prior_hash="prior")
    v2 = cache_key(**base)
    assert v1 != v2
    assert v2 != cache_key(**{**base, "config_hash": "changed"})
    assert cache_key(**base, thinking_mode="disabled") != cache_key(**base, thinking_mode="enabled")
    assert cache_key(**base, thinking_mode="disabled") != cache_key(**base, thinking_mode="provider_default")


def test_prompt_and_parser_versions_change_cache_identity(monkeypatch):
    args = dict(source_fulltext_hash="source", chunk_hash="chunk", provider="p", model="m", config_hash="c", candidate_prior_hash="prior")
    current = cache_key(**args)
    monkeypatch.setattr(l1_v2, "PROMPT_VERSION", "incompatible_prompt")
    prompt_changed = cache_key(**args)
    assert prompt_changed != current
    monkeypatch.setattr(l1_v2, "PARSER_VERSION", "incompatible_parser")
    assert cache_key(**args) != prompt_changed


def test_v2_extractor_fixture_then_reasoning_chain_without_network(tmp_path):
    artifacts = tmp_path / "run/artifacts"; article = artifacts / "fulltext/pmc_oa/PMC1"; article.mkdir(parents=True)
    (artifacts / "candidates.jsonl").write_text(json.dumps({"paper_id": "P1", "pmid": "1", "pmcid": "PMC1", "abstract_observation_ids": ["abs1"]}) + "\n")
    (article / "article_text.json").write_text(json.dumps({"sections": [{"section_title": "Results", "text": "COPS8 overexpression induced EMT."}]}))
    class Client:
        def extract_json(self, *_args, **_kwargs): return {"schema_version": SCHEMA_VERSION, "experimental_observations": [observation()]}
    result = run_fulltext_l1_v2_extraction(run_dir=tmp_path / "run", fulltext_candidates_path=artifacts / "candidates.jsonl", parsed_articles_dir=artifacts / "fulltext/pmc_oa", l1_provider="fixture", l1_model="fixture", api_enabled=True, network_enabled=True, client=Client())
    assert result["summary"]["observation_count"] == 1
    assert result["claims"][0]["intervention_sign"] == 1
    chains = evidence_chains_from_v2_observations(result["observations"])
    assert chains[0]["experiment_id"] == "e1"
    assert chains[0]["measurement_dimension"] == "morphology_marker_panel"
    class MustNotCall:
        def extract_json(self, *_args, **_kwargs): raise AssertionError("v2 structured trace must not make a second paid call")
    summary = run_fulltext_reasoning_trace_stage(tmp_path / "run", api_enabled=True, network_enabled=True, client=MustNotCall())
    assert summary["api_call_count"] == 0
    generated = [json.loads(x) for x in (artifacts / "experimental_evidence_chains.jsonl").read_text().splitlines()]
    assert generated[0]["extraction_origin"] == "fulltext_l1_v2"


def test_parse_failure_caches_raw_response_but_emits_no_observation(tmp_path):
    artifacts = tmp_path / "run/artifacts"; article = artifacts / "fulltext/pmc_oa/PMC1"; article.mkdir(parents=True)
    (artifacts / "candidates.jsonl").write_text(json.dumps({"paper_id": "P1", "pmcid": "PMC1"}) + "\n")
    (article / "article_text.json").write_text(json.dumps({"sections": [{"section_title": "Results", "text": "result"}]}))
    class BadClient:
        def extract_json(self, *_args, **_kwargs): return {"claims": [{"subject": "A"}]}
    result = run_fulltext_l1_v2_extraction(run_dir=tmp_path / "run", fulltext_candidates_path=artifacts / "candidates.jsonl", parsed_articles_dir=artifacts / "fulltext/pmc_oa", l1_provider="fixture", l1_model="fixture", api_enabled=True, network_enabled=True, client=BadClient())
    assert not result["observations"] and result["summary"]["parse_errors"] == 1
    assert list((artifacts / "cache/fulltext_l1_v2").glob("*.raw_error.json"))


def test_unknown_dimension_failure_preserves_raw_and_reason_in_parser_audit(tmp_path):
    artifacts = tmp_path / "run/artifacts"; article = artifacts / "fulltext/pmc_oa/PMC1"; article.mkdir(parents=True)
    (artifacts / "candidates.jsonl").write_text(json.dumps({"paper_id": "P1", "pmcid": "PMC1"}) + "\n")
    (article / "article_text.json").write_text(json.dumps({"sections": [{"section_title": "Results", "text": "result"}]}))
    class Client:
        def extract_json(self, *_args, **_kwargs):
            return {"schema_version": SCHEMA_VERSION, "experimental_observations": [observation(dimension="protein_abundance_score")]}
    result = run_fulltext_l1_v2_extraction(run_dir=tmp_path / "run", fulltext_candidates_path=artifacts / "candidates.jsonl", parsed_articles_dir=artifacts / "fulltext/pmc_oa", l1_provider="fixture", l1_model="fixture", api_enabled=True, network_enabled=True, client=Client())
    assert result["observations"] == []
    assert result["summary"]["parse_errors"] == 1
    audit = result["parser_normalization_audit"][0]
    assert audit["measurement_dimension_raw"] == "protein_abundance_score"
    assert audit["reason"] == "measurement_dimension_alias_not_whitelisted"
    raw_error = json.loads(next((artifacts / "cache/fulltext_l1_v2").glob("*.raw_error.json")).read_text())
    assert raw_error["raw_response"]["experimental_observations"][0]["measurement"]["measurement_dimension"] == "protein_abundance_score"
    assert raw_error["parser_normalization_audit"][0]["measurement_dimension_normalized"] is None


def test_successful_alias_block_recovers_from_new_v2_cache(tmp_path):
    artifacts = tmp_path / "run/artifacts"; article = artifacts / "fulltext/pmc_oa/PMC1"; article.mkdir(parents=True)
    candidates = artifacts / "candidates.jsonl"
    candidates.write_text(json.dumps({"paper_id": "P1", "pmcid": "PMC1"}) + "\n")
    (article / "article_text.json").write_text(json.dumps({"sections": [{"section_title": "Results", "text": "result"}]}))
    class First:
        def extract_json(self, *_args, **_kwargs): return {"schema_version": SCHEMA_VERSION, "experimental_observations": [observation(dimension="protein_level")]}
    args = dict(run_dir=tmp_path / "run", fulltext_candidates_path=candidates, parsed_articles_dir=artifacts / "fulltext/pmc_oa", l1_provider="fixture", l1_model="fixture", api_enabled=True, network_enabled=True)
    first = run_fulltext_l1_v2_extraction(**args, client=First())
    class MustNotCall:
        def extract_json(self, *_args, **_kwargs): raise AssertionError("successful block should be recovered")
    second = run_fulltext_l1_v2_extraction(**args, client=MustNotCall())
    assert first["observations"][0]["measurement"]["measurement_dimension"] == "abundance_expression"
    assert second["summary"]["cache_hits"] == 1 and second["summary"]["api_calls_made"] == 0
    assert second["parser_normalization_audit"][0]["measurement_dimension_raw"] == "protein_level"
    cached = json.loads(next((artifacts / "cache/fulltext_l1_v2").glob("*.json")).read_text())
    assert cached["configured_thinking_mode"] == "disabled"
    assert cached["effective_thinking_mode"] == "disabled"
    assert cached["thinking_parameter_sent"] is True


def test_cached_and_missing_input_plan_and_retry_ledger(tmp_path):
    candidates = tmp_path / "candidates.jsonl"; root = tmp_path / "fulltext"; cached = root / "PMC1"; cached.mkdir(parents=True)
    (cached / "article_text.json").write_text("{}")
    candidates.write_text("\n".join(json.dumps(x) for x in ({"pmcid": "PMC1"}, {"pmcid": "PMC2"}, {"pmcid": "PMC2"})) + "\n")
    ledger = tmp_path / "retry.jsonl"; plan = prepare_fulltext_inputs(candidates_path=candidates, fulltext_root=root, retry_ledger_path=ledger)
    assert plan["cached_ready_count"] == 1 and plan["missing_count"] == 1 and plan["download_calls"] == 0
    result = execute_missing_only(plan, downloader=lambda _: {"full_text_status": "unavailable", "reason": "temporary"}, retry_ledger_path=ledger)
    assert result["attempted"] == 1
    assert json.loads(ledger.read_text().splitlines()[0])["retryable"] is True


def test_compatibility_adapter_never_outputs_formal_decisions():
    claim = observation_as_legacy_claim(observation())
    assert "canonical_id" not in claim and "strict_core_eligible" not in claim and "derived_causal_sign" not in claim
