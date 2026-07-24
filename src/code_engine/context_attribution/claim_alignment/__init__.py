"""L3a proposition-level alignment, independent of pair comparability."""

from .adapters import align_legacy_candidate_endpoints
from .models import AlignedClaimGroup, CanonicalPropositionSignature
from .validation import validate_claim_alignment

__all__ = [
    "AlignedClaimGroup",
    "CanonicalPropositionSignature",
    "align_legacy_candidate_endpoints",
    "validate_claim_alignment",
]
