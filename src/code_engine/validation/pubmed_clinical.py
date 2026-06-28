"""Local-index-aware PubMed clinical-evidence validator skeleton."""

from code_engine.validation.skeleton import ExternalIndexValidator


class PubMedClinicalEvidenceValidator(ExternalIndexValidator):
    name = "PubMedClinicalEvidenceValidator"
    supported_domains = ("clinical_outcome",)
    supported_entity_types = ("compound", "disease", "phenotype")
    required_resources = ("pubmed_clinical_index",)
