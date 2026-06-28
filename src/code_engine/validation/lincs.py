"""Resource-aware LINCS summary-index validator; never loads the full matrix."""

from code_engine.validation.skeleton import ExternalIndexValidator


class LINCSValidator(ExternalIndexValidator):
    name = "LINCSValidator"
    supported_anchor_types = ("triple_anchor", "gene_set_anchor", "hypothesis_anchor")
    supported_validation_intents = ("expression_direction_check", "cancer_dependency_check")
    supported_relation_types = ("drug_gene_expression", "pathway_expression", "gene_expression")
    supported_entity_types = ("compound", "gene", "protein", "pathway")
    required_resources = ("lincs_index",)
    supports_local_index = True
    index_name = "lincs"
    source_database = "LINCS summary index"
    evidence_type = "perturbation_signature_summary"
    default_signal_type = "expression_support"
    interpretation_limits = ("Summary index only; the full LINCS expression matrix is not loaded.",)
