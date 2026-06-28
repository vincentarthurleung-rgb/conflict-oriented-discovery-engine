"""Select bounded, evidence-bearing spans from ranked full-text sections."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Any

from code_engine.extraction.evidence_tiers import EvidenceTier
from code_engine.extraction.section_ranker import CONTEXT_TERMS, DIRECTION_TERMS, SKIP_SECTIONS


RESULT_VERBS = ("show", "demonstrat", "observ", "found", "increased", "decreased", "inhibited", "activated", "result", "显示", "发现", "观察")


def _sentences(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"(?<=[.!?。！？])\s+", str(text or "")) if item.strip()]


def select_evidence_spans(
    ranked_sections: list[dict],
    conflict_candidate: dict,
    max_spans_per_paper: int = 8,
    max_tokens_per_span: int = 500,
) -> list[dict]:
    entities = [str(item) for item in (conflict_candidate.get("subject_name"), conflict_candidate.get("object_name")) if item]
    candidate_id = str(conflict_candidate.get("candidate_id") or "UNKNOWN")
    candidates = []
    for section in ranked_sections:
        title = str(section.get("section_title") or "").casefold()
        if any(term in title for term in SKIP_SECTIONS):
            continue
        for index, sentence in enumerate(_sentences(section.get("text", ""))):
            words = sentence.split()
            if len(words) > max_tokens_per_span:
                sentence = " ".join(words[:max_tokens_per_span])
            lowered = sentence.casefold()
            matched_entities = [item for item in entities if item.casefold() in lowered]
            directions = [term for term in DIRECTION_TERMS if term in lowered]
            contexts = [term for term in CONTEXT_TERMS if term in lowered]
            results = [term for term in RESULT_VERBS if term in lowered]
            if not (len(matched_entities) >= 2 or (matched_entities and directions) or (directions and results)):
                continue
            score = 2.0 * len(set(matched_entities)) + 1.0 * len(directions) + 0.7 * len(results) + 0.3 * len(contexts) + 0.1 * float(section.get("rank_score", 0.0))
            stable = f"{section.get('paper_id')}|{section.get('section_id')}|{index}|{sentence}"
            candidates.append({
                "span_id": hashlib.sha256(stable.encode()).hexdigest()[:16],
                "paper_id": str(section.get("paper_id") or "UNKNOWN"),
                "section_id": str(section.get("section_id") or ""),
                "section_type": str(section.get("section_type") or "unknown"),
                "source_scope": "full_text",
                "evidence_tier": EvidenceTier.FULLTEXT_EVIDENCE.value,
                "text": sentence,
                "selection_score": round(score, 4),
                "matched_entities": list(dict.fromkeys(matched_entities)),
                "matched_context_terms": list(dict.fromkeys(contexts)),
                "conflict_candidate_ids": [candidate_id],
                "warnings": [],
            })
    by_paper: dict[str, list[dict]] = defaultdict(list)
    for item in sorted(candidates, key=lambda value: (-value["selection_score"], value["span_id"])):
        if len(by_paper[item["paper_id"]]) < max_spans_per_paper:
            by_paper[item["paper_id"]].append(item)
    return [item for paper_id in sorted(by_paper) for item in by_paper[paper_id]]


__all__ = ["select_evidence_spans"]
