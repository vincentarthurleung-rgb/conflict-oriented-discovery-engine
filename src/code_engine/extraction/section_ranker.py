"""Deterministic full-text section ranking for conflict-focused extraction."""

from __future__ import annotations

import re
from typing import Any


SECTION_PRIORS = {
    "results": 3.0,
    "discussion": 2.4,
    "figure_caption": 2.2,
    "figure captions": 2.2,
    "conclusion": 1.8,
    "methods": 1.0,
    "introduction": 0.2,
    "background": 0.1,
}
SKIP_SECTIONS = ("references", "funding", "author contributions", "acknowledg")
DIRECTION_TERMS = ("inhibit", "activate", "increase", "decrease", "improve", "worsen", "no effect", "抑制", "激活", "上调", "下调", "改善", "恶化")
CONTEXT_TERMS = ("assay", "dose", "time", "mouse", "rat", "human", "cell", "tissue", "cortex", "hippocampus", "试验", "剂量", "小鼠", "细胞")


def _entities(candidate: dict[str, Any]) -> list[str]:
    return [str(value) for value in (
        candidate.get("subject_name"), candidate.get("object_name"),
        candidate.get("subject_canonical_id"), candidate.get("object_canonical_id"),
    ) if value]


def rank_fulltext_sections_for_conflict(
    fulltext_document: dict,
    conflict_candidate: dict,
    domain_profile: dict | None = None,
    max_sections: int = 5,
) -> list[dict]:
    paper_id = str(fulltext_document.get("paper_id") or fulltext_document.get("pmcid") or fulltext_document.get("pmid") or "UNKNOWN")
    sections = list(fulltext_document.get("sections") or [])
    if not sections and fulltext_document.get("full_text"):
        sections = [{"section_id": "full_text", "title": "Full text", "text": fulltext_document["full_text"]}]
    entities = _entities(conflict_candidate)
    ranked = []
    for index, section in enumerate(sections):
        title = str(section.get("section_title") or section.get("title") or section.get("section_type") or "unknown")
        section_type = str(section.get("section_type") or title).casefold().replace(" ", "_")
        lowered_title = title.casefold()
        if any(term in lowered_title for term in SKIP_SECTIONS):
            continue
        text = str(section.get("text") or section.get("content") or "")
        lowered = text.casefold()
        matched_entities = [item for item in entities if item.casefold() in lowered]
        matched_directions = [term for term in DIRECTION_TERMS if term in lowered]
        context_hits = [term for term in CONTEXT_TERMS if term in lowered]
        prior = next((score for key, score in SECTION_PRIORS.items() if key in lowered_title or key.replace("_", " ") in lowered_title), 0.5)
        co_mention_bonus = 2.5 if len(set(matched_entities)) >= 2 else 0.8 * len(set(matched_entities))
        score = prior + co_mention_bonus + min(1.5, 0.3 * len(matched_directions)) + min(1.0, 0.15 * len(context_hits))
        if "figure" in lowered_title or "table" in lowered_title:
            score += 0.5
        if ("method" in lowered_title and not matched_entities and not matched_directions):
            score -= 0.8
        ranked.append({
            "section_id": str(section.get("section_id") or f"{paper_id}_section_{index}"),
            "paper_id": paper_id,
            "section_title": title,
            "section_type": section_type,
            "text": text,
            "rank_score": round(max(0.0, score), 4),
            "matched_entities": list(dict.fromkeys(matched_entities)),
            "matched_direction_terms": list(dict.fromkeys(matched_directions)),
            "warnings": [],
        })
    return sorted(ranked, key=lambda item: (-item["rank_score"], item["section_id"]))[:max_sections]


__all__ = ["rank_fulltext_sections_for_conflict"]
