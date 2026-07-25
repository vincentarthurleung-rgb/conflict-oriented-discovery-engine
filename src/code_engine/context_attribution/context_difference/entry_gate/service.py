from __future__ import annotations
from typing import Any
from ...conflict_candidate.qualification.models import ConflictCandidateQualificationV1, QualifiedCandidateAuthoritySidecarV1
from .identities import identity
from .models import ContextDifferenceEntryAuthorizationV1, ContextEndpointAuthority

def authorize_entry(*, qualification: ConflictCandidateQualificationV1,
                    authority: QualifiedCandidateAuthoritySidecarV1,
                    endpoint_a: ContextEndpointAuthority,
                    endpoint_b: ContextEndpointAuthority,
                    policy_identity: str) -> ContextDifferenceEntryAuthorizationV1:
    secondary: list[str] = []
    if qualification.qualification_status != "qualified":
        status, primary = "blocked_candidate_unqualified", (
            "alignment_unvalidated" if qualification.qualification_status == "blocked_alignment"
            else f"candidate_{qualification.qualification_status}"
        )
        secondary = [f"candidate_qualification_{qualification.qualification_status}"]
    elif not endpoint_a.context_present and not endpoint_b.context_present:
        status, primary = "blocked_context_both_unavailable", "both_contexts_unavailable"
    elif not endpoint_a.context_present:
        status, primary = "blocked_context_a_unavailable", "context_a_unavailable"
    elif not endpoint_b.context_present:
        status, primary = "blocked_context_b_unavailable", "context_b_unavailable"
    elif not endpoint_a.context_validator_valid and not endpoint_b.context_validator_valid:
        status, primary = "blocked_context_both_unvalidated", "both_contexts_unvalidated"
    elif not endpoint_a.context_validator_valid:
        status, primary = "blocked_context_a_unvalidated", "context_a_unvalidated"
    elif not endpoint_b.context_validator_valid:
        status, primary = "blocked_context_b_unvalidated", "context_b_unvalidated"
    elif not endpoint_a.context_identity_valid or not endpoint_b.context_identity_valid:
        status, primary = "blocked_context_identity_mismatch", "context_identity_mismatch"
    elif not endpoint_a.endpoint_binding_valid or not endpoint_b.endpoint_binding_valid:
        status, primary = "blocked_endpoint_context_binding_mismatch", "endpoint_context_binding_mismatch"
    elif not endpoint_a.context_authority_valid or not endpoint_b.context_authority_valid:
        status, primary = "insufficient_information", "context_authority_incomplete"
    else:
        status, primary = "ready", None
    basis: dict[str, Any] = {
        "candidate_id": qualification.candidate_id,
        "scientific_candidate_pair_identity": qualification.scientific_candidate_pair_identity,
        "candidate_qualification_identity": qualification.qualification_identity,
        "candidate_qualification_status": qualification.qualification_status,
        "qualified_candidate_authority_identity": authority.identity,
        "qualified_for_l4_entry_evaluation": qualification.qualified_for_l4,
        "observation_a_id": qualification.observation_a_id, "observation_b_id": qualification.observation_b_id,
        "endpoint_claim_identity_a": qualification.endpoint_claim_identity_a,
        "endpoint_claim_identity_b": qualification.endpoint_claim_identity_b,
        "observation_context_identity_a": endpoint_a.observation_context_identity,
        "observation_context_identity_b": endpoint_b.observation_context_identity,
        "observation_context_status_a": endpoint_a.observation_context_status,
        "observation_context_status_b": endpoint_b.observation_context_status,
        "observation_context_validator_identity_a": endpoint_a.observation_context_validator_identity,
        "observation_context_validator_identity_b": endpoint_b.observation_context_validator_identity,
        "observation_context_source_identity_a": endpoint_a.observation_context_source_identity,
        "observation_context_source_identity_b": endpoint_b.observation_context_source_identity,
        "endpoint_context_binding_status_a": "valid" if endpoint_a.endpoint_binding_valid else "mismatch",
        "endpoint_context_binding_status_b": "valid" if endpoint_b.endpoint_binding_valid else "mismatch",
        "context_gate_policy_identity": policy_identity, "entry_status": status,
        "primary_block_reason": primary, "secondary_block_reasons": secondary,
        "ready_for_authoritative_context_difference": status == "ready",
        "provenance": {"comparability_consumed": False, "explanation_consumed": False,
                       "formal_decision_consumed": False, "source_contexts_read_only": True},
    }
    return ContextDifferenceEntryAuthorizationV1(**basis, identity=identity("context_difference_entry_authorization", basis))
