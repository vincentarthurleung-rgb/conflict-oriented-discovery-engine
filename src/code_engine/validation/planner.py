"""Public deterministic validation-plan builder."""

from code_engine.validation.router import DomainAdaptiveValidationRouter


def build_validation_plan(hypothesis, domain_profile, *, relation_type: str | None = None, mechanism_edge=None, evidence_record=None):
    return DomainAdaptiveValidationRouter().create_plan(hypothesis, domain_profile, relation_type=relation_type, mechanism_edge=mechanism_edge, evidence_record=evidence_record)
