"""Local-index-aware PubMed clinical-evidence validator skeleton."""

from code_engine.validation.skeleton import ExternalIndexValidator


class PubMedClinicalEvidenceValidator(ExternalIndexValidator):
    name = "PubMedClinicalEvidenceValidator"
    supported_domains = ("clinical_outcome",)
    supported_entity_types = ("compound", "disease", "phenotype")
    required_resources = ("pubmed_clinical_index",)
    supported_anchor_types = ("clinical_context_anchor", "hypothesis_anchor", "phenotype_anchor")
    supported_validation_intents = ("clinical_context_check", "literature_clinical_check")
    supports_local_index = True
    supports_remote_api = True
    index_name = "pubmed_clinical"
    source_database = "PubMed"
    evidence_type = "clinical_literature_record"
    default_signal_type = "clinical_context_signal"
    interpretation_limits = ("Clinical literature lookup is conservative evidence assessment, not proof.",)
