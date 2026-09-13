"""Context-aware V1_1 biological-unit compatibility for shadow development.

V1_1 composes the immutable V1 registry and policy. It limits biological-unit
authority to explicit biological-unit and anatomical-region dimensions; disease,
genotype, treatment, and unresolved context remain outside this module.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Literal

from code_engine.normalization.lexical import normalize_lexical_surface
from code_engine.search.biological_unit_compatibility_v1 import (
    BiologicalUnitRegistryV1,
    BiologicalUnitTargetV1,
    CompatibilityState,
    ResolutionStatus,
    _aggregate_cell_state,
    _aggregate_region_state,
    _dedup_refs,
    _longest_surface_matches,
    _unique,
)


ContextDimension = Literal[
    "BIOLOGICAL_UNIT", "ANATOMICAL_REGION", "DISEASE_CONTEXT", "GENOTYPE_CONTEXT",
    "TREATMENT_CONTEXT", "OTHER_CONTEXT", "UNRESOLVED_CONTEXT_DIMENSION",
]
CONTEXT_DIMENSIONS = (
    "BIOLOGICAL_UNIT", "ANATOMICAL_REGION", "DISEASE_CONTEXT", "GENOTYPE_CONTEXT",
    "TREATMENT_CONTEXT", "OTHER_CONTEXT", "UNRESOLVED_CONTEXT_DIMENSION",
)
APPLICABILITY_REASON_CODES = {
    "APPLICABLE_UNIT_CONSTRAINT", "APPLICABLE_REGION_CONSTRAINT",
    "NON_UNIT_DISEASE_CONTEXT", "NON_UNIT_GENOTYPE_CONTEXT", "NON_UNIT_TREATMENT_CONTEXT",
    "UNRESOLVED_CONTEXT_DIMENSION", "NO_UNIT_OR_REGION_CONSTRAINT",
}


@dataclass(frozen=True)
class BiologicalUnitCompatibilityApplicabilityV1:
    applicable: bool
    target_context_dimensions: tuple[ContextDimension, ...]
    unit_constraints_present: bool
    region_constraints_present: bool
    non_unit_context_qualifiers: tuple[str, ...]
    reason_codes: tuple[str, ...]
    resolver_status: ResolutionStatus


@dataclass(frozen=True)
class BiologicalUnitCompatibilityDecisionV1_1:
    applicability: dict[str, Any]
    target_units: tuple[dict[str, Any], ...]
    target_anatomical_regions: tuple[dict[str, Any], ...]
    observed_units: tuple[dict[str, Any], ...]
    cell_identity_state: CompatibilityState
    anatomical_region_state: CompatibilityState
    overall_state: CompatibilityState
    reason_codes: tuple[str, ...]
    matched_surfaces: tuple[dict[str, Any], ...]
    source_evidence_scope: tuple[str, ...]
    resolver_status: ResolutionStatus
    incompatibility_preconditions: dict[str, bool]
    registry_version: str
    policy_version: str
    decision_mode: str = "deterministic"
    preacquisition_only: bool = True
    modifies_tier: bool = False
    modifies_acquisition: bool = False
    modifies_sample_membership: bool = False


class BiologicalUnitRegistryV1_1:
    """Immutable V1 registry plus an explicit context-dimension overlay."""

    def __init__(self, base_payload: dict[str, Any], overlay: dict[str, Any]):
        self.base = BiologicalUnitRegistryV1(base_payload)
        self.version = overlay["registry_version"]
        defaults = overlay["dimension_defaults_by_unit_type"]
        self.dimensions_by_id: dict[str, tuple[str, ...]] = {
            canonical_id: tuple(defaults[ref.unit_type]) for canonical_id, ref in self.base.entries.items()
        }
        seen = set()
        for annotation in overlay["context_dimension_annotations"]:
            canonical_id = annotation["canonical_id"]
            if canonical_id not in self.base.entries or canonical_id in seen:
                raise ValueError(f"invalid or duplicate dimension annotation: {canonical_id}")
            dimensions = tuple(annotation["context_dimensions"])
            if not dimensions or not set(dimensions) <= set(CONTEXT_DIMENSIONS):
                raise ValueError(f"invalid context dimensions: {canonical_id}")
            self.dimensions_by_id[canonical_id] = dimensions
            seen.add(canonical_id)
        if overlay.get("relations_added_or_changed"):
            raise ValueError("V1_1 context overlay must not silently change registry relations")

    def dimensions(self, canonical_id: str) -> tuple[str, ...]:
        return self.dimensions_by_id[canonical_id]

    def resolve_target(self, qualifiers: list[str], base_policy: dict[str, Any]):
        resolved = self.base.resolve_target(qualifiers, base_policy)
        units = _dedup_refs([
            ref for ref in resolved.required_units if "BIOLOGICAL_UNIT" in self.dimensions(ref.canonical_id)
        ])
        regions = _dedup_refs([
            ref for ref in (*resolved.required_anatomical_regions, *resolved.required_units)
            if "ANATOMICAL_REGION" in self.dimensions(ref.canonical_id)
        ])
        return BiologicalUnitTargetV1(
            required_units=tuple(units),
            required_unit_types=tuple(_unique(ref.unit_type for ref in units)),
            required_anatomical_regions=tuple(regions),
            allow_exact=resolved.allow_exact,
            allow_alias=resolved.allow_alias,
            allow_descendant=resolved.allow_descendant,
            allow_model_of=resolved.allow_model_of,
            allow_broader_container=resolved.allow_broader_container,
            require_anatomical_region_match_when_specified=resolved.require_anatomical_region_match_when_specified,
        )

    def dimensions_for_qualifiers(self, qualifiers: list[str], v1_1_policy: dict[str, Any]):
        found = []
        for qualifier in qualifiers:
            normalized = normalize_lexical_surface(qualifier).normalized_surface
            for surface, _, _ in _longest_surface_matches(normalized, self.base.surface_index):
                for canonical_id, _ in self.base.surface_index[surface]:
                    found.extend(self.dimensions(canonical_id))
            if any(re.search(pattern, normalized) for pattern in v1_1_policy["genotype_context_patterns"]):
                found.append("GENOTYPE_CONTEXT")
            if any(re.search(pattern, normalized) for pattern in v1_1_policy["treatment_context_patterns"]):
                found.append("TREATMENT_CONTEXT")
        if not found:
            found.append("UNRESOLVED_CONTEXT_DIMENSION")
        return tuple(dimension for dimension in CONTEXT_DIMENSIONS if dimension in found)

    def filter_observations(self, observations):
        return [item for item in observations if set(self.dimensions(item.unit.canonical_id))
                & {"BIOLOGICAL_UNIT", "ANATOMICAL_REGION"}]


def determine_applicability(
    registry: BiologicalUnitRegistryV1_1,
    base_policy: dict[str, Any],
    v1_1_policy: dict[str, Any],
    target_context_qualifiers: list[str],
):
    target = registry.resolve_target(target_context_qualifiers, base_policy)
    dimensions = registry.dimensions_for_qualifiers(target_context_qualifiers, v1_1_policy)
    unit_present = bool(target.required_units)
    region_present = bool(target.required_anatomical_regions)
    applicable = unit_present or region_present
    reasons = []
    if unit_present:
        reasons.append("APPLICABLE_UNIT_CONSTRAINT")
    if region_present:
        reasons.append("APPLICABLE_REGION_CONSTRAINT")
    for dimension, reason in (
        ("DISEASE_CONTEXT", "NON_UNIT_DISEASE_CONTEXT"),
        ("GENOTYPE_CONTEXT", "NON_UNIT_GENOTYPE_CONTEXT"),
        ("TREATMENT_CONTEXT", "NON_UNIT_TREATMENT_CONTEXT"),
        ("UNRESOLVED_CONTEXT_DIMENSION", "UNRESOLVED_CONTEXT_DIMENSION"),
    ):
        if dimension in dimensions:
            reasons.append(reason)
    if not applicable:
        reasons.append("NO_UNIT_OR_REGION_CONSTRAINT")
    if not set(reasons) <= APPLICABILITY_REASON_CODES:
        raise ValueError("unknown applicability reason code")
    nonunit = {"DISEASE_CONTEXT", "GENOTYPE_CONTEXT", "TREATMENT_CONTEXT", "OTHER_CONTEXT",
               "UNRESOLVED_CONTEXT_DIMENSION"}
    applicability = BiologicalUnitCompatibilityApplicabilityV1(
        applicable=applicable,
        target_context_dimensions=dimensions,
        unit_constraints_present=unit_present,
        region_constraints_present=region_present,
        non_unit_context_qualifiers=tuple(target_context_qualifiers) if set(dimensions) & nonunit else (),
        reason_codes=tuple(reasons),
        resolver_status="resolved" if "UNRESOLVED_CONTEXT_DIMENSION" not in dimensions else "unresolved",
    )
    return applicability, target


def decide_biological_unit_compatibility_v1_1(
    registry: BiologicalUnitRegistryV1_1,
    base_policy: dict[str, Any],
    v1_1_policy: dict[str, Any],
    target_context_qualifiers: list[str],
    *,
    title: str,
    abstract: str,
    publication_metadata: dict[str, Any] | None = None,
) -> BiologicalUnitCompatibilityDecisionV1_1:
    """Decide from pre-acquisition fields without disease/genotype authority."""
    del publication_metadata
    applicability, target = determine_applicability(
        registry, base_policy, v1_1_policy, target_context_qualifiers
    )
    observed = registry.filter_observations(registry.base.detect(title, abstract, base_policy))
    relevant_experimental = [item for item in observed
                             if item.evidence_role == "experimental_biological_unit"]
    cell_reasons: list[str] = []
    region_reasons: list[str] = []
    if not applicability.applicable:
        cell_state = region_state = overall = "UNRESOLVED"
        reasons = ("NO_BIOLOGICAL_UNIT_EVIDENCE",)
        resolver_status = applicability.resolver_status
    else:
        if target.required_units:
            cell_state, cell_reasons, cell_status = _aggregate_cell_state(registry.base, target, observed)
        else:
            cell_state, cell_reasons, cell_status = "EXACT", [], "resolved"
        if target.required_anatomical_regions and target.require_anatomical_region_match_when_specified:
            region_state, region_reasons, region_status = _aggregate_region_state(registry.base, target, observed)
        else:
            region_state, region_reasons, region_status = "EXACT", [], "resolved"
        if "INCOMPATIBLE" in {cell_state, region_state}:
            overall = "INCOMPATIBLE"
        elif "UNRESOLVED" in {cell_state, region_state}:
            overall = "UNRESOLVED"
        elif "AUTHORIZED_COMPATIBLE" in {cell_state, region_state}:
            overall = "AUTHORIZED_COMPATIBLE"
        else:
            overall = "EXACT"
        reasons = tuple(_unique([*cell_reasons, *region_reasons]))
        statuses = {cell_status, region_status}
        resolver_status = "ambiguous" if "ambiguous" in statuses else (
            "unresolved" if "unresolved" in statuses else "resolved"
        )
    positive_incompatible_evidence = overall != "INCOMPATIBLE" or (
        cell_state == "INCOMPATIBLE" or region_state == "INCOMPATIBLE"
    )
    authorizing_reasons = {"EXACT_CANONICAL_MATCH", "ALIAS_MATCH", "AUTHORIZED_SUBTYPE", "AUTHORIZED_MODEL_OF"}
    no_authorization_in_incompatible_dimension = (
        (cell_state != "INCOMPATIBLE" or not set(cell_reasons) & authorizing_reasons)
        and (region_state != "INCOMPATIBLE" or not set(region_reasons) & authorizing_reasons)
    )
    preconditions = {
        "applicable_resolved_target_unit_or_region_constraint": applicability.applicable
        and applicability.resolver_status == "resolved",
        "resolved_relevant_experimental_observed_unit": bool(relevant_experimental),
        "positive_curated_directional_incompatibility": positive_incompatible_evidence,
        "no_exact_alias_subtype_or_model_of_authorization": overall != "INCOMPATIBLE"
        or no_authorization_in_incompatible_dimension,
        "not_background_or_incidental_mention": overall != "INCOMPATIBLE" or bool(relevant_experimental),
    }
    if overall == "INCOMPATIBLE" and not all(preconditions.values()):
        overall = "UNRESOLVED"
        if cell_state == "INCOMPATIBLE":
            cell_state = "UNRESOLVED"
        if region_state == "INCOMPATIBLE":
            region_state = "UNRESOLVED"
        reasons = tuple(_unique([*reasons, "CELL_TYPE_UNRESOLVED"]))
        resolver_status = "unresolved"
    return BiologicalUnitCompatibilityDecisionV1_1(
        applicability=asdict(applicability),
        target_units=tuple(asdict(ref) for ref in target.required_units),
        target_anatomical_regions=tuple(asdict(ref) for ref in target.required_anatomical_regions),
        observed_units=tuple({**asdict(item.unit), "evidence_role": item.evidence_role} for item in observed),
        cell_identity_state=cell_state,
        anatomical_region_state=region_state,
        overall_state=overall,
        reason_codes=reasons,
        matched_surfaces=tuple({
            "canonical_id": item.unit.canonical_id, "matched_surface": item.matched_surface,
            "match_type": item.match_type, "evidence_role": item.evidence_role, "field": item.field,
            "normalized_start": item.normalized_start, "normalized_end": item.normalized_end,
            "normalized_sentence": item.sentence,
        } for item in observed),
        source_evidence_scope=("ScientificPropositionTargetV1.context_qualifiers", "publication.title",
                               "publication.abstract"),
        resolver_status=resolver_status,
        incompatibility_preconditions=preconditions,
        registry_version=registry.version,
        policy_version=v1_1_policy["policy_version"],
    )
