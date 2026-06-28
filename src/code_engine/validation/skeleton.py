"""Structured no-coverage validator base for unconfigured external indexes."""

from code_engine.schemas.validation import ValidationQuestion, ValidationResult
from code_engine.validation.base import AbstractValidator


class ExternalIndexValidator(AbstractValidator):
    def __init__(self, configured_resources: set[str] | None = None):
        self.configured_resources = configured_resources or set()

    @property
    def configured(self) -> bool:
        return all(resource in self.configured_resources for resource in self.required_resources)

    def validate(self, question: ValidationQuestion) -> ValidationResult:
        if not self.can_validate(question):
            status = "not_applicable"
            limitation = "Validator does not cover this domain/relation."
        elif not self.configured:
            status = "external_index_not_configured"
            limitation = "Required local external index is not configured."
        else:
            status = "no_coverage"
            limitation = "Configured index returned no local coverage."
        return ValidationResult(
            hypothesis_id=question.hypothesis_id,
            validator_name=self.name,
            domain_id=question.domain_id,
            validator_profile_id=question.validator_profile_id,
            evidence_modality=question.evidence_modality,
            validation_status=status,
            coverage_status="none",
            limitations=[limitation],
        )
