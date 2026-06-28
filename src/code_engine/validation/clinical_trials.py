"""Local-index-aware clinical-trials validator skeleton."""

from code_engine.validation.skeleton import ExternalIndexValidator


class ClinicalTrialsValidator(ExternalIndexValidator):
    name = "ClinicalTrialsValidator"
    supported_domains = ("clinical_outcome",)
    supported_entity_types = ("compound", "disease", "phenotype")
    required_resources = ("clinical_trials_index",)
