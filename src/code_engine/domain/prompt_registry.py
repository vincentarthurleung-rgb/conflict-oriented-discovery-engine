"""Versioned local prompt profiles for deterministic L1 planning."""

from code_engine.domain.models import PromptProfile
from code_engine.domain.models import default_domain_profiles


GENERAL_CONTEXT_SLOTS = (
    "species", "cell_type", "treatment", "dose", "treatment_duration",
    "assay_or_readout", "genotype", "localization",
)
NEUROPHARMACOLOGY_CONTEXT_SLOTS = (
    "species", "sex", "age", "disease_model", "brain_region", "cell_type",
    "treatment", "dose", "route", "treatment_duration", "time_after_treatment",
    "assay_or_readout", "behavioral_assay", "clinical_outcome", "genotype",
    "oxygen_condition", "localization",
)


BASE_TEMPLATE = """You are a grounded biomedical claim extractor.
Domain: {domain_id}
Prompt profile: {prompt_profile_id} version {prompt_version}
Output schema: {output_schema_version}
Extraction policy: {extraction_policy_version}
Extract explicit evidence-backed claims only. Preserve exact evidence sentences and spans.
Do not extract speculative claims. Do not merge claims from different contexts.
Distinguish direct_relation_sign from therapeutic_direction.
evidence_sentence must be copied from the source text. Never invent context.
Context slots: {context_slots}
Return JSON with a root `claims` list matching the configured L1 v2 schema.
Text chunk:
{chunk_text}
"""

DOMAIN_INSTRUCTIONS = {
    "neuropharmacology": """
Domain focus: preserve species, sex, age, disease model, brain region, cell type,
genotype, treatment, dose, route, duration, post-treatment time, assay/readout,
behavioral assay, clinical outcome, receptor target, and pathway. Keep distinct
molecular mechanisms separate and do not infer an unstated mechanism.
""",
    "drug_target_binding": """
Domain focus: preserve drug, target receptor/protein, binding affinity, Ki, IC50,
EC50, antagonist/agonist/modulator role, assay type, species, and experimental
system. Do not convert functional modulation into direct binding without text.
""",
    "clinical_outcome": """
Domain focus: preserve population, intervention, comparator, outcome, trial
phase, sample size, response rate, remission rate, adverse events, and timepoint.
Do not infer efficacy from a study objective or protocol statement.
""",
    "pathway_biology": """
Domain focus: preserve pathway identity, activation direction, upstream and
downstream entities, perturbation, experimental system, assay, and timepoint.
""",
    "protein_interaction": """
Domain focus: preserve both proteins, interaction type, directness, assay,
species, experimental system, and interaction context.
""",
}


class PromptRegistry:
    def __init__(self):
        self._prompts: dict[str, str] = {}
        self._profiles: dict[str, PromptProfile] = {}

    def register(self, prompt_id: str, template: str) -> None:
        self._prompts[prompt_id] = template

    def get(self, prompt_id: str) -> str:
        return self._prompts[prompt_id]

    def register_profile(self, profile: PromptProfile) -> None:
        self._profiles[profile.profile_id] = profile

    def get_profile(self, profile_id: str) -> PromptProfile:
        return self._profiles[profile_id]


def default_prompt_registry() -> PromptRegistry:
    registry = PromptRegistry()
    for domain in default_domain_profiles():
        slots = domain.required_context_slots + domain.optional_context_slots
        template = BASE_TEMPLATE + DOMAIN_INSTRUCTIONS.get(domain.domain_id, "")
        registry.register_profile(PromptProfile(
            profile_id=domain.prompt_profile_id,
            domain_id=domain.domain_id,
            version=domain.prompt_version,
            template=template,
            context_slots=slots or GENERAL_CONTEXT_SLOTS,
            output_schema_version=domain.output_schema_version,
            extraction_policy_version=domain.extraction_policy_version,
        ))
    # Legacy aliases remain readable, but new selection emits *_l1_v2 IDs.
    registry.register_profile(PromptProfile("general_biomedical", "general_biomedical", "2.0", BASE_TEMPLATE, GENERAL_CONTEXT_SLOTS))
    registry.register_profile(PromptProfile("neuropharmacology", "neuropharmacology", "2.0", BASE_TEMPLATE, NEUROPHARMACOLOGY_CONTEXT_SLOTS))
    return registry
