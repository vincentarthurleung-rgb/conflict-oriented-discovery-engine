"""Local-index-aware pathway validator skeletons."""

from code_engine.validation.skeleton import ExternalIndexValidator


class ReactomeValidator(ExternalIndexValidator):
    name = "ReactomeValidator"
    supported_domains = ("pathway_biology", "neuropharmacology", "protein_interaction")
    supported_relation_types = ("pathway_mechanism", "pathway_activation", "protein_interaction", "ligand_receptor")
    supported_entity_types = ("gene", "protein", "pathway", "receptor_complex")
    required_resources = ("reactome_index",)


class PathwayValidator(ReactomeValidator):
    name = "PathwayValidator"
    supported_relation_types = (
        "drug_gene_expression",
        "pathway_expression",
        "pathway_mechanism",
        "pathway_activation",
    )
