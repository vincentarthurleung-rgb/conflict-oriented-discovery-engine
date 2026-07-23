from dataclasses import replace

import pytest
from pydantic import ValidationError

from code_engine.fulltext.evidence_anchors import generate_evidence_anchors, resolve_anchor
from code_engine.fulltext.fulltext_l1_draft_hydration_v3 import (
    TrustedDraftContextV3, audit_draft_anchor_bindings, hydrate_draft_response_v3,
)
from code_engine.schemas.fulltext_observation_draft import FulltextL1DraftResponse, fulltext_l1_draft_prompt_examples


TEXT = "Catalyst A increased conversion at 500 K."


def _context(block_text=f"CURRENT_RESULTS: {TEXT}", block_id="block"):
    return TrustedDraftContextV3(
        run_id="run", block_id=block_id, parent_block_id=block_id, child_block_id=None,
        block_text=block_text, source_block_hash="block-hash", source_document_id="doc",
        paper_id="paper", pmid=None, pmcid=None, fulltext_source_hash="source-hash",
        source_artifact="article_text.json", section="Results", domain_profile="catalysis",
    )


def _draft(*, anchor_id="block:S0001", excerpt="model paraphrased the result"):
    _, value = fulltext_l1_draft_prompt_examples()
    row = value["experimental_observations"][0]
    row["experiment"]["design_type_raw"] = "unknown"
    row["measurement"]["measurement_dimension_raw"] = "conversion"
    row["observation"]["observed_result"] = "conversion increased"
    row["candidate_relation"]["lexical_direction_raw"] = "positive"
    for reference in [*row["evidence_references"], row["observation"]["evidence"],
                      row["measurement"]["evidence"], row["interventions"][0]["evidence"]]:
        reference["evidence_anchor_ids"] = [anchor_id]
        reference["model_selected_excerpt_raw"] = excerpt
    return FulltextL1DraftResponse.model_validate(value)


def test_anchor_id_is_authoritative_and_excerpt_mismatch_is_warning_only():
    draft = _draft()
    audit = audit_draft_anchor_bindings(draft, _context())
    assert audit["valid"] is True
    assert audit["anchor_reference_count"] == audit["anchor_id_valid_reference_count"] == 5
    assert audit["unique_anchor_id_count"] == 1
    assert audit["anchor_excerpt_mismatch_count"] == 5
    assert audit["formal_evidence_binding_failure_count"] == 0
    result = hydrate_draft_response_v3(draft, _context())
    assert not result.rejected
    spans = result.formal_response["experimental_observations"][0]["provenance"]["evidence_spans"]
    assert {span["text"] for span in spans} == {TEXT}
    assert all(span["source_document_id"] == "doc" and span["anchor_version"] for span in spans)


@pytest.mark.parametrize(("anchor_id", "metric"), [
    ("block:S9999", "anchor_id_missing_count"),
    ("other:S0001", "anchor_id_cross_block_count"),
])
def test_true_anchor_identity_failures_remain_fail_closed(anchor_id, metric):
    audit = audit_draft_anchor_bindings(_draft(anchor_id=anchor_id), _context())
    assert audit["valid"] is False and audit[metric] == 5
    result = hydrate_draft_response_v3(_draft(anchor_id=anchor_id), _context())
    assert not result.formal_response["experimental_observations"]
    assert len(result.rejected) == 1


def test_methods_result_role_and_registry_integrity_fail_closed():
    context = _context(f"LINKED_METHODS: {TEXT}")
    role_audit = audit_draft_anchor_bindings(_draft(), context)
    assert role_audit["valid"] is False and role_audit["anchor_role_violation_count"] >= 1
    anchors = generate_evidence_anchors(block_id="block", source_document_id="doc",
                                        block_text=context.block_text, section="Results")
    with pytest.raises(ValueError, match="hash_mismatch"):
        resolve_anchor("block:S0001", [replace(anchors[0], text_hash="broken")],
                       expected_block_id="block", source_text=context.block_text,
                       expected_source_document_id="doc")
    with pytest.raises(ValueError, match="out_of_bounds"):
        resolve_anchor("block:S0001", [replace(anchors[0], char_end=len(context.block_text) + 1)],
                       expected_block_id="block", source_text=context.block_text,
                       expected_source_document_id="doc")


def test_draft_requires_anchor_ids_forbids_old_text_and_allows_missing_raw_excerpt():
    _, value = fulltext_l1_draft_prompt_examples()
    reference = value["experimental_observations"][0]["observation"]["evidence"]
    reference["model_selected_excerpt_raw"] = None
    FulltextL1DraftResponse.model_validate(value)
    reference["evidence_anchor_ids"] = []
    with pytest.raises(ValidationError):
        FulltextL1DraftResponse.model_validate(value)
    reference["evidence_anchor_ids"] = ["example_block:S0001"]
    reference["text"] = "provider-owned text is forbidden"
    with pytest.raises(ValidationError, match="Extra inputs"):
        FulltextL1DraftResponse.model_validate(value)
