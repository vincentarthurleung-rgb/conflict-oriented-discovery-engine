"""Local-index-aware GEO validator skeleton."""

from code_engine.validation.skeleton import ExternalIndexValidator


class GEOValidator(ExternalIndexValidator):
    name = "GEOValidator"
    supported_domains = ("neuropharmacology",)
    supported_relation_types = ("drug_gene_expression", "pathway_expression")
    supported_entity_types = ("compound", "gene", "protein", "pathway")
    required_resources = ("geo_index",)
