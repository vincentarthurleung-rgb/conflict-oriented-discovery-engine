import copy
import json

import pytest

from code_engine.fulltext.fulltext_l1_v2 import build_prompt, recover_fulltext_l1_v2_offline
from code_engine.fulltext.fulltext_l1_v2_migration import (
    HistoricalMigrationError, TrustedBlockContext, deterministic_observation_id,
    locate_evidence_span, migrate_historical_response,
)
from code_engine.schemas.fulltext_observation import (
    AuthorInterpretationDetail, CandidateRelation, DocumentProvenance, EvidenceSpan,
    ExperimentContext, ExperimentalObservationV2, FulltextL1V2Response,
    InterventionDetail, MeasurementDetail, ObservationDetail,
    fulltext_l1_v2_prompt_examples,
)


EVIDENCE = "HIF1A knockdown decreased target expression versus control."


def context(text=EVIDENCE):
    return TrustedBlockContext(
        run_id="run-1", block_id="block-1", parent_block_id="parent-1", text=text,
        source_block_hash="block-hash", source_document_id="PMC1", paper_id="paper-1",
        pmid="1", pmcid="PMC1", fulltext_source_hash="article-hash",
        source_artifact="article_text.json",
    )


def legacy_row():
    return {
        "provenance": {"evidence_span": EVIDENCE},
        "experiment": {"experiment_id": "exp-1", "evidence_family_id": "family-1",
                       "model_organism": "human", "experimental_system": "cells"},
        "intervention": {"type": "knockdown", "target": "HIF1A"},
        "measurement": {"dimension": "abundance_expression", "entity": "target"},
        "observation": {"direction": "decreased", "magnitude": None},
        "author_interpretation": None, "candidate_relation": None,
    }


def migrate(row=None, ctx=None):
    return migrate_historical_response(
        {"schema_version": "fulltext_l1_experimental_observation_schema_v2",
         "experimental_observations": [row or legacy_row()]},
        context=ctx or context(), raw_response_path="raw.txt",
        original_prompt_version="v3", original_prompt_hash="old-hash",
    )


def test_prompt_examples_are_complete_schema_owned_and_valid():
    empty, nonempty = fulltext_l1_v2_prompt_examples()
    FulltextL1V2Response.model_validate(empty)
    FulltextL1V2Response.model_validate(nonempty)
    row = nonempty["experimental_observations"][0]
    assert set(row) == set(ExperimentalObservationV2.model_fields)
    for key, model in (("provenance", DocumentProvenance), ("experiment", ExperimentContext),
                       ("intervention", InterventionDetail), ("measurement", MeasurementDetail),
                       ("observation", ObservationDetail),
                       ("author_interpretation", AuthorInterpretationDetail),
                       ("candidate_relation", CandidateRelation)):
        assert set(row[key]) == set(model.model_fields)
    assert set(row["provenance"]["evidence_spans"][0]) == set(EvidenceSpan.model_fields)
    prompt = build_prompt({}, {"paper_metadata": {}, "text": "text"})
    assert "Valid empty JSON output example:" in prompt
    assert "Valid complete non-empty Draft JSON output example:" in prompt
    assert "interventions" in prompt and "measurement_dimension_raw" in prompt
    assert "source_document_id" not in prompt and "observation_id" not in prompt
    assert "Do not use Markdown code fences" in prompt


def test_exact_field_mappings_and_trusted_provenance_validate_strictly():
    payload, audit = migrate()
    row = payload["experimental_observations"][0]
    assert row["experiment"]["species"] == "human"
    assert row["experiment"]["model_system"] == "cells"
    assert row["intervention"]["intervention_type"] == "knockdown"
    assert row["intervention"]["intervention_target_mention"] == "HIF1A"
    assert row["measurement"]["measurement_dimension"] == "abundance_expression"
    assert row["measurement"]["measured_entity_mention"] == "target"
    assert row["observation"]["observed_result"] == "decreased"
    assert row["observation"]["observed_outcome_sign"] is None
    assert row["intervention"]["intervention_sign"] is None
    assert row["provenance"]["source_document_id"] == "PMC1"
    assert row["provenance"]["fulltext_source_hash"] == "article-hash"
    assert any(x["value_source"] == "pipeline_metadata" for x in audit)
    assert row["observation_id"].startswith("ftl1v2_")


def test_unknown_fields_and_conflicting_aliases_fail_closed():
    row = legacy_row(); row["measurement"]["invented_alias"] = "x"
    with pytest.raises(HistoricalMigrationError, match="Extra inputs are not permitted"):
        migrate(row)
    row = legacy_row(); row["experiment"]["species"] = "mouse"
    with pytest.raises(HistoricalMigrationError, match="conflicting source/destination"):
        migrate(row)


def test_evidence_span_requires_unique_verbatim_location_and_hashable_offsets():
    span = locate_evidence_span(EVIDENCE, f"prefix {EVIDENCE} suffix")
    assert span["char_start"] == 7
    assert span["char_end"] == 7 + len(EVIDENCE)
    with pytest.raises(HistoricalMigrationError, match="ambiguous"):
        locate_evidence_span(EVIDENCE, f"{EVIDENCE} / {EVIDENCE}")
    with pytest.raises(HistoricalMigrationError, match="missing"):
        locate_evidence_span(EVIDENCE, "different source")


def test_observation_id_is_stable_and_sensitive_without_formal_fields():
    payload, _ = migrate(); row = payload["experimental_observations"][0]
    span = row["provenance"]["evidence_spans"][0]
    one, details = deterministic_observation_id(row, context(), span)
    two, _ = deterministic_observation_id(copy.deepcopy(row), context(), span)
    assert one == two
    changed = copy.deepcopy(row); changed["measurement"]["measured_entity_mention"] = "other endpoint"
    three, _ = deterministic_observation_id(changed, context(), span)
    assert three != one
    serialized = json.dumps(details)
    assert "candidate_relation" not in serialized
    assert "formal_relation" not in serialized


def test_direction_migration_is_only_for_equivalent_text():
    row = legacy_row(); row["observation"]["direction"] = "causes resistance"
    with pytest.raises(HistoricalMigrationError, match="not equivalent"):
        migrate(row)


def test_offline_recovery_is_zero_call_idempotent_and_keeps_failures(tmp_path, monkeypatch):
    run = tmp_path / "run-1"; artifacts = run / "artifacts"; cache = artifacts / "cache/fulltext_l1_v2"
    article_dir = artifacts / "fulltext/pmc_oa/PMC1"
    cache.mkdir(parents=True); article_dir.mkdir(parents=True)
    (artifacts / "l35_fulltext_oa_candidate_papers.jsonl").write_text(
        json.dumps({"paper_id": "paper-1", "pmid": "1", "pmcid": "PMC1"}) + "\n")
    (article_dir / "article_text.json").write_text(json.dumps({"sections": []}))
    blocks = [
        {"block_id": "b1", "text": EVIDENCE, "chunk_hash": "h1", "paper_metadata": {}},
        {"block_id": "b2", "text": "different source", "chunk_hash": "h2", "paper_metadata": {}},
    ]
    monkeypatch.setattr("code_engine.fulltext.fulltext_l1_v2.build_experiment_blocks", lambda *_a, **_k: blocks)
    empty = {"schema_version": "fulltext_l1_experimental_observation_schema_v2",
             "prompt_version": "old", "prompt_hash": "old-hash", "parser_version": "old-parser",
             "extractor_version": "old-extractor", "source_fulltext_hash": "old-source",
             "response": {"schema_version": "fulltext_l1_experimental_observation_schema_v2",
                          "experimental_observations": []}, "block_provenance": {"block_id": "empty"}}
    (cache / "empty.json").write_text(json.dumps(empty))
    for block_id, evidence in (("b1", EVIDENCE), ("b2", "not in source")):
        row = legacy_row(); row["provenance"]["evidence_span"] = evidence
        raw = cache / f"{block_id}.raw_response.txt"
        raw.write_text(json.dumps({"schema_version": "fulltext_l1_experimental_observation_schema_v2",
                                   "experimental_observations": [row]}))
        error = {"paper_id": "paper-1", "pmid": "1", "pmcid": "PMC1", "block_id": block_id,
                 "cache_key": block_id, "raw_response_path": str(raw), "prompt_hash": "old-hash",
                 "parser_version": "old-parser", "extractor_version": "old-extractor"}
        (cache / f"{block_id}.raw_error.json").write_text(json.dumps(error))
    original_error = (cache / "b2.raw_error.json").read_text()
    first = recover_fulltext_l1_v2_offline(run)
    second = recover_fulltext_l1_v2_offline(run)
    assert first["summary"]["api_calls"] == first["summary"]["network_calls"] == 0
    assert first["summary"]["successfully_migrated_block_count"] == 1
    assert first["summary"]["still_invalid_block_count"] == 1
    assert second["summary"]["successfully_migrated_block_count"] == 1
    assert (cache / "b2.raw_error.json").read_text() == original_error
    recovered = json.loads(next(cache.glob("b1.recovered.*.json")).read_text())
    assert recovered["origin"] == "recovered_from_historical_raw_response"
    assert recovered["original_prompt_hash"] == "old-hash"
    assert recovered["transport_metadata"]["usage_availability"] == "unavailable"
    assert "max_tokens" not in recovered
    executions = [json.loads(x) for x in (artifacts / "fulltext_l1_v2_execution_records.jsonl").read_text().splitlines()]
    assert sum(x.get("status") == "recovered_offline_success" for x in executions) == 1
    summary = json.loads((artifacts / "fulltext_l1_v2_summary.json").read_text())
    assert summary["scientific_input_complete"] is False
    assert summary["consistency_report"]["publication_allowed"] is False
