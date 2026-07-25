"""Versioned experimental context field registry."""
from __future__ import annotations

from .identities import context_asset_identity
from .models import ContextFieldRegistryRecord

CATEGORY_FIELDS = {
    "biological_system": (
        "species", "strain", "sex", "age_or_developmental_stage", "tissue", "organ",
        "cell_type", "cell_line", "primary_cell_status", "model_system",
        "organoid_or_ex_vivo_status",
    ),
    "disease_background": (
        "disease", "disease_stage", "phenotype", "baseline_state", "physiological_state",
        "hypoxia_or_oxygen_condition", "inflammatory_state", "stress_condition",
        "nutrient_condition", "genotype", "mutation", "knockout", "knockdown",
        "overexpression",
    ),
    "intervention_background": (
        "intervention", "intervention_role", "intervention_order", "dose", "concentration",
        "route", "frequency", "duration", "timepoint", "pretreatment", "post_treatment",
        "co_intervention", "control", "comparator",
    ),
    "measurement_background": (
        "assay", "measurement_method", "measurement_semantic_level", "measured_endpoint",
        "sample_type", "subcellular_localization", "normalization_control", "replicate_design",
    ),
    "experimental_design": (
        "in_vitro_in_vivo_ex_vivo", "randomization_if_explicit", "blinding_if_explicit",
        "group_definition", "experimental_arm", "baseline_comparison",
    ),
}

LEGACY_ALIASES = {
    "disease": ["disease_subtype"],
    "subcellular_localization": ["localization"],
    "intervention": ["intervention_type", "intervention_target"],
    "control": ["control_group"],
    "assay": ["assay_method"],
    "measured_endpoint": ["measurement_endpoint"],
    "in_vitro_in_vivo_ex_vivo": ["in_vivo_in_vitro"],
    "experimental_arm": ["experimental_design", "validation_design"],
}


def build_registry() -> list[ContextFieldRegistryRecord]:
    records = []
    for category, fields in CATEGORY_FIELDS.items():
        for field_id in fields:
            supported = field_id in {
                "species", "tissue", "cell_type", "cell_line", "model_system", "disease",
                "genotype", "intervention", "dose", "duration", "timepoint", "control",
                "comparator", "assay", "measurement_method", "measured_endpoint",
                "subcellular_localization", "in_vitro_in_vivo_ex_vivo", "experimental_arm",
            }
            base = {
                "field_id": field_id,
                "canonical_field_path": f"context.{field_id}",
                "legacy_aliases": LEGACY_ALIASES.get(field_id, []),
                "semantic_category": category,
                "value_type": "string_or_structured",
                "cardinality": "many",
                "ordered_or_unordered": "ordered" if field_id in {"intervention_order"} else "unordered",
                "direct_evidence_required": True,
                "scope_propagation_allowed": field_id not in {
                    "measured_endpoint", "subcellular_localization", "timepoint",
                },
                "scope_propagation_policy_identity": "context_scope_propagation_policy_v1",
                "normalization_contract": "existing_observation_context_normalization",
                "currently_supported": supported,
                "prompt_requested": supported,
                "schema_representable": supported,
                "parser_preserved": supported,
                "active_status": "active" if supported else "audit_only",
            }
            records.append(ContextFieldRegistryRecord(
                **base, identity=context_asset_identity("context_field_registry_record_v1", base)
            ))
    return records


def explicit_legacy_mapping(registry: list[ContextFieldRegistryRecord]) -> dict[str, tuple[str, str]]:
    mapping = {record.field_id: (record.field_id, "exact_same_field") for record in registry}
    for record in registry:
        for alias in record.legacy_aliases:
            mapping[alias] = (record.field_id, "versioned_alias")
    return mapping
