"""Resource-aware DepMap dependency summary validator."""

from code_engine.validation.skeleton import ExternalIndexValidator


class DepMapValidator(ExternalIndexValidator):
    name = "DepMapValidator"
    supported_anchor_types = ("gene_set_anchor", "entity_anchor", "hypothesis_anchor")
    supported_validation_intents = ("cancer_dependency_check",)
    supported_domains = ("oncology", "cancer_biology", "general_biomedical")
    supported_entity_types = ("gene", "protein", "disease")
    required_resources = ("depmap_index",)
    supports_local_index = True
    index_name = "depmap"
    source_database = "DepMap"
    evidence_type = "cancer_dependency_record"
    default_signal_type = "cancer_dependency_context"
    interpretation_limits = ("Cancer cell-line dependency is not clinical efficacy.",)
