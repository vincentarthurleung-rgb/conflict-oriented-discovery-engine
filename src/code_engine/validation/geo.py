"""Local-index-aware GEO validator skeleton."""

from code_engine.validation.skeleton import ExternalIndexValidator


class GEOValidator(ExternalIndexValidator):
    name = "GEOValidator"
    supported_domains = ("neuropharmacology",)
    supported_relation_types = ("drug_gene_expression", "pathway_expression")
    supported_entity_types = ("compound", "gene", "protein", "pathway")
    required_resources = ("geo_index",)
    supported_anchor_types = ("gene_set_anchor", "triple_anchor", "hypothesis_anchor", "conflict_anchor")
    supported_validation_intents = ("expression_direction_check", "dataset_discovery")
    supports_local_index = True
    supports_remote_api = True
    index_name = "geo"
    source_database = "GEO"
    evidence_type = "expression_metadata"
    default_signal_type = "expression_support"
    interpretation_limits = ("GEO metadata or summary evidence is not a raw-matrix differential analysis.", "External evidence is not proof.")
