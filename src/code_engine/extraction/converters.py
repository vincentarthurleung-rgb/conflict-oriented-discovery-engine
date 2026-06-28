"""Converters between L1 v2 claims, evidence records, and legacy tuples."""

from __future__ import annotations

import hashlib
from typing import Any

from code_engine.query.prompt_compatibility import build_l1_prompt_fingerprint
from code_engine.schemas.evidence import EvidenceRecord
from code_engine.schemas.l1_extraction import L1_CONTEXT_FIELDS, L1ExtractedClaim


SIGN_TO_INT = {"positive": 1, "negative": -1, "neutral_or_association": 0, "unknown": 0}
INT_TO_SIGN = {1: "positive", -1: "negative", 0: "neutral_or_association"}


def _fingerprint(claim: L1ExtractedClaim) -> dict[str, Any]:
    if claim.prompt_fingerprint:
        return dict(claim.prompt_fingerprint)
    return build_l1_prompt_fingerprint(
        paper_id=claim.paper_id,
        chunk_id=claim.chunk_id,
        chunk_hash=claim.chunk_hash,
        domain_id=claim.domain_id,
        prompt_profile_id=claim.prompt_profile_id,
        prompt_version=claim.prompt_version,
        output_schema_version=claim.output_schema_version,
        extraction_policy_version=claim.extraction_policy_version,
        model_name=claim.model_name,
        model_family=claim.model_family,
    ).model_dump()


def l1_claim_to_evidence_record(claim: L1ExtractedClaim) -> EvidenceRecord:
    """Preserve grounding and extraction identity in an EvidenceRecord."""

    role = {
        "positive": "supports_edge",
        "negative": "contradicts_edge",
    }.get(claim.direct_relation_sign, "background_only")
    return EvidenceRecord(
        evidence_id=claim.claim_id,
        paper_id=claim.paper_id,
        chunk_id=claim.chunk_id,
        chunk_hash=claim.chunk_hash,
        section=claim.section,
        sentence=claim.evidence_sentence,
        quote=claim.evidence_quote or claim.evidence_sentence,
        subject_span=claim.subject_span,
        relation_span=claim.relation_span,
        object_span=claim.object_span,
        context_spans=claim.context_spans,
        statement_type=claim.statement_type,
        evidence_type=claim.evidence_type,
        claim_role=role,
        extraction_prompt_profile=claim.prompt_profile_id,
        domain_id=claim.domain_id,
        prompt_version=claim.prompt_version,
        output_schema_version=claim.output_schema_version,
        extraction_policy_version=claim.extraction_policy_version,
        model_name=claim.model_name,
        model_family=claim.model_family,
        compiled_prompt_hash=claim.compiled_prompt_hash,
        prompt_fingerprint=_fingerprint(claim),
        confidence=claim.confidence,
        warnings=list(claim.extraction_warnings),
    )


def l1_claim_to_legacy_tuple(claim: L1ExtractedClaim) -> dict[str, Any]:
    """Return the tuple shape consumed by existing L1.5/L2 code."""

    context = {
        field: getattr(claim, field)
        for field in L1_CONTEXT_FIELDS
        if getattr(claim, field)
    }
    return {
        "subject": claim.subject_raw,
        "relation_raw": claim.relation_raw,
        "relation_family": claim.relation_family,
        "polarity_type": claim.polarity_type,
        "direction": claim.direction,
        "direction_confidence": claim.direction_confidence,
        "relation_sign": SIGN_TO_INT[claim.direct_relation_sign],
        "therapeutic_direction": claim.therapeutic_direction,
        "object": claim.object_raw,
        "context": context,
        "negated": claim.negated,
        "evidence_sentence": claim.evidence_sentence,
        "confidence": claim.confidence,
        "claim_id": claim.claim_id,
        "prompt_fingerprint": _fingerprint(claim),
        "domain_id": claim.domain_id,
        "subdomain_id": claim.subdomain_id,
        "domain_profile_id": claim.domain_profile_id,
        "validator_profile_id": claim.validator_profile_id,
        "required_context_slots": claim.required_context_slots,
        "extraction_warnings": list(claim.extraction_warnings),
    }


def legacy_tuple_to_l1_claim(
    tuple_dict: dict[str, Any],
    metadata: dict[str, Any],
) -> L1ExtractedClaim:
    """Adapt a historical tuple while marking its incomplete provenance."""

    evidence_sentence = str(tuple_dict.get("evidence_sentence") or "")
    paper_id = str(metadata.get("paper_id") or metadata.get("asset_id") or "UNKNOWN")
    chunk_id = str(metadata.get("chunk_id") or metadata.get("chunk_index") or "unknown")
    chunk_hash = str(metadata.get("chunk_hash") or hashlib.sha256(evidence_sentence.encode()).hexdigest())
    stable = "|".join((paper_id, chunk_id, str(tuple_dict.get("subject", "")), evidence_sentence))
    context = dict(tuple_dict.get("context") or {})
    warnings = list(tuple_dict.get("extraction_warnings") or [])
    warnings.append("converted_from_legacy_tuple_missing_native_l1_v2_provenance")
    values = {
        field: str(context.get(field) or context.get("cell_line_or_type" if field == "cell_type" else field) or "")
        for field in L1_CONTEXT_FIELDS
    }
    return L1ExtractedClaim(
        claim_id=str(tuple_dict.get("claim_id") or hashlib.sha256(stable.encode()).hexdigest()[:16]),
        paper_id=paper_id,
        chunk_id=chunk_id,
        chunk_hash=chunk_hash,
        domain_id=str(metadata.get("domain_id") or "legacy_unknown"),
        subdomain_id=str(metadata.get("subdomain_id") or ""),
        domain_profile_id=str(metadata.get("domain_profile_id") or metadata.get("domain_id") or "legacy_unknown"),
        validator_profile_id=str(metadata.get("validator_profile_id") or "general_validation"),
        required_context_slots=list(metadata.get("required_context_slots") or []),
        prompt_profile_id=str(metadata.get("prompt_profile_id") or "legacy_unknown"),
        prompt_version=str(metadata.get("prompt_version") or "legacy_unknown"),
        output_schema_version=str(metadata.get("output_schema_version") or "legacy_tuple_v1"),
        extraction_policy_version=str(metadata.get("extraction_policy_version") or "legacy_unknown"),
        model_name=str(metadata.get("model_name") or "legacy_unknown"),
        model_family=str(metadata.get("model_family") or "unknown"),
        compiled_prompt_hash=str(metadata.get("compiled_prompt_hash") or "legacy_unknown"),
        prompt_fingerprint=dict(metadata.get("prompt_fingerprint") or {}),
        subject_raw=str(tuple_dict.get("subject") or ""),
        subject_type=str(tuple_dict.get("subject_type") or "unknown"),
        relation_raw=str(tuple_dict.get("relation_raw") or ""),
        relation_family=str(tuple_dict.get("relation_family") or "legacy_causal_relation"),
        polarity_type=str(tuple_dict.get("polarity_type") or "unknown"),
        direction=str(tuple_dict.get("direction") or "unknown"),
        direction_confidence=float(tuple_dict.get("direction_confidence", 0.0)),
        direct_relation_sign=INT_TO_SIGN.get(int(tuple_dict.get("relation_sign", 0)), "unknown"),
        therapeutic_direction=str(tuple_dict.get("therapeutic_direction") or "unknown"),
        object_raw=str(tuple_dict.get("object") or ""),
        object_type=str(tuple_dict.get("object_type") or "unknown"),
        evidence_sentence=evidence_sentence,
        evidence_quote=str(tuple_dict.get("evidence_quote") or evidence_sentence),
        section=str(metadata.get("section") or ""),
        statement_type=str(tuple_dict.get("statement_type") or "unknown"),
        evidence_type=str(tuple_dict.get("evidence_type") or "unknown"),
        confidence=float(tuple_dict.get("confidence", 0.6 if evidence_sentence else 0.0)),
        negated=bool(tuple_dict.get("negated", False)),
        speculative=bool(tuple_dict.get("speculative", False)),
        subject_span=str(tuple_dict.get("subject_span") or ""),
        relation_span=str(tuple_dict.get("relation_span") or ""),
        object_span=str(tuple_dict.get("object_span") or ""),
        context_spans=dict(tuple_dict.get("context_spans") or {}),
        extraction_warnings=warnings,
        **values,
    )
