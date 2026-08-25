"""Deterministic, fail-closed integrity checks for entity surface cleaning.

The contract in this module is deliberately independent of publications,
claims, signals, full text, and provider clients. It only authorizes a
boundary mutation when repository code names the transformation class or when
the mutation is formatting-only. Historical values remain audit inputs; they
are never rewritten by this module.
"""
from __future__ import annotations

import json
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code_engine.normalization.composite_endpoints import decompose_endpoint
from code_engine.normalization.lexical import normalize_lexical_surface
from code_engine.normalization.llm_entity_cleaner import deterministic_clean_entity_surface


BoundaryPrimaryClass = Literal[
    "validated_semantic_normalization",
    "validated_formatting_normalization",
    "unsupported_boundary_change",
    "ambiguous_rule_authority",
    "unclassified",
]
SemanticEffect = Literal[
    "semantically_preserving_by_existing_authority",
    "canonical_identity_unchanged",
    "canonical_identity_changed",
    "canonical_identity_became_unresolved",
    "canonical_identity_collision",
    "unknown_semantic_effect",
]
EntityIntegrityStatus = Literal[
    "validated",
    "validated_normalization",
    "historical_normalization_retained",
    "blocked_lossy_cleaning",
    "canonical_identity_unresolved",
    "normalization_revision_candidate",
    "historical_integrity_warning",
]

# Compatibility vocabulary retained for the completed v1 audit adapter.
CleanerIntegrityClass = Literal[
    "validated_normalization",
    "formatting_only",
    "potentially_lossy_cleaning",
    "canonical_identity_changed",
    "downstream_scientific_object_affected",
    "unresolved",
]


def exact_surface(value: Any) -> str:
    return unicodedata.normalize("NFKC", str(value or "")).strip()


def normalized_format(value: Any) -> str:
    """Formatting fingerprint that preserves every Unicode letter/digit."""
    text = exact_surface(value).casefold()
    return "".join(character for character in text if character.isalnum())


def boundary_change(source: Any, target: Any) -> tuple[bool, bool]:
    """Return leading/trailing removal flags for a surface transformation."""
    before, after = exact_surface(source), exact_surface(target)
    if not before or not after or before.casefold() == after.casefold():
        return False, False
    folded_before, folded_after = before.casefold(), after.casefold()
    leading = len(before) > len(after) and folded_before.endswith(folded_after)
    trailing = len(before) > len(after) and folded_before.startswith(folded_after)
    return leading, trailing


def boundary_attributes(source: Any, target: Any) -> dict[str, bool]:
    before, after = exact_surface(source), exact_surface(target)
    leading, trailing = boundary_change(before, after)
    before_punctuation = "".join(c for c in before if not c.isalnum() and not c.isspace())
    after_punctuation = "".join(c for c in after if not c.isalnum() and not c.isspace())
    return {
        "leading_changed": leading,
        "trailing_changed": trailing,
        "case_changed": before.casefold() == after.casefold() and before != after,
        "punctuation_changed": before_punctuation != after_punctuation,
        "whitespace_changed": " ".join(before.split()) != " ".join(after.split()),
        "prefix_removed": leading,
        "suffix_removed": trailing,
        "token_boundary_changed": normalized_format(before) != normalized_format(after),
    }


def _plural_rule_supports(source: str, target: str) -> bool:
    """Conservative documented plural-to-singular surface normalization."""
    before, after = exact_surface(source), exact_surface(target)
    if not before or not after or " " in before.strip() or " " in after.strip():
        return False
    folded_before, folded_after = before.casefold(), after.casefold()
    if len(after) >= 3 and folded_before == folded_after + "s":
        return True
    return bool(
        len(after) >= 3
        and folded_after.endswith("y")
        and folded_before == folded_after[:-1] + "ies"
    )


def deterministic_rule_supports(source: Any, target: Any) -> tuple[bool, str | None]:
    """Return the exact repository rule that authorizes a surface change."""
    before, after = exact_surface(source), exact_surface(target)
    if not before or not after or before == after:
        return False, None
    if normalized_format(before) == normalized_format(after):
        return True, "formatting_nfkc_case_whitespace_punctuation_v1"
    decomposition = decompose_endpoint(before)
    if (
        decomposition.endpoint_decomposition_status == "decomposed"
        and exact_surface(decomposition.measured_entity_raw).casefold() == after.casefold()
    ):
        return True, decomposition.endpoint_decomposition_method
    cleaned, _removed, _aliases, extra_heads = deterministic_clean_entity_surface(before)
    if exact_surface(cleaned).casefold() == after.casefold() and before.casefold() != after.casefold():
        return True, "entity_cleaner_deterministic_modifier_rule_v1"
    if any(exact_surface(head.surface).casefold() == after.casefold() for head in extra_heads):
        return True, "entity_cleaner_deterministic_pathway_component_rule_v1"
    if _plural_rule_supports(before, after):
        return True, "documented_plural_to_singular_rule_v1"
    return False, None


class EntityCleanerBoundaryIntegrityV1(BaseModel):
    """One immutable before/proposal/repair boundary decision."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["entity_cleaner_boundary_integrity_v1"] = "entity_cleaner_boundary_integrity_v1"
    transformation_stage: Literal[
        "endpoint_preclean", "entity_cleaner", "entity_normalization",
        "alias_lookup", "generic_text_cleanup",
    ]
    source_surface_value: str
    l1_raw_extracted_value: str | None = None
    historical_cleaned_value: str | None = None
    historical_normalized_value: str | None = None
    proposed_cleaned_value: str
    new_cleaned_candidate: str
    new_normalized_candidate: str | None = None
    normalization_status: str = "not_attempted"
    primary_class: BoundaryPrimaryClass
    secondary_attributes: dict[str, bool]
    rule_id: str | None = None
    rule_authority: str
    boundary_change_allowed: bool
    entity_integrity_status: EntityIntegrityStatus
    raw_before: str | None = None
    raw_after: str | None = None
    historical_cleaned_retained: bool = True
    historical_normalized_retained: bool = True
    historical_object_modified: bool = False
    fuzzy_authority_used: bool = False
    fulltext_authority_used: bool = False
    same_publication_authority_used: bool = False

    @model_validator(mode="after")
    def immutable_and_fail_closed(self):
        if self.raw_before != self.raw_after:
            raise ValueError("raw_entity_mutation_forbidden")
        if self.historical_object_modified:
            raise ValueError("historical_entity_lineage_mutation_forbidden")
        if self.fuzzy_authority_used or self.fulltext_authority_used or self.same_publication_authority_used:
            raise ValueError("forbidden_entity_repair_authority")
        if not self.boundary_change_allowed and self.new_cleaned_candidate != self.source_surface_value:
            raise ValueError("rejected_boundary_change_must_preserve_source_surface")
        return self


def evaluate_boundary_integrity(
    source: Any,
    proposed: Any,
    *,
    stage: Literal[
        "endpoint_preclean", "entity_cleaner", "entity_normalization",
        "alias_lookup", "generic_text_cleanup",
    ],
    l1_raw_entity: Any = None,
    historical_cleaned: Any = None,
    historical_normalized: Any = None,
    proposal_authority: str = "historical_cleaner_output",
) -> EntityCleanerBoundaryIntegrityV1:
    before, after = exact_surface(source), exact_surface(proposed)
    attributes = boundary_attributes(before, after)
    is_boundary_change = attributes["leading_changed"] or attributes["trailing_changed"]
    supported, rule_id = deterministic_rule_supports(before, after)

    if not is_boundary_change:
        primary: BoundaryPrimaryClass = "unclassified"
        allowed = True
        authority = "not_a_boundary_change"
    elif normalized_format(before) == normalized_format(after):
        primary = "validated_formatting_normalization"
        allowed = True
        rule_id = rule_id or "formatting_nfkc_case_whitespace_punctuation_v1"
        authority = "repository_deterministic_formatting_contract"
    elif supported:
        primary = "validated_semantic_normalization"
        allowed = True
        authority = "repository_deterministic_semantic_contract"
    elif stage == "entity_cleaner" and proposal_authority in {
        "historical_cleaner_output", "llm_model_output", "llm_cache_output",
    }:
        primary = "ambiguous_rule_authority"
        allowed = False
        authority = proposal_authority
    elif stage in {"endpoint_preclean", "entity_normalization", "alias_lookup", "generic_text_cleanup"}:
        primary = "unsupported_boundary_change"
        allowed = False
        authority = "no_explicit_deterministic_rule"
    else:
        primary = "unclassified"
        allowed = False
        authority = "no_classification_authority"

    raw = exact_surface(l1_raw_entity) if l1_raw_entity is not None else None
    return EntityCleanerBoundaryIntegrityV1(
        transformation_stage=stage,
        source_surface_value=before,
        l1_raw_extracted_value=raw,
        historical_cleaned_value=(
            exact_surface(historical_cleaned) if historical_cleaned is not None else None
        ),
        historical_normalized_value=(
            exact_surface(historical_normalized) if historical_normalized is not None else None
        ),
        proposed_cleaned_value=after,
        new_cleaned_candidate=after if allowed else before,
        primary_class=primary,
        secondary_attributes=attributes,
        rule_id=rule_id,
        rule_authority=authority,
        boundary_change_allowed=allowed,
        entity_integrity_status=("validated_normalization" if allowed else "blocked_lossy_cleaning"),
        raw_before=raw,
        raw_after=raw,
    )


class ExactLocalIdentityV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_id: str
    canonical_name: str
    authority: str


class LocalExactIdentityAuthority:
    """Read-only exact index over accepted local cache records."""

    def __init__(self, accepted_cache_path: str | Path):
        self.path = Path(accepted_cache_path)
        index: dict[str, dict[tuple[str, str], set[str]]] = defaultdict(lambda: defaultdict(set))
        if self.path.is_file():
            with self.path.open(encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    record = json.loads(line)
                    canonical_id = str(record.get("canonical_id") or "")
                    canonical_name = str(record.get("canonical_name") or "")
                    if not canonical_id or not canonical_name:
                        continue
                    identity = (canonical_id, canonical_name)
                    surfaces = {
                        str(record.get("surface") or ""),
                        str(record.get("normalized_surface") or ""),
                        canonical_name,
                        *(str(value) for value in record.get("aliases") or []),
                    }
                    for surface in surfaces:
                        key = normalize_lexical_surface(surface).normalized_surface.casefold()
                        if key:
                            index[key][identity].add("accepted_local_cache_exact_surface_or_alias")
        self._index = index

    def lookup(self, surface: Any) -> tuple[ExactLocalIdentityV1 | None, str, list[ExactLocalIdentityV1]]:
        key = normalize_lexical_surface(exact_surface(surface)).normalized_surface.casefold()
        candidates = [
            ExactLocalIdentityV1(
                canonical_id=identity[0], canonical_name=identity[1],
                authority=sorted(authorities)[0],
            )
            for identity, authorities in sorted(self._index.get(key, {}).items())
        ]
        if len(candidates) == 1:
            return candidates[0], "resolved_exact_local_authority", candidates
        if len(candidates) > 1:
            return None, "ambiguous_multiple_local_identities", candidates
        return None, "unresolved_exact_local_authority", []


def classify_surface_lineage(
    *, l1_raw_entity: Any, cleaner_input_entity: Any,
    cleaner_output_entity: Any, historical_canonical_entity: Any = None,
    historical_canonical_aliases: list[str] | None = None,
    downstream_object_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Compatibility adapter for the completed corruption audit v1."""
    raw = exact_surface(l1_raw_entity)
    cleaner_input = exact_surface(cleaner_input_entity)
    cleaner_output = exact_surface(cleaner_output_entity)
    canonical = exact_surface(historical_canonical_entity)
    canonical_aliases = [exact_surface(item) for item in historical_canonical_aliases or [] if exact_surface(item)]
    downstream = sorted(set(downstream_object_ids or []))

    stages: list[tuple[str, str, str]] = []
    if raw and cleaner_input and raw != cleaner_input:
        stages.append(("endpoint_preclean", raw, cleaner_input))
    if cleaner_input and cleaner_output and cleaner_input != cleaner_output:
        stages.append(("entity_cleaner", cleaner_input, cleaner_output))

    supported_rules: list[str] = []
    formatting_stage_count = 0
    leading_changed = trailing_changed = potentially_lossy = False
    for stage, before, after in stages:
        decision = evaluate_boundary_integrity(before, after, stage=stage)  # type: ignore[arg-type]
        leading_changed |= decision.secondary_attributes["leading_changed"]
        trailing_changed |= decision.secondary_attributes["trailing_changed"]
        if normalized_format(before) == normalized_format(after):
            formatting_stage_count += 1
        if decision.primary_class == "validated_semantic_normalization" and decision.rule_id:
            supported_rules.append(decision.rule_id)
        elif decision.primary_class in {"unsupported_boundary_change", "ambiguous_rule_authority"}:
            potentially_lossy = True

    classifications: list[CleanerIntegrityClass]
    if stages and not potentially_lossy and supported_rules:
        classifications = ["validated_normalization"]
    elif stages and not potentially_lossy and formatting_stage_count == len(stages):
        classifications = ["formatting_only"]
    elif potentially_lossy:
        classifications = ["potentially_lossy_cleaning"]
    elif stages:
        classifications = ["unresolved"]
    else:
        classifications = ["formatting_only"]

    resolution_surfaces = {normalized_format(canonical), *(normalized_format(item) for item in canonical_aliases)}
    corrupted_surface_selected = bool(
        normalized_format(cleaner_input) in resolution_surfaces
        or normalized_format(cleaner_output) in resolution_surfaces
    )
    canonical_changed = bool(
        potentially_lossy and any(stage == "endpoint_preclean" for stage, _b, _a in stages)
        and canonical and raw and normalized_format(canonical) != normalized_format(raw)
        and corrupted_surface_selected
    )
    if canonical_changed:
        classifications.append("canonical_identity_changed")
    if potentially_lossy and downstream:
        classifications.append("downstream_scientific_object_affected")

    return {
        "classifications": classifications,
        "transformation_stages": [stage for stage, _before, _after in stages],
        "supported_normalization_rules": sorted(set(supported_rules)),
        "leading_character_changed": leading_changed,
        "trailing_character_changed": trailing_changed,
        "potentially_lossy": potentially_lossy,
        "canonical_identity_changed_due_lossy_cleaning": canonical_changed,
        "downstream_scientific_object_affected": bool(potentially_lossy and downstream),
    }


class EntityCleanerCorruptionAuditV1(BaseModel):
    """Compatibility schema retained for existing completed-run validation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["entity_cleaner_corruption_audit_v1"] = "entity_cleaner_corruption_audit_v1"
    source_run_ref: str
    claim_id: str | None
    observation_id: str | None
    mention_role: Literal["subject", "object"]
    l1_raw_entity: str | None
    historical_cleaner_input_entity: str
    historical_cleaner_output_entities: list[str] = Field(default_factory=list)
    historical_normalized_canonical_entity: str | None
    historical_normalized_canonical_aliases: list[str] = Field(default_factory=list)
    classifications: list[CleanerIntegrityClass] = Field(min_length=1)
    transformation_stages: list[Literal["endpoint_preclean", "entity_cleaner"]] = Field(default_factory=list)
    supported_normalization_rules: list[str] = Field(default_factory=list)
    leading_character_changed: bool
    trailing_character_changed: bool
    potentially_lossy: bool
    canonical_identity_changed_due_lossy_cleaning: bool
    downstream_scientific_object_affected: bool
    downstream_signal_ids: list[str] = Field(default_factory=list)
    raw_value_retained: bool = True
    historical_value_retained: bool = True
    historical_object_modified: bool = False

    @model_validator(mode="after")
    def lossy_rows_fail_closed(self):
        if self.potentially_lossy and "potentially_lossy_cleaning" not in self.classifications:
            raise ValueError("lossy_lineage_must_be_classified")
        if self.historical_object_modified:
            raise ValueError("historical_cleaner_lineage_must_be_immutable")
        return self
