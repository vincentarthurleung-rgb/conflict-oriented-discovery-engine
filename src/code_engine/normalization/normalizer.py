"""Public facade for deterministic biomedical entity resolution."""

from code_engine.normalization.resolver import resolve_entity


def normalize_entity(value: str, synonym_map: dict[str, str] | None = None):
    """Resolve an entity; synonym_map is retained only for call compatibility."""

    return resolve_entity(value)
