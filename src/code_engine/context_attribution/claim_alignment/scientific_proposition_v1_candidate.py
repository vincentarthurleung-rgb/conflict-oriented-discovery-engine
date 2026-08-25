"""Candidate-only scientific proposition compatibility for Claim Alignment.

The contract consumes validated Claim Alignment v2 and Experimental Core
structures.  It deliberately does not infer scientific identity from free text,
string similarity, publication identity, or result direction.  Historical
alignment records are inputs and are never rewritten.
"""
from __future__ import annotations

from typing import Any, Iterable, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from code_engine.extraction_assets.experimental_core.models import (
    ExperimentalFactorRecord,
    MeasurementRecord,
    ObservedResultRecord,
    StructuredExperimentalObservationRevision,
)
from code_engine.extraction_assets.scientific_entity_integrity import (
    ScientificEntityIntegrityGateResultV1,
    require_scientific_entity_integrity,
)

from ..layer_identity import layer_identity
from .granularity import GranularityBridgeAssessment


SemanticRoleV1 = Literal[
    "proposition_critical",
    "compatibility_qualifier",
    "context_only",
    "not_applicable",
    "semantic_role_unresolved",
]
DimensionCompatibilityStateV1 = Literal[
    "compatible_exact",
    "compatible_semantic_family",
    "compatible_with_granularity_qualification",
    "unresolved",
    "incompatible",
    "missing_authority",
    "not_applicable",
]
MeasurementCompatibilityStateV1 = Literal[
    "compatible_exact",
    "compatible_semantic_family",
    "compatible_with_granularity_qualification",
    "unresolved",
    "incompatible_target",
    "incompatible_endpoint",
    "incompatible_result_semantics",
    "missing_authority",
]
AlignmentV3State = Literal[
    "aligned_exact",
    "aligned_compatible",
    "aligned_with_granularity_qualification",
    "partial_reviewable",
    "blocked_proposition_mismatch",
    "blocked_measurement_target_mismatch",
    "blocked_endpoint_mismatch",
    "blocked_result_semantic_mismatch",
    "blocked_intervention_proposition_mismatch",
    "blocked_causal_mode_mismatch",
    "unresolved_missing_authority",
]


# These maps operate only on already structured enum-like values.  They are
# intentionally small: unknown values stay unresolved and no lexical or fuzzy
# matching is attempted.
MEASUREMENT_PROPERTY_FAMILY_V1: dict[str, str] = {
    "abundance": "abundance",
    "abundance_expression": "abundance",
    "activity": "activity",
    "modification_state": "modification_state",
    "localization": "localization",
    "apoptosis": "phenotype_apoptosis",
    "viability": "phenotype_viability",
    "migration": "phenotype_migration",
    "invasion": "phenotype_invasion",
    "phenotype": "phenotype",
    "association": "association",
    "clinical_outcome": "clinical_outcome",
    "response_rate": "clinical_response_rate",
    "survival": "clinical_survival",
}

CAUSAL_MODE_FAMILY_V1: dict[str, str | None] = {
    "interventional_experiment": "interventional_effect",
    "observational_comparison": "observational_association",
    "descriptive_measurement": "descriptive_observation",
    "non_experimental_claim": "non_experimental_evidence",
    "unresolved": None,
}

INTERVENTION_ROLE_FAMILY_V1: dict[str, str | None] = {
    "intervention": "controlled_perturbation",
    "treatment": "controlled_perturbation",
    "genetic_manipulation": "genetic_perturbation",
    "exposure": "exposure_perturbation",
    "environmental_condition": None,
    "disease_condition": None,
    "cohort": None,
    "experimental_group": None,
    "control": None,
    "comparator": None,
    "baseline": None,
    "sample_condition": None,
    "unresolved": None,
}

CONTEXT_ONLY_DIMENSIONS_V1 = (
    "species",
    "genotype",
    "time",
    "localization",
    "disease_state",
    "dose",
    "cohort",
)


class StrictCandidateModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class StructuredSemanticValueV1(StrictCandidateModel):
    schema_version: Literal[
        "structured_semantic_value_v1"
    ] = "structured_semantic_value_v1"
    value: str | None = None
    canonical_identity: str | None = None
    semantic_family: str | None = None
    authority_state: Literal[
        "validated_canonical",
        "controlled_vocabulary",
        "structured_only",
        "missing",
        "not_applicable",
    ]
    source_refs: list[str] = Field(default_factory=list)


class SemanticRoleAssignmentV1(StrictCandidateModel):
    schema_version: Literal[
        "scientific_proposition_semantic_role_v1"
    ] = "scientific_proposition_semantic_role_v1"
    dimension_id: str
    semantic_role: SemanticRoleV1
    role_basis: str
    proposition_scope_explicit: bool = False


class InterventionPropositionV1(StrictCandidateModel):
    schema_version: Literal[
        "intervention_proposition_v1"
    ] = "intervention_proposition_v1"
    intervention_mode: Literal["none", "single", "combination", "unresolved"]
    factor_families: list[str] = Field(default_factory=list)
    target_values: list[StructuredSemanticValueV1] = Field(default_factory=list)
    authority_state: Literal["resolved", "unresolved", "not_applicable"]
    source_refs: list[str] = Field(default_factory=list)


class CausalEvidentialModeV1(StrictCandidateModel):
    schema_version: Literal[
        "causal_evidential_mode_v1"
    ] = "causal_evidential_mode_v1"
    observation_type: str
    mode_family: str | None
    authority_state: Literal["resolved", "unresolved"]
    source_refs: list[str] = Field(default_factory=list)


class ExperimentalContrastSemanticsV1(StrictCandidateModel):
    schema_version: Literal[
        "experimental_contrast_semantics_v1"
    ] = "experimental_contrast_semantics_v1"
    contrast_role: Literal[
        "experimental_vs_reference",
        "observational_group_vs_reference",
        "no_explicit_contrast",
        "unresolved_reference_structure",
        "unresolved",
    ]
    reference_labels: list[StructuredSemanticValueV1] = Field(default_factory=list)
    comparison_link_count: int = 0
    baseline_link_count: int = 0
    authority_state: Literal["resolved", "unresolved", "not_applicable"]
    source_refs: list[str] = Field(default_factory=list)


class GranularityQualifierV1(StrictCandidateModel):
    schema_version: Literal[
        "scientific_proposition_granularity_qualifier_v1"
    ] = "scientific_proposition_granularity_qualifier_v1"
    dimension_id: str
    value: str | None = None
    canonical_identity: str | None = None
    bridge_status: str
    bridge_policy_identity: str | None = None
    semantic_role: SemanticRoleV1
    source_refs: list[str] = Field(default_factory=list)


class ScientificPropositionSignatureV1(StrictCandidateModel):
    schema_version: Literal[
        "scientific_proposition_signature_v1"
    ] = "scientific_proposition_signature_v1"
    observation_id: str
    subject_identity: str | None = None
    relation_effect_family: str | None = None
    object_target_identity: str | None = None
    outcome_variable_identity: str | None = None
    measurement_targets: list[StructuredSemanticValueV1] = Field(default_factory=list)
    measured_properties: list[StructuredSemanticValueV1] = Field(default_factory=list)
    assay_methods: list[StructuredSemanticValueV1] = Field(default_factory=list)
    unit_representations: list[StructuredSemanticValueV1] = Field(default_factory=list)
    result_semantics: list[StructuredSemanticValueV1] = Field(default_factory=list)
    intervention_proposition: InterventionPropositionV1
    causal_evidential_mode: CausalEvidentialModeV1
    experimental_contrast: ExperimentalContrastSemanticsV1
    granularity_qualifiers: list[GranularityQualifierV1] = Field(default_factory=list)
    semantic_roles: list[SemanticRoleAssignmentV1]
    excluded_result_identity_fields: list[str] = Field(
        default_factory=lambda: ["direction", "sign", "polarity", "negation"]
    )
    source_refs: list[str] = Field(default_factory=list)
    projection_version: Literal[
        "experimental_core_to_scientific_proposition_v1"
    ] = "experimental_core_to_scientific_proposition_v1"
    scientific_proposition_signature_identity: str

    @model_validator(mode="after")
    def enforce_direction_separation(self):
        required = {"direction", "sign", "polarity"}
        if not required.issubset(self.excluded_result_identity_fields):
            raise ValueError("result_direction_must_remain_outside_proposition_identity")
        role_ids = [row.dimension_id for row in self.semantic_roles]
        if len(role_ids) != len(set(role_ids)):
            raise ValueError("duplicate_semantic_role_assignment")
        return self


class DimensionCompatibilityAssessmentV1(StrictCandidateModel):
    schema_version: Literal[
        "scientific_dimension_compatibility_assessment_v1"
    ] = "scientific_dimension_compatibility_assessment_v1"
    dimension_id: str
    semantic_role: SemanticRoleV1
    values_a: list[str] = Field(default_factory=list)
    values_b: list[str] = Field(default_factory=list)
    compatibility_state: DimensionCompatibilityStateV1
    authority_refs: list[str] = Field(default_factory=list)
    reason: str
    raw_string_inequality_used_as_incompatibility: Literal[False] = False
    direction_used_as_identity: Literal[False] = False


class MeasurementPropositionCompatibilityV1(StrictCandidateModel):
    schema_version: Literal[
        "measurement_proposition_compatibility_v1"
    ] = "measurement_proposition_compatibility_v1"
    measurement_target: DimensionCompatibilityAssessmentV1
    measured_property_endpoint: DimensionCompatibilityAssessmentV1
    assay_method: DimensionCompatibilityAssessmentV1
    unit_representation: DimensionCompatibilityAssessmentV1
    result_semantic_level: DimensionCompatibilityAssessmentV1
    compatibility_state: MeasurementCompatibilityStateV1
    blocking_dimensions: list[str] = Field(default_factory=list)
    unresolved_dimensions: list[str] = Field(default_factory=list)
    assay_difference_is_proposition_mismatch: Literal[False] = False
    compatibility_identity: str


class ScientificPropositionCompatibilityV1(StrictCandidateModel):
    schema_version: Literal[
        "scientific_proposition_compatibility_v1"
    ] = "scientific_proposition_compatibility_v1"
    pair_id: str
    observation_a_id: str
    observation_b_id: str
    signature_a_identity: str
    signature_b_identity: str
    historical_alignment_v2_identity: str
    historical_alignment_v2_state: str
    entity_proposition: list[DimensionCompatibilityAssessmentV1]
    measurement_compatibility: MeasurementPropositionCompatibilityV1
    intervention_proposition: DimensionCompatibilityAssessmentV1
    causal_evidential_mode: DimensionCompatibilityAssessmentV1
    experimental_contrast: DimensionCompatibilityAssessmentV1
    granularity: list[DimensionCompatibilityAssessmentV1]
    alignment_v3_candidate_state: AlignmentV3State
    blocking_dimensions: list[str] = Field(default_factory=list)
    unresolved_dimensions: list[str] = Field(default_factory=list)
    compatibility_qualifier_dimensions: list[str] = Field(default_factory=list)
    alignment_basis: list[str]
    candidate_only: Literal[True] = True
    historical_alignment_modified: Literal[False] = False
    context_comparability_evaluated: Literal[False] = False
    result_direction_used_as_identity: Literal[False] = False
    string_inequality_used_as_incompatibility: Literal[False] = False
    validator_version: Literal[
        "scientific_proposition_compatibility_validator_v1"
    ] = "scientific_proposition_compatibility_validator_v1"
    scientific_proposition_compatibility_identity: str

    @model_validator(mode="after")
    def aligned_candidate_has_no_critical_gaps(self):
        if self.alignment_v3_candidate_state.startswith("aligned_") and (
            self.blocking_dimensions or self.unresolved_dimensions
        ):
            raise ValueError("aligned_candidate_has_unresolved_or_blocking_dimension")
        return self


def _semantic_value(
    *,
    value: Any,
    canonical_identity: str | None,
    semantic_family: str | None,
    authority_state: str,
    source_refs: Iterable[str],
) -> StructuredSemanticValueV1:
    rendered = None if value is None else str(value)
    return StructuredSemanticValueV1(
        value=rendered,
        canonical_identity=canonical_identity,
        semantic_family=semantic_family,
        authority_state=authority_state,
        source_refs=sorted(set(source_refs)),
    )


def _preferred_measurement_value(
    row: MeasurementRecord, field: Literal["target", "endpoint", "method", "unit"]
) -> StructuredSemanticValueV1:
    fields = {
        "target": (
            row.measured_entity_canonical,
            row.measured_entity_extracted,
            row.measured_entity_raw,
        ),
        "endpoint": (
            row.property_or_endpoint_canonical,
            row.property_or_endpoint_extracted,
            row.property_or_endpoint_raw,
        ),
        "method": (row.method_canonical, row.method_extracted, row.method_raw),
        "unit": (row.unit_canonical, row.unit_raw, None),
    }
    canonical, extracted, raw = fields[field]
    source = [row.measurement_id]
    if canonical is not None and row.authority_status in {"authoritative", "deterministic"}:
        return _semantic_value(
            value=canonical,
            canonical_identity=f"{field}:{canonical}",
            semantic_family=None,
            authority_state="validated_canonical",
            source_refs=source,
        )
    value = extracted if extracted is not None else raw
    return _semantic_value(
        value=value,
        canonical_identity=None,
        semantic_family=None,
        authority_state="structured_only" if value is not None else "missing",
        source_refs=source,
    )


def _unique_values(values: Iterable[StructuredSemanticValueV1]) -> list[StructuredSemanticValueV1]:
    by_key: dict[tuple[Any, ...], StructuredSemanticValueV1] = {}
    for value in values:
        key = (
            value.value,
            value.canonical_identity,
            value.semantic_family,
            value.authority_state,
        )
        by_key[key] = value
    return [by_key[key] for key in sorted(by_key, key=lambda item: tuple(str(x) for x in item))]


def _default_roles(
    qualifiers: Sequence[GranularityQualifierV1],
) -> list[SemanticRoleAssignmentV1]:
    rows = [
        SemanticRoleAssignmentV1(dimension_id=name, semantic_role="proposition_critical", role_basis=basis)
        for name, basis in (
            ("entity_proposition", "canonical Claim Alignment proposition core"),
            ("relation_effect_family", "canonical Claim Alignment proposition core"),
            ("measurement_target", "measured scientific object defines the proposition"),
            ("endpoint_property", "measured property defines the proposition"),
            ("result_semantic_level", "semantic result object defines claim meaning"),
            ("intervention_proposition", "proposition-defining perturbation structure"),
            ("causal_evidential_mode", "claim mode distinguishes description, association, and effect"),
            ("comparison_structure", "scientific contrast role defines the asserted comparison"),
            ("granularity", "explicit proposition-scoped granularity only"),
        )
    ]
    rows.extend([
        SemanticRoleAssignmentV1(
            dimension_id="assay_method",
            semantic_role="compatibility_qualifier",
            role_basis="method is separate from target and measured property",
        ),
        SemanticRoleAssignmentV1(
            dimension_id="unit_representation",
            semantic_role="compatibility_qualifier",
            role_basis="representation does not normally change proposition identity",
        ),
    ])
    explicitly_scoped = {row.dimension_id for row in qualifiers if row.value is not None}
    if "endpoint_compartment" in explicitly_scoped:
        explicitly_scoped.add("localization")
    rows.extend(
        SemanticRoleAssignmentV1(
            dimension_id=name,
            semantic_role="proposition_critical" if name in explicitly_scoped else "context_only",
            role_basis=(
                "explicit normalized proposition qualifier"
                if name in explicitly_scoped
                else "ordinary explanatory Context remains downstream"
            ),
            proposition_scope_explicit=name in explicitly_scoped,
        )
        for name in CONTEXT_ONLY_DIMENSIONS_V1
    )
    rows.append(SemanticRoleAssignmentV1(
        dimension_id="result_direction",
        semantic_role="not_applicable",
        role_basis="Contradiction Signal owns direction, sign, and polarity",
    ))
    return rows


def _signature_identity_payload(payload: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "observation_id",
        "subject_identity",
        "relation_effect_family",
        "object_target_identity",
        "outcome_variable_identity",
        "measurement_targets",
        "measured_properties",
        "assay_methods",
        "unit_representations",
        "result_semantics",
        "intervention_proposition",
        "causal_evidential_mode",
        "experimental_contrast",
        "granularity_qualifiers",
        "semantic_roles",
        "excluded_result_identity_fields",
        "projection_version",
    )
    return {key: payload[key] for key in keys}


def make_scientific_proposition_signature_v1(
    *,
    observation_id: str,
    subject_identity: str | None,
    relation_effect_family: str | None,
    object_target_identity: str | None,
    outcome_variable_identity: str | None = None,
    measurement_targets: Sequence[StructuredSemanticValueV1] = (),
    measured_properties: Sequence[StructuredSemanticValueV1] = (),
    assay_methods: Sequence[StructuredSemanticValueV1] = (),
    unit_representations: Sequence[StructuredSemanticValueV1] = (),
    result_semantics: Sequence[StructuredSemanticValueV1] = (),
    intervention_proposition: InterventionPropositionV1,
    causal_evidential_mode: CausalEvidentialModeV1,
    experimental_contrast: ExperimentalContrastSemanticsV1,
    granularity_qualifiers: Sequence[GranularityQualifierV1] = (),
    semantic_roles: Sequence[SemanticRoleAssignmentV1] | None = None,
    source_refs: Sequence[str] = (),
) -> ScientificPropositionSignatureV1:
    qualifiers = list(granularity_qualifiers)
    payload: dict[str, Any] = {
        "schema_version": "scientific_proposition_signature_v1",
        "observation_id": observation_id,
        "subject_identity": subject_identity,
        "relation_effect_family": relation_effect_family,
        "object_target_identity": object_target_identity,
        "outcome_variable_identity": outcome_variable_identity,
        "measurement_targets": list(measurement_targets),
        "measured_properties": list(measured_properties),
        "assay_methods": list(assay_methods),
        "unit_representations": list(unit_representations),
        "result_semantics": list(result_semantics),
        "intervention_proposition": intervention_proposition,
        "causal_evidential_mode": causal_evidential_mode,
        "experimental_contrast": experimental_contrast,
        "granularity_qualifiers": qualifiers,
        "semantic_roles": list(semantic_roles) if semantic_roles is not None else _default_roles(qualifiers),
        "excluded_result_identity_fields": ["direction", "sign", "polarity", "negation"],
        "source_refs": sorted(set(source_refs)),
        "projection_version": "experimental_core_to_scientific_proposition_v1",
    }
    dumped = {
        key: (value.model_dump(mode="json") if hasattr(value, "model_dump") else value)
        for key, value in payload.items()
    }
    for key in (
        "measurement_targets", "measured_properties", "assay_methods",
        "unit_representations", "result_semantics", "granularity_qualifiers",
        "semantic_roles",
    ):
        dumped[key] = [
            value.model_dump(mode="json") if hasattr(value, "model_dump") else value
            for value in payload[key]
        ]
    payload["scientific_proposition_signature_identity"] = layer_identity(
        "scientific_proposition_signature",
        "scientific_proposition_signature_identity_v1",
        _signature_identity_payload(dumped),
    )
    return ScientificPropositionSignatureV1.model_validate(payload)


def project_scientific_proposition_signature_v1(
    *,
    observation_id: str,
    proposition_core_signature: dict[str, Any],
    revision: StructuredExperimentalObservationRevision,
    factors: Sequence[ExperimentalFactorRecord],
    measurements: Sequence[MeasurementRecord],
    results: Sequence[ObservedResultRecord],
    granularity_bridges: Sequence[GranularityBridgeAssessment],
    side: Literal["a", "b"],
) -> ScientificPropositionSignatureV1:
    """Project one signature using fields already validated by repository models."""
    if revision.source_observation_identity != observation_id:
        raise ValueError("revision_observation_identity_mismatch")
    if {row.factor_id for row in factors} != set(revision.experimental_factor_ids):
        raise ValueError("factor_projection_refs_incomplete")
    if {row.measurement_id for row in measurements} != set(revision.measurement_ids):
        raise ValueError("measurement_projection_refs_incomplete")
    if {row.observed_result_id for row in results} != set(revision.observed_result_ids):
        raise ValueError("result_projection_refs_incomplete")

    targets = _unique_values(_preferred_measurement_value(row, "target") for row in measurements)
    endpoints = []
    properties = []
    methods = []
    units = []
    for row in measurements:
        endpoint = _preferred_measurement_value(row, "endpoint")
        family = MEASUREMENT_PROPERTY_FAMILY_V1.get(row.measurement_semantic_level)
        properties.append(StructuredSemanticValueV1(
            value=endpoint.value,
            canonical_identity=endpoint.canonical_identity,
            semantic_family=family,
            authority_state=(
                endpoint.authority_state
                if family is not None
                else "structured_only" if endpoint.value is not None else "missing"
            ),
            source_refs=endpoint.source_refs,
        ))
        endpoints.append(endpoint)
        methods.append(_preferred_measurement_value(row, "method"))
        units.append(_preferred_measurement_value(row, "unit"))

    measurement_by_id = {row.measurement_id: row for row in measurements}
    result_semantics = []
    for row in results:
        measurement = measurement_by_id.get(row.measurement_ref or "")
        level = measurement.measurement_semantic_level if measurement else None
        family = MEASUREMENT_PROPERTY_FAMILY_V1.get(level or "")
        has_qualitative = row.qualitative_result is not None
        has_quantitative = any(
            value is not None
            for value in (row.quantitative_value_canonical, row.effect_size, row.confidence_interval)
        )
        representation = (
            "mixed_result" if has_qualitative and has_quantitative else
            "qualitative_result" if has_qualitative else
            "quantitative_result" if has_quantitative else
            "unresolved_result_representation"
        )
        result_semantics.append(_semantic_value(
            value=f"{level or 'unknown'}:{representation}",
            canonical_identity=(
                f"result_semantics:{family}:{representation}" if family is not None else None
            ),
            semantic_family=(f"{family}:{representation}" if family is not None else None),
            authority_state="controlled_vocabulary" if family is not None else "structured_only",
            source_refs=[
                row.observed_result_id,
                *([] if measurement is None else [measurement.measurement_id]),
            ],
        ))

    active_factors = [
        row for row in factors
        if row.control_or_comparator_status == "not_control_or_comparator"
        and INTERVENTION_ROLE_FAMILY_V1.get(row.role) is not None
    ]
    if not active_factors and revision.observation_type == "descriptive_measurement":
        intervention = InterventionPropositionV1(
            intervention_mode="none",
            authority_state="not_applicable",
            source_refs=[revision.structured_observation_revision_id],
        )
    else:
        intervention_targets = []
        for row in active_factors:
            value = row.canonical_value
            canonical = row.canonical_identity
            if value is None:
                value = row.extracted_value if row.extracted_value is not None else row.raw_text
            intervention_targets.append(_semantic_value(
                value=value,
                canonical_identity=canonical,
                semantic_family=INTERVENTION_ROLE_FAMILY_V1.get(row.role),
                authority_state="validated_canonical" if canonical is not None else (
                    "structured_only" if value is not None else "missing"
                ),
                source_refs=[row.factor_id],
            ))
        intervention = InterventionPropositionV1(
            intervention_mode=(
                "unresolved" if not active_factors else
                "single" if len(active_factors) == 1 else "combination"
            ),
            factor_families=sorted({
                family for row in active_factors
                if (family := INTERVENTION_ROLE_FAMILY_V1.get(row.role)) is not None
            }),
            target_values=_unique_values(intervention_targets),
            authority_state=(
                "unresolved" if not active_factors or any(
                    value.canonical_identity is None for value in intervention_targets
                ) else "resolved"
            ),
            source_refs=[row.factor_id for row in active_factors],
        )

    mode_family = CAUSAL_MODE_FAMILY_V1.get(revision.observation_type)
    causal_mode = CausalEvidentialModeV1(
        observation_type=revision.observation_type,
        mode_family=mode_family,
        authority_state="resolved" if mode_family is not None else "unresolved",
        source_refs=[revision.structured_observation_revision_id],
    )

    comparison_count = sum(len(row.comparison_factor_refs) for row in results)
    baseline_count = sum(row.baseline_ref is not None for row in results)
    reference_factors = [
        row for row in factors
        if row.control_or_comparator_status == "control_or_comparator"
    ]
    reference_labels = [
        _semantic_value(
            value=(row.canonical_value if row.canonical_value is not None else row.extracted_value),
            canonical_identity=row.canonical_identity,
            semantic_family=row.role,
            authority_state="validated_canonical" if row.canonical_identity else "structured_only",
            source_refs=[row.factor_id],
        )
        for row in reference_factors
    ]
    if revision.observation_type == "descriptive_measurement" and not comparison_count and not baseline_count:
        contrast_role = "no_explicit_contrast"
        contrast_authority = "not_applicable"
    elif revision.observation_type == "interventional_experiment" and (comparison_count or baseline_count):
        contrast_role = "experimental_vs_reference"
        contrast_authority = "resolved"
    elif revision.observation_type == "observational_comparison" and (comparison_count or baseline_count):
        contrast_role = "observational_group_vs_reference"
        contrast_authority = "resolved"
    elif reference_factors:
        contrast_role = "unresolved_reference_structure"
        contrast_authority = "unresolved"
    else:
        contrast_role = "unresolved"
        contrast_authority = "unresolved"
    contrast = ExperimentalContrastSemanticsV1(
        contrast_role=contrast_role,
        reference_labels=_unique_values(reference_labels),
        comparison_link_count=comparison_count,
        baseline_link_count=baseline_count,
        authority_state=contrast_authority,
        source_refs=[row.observed_result_id for row in results] + [row.factor_id for row in reference_factors],
    )

    qualifiers = [
        GranularityQualifierV1(
            dimension_id=row.dimension_id,
            value=row.qualifier_a if side == "a" else row.qualifier_b,
            canonical_identity=(
                row.qualifier_a_identity if side == "a" else row.qualifier_b_identity
            ),
            bridge_status=row.bridge_status,
            bridge_policy_identity=row.bridge_policy_identity,
            semantic_role=(
                "proposition_critical"
                if (row.qualifier_a if side == "a" else row.qualifier_b) is not None
                else "not_applicable"
            ),
            source_refs=[row.granularity_bridge_identity],
        )
        for row in granularity_bridges
    ]

    return make_scientific_proposition_signature_v1(
        observation_id=observation_id,
        subject_identity=proposition_core_signature.get("canonical_subject_identity"),
        relation_effect_family=proposition_core_signature.get("canonical_relation_family"),
        object_target_identity=proposition_core_signature.get("canonical_endpoint_identity"),
        outcome_variable_identity=proposition_core_signature.get("outcome_variable_identity"),
        measurement_targets=targets,
        measured_properties=_unique_values(properties),
        assay_methods=_unique_values(methods),
        unit_representations=_unique_values(units),
        result_semantics=_unique_values(result_semantics),
        intervention_proposition=intervention,
        causal_evidential_mode=causal_mode,
        experimental_contrast=contrast,
        granularity_qualifiers=qualifiers,
        source_refs=[
            revision.structured_observation_revision_id,
            *[row.factor_id for row in factors],
            *[row.measurement_id for row in measurements],
            *[row.observed_result_id for row in results],
        ],
    )


def _display(values: Sequence[StructuredSemanticValueV1]) -> list[str]:
    return sorted({value.value for value in values if value.value is not None})


def _assessment(
    dimension_id: str,
    role: SemanticRoleV1,
    values_a: Sequence[str],
    values_b: Sequence[str],
    state: DimensionCompatibilityStateV1,
    reason: str,
    authority_refs: Iterable[str] = (),
) -> DimensionCompatibilityAssessmentV1:
    return DimensionCompatibilityAssessmentV1(
        dimension_id=dimension_id,
        semantic_role=role,
        values_a=sorted(set(values_a)),
        values_b=sorted(set(values_b)),
        compatibility_state=state,
        authority_refs=sorted(set(authority_refs)),
        reason=reason,
    )


def _compare_canonical_scalar(
    dimension: str, a: str | None, b: str | None
) -> DimensionCompatibilityAssessmentV1:
    if a is None or b is None:
        return _assessment(
            dimension, "proposition_critical", [] if a is None else [a],
            [] if b is None else [b], "missing_authority",
            "required canonical proposition identity is unavailable",
        )
    if a == b:
        return _assessment(
            dimension, "proposition_critical", [a], [b], "compatible_exact",
            "exact canonical proposition identity match", ["claim_alignment_v2"],
        )
    return _assessment(
        dimension, "proposition_critical", [a], [b], "incompatible",
        "distinct canonical proposition identities", ["claim_alignment_v2"],
    )


def _compare_canonical_values(
    dimension: str,
    values_a: Sequence[StructuredSemanticValueV1],
    values_b: Sequence[StructuredSemanticValueV1],
) -> DimensionCompatibilityAssessmentV1:
    if not values_a or not values_b:
        return _assessment(
            dimension, "proposition_critical", _display(values_a), _display(values_b),
            "missing_authority", "one or both structured value sets are absent",
        )
    ids_a = {value.canonical_identity for value in values_a if value.canonical_identity}
    ids_b = {value.canonical_identity for value in values_b if value.canonical_identity}
    if len(ids_a) != len(values_a) or len(ids_b) != len(values_b):
        return _assessment(
            dimension, "proposition_critical", _display(values_a), _display(values_b),
            "missing_authority",
            "structured values exist but canonical identity authority is incomplete",
        )
    if ids_a == ids_b:
        return _assessment(
            dimension, "proposition_critical", _display(values_a), _display(values_b),
            "compatible_exact", "exact canonical identity set match", ids_a,
        )
    return _assessment(
        dimension, "proposition_critical", _display(values_a), _display(values_b),
        "incompatible", "distinct validated canonical identity sets", ids_a | ids_b,
    )


def _compare_semantic_families(
    dimension: str,
    values_a: Sequence[StructuredSemanticValueV1],
    values_b: Sequence[StructuredSemanticValueV1],
) -> DimensionCompatibilityAssessmentV1:
    if not values_a or not values_b:
        return _assessment(
            dimension, "proposition_critical", _display(values_a), _display(values_b),
            "missing_authority", "one or both structured semantic value sets are absent",
        )
    families_a = {value.semantic_family for value in values_a if value.semantic_family}
    families_b = {value.semantic_family for value in values_b if value.semantic_family}
    if len(families_a) != len({value.semantic_family for value in values_a}) or len(families_b) != len({value.semantic_family for value in values_b}):
        return _assessment(
            dimension, "proposition_critical", _display(values_a), _display(values_b),
            "unresolved", "a structured semantic value has no deterministic family mapping",
        )
    if not families_a or not families_b:
        return _assessment(
            dimension, "proposition_critical", _display(values_a), _display(values_b),
            "unresolved", "semantic family authority is unavailable",
        )
    if families_a == families_b:
        exact_values = _display(values_a) == _display(values_b)
        return _assessment(
            dimension, "proposition_critical", _display(values_a), _display(values_b),
            "compatible_exact" if exact_values else "compatible_semantic_family",
            "deterministic structured semantic-family match",
            ["measurement_property_family_v1"],
        )
    return _assessment(
        dimension, "proposition_critical", _display(values_a), _display(values_b),
        "incompatible", "distinct deterministic semantic families",
        ["measurement_property_family_v1"],
    )


def _compare_qualifier_values(
    dimension: str,
    values_a: Sequence[StructuredSemanticValueV1],
    values_b: Sequence[StructuredSemanticValueV1],
) -> DimensionCompatibilityAssessmentV1:
    if not values_a and not values_b:
        return _assessment(
            dimension, "compatibility_qualifier", [], [], "not_applicable",
            "qualifier is absent on both observations",
        )
    ids_a = {value.canonical_identity for value in values_a if value.canonical_identity}
    ids_b = {value.canonical_identity for value in values_b if value.canonical_identity}
    if ids_a and ids_a == ids_b and len(ids_a) == len(values_a) == len(values_b):
        return _assessment(
            dimension, "compatibility_qualifier", _display(values_a), _display(values_b),
            "compatible_exact", "exact canonical qualifier match", ids_a,
        )
    if dimension == "assay_method" and values_a and values_b:
        return _assessment(
            dimension, "compatibility_qualifier", _display(values_a), _display(values_b),
            "compatible_with_granularity_qualification",
            "method is recorded separately and does not change target or measured property",
            ["measurement_proposition_compatibility_v1"],
        )
    return _assessment(
        dimension, "compatibility_qualifier", _display(values_a), _display(values_b),
        "unresolved", "qualifier compatibility lacks deterministic conversion authority",
    )


def compare_measurement_propositions_v1(
    signature_a: ScientificPropositionSignatureV1,
    signature_b: ScientificPropositionSignatureV1,
) -> MeasurementPropositionCompatibilityV1:
    target = _compare_canonical_values(
        "measurement_target", signature_a.measurement_targets, signature_b.measurement_targets
    )
    endpoint = _compare_canonical_values(
        "endpoint_property", signature_a.measured_properties, signature_b.measured_properties
    )
    result = _compare_semantic_families(
        "result_semantic_level", signature_a.result_semantics, signature_b.result_semantics
    )
    method = _compare_qualifier_values(
        "assay_method", signature_a.assay_methods, signature_b.assay_methods
    )
    unit = _compare_qualifier_values(
        "unit_representation", signature_a.unit_representations, signature_b.unit_representations
    )
    blocking = []
    if target.compatibility_state == "incompatible":
        blocking.append("measurement_target")
        state: MeasurementCompatibilityStateV1 = "incompatible_target"
    elif endpoint.compatibility_state == "incompatible":
        blocking.append("endpoint_property")
        state = "incompatible_endpoint"
    elif result.compatibility_state == "incompatible":
        blocking.append("result_semantic_level")
        state = "incompatible_result_semantics"
    else:
        critical = (target, endpoint, result)
        unresolved = [
            row.dimension_id for row in critical
            if row.compatibility_state in {"unresolved", "missing_authority"}
        ]
        if unresolved:
            state = (
                "missing_authority"
                if any(row.compatibility_state == "missing_authority" for row in critical)
                else "unresolved"
            )
        elif any(row.compatibility_state == "compatible_semantic_family" for row in critical):
            state = "compatible_semantic_family"
        elif method.compatibility_state == "compatible_with_granularity_qualification":
            state = "compatible_with_granularity_qualification"
        else:
            state = "compatible_exact"
    unresolved = [
        row.dimension_id for row in (target, endpoint, result)
        if row.compatibility_state in {"unresolved", "missing_authority"}
    ]
    payload = {
        "schema_version": "measurement_proposition_compatibility_v1",
        "measurement_target": target,
        "measured_property_endpoint": endpoint,
        "assay_method": method,
        "unit_representation": unit,
        "result_semantic_level": result,
        "compatibility_state": state,
        "blocking_dimensions": blocking,
        "unresolved_dimensions": unresolved,
        "assay_difference_is_proposition_mismatch": False,
    }
    payload["compatibility_identity"] = layer_identity(
        "measurement_proposition_compatibility",
        "measurement_proposition_compatibility_identity_v1",
        {
            "measurement_target": target.model_dump(mode="json"),
            "measured_property_endpoint": endpoint.model_dump(mode="json"),
            "assay_method": method.model_dump(mode="json"),
            "unit_representation": unit.model_dump(mode="json"),
            "result_semantic_level": result.model_dump(mode="json"),
            "compatibility_state": state,
        },
    )
    return MeasurementPropositionCompatibilityV1.model_validate(payload)


def _compare_intervention(
    a: InterventionPropositionV1, b: InterventionPropositionV1
) -> DimensionCompatibilityAssessmentV1:
    if a.intervention_mode == b.intervention_mode == "none":
        return _assessment(
            "intervention_proposition", "proposition_critical", ["none"], ["none"],
            "not_applicable", "both claims are explicitly non-interventional",
        )
    if "unresolved" in {a.intervention_mode, b.intervention_mode}:
        return _assessment(
            "intervention_proposition", "proposition_critical", [a.intervention_mode],
            [b.intervention_mode], "unresolved", "intervention structure is unresolved",
        )
    if a.intervention_mode != b.intervention_mode:
        return _assessment(
            "intervention_proposition", "proposition_critical", [a.intervention_mode],
            [b.intervention_mode], "incompatible",
            "non-interventional, single, and combination propositions are distinct",
            ["intervention_proposition_v1"],
        )
    if set(a.factor_families) != set(b.factor_families):
        if "controlled_perturbation" in {*a.factor_families, *b.factor_families}:
            return _assessment(
                "intervention_proposition", "proposition_critical", a.factor_families,
                b.factor_families, "unresolved",
                "generic controlled perturbation and a more specific intervention family require granularity authority",
            )
        return _assessment(
            "intervention_proposition", "proposition_critical", a.factor_families,
            b.factor_families, "incompatible", "structured intervention families differ",
            ["intervention_role_family_v1"],
        )
    target = _compare_canonical_values(
        "intervention_proposition", a.target_values, b.target_values
    )
    return target.model_copy(update={
        "reason": (
            "intervention family and canonical target identities match"
            if target.compatibility_state == "compatible_exact"
            else target.reason
        )
    })


def _compare_causal_mode(
    a: CausalEvidentialModeV1, b: CausalEvidentialModeV1
) -> DimensionCompatibilityAssessmentV1:
    if a.mode_family is None or b.mode_family is None:
        return _assessment(
            "causal_evidential_mode", "proposition_critical",
            [] if a.mode_family is None else [a.mode_family],
            [] if b.mode_family is None else [b.mode_family],
            "unresolved", "causal or evidential mode lacks structured authority",
        )
    if a.mode_family == b.mode_family:
        return _assessment(
            "causal_evidential_mode", "proposition_critical", [a.mode_family], [b.mode_family],
            "compatible_exact", "same structured causal/evidential mode",
            ["causal_mode_family_v1"],
        )
    return _assessment(
        "causal_evidential_mode", "proposition_critical", [a.mode_family], [b.mode_family],
        "incompatible", "descriptive, observational, interventional, and non-experimental modes are not silently equivalent",
        ["causal_mode_family_v1"],
    )


def compare_contrast_roles_v1(
    a: ExperimentalContrastSemanticsV1, b: ExperimentalContrastSemanticsV1
) -> DimensionCompatibilityAssessmentV1:
    if a.authority_state == "unresolved" or b.authority_state == "unresolved":
        return _assessment(
            "comparison_structure", "proposition_critical", [a.contrast_role],
            [b.contrast_role], "unresolved", "contrast linkage or reference role is unresolved",
        )
    if a.contrast_role == b.contrast_role:
        return _assessment(
            "comparison_structure", "proposition_critical", [a.contrast_role],
            [b.contrast_role], "compatible_exact",
            "canonical contrast roles match; raw reference labels are qualifiers",
            ["contrast_role_inventory_v1"],
        )
    return _assessment(
        "comparison_structure", "proposition_critical", [a.contrast_role], [b.contrast_role],
        "incompatible", "canonical scientific contrast roles differ",
        ["contrast_role_inventory_v1"],
    )


def _compare_granularity(
    signature_a: ScientificPropositionSignatureV1,
    signature_b: ScientificPropositionSignatureV1,
    measurement: MeasurementPropositionCompatibilityV1,
) -> list[DimensionCompatibilityAssessmentV1]:
    left = {row.dimension_id: row for row in signature_a.granularity_qualifiers}
    right = {row.dimension_id: row for row in signature_b.granularity_qualifiers}
    rows = []
    for dimension in sorted(set(left) | set(right)):
        a = left.get(dimension)
        b = right.get(dimension)
        status = (a or b).bridge_status
        values_a = [] if a is None or a.value is None else [a.value]
        values_b = [] if b is None or b.value is None else [b.value]
        if dimension == "measurement_semantic_level" and (
            measurement.result_semantic_level.compatibility_state
            in {"compatible_exact", "compatible_semantic_family"}
        ):
            state: DimensionCompatibilityStateV1 = "compatible_semantic_family"
            reason = "V3 controlled semantic-family projection resolves the legacy bridge"
            refs = ["measurement_property_family_v1"]
        elif status in {"exact_match", "not_applicable"}:
            state = "not_applicable" if status == "not_applicable" else "compatible_exact"
            reason = "existing versioned granularity bridge is exact or not applicable"
            refs = ["claim_alignment_v2_granularity_bridge"]
        elif status in {"policy_equivalent", "policy_compatible"}:
            state = "compatible_with_granularity_qualification"
            reason = "explicit versioned granularity bridge policy permits comparison"
            refs = [a.bridge_policy_identity or b.bridge_policy_identity or "granularity_bridge_policy"]
        elif status == "incompatible":
            state = "incompatible"
            reason = "existing versioned granularity authority establishes incompatibility"
            refs = ["claim_alignment_v2_granularity_bridge"]
        else:
            state = "unresolved"
            reason = "nonexact proposition-scoped granularity lacks bridge authority"
            refs = []
        rows.append(_assessment(
            dimension, "proposition_critical", values_a, values_b, state, reason, refs
        ))
    return rows


def evaluate_scientific_proposition_compatibility_v1(
    *,
    pair_id: str,
    signature_a: ScientificPropositionSignatureV1,
    signature_b: ScientificPropositionSignatureV1,
    historical_alignment_v2_identity: str,
    historical_alignment_v2_state: str,
    entity_integrity_decisions: Sequence[ScientificEntityIntegrityGateResultV1] | None = None,
) -> ScientificPropositionCompatibilityV1:
    require_scientific_entity_integrity("claim_alignment", entity_integrity_decisions)
    entity = [
        _compare_canonical_scalar("subject_identity", signature_a.subject_identity, signature_b.subject_identity),
        _compare_canonical_scalar("relation_effect_family", signature_a.relation_effect_family, signature_b.relation_effect_family),
        _compare_canonical_scalar("object_target_identity", signature_a.object_target_identity, signature_b.object_target_identity),
    ]
    if signature_a.outcome_variable_identity is not None or signature_b.outcome_variable_identity is not None:
        entity.append(_compare_canonical_scalar(
            "outcome_variable_identity",
            signature_a.outcome_variable_identity,
            signature_b.outcome_variable_identity,
        ))
    measurement = compare_measurement_propositions_v1(signature_a, signature_b)
    intervention = _compare_intervention(
        signature_a.intervention_proposition, signature_b.intervention_proposition
    )
    causal = _compare_causal_mode(
        signature_a.causal_evidential_mode, signature_b.causal_evidential_mode
    )
    contrast = compare_contrast_roles_v1(
        signature_a.experimental_contrast, signature_b.experimental_contrast
    )
    granularity = _compare_granularity(signature_a, signature_b, measurement)

    blocking = [row.dimension_id for row in entity if row.compatibility_state == "incompatible"]
    unresolved = [
        row.dimension_id for row in entity
        if row.compatibility_state in {"unresolved", "missing_authority"}
    ]
    unresolved.extend(measurement.unresolved_dimensions)
    for row in (intervention, causal, contrast, *granularity):
        if row.compatibility_state == "incompatible":
            blocking.append(row.dimension_id)
        elif row.compatibility_state in {"unresolved", "missing_authority"}:
            unresolved.append(row.dimension_id)

    if any(row.compatibility_state == "incompatible" for row in entity):
        state: AlignmentV3State = "blocked_proposition_mismatch"
    elif measurement.compatibility_state == "incompatible_target":
        state = "blocked_measurement_target_mismatch"
    elif measurement.compatibility_state == "incompatible_endpoint":
        state = "blocked_endpoint_mismatch"
    elif measurement.compatibility_state == "incompatible_result_semantics":
        state = "blocked_result_semantic_mismatch"
    elif intervention.compatibility_state == "incompatible":
        state = "blocked_intervention_proposition_mismatch"
    elif causal.compatibility_state == "incompatible":
        state = "blocked_causal_mode_mismatch"
    elif contrast.compatibility_state == "incompatible" or any(
        row.compatibility_state == "incompatible" for row in granularity
    ):
        state = "blocked_proposition_mismatch"
    elif unresolved:
        state = "partial_reviewable"
    elif any(
        row.compatibility_state == "compatible_with_granularity_qualification"
        for row in granularity
    ):
        state = "aligned_with_granularity_qualification"
    elif measurement.compatibility_state in {
        "compatible_semantic_family", "compatible_with_granularity_qualification"
    } or intervention.compatibility_state == "compatible_semantic_family":
        state = "aligned_compatible"
    else:
        state = "aligned_exact"

    qualifier_dimensions = [
        row.dimension_id for row in (
            measurement.assay_method, measurement.unit_representation
        ) if row.compatibility_state != "not_applicable"
    ]
    payload: dict[str, Any] = {
        "schema_version": "scientific_proposition_compatibility_v1",
        "pair_id": pair_id,
        "observation_a_id": signature_a.observation_id,
        "observation_b_id": signature_b.observation_id,
        "signature_a_identity": signature_a.scientific_proposition_signature_identity,
        "signature_b_identity": signature_b.scientific_proposition_signature_identity,
        "historical_alignment_v2_identity": historical_alignment_v2_identity,
        "historical_alignment_v2_state": historical_alignment_v2_state,
        "entity_proposition": entity,
        "measurement_compatibility": measurement,
        "intervention_proposition": intervention,
        "causal_evidential_mode": causal,
        "experimental_contrast": contrast,
        "granularity": granularity,
        "alignment_v3_candidate_state": state,
        "blocking_dimensions": sorted(set(blocking + measurement.blocking_dimensions)),
        "unresolved_dimensions": sorted(set(unresolved)),
        "compatibility_qualifier_dimensions": sorted(set(qualifier_dimensions)),
        "alignment_basis": [
            "validated structured semantics only",
            "assay and representation are separate from target and measured property",
            "direction, sign, polarity, and negation remain Contradiction-owned",
            "ordinary Context remains downstream unless explicitly proposition-scoped",
        ],
        "candidate_only": True,
        "historical_alignment_modified": False,
        "context_comparability_evaluated": False,
        "result_direction_used_as_identity": False,
        "string_inequality_used_as_incompatibility": False,
        "validator_version": "scientific_proposition_compatibility_validator_v1",
    }
    identity_fields = {
        key: (
            value.model_dump(mode="json") if hasattr(value, "model_dump") else
            [item.model_dump(mode="json") for item in value]
            if isinstance(value, list) and value and hasattr(value[0], "model_dump") else value
        )
        for key, value in payload.items()
        if key not in {"alignment_basis", "candidate_only", "historical_alignment_modified", "context_comparability_evaluated"}
    }
    payload["scientific_proposition_compatibility_identity"] = layer_identity(
        "scientific_proposition_compatibility",
        "scientific_proposition_compatibility_identity_v1",
        identity_fields,
    )
    return ScientificPropositionCompatibilityV1.model_validate(payload)


def semantic_family_contract_snapshot_v1() -> dict[str, Any]:
    return {
        "schema_version": "scientific_proposition_semantic_family_contract_snapshot_v1",
        "measurement_property_family": {
            "contract_version": "measurement_property_family_v1",
            "exact_structured_value_map": MEASUREMENT_PROPERTY_FAMILY_V1,
            "unknown_policy": "unresolved",
            "free_text_inference": False,
            "fuzzy_matching": False,
        },
        "result_semantic_family": {
            "contract_version": "result_semantic_family_v1",
            "property_source": "measurement_property_family_v1",
            "representation_values": [
                "qualitative_result", "quantitative_result", "mixed_result",
                "unresolved_result_representation",
            ],
            "direction_fields_excluded": ["direction", "sign", "polarity", "negation"],
            "unknown_policy": "unresolved",
        },
        "causal_mode": {
            "contract_version": "causal_mode_family_v1",
            "exact_observation_type_map": CAUSAL_MODE_FAMILY_V1,
            "cross_family_default": "incompatible_modes",
            "unknown_policy": "causal_mode_unresolved",
        },
        "contrast_role": {
            "contract_version": "contrast_role_inventory_v1",
            "roles": [
                "experimental_vs_reference", "observational_group_vs_reference",
                "no_explicit_contrast", "unresolved_reference_structure", "unresolved",
            ],
            "reference_labels_are_identity": False,
            "unknown_policy": "unresolved",
        },
        "intervention_role_family": {
            "contract_version": "intervention_role_family_v1",
            "exact_factor_role_map": INTERVENTION_ROLE_FAMILY_V1,
            "unknown_policy": "unresolved",
        },
    }


__all__ = [
    "AlignmentV3State",
    "CausalEvidentialModeV1",
    "DimensionCompatibilityAssessmentV1",
    "ExperimentalContrastSemanticsV1",
    "GranularityQualifierV1",
    "InterventionPropositionV1",
    "MeasurementPropositionCompatibilityV1",
    "ScientificPropositionCompatibilityV1",
    "ScientificPropositionSignatureV1",
    "SemanticRoleAssignmentV1",
    "StructuredSemanticValueV1",
    "compare_contrast_roles_v1",
    "compare_measurement_propositions_v1",
    "evaluate_scientific_proposition_compatibility_v1",
    "make_scientific_proposition_signature_v1",
    "project_scientific_proposition_signature_v1",
    "semantic_family_contract_snapshot_v1",
]
