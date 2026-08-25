"""L3a proposition-level alignment, independent of pair comparability."""

from .adapters import align_legacy_candidate_endpoints
from .models import AlignedClaimGroup, CanonicalPropositionSignature
from .validation import validate_claim_alignment
from .granularity import GranularityBridgeAssessment, assess_granularity_bridge
from .v2 import ClaimAlignmentRecordV2, align_semantic_views, validate_claim_alignment_v2
from .scientific_proposition_v1_candidate import (
    MeasurementPropositionCompatibilityV1,
    ScientificPropositionCompatibilityV1,
    ScientificPropositionSignatureV1,
    evaluate_scientific_proposition_compatibility_v1,
    project_scientific_proposition_signature_v1,
)

__all__ = [
    "AlignedClaimGroup",
    "CanonicalPropositionSignature",
    "align_legacy_candidate_endpoints",
    "validate_claim_alignment",
    "GranularityBridgeAssessment",
    "assess_granularity_bridge",
    "ClaimAlignmentRecordV2",
    "align_semantic_views",
    "validate_claim_alignment_v2",
    "MeasurementPropositionCompatibilityV1",
    "ScientificPropositionCompatibilityV1",
    "ScientificPropositionSignatureV1",
    "evaluate_scientific_proposition_compatibility_v1",
    "project_scientific_proposition_signature_v1",
]
