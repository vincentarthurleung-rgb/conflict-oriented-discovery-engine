"""Plan-only deterministic domain-adaptive validator routing."""

import hashlib

from code_engine.schemas.validation import ValidationPlan
from code_engine.validation.question_builder import build_validation_question


ROUTES = {
    "drug_gene_expression": ("CuratedOmicsValidator", "GEOValidator", "PathwayValidator"),
    "pathway_expression": ("CuratedOmicsValidator", "GEOValidator", "PathwayValidator"),
    "drug_target_binding": ("ChEMBLValidator", "DrugBankValidator", "BindingDBValidator"),
    "receptor_modulation": ("ChEMBLValidator", "DrugBankValidator", "BindingDBValidator"),
    "pathway_mechanism": ("ReactomeValidator", "PathwayValidator"),
    "pathway_activation": ("ReactomeValidator", "PathwayValidator"),
    "protein_interaction": ("STRINGValidator", "ReactomeValidator"),
    "ligand_receptor": ("STRINGValidator", "ReactomeValidator"),
}
EVIDENCE_MODALITIES = {
    "drug_gene_expression": "omics",
    "pathway_expression": "omics",
    "drug_target_binding": "binding_assay",
    "receptor_modulation": "binding_or_functional_assay",
    "pathway_mechanism": "pathway_database",
    "pathway_activation": "pathway_database",
    "protein_interaction": "protein_interaction_database",
    "ligand_receptor": "protein_interaction_database",
    "clinical_outcome": "human_clinical",
}


class DomainAdaptiveValidationRouter:
    def create_plan(self, hypothesis, domain_profile, *, mechanism_edge=None, evidence_record=None, relation_type: str | None = None) -> ValidationPlan:
        if isinstance(hypothesis, dict):
            hypothesis_relation = hypothesis.get("relation_type") or hypothesis.get("relation_family")
        else:
            hypothesis_relation = (
                getattr(hypothesis, "relation_type", None)
                or getattr(hypothesis, "relation_family", None)
            )
        selected_relation = (
            relation_type
            or getattr(mechanism_edge, "relation_family", None)
            or hypothesis_relation
            or "unknown"
        )
        if domain_profile.domain_id == "clinical_outcome":
            validators = ("ClinicalTrialsValidator", "PubMedClinicalEvidenceValidator")
        else:
            validators = ROUTES.get(selected_relation, ())
        if not validators:
            validators = ("NullValidator",)
        question = build_validation_question(hypothesis, domain_profile, selected_relation)
        question.evidence_modality = EVIDENCE_MODALITIES.get(selected_relation, "unknown")
        question.preferred_validators = list(validators)
        question.fallback_validators = list(domain_profile.fallback_validators)
        plan_id = hashlib.sha256(f"{question.hypothesis_id}|{domain_profile.domain_id}|{selected_relation}".encode()).hexdigest()[:16]
        return ValidationPlan(
            plan_id=plan_id,
            hypothesis_id=question.hypothesis_id,
            domain_id=domain_profile.domain_id,
            validator_profile_id=domain_profile.validator_profile_id,
            questions=[question],
            selected_validators=list(validators),
            fallback_validators=list(domain_profile.fallback_validators),
            coverage_expectation="external_or_local_plugin_dependent",
            warnings=[] if validators != ("NullValidator",) else ["no_domain_validator_route_null_validator_selected"],
        )

    route = create_plan
