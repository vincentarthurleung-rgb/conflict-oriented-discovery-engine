"""Local-index-aware STRING validator skeleton."""

from code_engine.validation.skeleton import ExternalIndexValidator


class STRINGValidator(ExternalIndexValidator):
    name = "STRINGValidator"
    supported_domains = ("protein_interaction",)
    supported_relation_types = ("protein_interaction", "ligand_receptor")
    supported_entity_types = ("gene", "protein", "receptor_complex")
    required_resources = ("string_index",)
    supported_anchor_types = ("triple_anchor", "mechanism_gap_anchor", "mechanism_path_anchor")
    supported_validation_intents = ("protein_interaction_check",)
    supports_local_index = True
    supports_remote_api = True
    index_name = "stringdb"
    source_database = "STRING"
    evidence_type = "protein_interaction_record"
    default_signal_type = "protein_interaction_support"
    interpretation_limits = ("Network interaction does not establish causal direction.",)
