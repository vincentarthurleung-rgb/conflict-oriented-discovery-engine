#!/usr/bin/env python3
"""Prospective V4 exact BODY quote localization; no V3 offset dependency."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


SUCCESS = "V4_UNIQUE_EXACT_LOCALIZATION_SUCCESS"
NOT_FOUND = "GROUNDING_TEXT_NOT_FOUND"
NONUNIQUE = "GROUNDING_TEXT_NONUNIQUE"
CROSS_PARAGRAPH = "GROUNDING_TEXT_CROSSES_PARAGRAPH_BOUNDARY"
COORDINATE_FAILURE = "V4_COORDINATE_DERIVATION_FAILURE"
INVALID_BODY = "V4_CANONICAL_BODY_INVALID"
EMPTY_QUOTE = "V4_EMPTY_EXACT_TEXT"


def _failure(state: str, occurrence_count: int = 0) -> dict[str, Any]:
    result: dict[str, Any] = {
        "development_v4_localization_state": state,
        "source_field": "body",
        "exact_occurrence_count": occurrence_count,
        "coordinate_end_semantics": "exclusive",
        "body_document_start_offset": None,
        "body_document_end_offset": None,
        "paragraph_local_start_offset": None,
        "paragraph_local_end_offset": None,
        "paragraph_ordinal": None,
        "anchor_id": None,
    }
    if state == CROSS_PARAGRAPH:
        # Specific diagnostic name for the master contract's broader state.
        result["master_contract_state"] = "GROUNDING_PARAGRAPH_BOUNDARY_INVALID"
    return result


def localize_exact_body_quote(
    exact_text: str,
    canonical_body: str,
    paragraphs: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return controller-owned zero-based, end-exclusive coordinates.

    The function has no source identity, abstract, bibliography, model-offset,
    proposition, or semantic-match input. It performs no normalization.
    """
    if not isinstance(exact_text, str) or not exact_text:
        return _failure(EMPTY_QUOTE)
    if not isinstance(canonical_body, str) or not isinstance(paragraphs, Sequence):
        return _failure(INVALID_BODY)
    seen_anchors: set[str] = set()
    for paragraph in paragraphs:
        if not isinstance(paragraph, Mapping):
            return _failure(INVALID_BODY)
        start, end, text, anchor, ordinal = (paragraph.get("start_offset"),
                                    paragraph.get("end_offset"),
                                    paragraph.get("text"),
                                    paragraph.get("span_id"),
                                    paragraph.get("ordinal"))
        if (type(start) is not int or type(end) is not int or
                not 0 <= start < end <= len(canonical_body) or
                not isinstance(text, str) or
                canonical_body[start:end] != text or
                not isinstance(anchor, str) or not anchor or
                type(ordinal) is not int or ordinal < 1 or
                anchor in seen_anchors):
            return _failure(INVALID_BODY)
        seen_anchors.add(anchor)

    positions = []
    cursor = 0
    while True:
        position = canonical_body.find(exact_text, cursor)
        if position < 0:
            break
        positions.append(position)
        cursor = position + 1  # Count overlapping exact occurrences too.
    if not positions:
        return _failure(NOT_FOUND)
    if len(positions) > 1:
        return _failure(NONUNIQUE, len(positions))

    start = positions[0]
    end = start + len(exact_text)  # End is exclusive, in Unicode code points.
    containing = [paragraph for paragraph in paragraphs
                  if paragraph["start_offset"] <= start and
                  end <= paragraph["end_offset"]]
    if len(containing) != 1:
        return _failure(CROSS_PARAGRAPH, 1)
    paragraph = containing[0]
    local_start = start - paragraph["start_offset"]
    local_end = end - paragraph["start_offset"]
    if (canonical_body[start:end] != exact_text or
            paragraph["text"][local_start:local_end] != exact_text):
        return _failure(COORDINATE_FAILURE, 1)
    return {
        "development_v4_localization_state": SUCCESS,
        "source_field": "body",
        "exact_occurrence_count": 1,
        "coordinate_end_semantics": "exclusive",
        "body_document_start_offset": start,
        "body_document_end_offset": end,
        "paragraph_local_start_offset": local_start,
        "paragraph_local_end_offset": local_end,
        "paragraph_ordinal": paragraph["ordinal"],
        "anchor_id": paragraph["span_id"],
    }
