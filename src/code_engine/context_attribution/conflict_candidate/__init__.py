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
from .proposition_authority_v1_candidate import (
    MinimumScientificPropositionProfileV1,
    ObservationScientificReadinessAxesV1,
    PropositionAuthorityRecoveryV1,
    PropositionSufficiencyAssessmentV1,
    evaluate_minimum_proposition_sufficiency_v1,
    measurement_semantic_family_v1,
    profile_for_observation_type_v1,
    recover_exact_local_alias_v1,
    repository_proposition_profiles_v1,
)
from .entity_identity_authority_v1_candidate import (
    EntityMentionEvidenceV1,
    LocalEntityEquivalenceDecisionV1,
    decide_local_equivalence_v1,
    exact_surface_v1,
    local_identity_key_v1,
)
from .proposition_frontier_v1_candidate import (
    FrontierSemanticRecoveryV1,
    PropositionSufficiencyBlockerV1,
    deterministic_measurement_property_family_v1,
    deterministic_relation_effect_family_v1,
    deterministic_result_semantic_family_v1,
    field_is_required_v2_candidate,
)
from .cross_publication_frontier_v1_candidate import (
    CrossPublicationCompatibilityEnvelopeV1,
    PartialDimensionV1,
    PartialScientificPropositionSignatureV1,
    compare_cross_publication_envelope_v1,
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
    "MinimumScientificPropositionProfileV1",
    "ObservationScientificReadinessAxesV1",
    "PropositionAuthorityRecoveryV1",
    "PropositionSufficiencyAssessmentV1",
    "evaluate_minimum_proposition_sufficiency_v1",
    "measurement_semantic_family_v1",
    "profile_for_observation_type_v1",
    "recover_exact_local_alias_v1",
    "repository_proposition_profiles_v1",
    "EntityMentionEvidenceV1",
    "LocalEntityEquivalenceDecisionV1",
    "decide_local_equivalence_v1",
    "exact_surface_v1",
    "local_identity_key_v1",
    "FrontierSemanticRecoveryV1",
    "PropositionSufficiencyBlockerV1",
    "deterministic_measurement_property_family_v1",
    "deterministic_relation_effect_family_v1",
    "deterministic_result_semantic_family_v1",
    "field_is_required_v2_candidate",
    "CrossPublicationCompatibilityEnvelopeV1",
    "PartialDimensionV1",
    "PartialScientificPropositionSignatureV1",
    "compare_cross_publication_envelope_v1",
]
