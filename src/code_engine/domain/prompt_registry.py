"""Versioned, domain-neutral prompt profiles for deterministic L1 planning."""

from __future__ import annotations

import json

from code_engine.domain.models import PromptProfile, default_domain_profiles


PROMPT_VERSION = "2.1"

GENERAL_CONTEXT_SLOTS = (
    "species", "cell_type", "treatment", "dose", "treatment_duration",
    "assay_or_readout", "genotype", "localization",
)

NEUROPHARMACOLOGY_CONTEXT_SLOTS = (
    "species", "sex", "age", "disease_model", "clinical_condition",
    "brain_region", "cell_type", "treatment", "drug_form", "metabolite",
    "dose", "route", "treatment_duration", "time_after_treatment",
    "control_or_comparator", "receptor_target", "pathway",
    "molecular_readout", "assay_or_readout", "behavioral_assay",
    "clinical_outcome", "genotype", "oxygen_condition", "localization",
)


BASE_TEMPLATE = """You are a strict grounded biomedical relation extraction system.

Domain: {domain_id}
Prompt profile: {prompt_profile_id} version {prompt_version}
Output schema: {output_schema_version}
Extraction policy: {extraction_policy_version}

Task:
Extract explicitly stated biomedical causal, regulatory, directional, null-effect,
context-dependent, association-only, or binding relations from ONE text chunk.

Return ONLY valid JSON. No markdown, code fences, explanations, or extra keys.
Root object: {{"claims": [...]}}

Each claim must contain:
- subject, object: exact surface forms from the text
- subject_type, object_type: gene, protein, compound, drug, metabolite,
  receptor, pathway, biological_process, cell_type, disease, phenotype,
  clinical_outcome, assay_readout, or unknown
- relation_raw: exact relational phrase
- relation_family: activation, inhibition, expression_regulation,
  phosphorylation_regulation, binding, receptor_modulation, pathway_regulation,
  causal_mediation, phenotype_regulation, clinical_effect, null_effect,
  context_dependent_effect, association_only, or unknown
- direct_relation_sign: 1 for increase/promotion, -1 for decrease/inhibition,
  or 0 for no effect, association, pure binding, or unclear direction
- therapeutic_direction: beneficial, adverse, mixed, not_applicable, or unknown
- context: an object containing every configured context slot
- negated, null_or_no_effect, speculative: booleans
- evidence_sentence: exact verbatim sentence from the text
- confidence: number from 0.0 to 1.0

Core rules:
1. Extract only explicit relations. Never infer from background knowledge.
2. Preserve entity surface forms; normalization happens later.
3. Copy evidence_sentence verbatim.
4. Do not invent context. If a slot is not explicitly stated, output "".
   Never use "unspecified", "unknown", "not stated", "N/A", or null for a
   missing context slot.
5. Keep different contexts, directions, and assays as separate claims.
6. Preserve positive, negative, null, and context-dependent findings.
7. A negation is not automatically the opposite effect. Explicit no-effect
   findings use sign 0 and null_or_no_effect=true.
8. Skip pure speculation; retain concrete results even if interpretation is hedged.
9. direct_relation_sign is biological direction. therapeutic_direction is explicit
   clinical, behavioral, or therapeutic meaning. Never infer one from the other.
10. Use therapeutic_direction=not_applicable for molecular/mechanistic claims;
    unknown only when clinical/behavioral meaning exists but its direction is unclear.
11. Association-only and pure binding claims use sign 0 unless functional direction
    is explicit. Do not convert association or interaction into causation.
12. Use only the provided text chunk.

Context slots for this profile:
{context_slots}

Domain-specific instructions:
{domain_instructions}

Example:
{example_block}

Text chunk:
<<<BEGIN_TEXT_CHUNK
{chunk_text}
END_TEXT_CHUNK>>>
"""


DOMAIN_INSTRUCTIONS = {
    "general_biomedical": (
        "Preserve the explicit experimental system, species, cell type, treatment, "
        "dose, timing, assay/readout, genotype, and localization. Do not infer an "
        "unstated disease context or mechanism."
    ),
    "neuropharmacology": (
        "Preserve exact compound forms, enantiomers, metabolites, receptor targets, "
        "pathways, brain regions, behavioral assays, clinical outcomes, doses, routes, "
        "timing, comparators, and experimental models when stated. Keep molecular and "
        "therapeutic conclusions separate."
    ),
    "drug_target_binding": (
        "Preserve compound, target, affinity, agonist/antagonist/modulator role, assay, "
        "species, and experimental system. Do not infer direct binding from functional "
        "modulation."
    ),
    "clinical_outcome": (
        "Preserve population, intervention, comparator, outcome, trial phase, sample "
        "size, adverse events, dose, route, duration, and timepoint. Extract efficacy "
        "only from reported outcomes."
    ),
    "pathway_biology": (
        "Preserve pathway identity, direction, upstream/downstream entities, perturbation, "
        "system, readout, and timing. Do not infer pathway activity from a marker alone."
    ),
    "protein_interaction": (
        "Preserve both proteins, interaction type, directness, assay, species, system, "
        "localization, and context. Interaction alone does not establish regulation."
    ),
}


EXAMPLE_CLAIMS = {
    "general_biomedical": {
        "text": "In human fibroblasts, Protein A decreased Gene B expression.",
        "subject": "Protein A", "subject_type": "protein", "relation_raw": "decreased",
        "relation_family": "expression_regulation", "direct_relation_sign": -1,
        "therapeutic_direction": "not_applicable", "object": "Gene B expression",
        "object_type": "assay_readout", "context_values": {"species": "human", "cell_type": "fibroblasts", "assay_or_readout": "Gene B expression"},
    },
    "neuropharmacology": {
        "text": "Compound X reduced Receptor Y signaling in mouse cortical neurons.",
        "subject": "Compound X", "subject_type": "compound", "relation_raw": "reduced",
        "relation_family": "receptor_modulation", "direct_relation_sign": -1,
        "therapeutic_direction": "not_applicable", "object": "Receptor Y signaling",
        "object_type": "assay_readout", "context_values": {"species": "mouse", "cell_type": "cortical neurons", "treatment": "Compound X", "receptor_target": "Receptor Y", "molecular_readout": "Receptor Y signaling"},
    },
    "drug_target_binding": {
        "text": "Compound Q bound Receptor R with a Ki of 8 nM.",
        "subject": "Compound Q", "subject_type": "compound", "relation_raw": "bound",
        "relation_family": "binding", "direct_relation_sign": 0,
        "therapeutic_direction": "not_applicable", "object": "Receptor R",
        "object_type": "receptor", "context_values": {"assay_or_readout": "Ki of 8 nM"},
    },
    "clinical_outcome": {
        "text": "Treatment Z improved symptom scores compared with placebo.",
        "subject": "Treatment Z", "subject_type": "drug", "relation_raw": "improved",
        "relation_family": "clinical_effect", "direct_relation_sign": 1,
        "therapeutic_direction": "beneficial", "object": "symptom scores",
        "object_type": "clinical_outcome", "context_values": {"treatment": "Treatment Z", "control_or_comparator": "placebo", "clinical_outcome": "symptom scores"},
    },
    "pathway_biology": {
        "text": "Protein M activated Pathway N in epithelial cells.",
        "subject": "Protein M", "subject_type": "protein", "relation_raw": "activated",
        "relation_family": "pathway_regulation", "direct_relation_sign": 1,
        "therapeutic_direction": "not_applicable", "object": "Pathway N",
        "object_type": "pathway", "context_values": {"cell_type": "epithelial cells", "pathway": "Pathway N"},
    },
    "protein_interaction": {
        "text": "Protein U interacted with Protein V in the nucleus.",
        "subject": "Protein U", "subject_type": "protein", "relation_raw": "interacted with",
        "relation_family": "binding", "direct_relation_sign": 0,
        "therapeutic_direction": "not_applicable", "object": "Protein V",
        "object_type": "protein", "context_values": {"localization": "nucleus"},
    },
}


KETAMINE_PILOT_EXAMPLE = {
    "text": "Ketamine increased BDNF expression in the hippocampus of stressed rats.",
    "subject": "Ketamine", "subject_type": "drug", "relation_raw": "increased",
    "relation_family": "expression_regulation", "direct_relation_sign": 1,
    "therapeutic_direction": "not_applicable", "object": "BDNF expression",
    "object_type": "assay_readout", "context_values": {
        "species": "rats", "disease_model": "stressed", "brain_region": "hippocampus",
        "treatment": "Ketamine", "molecular_readout": "BDNF expression",
        "assay_or_readout": "BDNF expression",
    },
}


def _example_block(domain_id: str, context_slots: tuple[str, ...], pilot_profile: str | None) -> str:
    spec = KETAMINE_PILOT_EXAMPLE if pilot_profile == "ketamine" else EXAMPLE_CLAIMS.get(
        domain_id, EXAMPLE_CLAIMS["general_biomedical"]
    )
    context = {slot: spec["context_values"].get(slot, "") for slot in context_slots}
    claim = {key: value for key, value in spec.items() if key not in {"text", "context_values"}}
    claim.update({
        "context": context, "negated": False, "null_or_no_effect": False,
        "speculative": False, "evidence_sentence": spec["text"], "confidence": 0.95,
    })
    rendered = "Input: " + spec["text"] + "\nOutput: " + json.dumps({"claims": [claim]}, ensure_ascii=False)
    return rendered.replace("{", "{{").replace("}", "}}")


def build_prompt_template(
    domain_id: str,
    context_slots: tuple[str, ...] = GENERAL_CONTEXT_SLOTS,
    *,
    pilot_profile: str | None = None,
) -> str:
    instructions = DOMAIN_INSTRUCTIONS.get(domain_id, DOMAIN_INSTRUCTIONS["general_biomedical"])
    return BASE_TEMPLATE.replace("{domain_instructions}", instructions).replace(
        "{example_block}", _example_block(domain_id, context_slots, pilot_profile)
    )


class PromptRegistry:
    def __init__(self):
        self._prompts: dict[str, str] = {}
        self._profiles: dict[str, PromptProfile] = {}
        self._aliases: dict[str, str] = {}

    def register(self, prompt_id: str, template: str) -> None:
        self._prompts[prompt_id] = template

    def get(self, prompt_id: str) -> str:
        return self._prompts[prompt_id]

    def register_profile(self, profile: PromptProfile) -> None:
        self._profiles[profile.profile_id] = profile

    def register_alias(self, alias: str, profile_id: str) -> None:
        self._aliases[alias] = profile_id

    def get_profile(self, profile_id: str) -> PromptProfile:
        return self._profiles[self._aliases.get(profile_id, profile_id)]

    def resolution_metadata(self, profile_id: str) -> dict[str, object]:
        resolved = self._aliases.get(profile_id, profile_id)
        return {
            "deprecated_alias": profile_id in self._aliases,
            "resolved_prompt_profile_id": resolved,
        }


def default_prompt_registry() -> PromptRegistry:
    registry = PromptRegistry()
    for domain in default_domain_profiles():
        slots = domain.required_context_slots + domain.optional_context_slots or GENERAL_CONTEXT_SLOTS
        registry.register_profile(PromptProfile(
            profile_id=domain.prompt_profile_id,
            domain_id=domain.domain_id,
            version=PROMPT_VERSION,
            template=build_prompt_template(domain.domain_id, slots),
            context_slots=slots,
            output_schema_version=domain.output_schema_version,
            extraction_policy_version=domain.extraction_policy_version,
        ))

    registry.register_profile(PromptProfile(
        profile_id="neuropharmacology_ketamine_l1_v2_1",
        domain_id="neuropharmacology",
        version=PROMPT_VERSION,
        template=build_prompt_template("neuropharmacology", NEUROPHARMACOLOGY_CONTEXT_SLOTS, pilot_profile="ketamine"),
        context_slots=NEUROPHARMACOLOGY_CONTEXT_SLOTS,
    ))

    registry.register_alias("general_biomedical", "general_biomedical_l1_v2")
    registry.register_alias("neuropharmacology", "neuropharmacology_l1_v2")
    return registry
