"""L3: high-recall conflict candidate structure."""

from .adapters import adapt_legacy_weak_candidate
from .models import ConflictCandidate
from .validation import validate_conflict_candidate
from .contradiction import ContradictionSignal, validate_contradiction_signal
from .migration import CandidateMigrationBinding, bind_historical_candidate
from .contradiction_v2 import (
    ContradictionSignalV2,
    build_contradiction_signal_v2,
    compare_result_directions_v2,
    validate_contradiction_signal_v2,
)
from .binding_v2 import CandidateAlignmentSignalBindingV2, bind_candidate_v2
from .scientific_regeneration_v1_candidate import (
    DiagnosticFulltextPairV1,
    FulltextScientificObservationV1,
    ScientificConflictCandidateV2Candidate,
    ScientificPropositionBlockV1,
    generate_bounded_diagnostic_pairs_v1,
)

__all__ = [
    "ConflictCandidate",
    "adapt_legacy_weak_candidate",
    "validate_conflict_candidate",
    "ContradictionSignal",
    "validate_contradiction_signal",
    "CandidateMigrationBinding",
    "bind_historical_candidate",
    "ContradictionSignalV2",
    "build_contradiction_signal_v2",
    "compare_result_directions_v2",
    "validate_contradiction_signal_v2",
    "CandidateAlignmentSignalBindingV2",
    "bind_candidate_v2",
    "DiagnosticFulltextPairV1",
    "FulltextScientificObservationV1",
    "ScientificConflictCandidateV2Candidate",
    "ScientificPropositionBlockV1",
    "generate_bounded_diagnostic_pairs_v1",
]
