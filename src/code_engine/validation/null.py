"""Null validator for hypotheses with no external coverage."""

from .base import AbstractValidator


class NullValidator(AbstractValidator):
    name = "NullValidator"

    def can_validate(self, hypothesis: dict) -> bool:
        return True

    def validate(self, hypothesis: dict) -> dict:
        return {
            "hypothesis_id": hypothesis.get("hypothesis_id", "UNKNOWN"),
            "validator": self.name,
            "status": "Unresolved_No_Coverage",
            "coverage": "none",
            "score": None,
            "evidence": [],
            "limitations": ["No validator coverage for this hypothesis."],
        }
