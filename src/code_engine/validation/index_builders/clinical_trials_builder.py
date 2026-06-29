"""clinical_trials validation index builder."""

from code_engine.validation.index_builders.base import ValidationIndexBuilder


class ClinicalTrialsIndexBuilder(ValidationIndexBuilder):
    name = "clinical_trials_index_builder"
    validator_name = "ClinicalTrialsValidator"
    schema_name = "clinical_trials"


__all__ = ["ClinicalTrialsIndexBuilder"]
