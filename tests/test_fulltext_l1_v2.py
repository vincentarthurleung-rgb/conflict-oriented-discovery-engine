import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from code_engine.fulltext.fulltext_l1_extractor import fulltext_l1_cache_key
from code_engine.fulltext.fulltext_l1_v2 import (
    SCHEMA_VERSION, cache_key, observation_as_legacy_claim, parse_response,
    run_fulltext_l1_v2_extraction,
)
from code_engine.fulltext.input_preparation import execute_missing_only, prepare_fulltext_inputs
from code_engine.fulltext.reasoning_trace import evidence_chains_from_v2_observations, run_fulltext_reasoning_trace_stage


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
