"""depmap validation index builder."""

from code_engine.validation.index_builders.base import ValidationIndexBuilder


class DepMapIndexBuilder(ValidationIndexBuilder):
    name = "depmap_index_builder"
    validator_name = "DepMapValidator"
    schema_name = "depmap"


__all__ = ["DepMapIndexBuilder"]
