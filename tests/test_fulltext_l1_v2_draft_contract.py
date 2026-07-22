import copy
import json

import pytest
from pydantic import ValidationError

from code_engine.fulltext.fulltext_l1_draft_hydration import (
    DraftHydrationError, TrustedDraftContext, deterministic_draft_observation_id,
    hydrate_draft_response, locate_exact_evidence, normalize_draft_enum,
)
from code_engine.fulltext.fulltext_l1_v2 import (
    CACHE_IDENTITY_VERSION, PROMPT_VERSION, build_prompt, cache_key, formal_schema_hash,
    prompt_hash, schema_hash,
)
from code_engine.fulltext.fulltext_l1_v2_draft_reparse import (
    adapt_v4_formal_direct_to_draft, reparse_smoke_responses_offline,
)
from code_engine.schemas.fulltext_observation import FulltextL1V2Response, fulltext_l1_v2_prompt_examples
from code_engine.schemas.fulltext_observation_draft import (
    DRAFT_SCHEMA_VERSION, ExperimentalObservationDraft, FulltextL1DraftResponse,
    fulltext_l1_draft_prompt_examples,
)


EVIDENCE = "HIF1A knockdown decreased target-gene expression versus control."


def context(text=f"CURRENT_RESULTS: {EVIDENCE}"):
    return TrustedDraftContext(
        run_id="run", block_id="block", parent_block_id="parent", child_block_id="child",
        block_text=text, source_block_hash="block-hash", source_document_id="PMC1",
        paper_id="paper-1", pmid="1", pmcid="PMC1", fulltext_source_hash="article-hash",
        source_artifact="article_text.json", section="Results",
    )


def draft_response():
    _, payload = fulltext_l1_draft_prompt_examples()
    return FulltextL1DraftResponse.model_validate(payload)


def test_draft_is_strict_has_no_pipeline_identity_and_supports_raw_multi_intervention():
    empty, nonempty = fulltext_l1_draft_prompt_examples()
    FulltextL1DraftResponse.model_validate(empty)
    parsed = FulltextL1DraftResponse.model_validate(nonempty)
    forbidden = {"source_document_id", "paper_id", "fulltext_source_hash", "observation_id", "char_start", "char_end"}
    schema_text = json.dumps(FulltextL1DraftResponse.model_json_schema())
    assert all(name not in schema_text for name in forbidden)
    altered = copy.deepcopy(nonempty)
    altered["experimental_observations"][0]["unexpected"] = True
    with pytest.raises(ValidationError, match="Extra inputs"):
        FulltextL1DraftResponse.model_validate(altered)
    second = copy.deepcopy(parsed.experimental_observations[0].interventions[0])
    second.intervention_type_raw = "stabilization"
    parsed.experimental_observations[0].interventions.append(second)
    assert len(parsed.experimental_observations[0].interventions) == 2


def test_prompt_v7_is_draft_owned_anchored_and_excludes_pipeline_responsibilities():
    prompt = build_prompt({}, {"paper_metadata": {"paper_id": "must-not-appear"}, "text": f"CURRENT_RESULTS: {EVIDENCE}"})
    assert PROMPT_VERSION == "fulltext_experimental_observation_prompt_v7_anchor_id_authoritative"
    assert DRAFT_SCHEMA_VERSION in prompt
    assert "source_document_id" not in prompt and "observation_id" not in prompt
    assert "char_start" not in prompt and "char_end" not in prompt
    assert "canonical" in prompt and "conflict" in prompt and "hypotheses" in prompt
    assert "Do not use Markdown code fences" in prompt
    assert "evidence_anchor_ids" in prompt and "block:S0001" in prompt
    assert "must-not-appear" not in prompt


def test_trusted_hydration_localizes_exact_span_and_generates_stable_sensitive_id():
    draft = draft_response()
    hydrated = hydrate_draft_response(draft, context())
    assert not hydrated.rejected
    formal = FulltextL1V2Response.model_validate(hydrated.formal_response)
    row = formal.experimental_observations[0]
    assert row.provenance.source_document_id == "PMC1"
    assert row.provenance.fulltext_source_hash == "article-hash"
    span = row.observation.observation_span
    assert span is not None and span.char_start == len("CURRENT_RESULTS: ")
    one, detail = deterministic_draft_observation_id(draft.experimental_observations[0], context(), span)
    two, _ = deterministic_draft_observation_id(draft.experimental_observations[0], context(), span)
    changed = draft.model_copy(deep=True)
    changed.experimental_observations[0].measurement.endpoint_raw = "different endpoint"
    three, _ = deterministic_draft_observation_id(changed.experimental_observations[0], context(), span)
    assert one == two and one != three
    assert "canonical" not in json.dumps(detail) and "formal" not in json.dumps(detail)


def test_evidence_fails_closed_for_missing_ambiguous_and_methods_as_result():
    span, _ = locate_exact_evidence(EVIDENCE, context(), span_type="observation")
    assert span.text == EVIDENCE
    with pytest.raises(DraftHydrationError, match="ambiguous"):
        locate_exact_evidence(EVIDENCE, context(f"{EVIDENCE}\n{EVIDENCE}"), span_type="observation")
    with pytest.raises(DraftHydrationError, match="missing"):
        locate_exact_evidence(EVIDENCE, context("different"), span_type="observation")
    with pytest.raises(DraftHydrationError, match="linked Methods"):
        locate_exact_evidence(EVIDENCE, context(f"LINKED_METHODS: {EVIDENCE}"), span_type="observation")


def test_enum_policy_is_conservative_and_versioned():
    assert normalize_draft_enum("lexical_direction", "unknown")[0] == "unclear"
    for value in ("mixed", "none"):
        mapped, audit = normalize_draft_enum("lexical_direction", value)
        assert mapped is None and audit["status"] == "unresolved"
    assert normalize_draft_enum("intervention_type", "stabilization")[0] is None
    assert normalize_draft_enum("design_type", "clinical")[0] is None


def test_structured_multi_intervention_is_preserved_then_formal_fails_closed():
    draft = draft_response()
    draft.experimental_observations[0].interventions.append(
        draft.experimental_observations[0].interventions[0].model_copy(update={"intervention_target_mention": "drug B"})
    )
    result = hydrate_draft_response(draft, context())
    assert not result.formal_response["experimental_observations"]
    assert result.rejected[0]["status"] == "unsupported_multi_intervention"
    assert len(result.rejected[0]["draft"]["interventions"]) == 2


def test_v4_adapter_removes_model_provenance_and_keeps_structured_secondary():
    formal = {
        "schema_version": "fulltext_l1_experimental_observation_schema_v2",
        "experimental_observations": [{
            "observation_id": "model-made", "provenance": {"paper_id": "wrong", "source_document_id": None,
                "evidence_spans": [{"text": EVIDENCE, "span_type": "observation"}], "fulltext_source_hash": "wrong"},
            "experiment": {"experiment_id": "exp", "evidence_family_id": "fam", "design_type": "in_vitro"},
            "intervention": {"intervention_type": "knockdown", "intervention_target_mention": "HIF1A",
                "secondary_intervention": {"intervention_type": "drug_treatment", "intervention_target_mention": "drug B"}},
            "measurement": {"measurement_dimension": "abundance_expression", "measured_entity_mention": "target"},
            "observation": {"observed_result": "decreased", "observation_span": {"text": EVIDENCE, "span_type": "observation"}},
            "candidate_relation": {"lexical_direction": "negative"}, "statement_role": "current_study_experiment",
        }],
    }
    adapted = adapt_v4_formal_direct_to_draft(formal)
    serialized = json.dumps(adapted)
    assert "model-made" not in serialized and "wrong" not in serialized
    assert len(adapted["experimental_observations"][0]["interventions"]) == 2


def test_cache_identity_binds_both_contracts_and_versions():
    key = cache_key(source_fulltext_hash="source", chunk_hash="block", provider="p", model="m",
                    config_hash="config", candidate_prior_hash="prior", thinking_mode="disabled")
    assert len(key) == 64 and CACHE_IDENTITY_VERSION.endswith("authoritative_anchors")
    assert len(prompt_hash()) == len(schema_hash()) == len(formal_schema_hash()) == 64


def test_offline_smoke_reparse_is_idempotent_zero_call_and_fixes_legacy_metric(tmp_path, monkeypatch):
    run = tmp_path / "run"; artifacts = run / "artifacts"; cache = artifacts / "cache/fulltext_l1_v2"
    cache.mkdir(parents=True)
    _, nonempty = fulltext_l1_v2_prompt_examples()
    row = nonempty["experimental_observations"][0]
    row["candidate_relation"]["lexical_direction"] = "unknown"
    nonempty_path = cache / "nonempty.raw_response.txt"
    empty_path = cache / "empty.raw_response.txt"
    nonempty_path.write_text(json.dumps(nonempty)); empty_path.write_text(json.dumps({
        "schema_version": "fulltext_l1_experimental_observation_schema_v2", "experimental_observations": []}))
    samples = [
        {"block_id": "b1", "parent_block_id": "b1", "child_block_id": None,
         "sample_group": "historical_completed_empty", "original_block_hash": "h1"},
        {"block_id": "b2", "parent_block_id": "b2", "child_block_id": None,
         "sample_group": "historical_completed_empty", "original_block_hash": "h2"},
    ]
    (artifacts / "fulltext_l1_v2_smoke_manifest.json").write_text(json.dumps({"samples": samples}))
    results = [
        {"block_id": "b1", "status": "schema_failure", "raw_response_path": str(nonempty_path),
         "prompt_version": "v4", "prompt_hash": "p4", "schema_version": "fulltext_l1_experimental_observation_schema_v2"},
        {"block_id": "b2", "status": "strict_schema_success", "raw_response_path": str(empty_path),
         "prompt_version": "v4", "prompt_hash": "p4", "schema_version": "fulltext_l1_experimental_observation_schema_v2"},
    ]
    (artifacts / "fulltext_l1_v2_provider_smoke_results.json").write_text(json.dumps({"results": results}))
    (artifacts / "fulltext_l1_v2_execution_records.jsonl").write_text("{}\n")
    block_text = f"CURRENT_RESULTS: {EVIDENCE}"
    inventory = {block_id: {
        "block": {"block_id": block_id, "text": block_text, "chunk_hash": f"h-{block_id}",
                  "section": {"section_title": "Results"}},
        "paper": {"paper_id": "paper", "pmid": "1", "pmcid": "PMC1"},
        "source_fulltext_hash": "article-hash", "article_path": "article_text.json",
    } for block_id in ("b1", "b2")}
    monkeypatch.setattr("code_engine.fulltext.fulltext_l1_v2_draft_reparse._historical_config", lambda *_: {})
    monkeypatch.setattr("code_engine.fulltext.fulltext_l1_v2_draft_reparse._block_inventory", lambda *_: inventory)
    first = reparse_smoke_responses_offline(run)["summary"]
    first_bytes = (artifacts / "fulltext_l1_v3_smoke_offline_rehydrate_audit.jsonl").read_bytes()
    second = reparse_smoke_responses_offline(run)["summary"]
    assert first == second
    assert (artifacts / "fulltext_l1_v3_smoke_offline_rehydrate_audit.jsonl").read_bytes() == first_bytes
    assert first["api_calls"] == first["network_calls"] == first["downloads"] == 0
    assert first["legacy_empty_raw_nonempty_count"] == 1
    assert first["legacy_empty_nonempty_schema_failure_count"] == 1
    assert first["legacy_empty_false_negative_candidate_count"] == 1
    assert first["scientific_input_complete"] is False and first["publication_allowed"] is False
