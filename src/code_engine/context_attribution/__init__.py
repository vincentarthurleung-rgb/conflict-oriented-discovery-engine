"""Evidence-grounded, fail-closed L4 context attribution."""

from .engine import (
    build_abstract_input, build_fulltext_input, candidate_pairs,
    extraction_cache_identity, pair_cache_identity,
)
from .gate import apply_comparability_gate
from .models import ContextExtraction, ContextPairAttribution
from .readiness import calculate_scientific_status, scientific_readiness
from .registry import RegistryResolution, resolve_registry
from .validation import validate_context_extraction, validate_pair_attribution

__all__ = [
    "ContextExtraction", "ContextPairAttribution", "RegistryResolution",
    "apply_comparability_gate", "calculate_scientific_status",
    "build_abstract_input", "build_fulltext_input", "candidate_pairs",
    "extraction_cache_identity", "pair_cache_identity", "resolve_registry",
    "scientific_readiness",
    "validate_context_extraction", "validate_pair_attribution",
]
