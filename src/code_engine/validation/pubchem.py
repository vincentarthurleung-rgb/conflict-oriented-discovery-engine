"""Optional remote/cache-only PubChem identity validator."""

from code_engine.validation.skeleton import ExternalIndexValidator


class PubChemValidator(ExternalIndexValidator):
    name = "PubChemValidator"
    supported_anchor_types = ("entity_anchor", "triple_anchor", "hypothesis_anchor")
    supported_validation_intents = ("identity_lookup",)
    supported_entity_types = ("compound",)
    supports_remote_api = True
    index_name = "pubchem"
    source_database = "PubChem"
    evidence_type = "compound_identity_record"
    default_signal_type = "identity_support"
    interpretation_limits = ("Compound identity and cross-references do not validate a mechanism.",)
