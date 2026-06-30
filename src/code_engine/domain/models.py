"""Configuration-only domain profiles shared across scientific layers."""

from dataclasses import dataclass, field, asdict


@dataclass(frozen=True)
class DomainProfile:
    domain_id: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    prompt_id: str = ""
    subdomain_id: str | None = None
    display_name: str = ""
    description: str = ""
    search_profile_id: str = "general_search_v1"
    prompt_profile_id: str = "general_biomedical_l1_v2"
    prompt_version: str = "2.0"
    output_schema_version: str = "l1_v2_evidence_mechanism_schema"
    extraction_policy_version: str = "evidence_grounded_v2"
    entity_registry_profile: str = "general_entity_resolution_hub"
    resolver_policy_id: str = "conservative_resolver_v2"
    validator_profile_id: str = "general_validation"
    preferred_validators: tuple[str, ...] = field(default_factory=tuple)
    fallback_validators: tuple[str, ...] = ("NullValidator",)
    required_context_slots: tuple[str, ...] = field(default_factory=tuple)
    optional_context_slots: tuple[str, ...] = field(default_factory=tuple)
    key_entity_types: tuple[str, ...] = field(default_factory=tuple)
    key_relation_types: tuple[str, ...] = field(default_factory=tuple)
    key_evidence_types: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def name(self) -> str:  # legacy compatibility
        return self.domain_id

    @property
    def profile_id(self) -> str:
        return self.domain_id

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class PromptProfile:
    profile_id: str
    domain_id: str
    version: str
    template: str
    context_slots: tuple[str, ...] = field(default_factory=tuple)
    output_schema_version: str = "l1_v2_evidence_mechanism_schema"
    extraction_policy_version: str = "evidence_grounded_v2"


def default_domain_profiles() -> list[DomainProfile]:
    neuro_slots = ("species", "disease_model", "brain_region", "cell_type", "treatment", "dose", "route", "treatment_duration", "time_after_treatment", "assay_or_readout", "behavioral_assay", "clinical_outcome")
    return [
        DomainProfile(
            "general_biomedical", aliases=("biomedical",), prompt_id="general_biomedical_l1_v2",
            display_name="General Biomedical", search_profile_id="general_biomedical_search",
            preferred_validators=(), required_context_slots=("species", "treatment", "assay_or_readout"),
            key_entity_types=("compound", "gene", "protein", "phenotype"),
        ),
        DomainProfile(
            "neuropharmacology", aliases=("neuropharmacology", "central_nervous_system_pharmacology"), prompt_id="neuropharmacology_l1_v2",
            subdomain_id="antidepressant_mechanism", display_name="Neuropharmacology",
            search_profile_id="neuropharmacology_search", prompt_profile_id="neuropharmacology_l1_v2",
            entity_registry_profile="biomedical_entity_resolution_hub", resolver_policy_id="neuropharmacology_resolver_v2",
            validator_profile_id="neuropharmacology_validation",
            preferred_validators=("CuratedOmicsValidator", "GEOValidator", "PathwayValidator"),
            required_context_slots=neuro_slots,
            optional_context_slots=("sex", "age", "genotype", "oxygen_condition", "localization"),
            key_entity_types=("compound", "gene", "protein", "receptor_complex", "pathway", "phenotype", "behavioral_assay"),
            key_relation_types=("drug_gene_expression", "drug_receptor_modulation", "pathway_activation", "behavioral_outcome"),
        ),
        DomainProfile(
            "drug_target_binding", prompt_id="drug_target_binding_l1_v2", subdomain_id="receptor_modulation",
            display_name="Drug Target Binding", search_profile_id="drug_target_binding_search",
            prompt_profile_id="drug_target_binding_l1_v2", entity_registry_profile="chemical_target_provider_policy",
            resolver_policy_id="binding_resolver_v2", validator_profile_id="drug_target_validation",
            preferred_validators=("DrugBankValidator", "ChEMBLValidator", "BindingDBValidator"),
            required_context_slots=("drug", "target", "binding_affinity", "assay_type", "species", "experimental_system"),
            key_relation_types=("drug_target_binding", "receptor_modulation"),
        ),
        DomainProfile(
            "pathway_biology", prompt_id="pathway_biology_l1_v2", display_name="Pathway Biology",
            search_profile_id="pathway_search", prompt_profile_id="pathway_biology_l1_v2",
            entity_registry_profile="pathway_resolution_provider_policy", resolver_policy_id="pathway_resolver_v2",
            validator_profile_id="pathway_validation", preferred_validators=("ReactomeValidator", "PathwayValidator"),
            key_relation_types=("pathway_mechanism", "pathway_activation"),
        ),
        DomainProfile(
            "clinical_outcome", prompt_id="clinical_outcome_l1_v2", subdomain_id="treatment_outcome",
            display_name="Clinical Outcome", search_profile_id="clinical_outcome_search",
            prompt_profile_id="clinical_outcome_l1_v2", entity_registry_profile="clinical_resolution_provider_policy",
            resolver_policy_id="clinical_resolver_v2", validator_profile_id="clinical_outcome_validation",
            preferred_validators=("ClinicalTrialsValidator", "PubMedClinicalEvidenceValidator"),
            required_context_slots=("population", "intervention", "comparator", "clinical_outcome", "timepoint", "sample_size", "adverse_events"),
            key_evidence_types=("human_clinical",),
        ),
        DomainProfile(
            "protein_interaction", prompt_id="protein_interaction_l1_v2", display_name="Protein Interaction",
            search_profile_id="protein_interaction_search", prompt_profile_id="protein_interaction_l1_v2",
            entity_registry_profile="protein_resolution_provider_policy", resolver_policy_id="protein_resolver_v2",
            validator_profile_id="protein_interaction_validation",
            preferred_validators=("STRINGValidator", "ReactomeValidator"),
            key_relation_types=("protein_interaction", "ligand_receptor"),
        ),
    ]
