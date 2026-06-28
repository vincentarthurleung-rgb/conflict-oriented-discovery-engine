"""Optional Open Targets association validator."""

from code_engine.validation.skeleton import ExternalIndexValidator


class OpenTargetsValidator(ExternalIndexValidator):
    name = "OpenTargetsValidator"
    supported_anchor_types = ("clinical_context_anchor", "entity_anchor", "hypothesis_anchor", "gene_set_anchor")
    supported_validation_intents = ("clinical_context_check", "cancer_dependency_check")
    supported_entity_types = ("gene", "protein", "disease")
    supports_local_index = True
    supports_remote_api = True
    index_name = "opentargets"
    source_database = "Open Targets"
    evidence_type = "target_disease_association"
    default_signal_type = "target_disease_association_signal"
    interpretation_limits = ("Target-disease association is not causal proof.",)
