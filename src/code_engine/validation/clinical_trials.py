"""Local-index-aware clinical-trials validator skeleton."""

from code_engine.validation.skeleton import ExternalIndexValidator


class ClinicalTrialsValidator(ExternalIndexValidator):
    name = "ClinicalTrialsValidator"
    supported_domains = ("clinical_outcome",)
    supported_entity_types = ("compound", "disease", "phenotype")
    required_resources = ("clinical_trials_index",)
    supported_anchor_types = ("clinical_context_anchor", "hypothesis_anchor", "phenotype_anchor")
    supported_validation_intents = ("clinical_context_check",)
    supports_local_index = True
    supports_remote_api = True
    index_name = "clinical_trials"
    source_database = "ClinicalTrials.gov"
    evidence_type = "clinical_trial_record"
    default_signal_type = "trial_existence_signal"
    interpretation_limits = ("Trial existence is not efficacy support.", "No trial found is not contradiction.")
