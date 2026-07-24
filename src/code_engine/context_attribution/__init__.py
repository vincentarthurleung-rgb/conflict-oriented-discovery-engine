"""Deprecated compatibility facade plus separated context pipeline layers.

New runtime code must import the layer package it owns.  Legacy exports remain
readable for historical runs and will be removed in a later migration.
"""

from .engine import (
    build_abstract_input, build_fulltext_input, candidate_pairs,
    extraction_cache_identity, pair_cache_identity,
)
from .gate import apply_comparability_gate
from .models import ContextExtraction, ContextPairAttribution
from .readiness import calculate_scientific_status, scientific_readiness
from .registry import RegistryResolution, resolve_registry
from .validation import validate_context_extraction, validate_pair_attribution
from .conflict_candidate import ConflictCandidate
from .conflict_comparability import ConflictComparabilityAssessment
from .conflict_judgment import FormalConflictDecision
from .context_difference import ContextDifference
from .observation_context import ObservationContext

__all__ = [
    "ContextExtraction", "ContextPairAttribution", "RegistryResolution",
    "ObservationContext", "ConflictCandidate", "ContextDifference",
    "ConflictComparabilityAssessment", "FormalConflictDecision",
    "apply_comparability_gate", "calculate_scientific_status",
    "build_abstract_input", "build_fulltext_input", "candidate_pairs",
    "extraction_cache_identity", "pair_cache_identity", "resolve_registry",
    "scientific_readiness",
    "validate_context_extraction", "validate_pair_attribution",
]
