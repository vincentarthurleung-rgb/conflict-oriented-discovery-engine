"""Optional UniProt identity/function validator."""

from code_engine.validation.skeleton import ExternalIndexValidator


class UniProtValidator(ExternalIndexValidator):
    name = "UniProtValidator"
    supported_anchor_types = ("entity_anchor", "triple_anchor", "mechanism_gap_anchor")
    supported_validation_intents = ("identity_lookup", "protein_interaction_check")
    supported_entity_types = ("gene", "protein")
    supports_local_index = True
    supports_remote_api = True
    index_name = "uniprot"
    source_database = "UniProt"
    evidence_type = "protein_annotation_record"
    default_signal_type = "protein_function_annotation"
    interpretation_limits = ("Function annotation is not causal mechanism proof.",)
