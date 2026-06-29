"""lincs validation index builder."""

from code_engine.validation.index_builders.base import ValidationIndexBuilder


class LINCSIndexBuilder(ValidationIndexBuilder):
    name = "lincs_index_builder"
    validator_name = "LINCSValidator"
    schema_name = "lincs"


__all__ = ["LINCSIndexBuilder"]
