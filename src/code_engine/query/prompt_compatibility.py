"""Prompt-aware L1 reuse decisions and cache-key construction."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import Field

from code_engine.query.intent import ResearchIntent
from code_engine.schemas.models import CODEBaseModel


class PromptProfileFingerprint(CODEBaseModel):
    domain_id: str
    prompt_profile_id: str
    prompt_version: str
    output_schema_version: str
    extraction_policy_version: str
    model_name: str
    model_family: str
    fingerprint_hash: str


class L1PromptFingerprint(CODEBaseModel):
    paper_id: str
    chunk_id: str
    chunk_hash: str
    domain_id: str
    prompt_profile_id: str
    prompt_version: str
    output_schema_version: str
    extraction_policy_version: str
    model_name: str
    model_family: str
    fingerprint_hash: str


class ChunkProcessingRecord(CODEBaseModel):
    paper_id: str
    chunk_id: str
    chunk_hash: str
    l1_output_path: str = ""
    domain_id: str
    prompt_profile_id: str
    prompt_version: str
    output_schema_version: str
    extraction_policy_version: str
    model_name: str
    model_family: str = "unknown"
    fingerprint_hash: str = ""
    prompt_fingerprint: dict[str, Any] = Field(default_factory=dict)
    processed_at: str = ""


class PromptCompatibilityDecision(CODEBaseModel):
    paper_id: str
    chunk_id: str
    can_reuse: bool
    reason: str
    previous_fingerprint: dict[str, Any] = Field(default_factory=dict)
    required_fingerprint: dict[str, Any] = Field(default_factory=dict)
    chunk_hash_same: bool = False
    requires_reextraction: bool = True
    warnings: list[str] = Field(default_factory=list)


FINGERPRINT_FIELDS = (
    "domain_id", "prompt_profile_id", "prompt_version", "output_schema_version",
    "extraction_policy_version", "model_name", "model_family",
)
L1_FINGERPRINT_FIELDS = (
    "paper_id", "chunk_id", "chunk_hash", "domain_id", "prompt_profile_id",
    "prompt_version", "output_schema_version", "extraction_policy_version",
    "model_name", "model_family",
)


def compute_prompt_fingerprint_hash(**fields: str) -> str:
    payload = {key: str(fields.get(key, "")) for key in FINGERPRINT_FIELDS}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build_prompt_fingerprint(
    *,
    domain_id: str,
    prompt_profile_id: str,
    prompt_version: str,
    output_schema_version: str,
    extraction_policy_version: str,
    model_name: str,
    model_family: str,
) -> PromptProfileFingerprint:
    values = locals()
    return PromptProfileFingerprint(**values, fingerprint_hash=compute_prompt_fingerprint_hash(**values))


def build_l1_prompt_fingerprint(
    *,
    paper_id: str,
    chunk_id: str,
    chunk_hash: str,
    domain_id: str,
    prompt_profile_id: str,
    prompt_version: str,
    output_schema_version: str,
    extraction_policy_version: str,
    model_name: str,
    model_family: str,
) -> L1PromptFingerprint:
    """Build the canonical chunk-level L1 extraction identity."""

    values = {
        "paper_id": paper_id,
        "chunk_id": chunk_id,
        "chunk_hash": chunk_hash,
        "domain_id": domain_id,
        "prompt_profile_id": prompt_profile_id,
        "prompt_version": prompt_version,
        "output_schema_version": output_schema_version,
        "extraction_policy_version": extraction_policy_version,
        "model_name": model_name,
        "model_family": model_family,
    }
    digest = hashlib.sha256(
        json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return L1PromptFingerprint(**values, fingerprint_hash=digest)


def compute_l1_cache_key(fingerprint: L1PromptFingerprint) -> str:
    """Return a cache key containing every strict L1 fingerprint field."""

    return hashlib.sha256(
        "\x1f".join(str(getattr(fingerprint, field)) for field in L1_FINGERPRINT_FIELDS).encode("utf-8")
    ).hexdigest()


def compute_prompt_aware_cache_key(paper_id: str, chunk_hash: str, fingerprint: PromptProfileFingerprint) -> str:
    components = (
        paper_id, chunk_hash, fingerprint.domain_id, fingerprint.prompt_profile_id,
        fingerprint.prompt_version, fingerprint.output_schema_version,
        fingerprint.extraction_policy_version, fingerprint.model_name,
        fingerprint.model_family,
    )
    return hashlib.sha256("\x1f".join(components).encode()).hexdigest()


def _record_fingerprint(record: ChunkProcessingRecord) -> PromptProfileFingerprint:
    return build_prompt_fingerprint(
        domain_id=record.domain_id,
        prompt_profile_id=record.prompt_profile_id,
        prompt_version=record.prompt_version,
        output_schema_version=record.output_schema_version,
        extraction_policy_version=record.extraction_policy_version,
        model_name=record.model_name,
        model_family=record.model_family,
    )


def compare_prompt_compatibility(
    previous: ChunkProcessingRecord | dict[str, Any] | None,
    required: PromptProfileFingerprint,
    *,
    required_chunk_hash: str | None = None,
    allow_model_family_reuse: bool = False,
) -> PromptCompatibilityDecision:
    """Apply ordered, deterministic L1 reuse rules."""

    if previous is None:
        return PromptCompatibilityDecision(paper_id="UNKNOWN", chunk_id="UNKNOWN", can_reuse=False, reason="missing_l1_output", required_fingerprint=required.model_dump(), chunk_hash_same=False, requires_reextraction=True)
    record = previous if isinstance(previous, ChunkProcessingRecord) else ChunkProcessingRecord.model_validate(previous)
    previous_fingerprint = _record_fingerprint(record)

    def decision(can_reuse: bool, reason: str, chunk_same: bool, warnings: list[str] | None = None):
        return PromptCompatibilityDecision(
            paper_id=record.paper_id,
            chunk_id=record.chunk_id,
            can_reuse=can_reuse,
            reason=reason,
            previous_fingerprint=previous_fingerprint.model_dump(),
            required_fingerprint=required.model_dump(),
            chunk_hash_same=chunk_same,
            requires_reextraction=not can_reuse,
            warnings=warnings or [],
        )

    if not record.l1_output_path:
        return decision(False, "missing_l1_output", False)
    chunk_same = required_chunk_hash is None or record.chunk_hash == required_chunk_hash
    if not chunk_same:
        return decision(False, "chunk_hash_changed", False)
    checks = (
        ("domain_id", "domain_changed"),
        ("prompt_profile_id", "prompt_profile_changed"),
        ("prompt_version", "prompt_version_changed"),
        ("output_schema_version", "schema_version_changed"),
        ("extraction_policy_version", "policy_version_changed"),
    )
    for field, reason in checks:
        if getattr(record, field) != getattr(required, field):
            return decision(False, reason, True)
    if record.model_name != required.model_name:
        same_family = record.model_family == required.model_family
        if same_family and allow_model_family_reuse:
            return decision(True, "compatible_model_family_l1", True, ["model_name_changed_family_reuse_explicitly_enabled"])
        return decision(False, "model_name_changed", True)
    return decision(True, "compatible_existing_l1", True)


def build_required_fingerprint_for_intent(intent: ResearchIntent) -> PromptProfileFingerprint:
    domain = intent.selected_domain if intent.selected_domain != "unknown" else "general_biomedical"
    profile = "neuropharmacology" if domain == "neuropharmacology" else "general_biomedical"
    return build_prompt_fingerprint(
        domain_id=domain,
        prompt_profile_id=profile,
        prompt_version="2.0",
        output_schema_version="l1_v2_evidence_mechanism_schema",
        extraction_policy_version="evidence_grounded_v2",
        model_name="deepseek-v4-pro",
        model_family="deepseek",
    )
