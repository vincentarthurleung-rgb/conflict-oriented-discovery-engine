"""Synthetic, source-free tests for prospective V4 BODY localization."""

from __future__ import annotations

import inspect

import pytest

from scripts import search_plan_v24_alpha320a_v4_localizer as v4


def paragraphs(*parts: str) -> tuple[str, list[dict]]:
    body = "\n\n".join(parts)
    result = []
    cursor = 0
    for index, text in enumerate(parts, 1):
        result.append({"start_offset": cursor, "end_offset": cursor + len(text),
                       "text": text, "ordinal": index,
                       "span_id": f"spanv1_synthetic_{index}"})
        cursor += len(text) + 2
    return body, result


@pytest.mark.parametrize("parts,quote,state,count", [
    (("alpha beta",), "beta", v4.SUCCESS, 1),
    (("alpha beta",), "gamma", v4.NOT_FOUND, 0),
    (("alpha beta alpha",), "alpha", v4.NONUNIQUE, 2),
    (("alpha", "alpha"), "alpha", v4.NONUNIQUE, 2),
    (("alpha", "beta"), "ha\n\nbe", v4.CROSS_PARAGRAPH, 1),
    (("aaa",), "aa", v4.NONUNIQUE, 2),
    (("alpha",), "", v4.EMPTY_QUOTE, 0),
])
def test_exact_match_states(parts, quote, state, count):
    body, spans = paragraphs(*parts)
    result = v4.localize_exact_body_quote(quote, body, spans)
    assert result["development_v4_localization_state"] == state
    assert result["exact_occurrence_count"] == count
    if state == v4.CROSS_PARAGRAPH:
        assert result["master_contract_state"] == "GROUNDING_PARAGRAPH_BOUNDARY_INVALID"


def test_end_exclusive_unicode_roundtrip_and_anchor():
    body, spans = paragraphs("αβ γδ")
    result = v4.localize_exact_body_quote("γδ", body, spans)
    assert result["development_v4_localization_state"] == v4.SUCCESS
    assert (result["body_document_start_offset"], result["body_document_end_offset"]) == (3, 5)
    assert body[3:5] == "γδ"
    assert result["coordinate_end_semantics"] == "exclusive"
    assert result["anchor_id"] == spans[0]["span_id"]


def test_duplicate_paragraph_ordinals_do_not_replace_unique_anchor_identity():
    body, spans = paragraphs("first", "second")
    spans[1]["ordinal"] = spans[0]["ordinal"]  # Ordinals can repeat across sections.
    result = v4.localize_exact_body_quote("second", body, spans)
    assert result["development_v4_localization_state"] == v4.SUCCESS
    assert result["anchor_id"] == spans[1]["span_id"]
    assert spans[1]["text"][result["paragraph_local_start_offset"]:
                             result["paragraph_local_end_offset"]] == "second"


def test_abstract_bibliography_model_offsets_and_private_identity_not_inputs():
    body, spans = paragraphs("alpha beta")
    assert tuple(inspect.signature(v4.localize_exact_body_quote).parameters) == (
        "exact_text", "canonical_body", "paragraphs")
    # A quote in an abstract or bibliography is not in this canonical BODY.
    assert v4.localize_exact_body_quote("secret evidence", body, spans)[
        "development_v4_localization_state"] == v4.NOT_FOUND
    result = v4.localize_exact_body_quote("beta", body, spans)
    assert (result["body_document_start_offset"], result["body_document_end_offset"]) == (6, 10)
    assert "PMID99999999" not in str(result)


def test_invalid_canonical_paragraph_rejected():
    body, spans = paragraphs("alpha beta")
    spans[0]["text"] = "changed"
    assert v4.localize_exact_body_quote("beta", body, spans)[
        "development_v4_localization_state"] == v4.INVALID_BODY
