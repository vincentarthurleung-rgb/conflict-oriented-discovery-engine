"""Prompt construction for semantic encoding; profiles are supplied dynamically."""

from __future__ import annotations

import json

from code_engine.encoder.models import SemanticIntakeRequest, SemanticIntakeResult


def build_semantic_intake_prompt(request: SemanticIntakeRequest) -> str:
    schema = SemanticIntakeResult.model_json_schema()
    return (
        "You are a Scientific Encoder. Encode semantics only; do not judge scientific truth.\n"
        "User intent is not evidence. Seed triples must have is_evidence=false and are planning artifacts.\n"
        "Search queries are planning artifacts. Do not invent papers, citations, or experimental evidence.\n"
        "Choose domain_id only from allowed_domain_ids. Include alternatives when multiple domains fit.\n"
        "Set requires_manual_review=true when uncertain. Return strict JSON only.\n"
        f"Allowed domain IDs: {json.dumps(request.allowed_domain_ids)}\n"
        f"Available DomainProfile summaries: {json.dumps(request.available_domain_profiles, ensure_ascii=False)}\n"
        f"Output schema: {json.dumps(schema, ensure_ascii=False)}\n"
        f"Raw query: {request.query}"
    )
