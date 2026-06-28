"""Compatibility facade for deterministic domain routing."""

from code_engine.domain.router import default_domain_router


def detect_validation_domain(text: str):
    """Return the deterministic domain profile used by validation planning."""

    return default_domain_router().route_text(text)
