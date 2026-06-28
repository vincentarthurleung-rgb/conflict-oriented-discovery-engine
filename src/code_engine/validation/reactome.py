"""Local-index-aware pathway validator skeletons."""

from code_engine.validation.skeleton import ExternalIndexValidator


class ReactomeValidator(ExternalIndexValidator):
    name = "ReactomeValidator"
    supported_domains = ("pathway_biology", "neuropharmacology", "protein_interaction")
    supported_relation_types = ("pathway_mechanism", "pathway_activation", "protein_interaction", "ligand_receptor")
    supported_entity_types = ("gene", "protein", "pathway", "receptor_complex")
    required_resources = ("reactome_index",)
    supported_anchor_types = ("pathway_anchor", "mechanism_path_anchor", "mechanism_gap_anchor", "hypothesis_anchor")
    supported_validation_intents = ("pathway_membership_check",)
    supports_local_index = True
    supports_remote_api = True
    index_name = "reactome"
    source_database = "Reactome"
    evidence_type = "pathway_membership_record"
    default_signal_type = "pathway_membership_support"
    interpretation_limits = ("Pathway membership is not causality proof.",)


class PathwayValidator(ReactomeValidator):
    name = "PathwayValidator"
    index_name = "pathway"
    supported_relation_types = (
        "drug_gene_expression",
        "pathway_expression",
        "pathway_mechanism",
        "pathway_activation",
    )
