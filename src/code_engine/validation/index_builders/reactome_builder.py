"""reactome validation index builder."""

from code_engine.validation.index_builders.base import ValidationIndexBuilder


class ReactomeIndexBuilder(ValidationIndexBuilder):
    name = "reactome_index_builder"
    validator_name = "ReactomeValidator"
    schema_name = "reactome"


__all__ = ["ReactomeIndexBuilder"]
