"""Plan-only deterministic domain-adaptive validator routing."""

import hashlib
import json
from pathlib import Path

from code_engine.schemas.validation import ValidationPlan, ValidationQuestion, ValidatorRoute
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


def route_validation_questions(
    questions: list[ValidationQuestion], registry,
    domain_profile: dict | None = None, max_validators_per_question: int = 4,
) -> list[ValidatorRoute]:
    """Route semantic questions using capability metadata only."""

    profile = domain_profile or {}
    if hasattr(profile, "to_dict"):
        profile = profile.to_dict()
    routes = []
    for question in questions:
        scored = []
        for capability in registry.list_capabilities():
            if capability.validator_name == "NullValidator":
                continue
            intent_match = question.validator_intent in capability.supported_validation_intents
            relation = question.relation_family or question.relation_type
            relation_match = relation in capability.supported_relation_families
            entity_types = {str(item.get("entity_type") or "") for item in question.entities} - {""}
            entity_match = bool(entity_types.intersection(capability.supported_entity_types)) if entity_types and capability.supported_entity_types else False
            domain_match = bool(question.domain_id and question.domain_id in capability.supported_domains)
            if not intent_match and not relation_match:
                continue
            score = 0.65 + 0.2 * intent_match + 0.05 * relation_match + 0.05 * entity_match + 0.05 * domain_match
            scored.append((score, capability.validator_name, intent_match, relation_match))
        scored.sort(key=lambda item: (-item[0], item[1]))
        for priority, (score, name, intent_match, relation_match) in enumerate(scored[:max_validators_per_question], 1):
            stable = f"{question.question_id}|{name}"
            routes.append(ValidatorRoute(
                route_id=hashlib.sha256(stable.encode()).hexdigest()[:16],
                question_id=question.question_id, anchor_id=question.anchor_id,
                validator_name=name,
                reason=f"capability_match:intent={intent_match},relation={relation_match}",
                priority=priority, confidence=min(1.0, score), warnings=[],
            ))
        if not scored:
            stable = f"{question.question_id}|NullValidator"
            routes.append(ValidatorRoute(
                route_id=hashlib.sha256(stable.encode()).hexdigest()[:16],
                question_id=question.question_id, anchor_id=question.anchor_id,
                validator_name="NullValidator", reason="no_matching_validator_capability",
                priority=1, confidence=1.0,
                warnings=["null_validator_route_no_external_coverage"],
            ))
    return routes


def write_validation_routes(routes: list[ValidatorRoute], output_dir: str | Path) -> dict[str, str]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    records = output / "validation_routes.jsonl"
    summary = output / "validation_route_summary.json"
    records.write_text("".join(item.model_dump_json() + "\n" for item in routes), encoding="utf-8")
    validators: dict[str, int] = {}
    for item in routes:
        validators[item.validator_name] = validators.get(item.validator_name, 0) + 1
    summary.write_text(json.dumps({"route_count": len(routes), "validator_route_counts": validators}, indent=2), encoding="utf-8")
    return {"routes": str(records), "summary": str(summary)}


__all__ = ["DomainAdaptiveValidationRouter", "route_validation_questions", "write_validation_routes"]
