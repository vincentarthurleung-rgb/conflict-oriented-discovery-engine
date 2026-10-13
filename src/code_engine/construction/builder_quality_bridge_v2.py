"""Small engineering correction to V1's reviewable-claim graph handoff.

Retain V1 unchanged for its frozen run. Export its existing lexical relation
through the graph's native field; do not grant scientific or entity authority.
"""
from __future__ import annotations

from code_engine.construction.builder_quality_bridge import (
    normalize_reviewable_builder_claims as normalize_v1,
    require,
)
from code_engine.normalization.resolver import ResolverCascade
from code_engine.schemas.l1_extraction import L1ExtractedClaim


def normalize_reviewable_builder_claims(claims: list[dict], resolver: ResolverCascade | None = None) -> list[dict]:
    for raw in claims:
        claim = L1ExtractedClaim.model_validate(raw)
        value = claim.model_dump(mode="json")
        candidate = value.get("builder_candidate") or {}
        require(claim.claim_id == value.get("candidate_id") == value.get("quality_candidate_id"), "CLAIM_ID_BINDING_MISMATCH")
        require(claim.paper_id == (value.get("source_identity") or {}).get("pmid"), "CLAIM_SOURCE_BINDING_MISMATCH")
        for projected, original in (("subject_raw", "actor_or_intervention"), ("object_raw", "response_or_endpoint"),
                                    ("relation_raw", "relation_direction"), ("neutral_proposition", "neutral_proposition")):
            require(value.get(projected) == candidate.get(original), "CLAIM_PROJECTION_MISMATCH:" + projected)
        exact = (candidate.get("construction_evidence_span") or {}).get("exact_text")
        span = value.get("evidence_span") or {}
        require(exact and claim.evidence_quote == claim.evidence_sentence == span.get("exact_text") == exact, "CLAIM_EVIDENCE_BINDING_MISMATCH")
        start, end = span.get("start_offset"), span.get("end_offset")
        require(type(start) is int and type(end) is int and 0 <= start < end and end-start == len(exact), "CLAIM_OFFSET_BINDING_MISMATCH")
        require(claim.chunk_id == span.get("anchor_id"), "CLAIM_ANCHOR_BINDING_MISMATCH")
        require(all(claim.context.get(k) == candidate.get(k) for k in (
            "species", "biological_unit", "intrinsic_conditioning", "intrinsic_therapy_context", "intrinsic_disease_or_genotype_context")), "CLAIM_CONTEXT_BINDING_MISMATCH")
    records = normalize_v1(claims, resolver)
    for record in records:
        relation = record["lexical_relation_projection"]
        # Existing graph builder reads formal_relation before relation_family.
        # The name is an existing serialization field, NOT approval for core use.
        record["formal_relation"] = relation["relation"] if relation else None
        record["normalized_relation_family"] = relation["family"] if relation else None
        record["formal_relation_basis"] = "existing_lexical_registry_only_not_verified_causal_relation"
        record["bridge_handoff_version"] = "builder_quality_graph_field_handoff_v2"
        require(not record["canonical_graph_eligible"] and not record["conflict_reasoning_eligible"]
                and record["observation_id"] is None, "CLAIM_AUTHORITY_ESCALATION")
    return records
