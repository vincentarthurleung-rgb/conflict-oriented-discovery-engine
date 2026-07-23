"""Evidence-grounded, fail-closed L4 context attribution."""

from .engine import (
    build_abstract_input, build_fulltext_input, candidate_pairs,
    extraction_cache_identity, pair_cache_identity,
)
from .gate import apply_comparability_gate
from .models import ContextExtraction, ContextPairAttribution
from .validation import validate_context_extraction, validate_pair_attribution

__all__ = [
    "ContextExtraction", "ContextPairAttribution", "apply_comparability_gate",
    "build_abstract_input", "build_fulltext_input", "candidate_pairs",
    "extraction_cache_identity", "pair_cache_identity",
    "validate_context_extraction", "validate_pair_attribution",
]
