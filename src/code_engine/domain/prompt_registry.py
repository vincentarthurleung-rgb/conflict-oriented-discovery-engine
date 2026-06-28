"""Versioned local prompt profiles for deterministic L1 planning."""

from code_engine.domain.models import PromptProfile


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
    registry.register_profile(PromptProfile(
        profile_id="general_biomedical",
        domain_id="general_biomedical",
        version="2.0",
        template=BASE_TEMPLATE,
        context_slots=GENERAL_CONTEXT_SLOTS,
    ))
    registry.register_profile(PromptProfile(
        profile_id="neuropharmacology",
        domain_id="neuropharmacology",
        version="2.0",
        template=BASE_TEMPLATE,
        context_slots=NEUROPHARMACOLOGY_CONTEXT_SLOTS,
    ))
    return registry
