"""Null validator for hypotheses with no external coverage."""

from .base import AbstractValidator
from code_engine.schemas.validation import ValidationQuestion, ValidationResult


class NullValidator(AbstractValidator):
    name = "NullValidator"
    supported_anchor_types = ()
    supported_validation_intents = ()
    supports_cache_only = False

    def can_validate(self, hypothesis: dict) -> bool:
        return True

    def validate(self, hypothesis: dict) -> dict:
        if isinstance(hypothesis, ValidationQuestion):
            return ValidationResult(
                hypothesis_id=hypothesis.hypothesis_id,
                validator_name=self.name,
                domain_id=hypothesis.domain_id,
                validator_profile_id=hypothesis.validator_profile_id,
                validation_status="no_coverage",
                coverage_status="none",
                limitations=["No applicable validator coverage for this question."],
            )
        return {
            "hypothesis_id": hypothesis.get("hypothesis_id", "UNKNOWN"),
            "validator": self.name,
            "status": "Unresolved_No_Coverage",
            "coverage": "none",
            "score": None,
            "evidence": [],
            "limitations": ["No validator coverage for this hypothesis."],
        }
