from __future__ import annotations

from typing import Any

from .identities import authority_sidecar_identity, qualification_identity, scientific_pair_identity
from .models import (
    ConflictCandidateQualificationV1,
    QualifiedCandidateAuthoritySidecarV1,
    ScientificCandidatePairIdentityV1,
)
from .validation import VALIDATOR_IDENTITY, validate_qualification


def build_scientific_pair(
    *, claim_a: str, claim_b: str, core_a: str, core_b: str,
    signal_type: str, contract_identity: str,
) -> ScientificCandidatePairIdentityV1:
    basis = {
        "endpoint_claim_identity_a": claim_a,
        "endpoint_claim_identity_b": claim_b,
        "proposition_core_identity_a": core_a,
        "proposition_core_identity_b": core_b,
        "observation_pair_ordering_policy": "legacy_candidate_endpoint_order_v1",
        "contradiction_signal_type": signal_type,
        "candidate_scientific_pair_contract_identity": contract_identity,
    }
    return ScientificCandidatePairIdentityV1(
        **basis, scientific_candidate_pair_identity=scientific_pair_identity(basis)
    )


def qualify_candidate(*, candidate: dict[str, Any], alignment: dict[str, Any],
                      signal: dict[str, Any], pair: ScientificCandidatePairIdentityV1,
                      contract_identity: str, generation_policy_identity: str,
                      context_a: str | None = None, context_b: str | None = None
                      ) -> ConflictCandidateQualificationV1:
    errors: list[str] = []
    if not candidate.get("claim_a_identity") or not candidate.get("claim_b_identity"):
        errors.append("endpoint_identity_incomplete")
    if candidate["observation_a_id"] != alignment["observation_a_id"] or candidate["observation_b_id"] != alignment["observation_b_id"]:
        errors.append("lineage_endpoint_mismatch")
    if signal["alignment_record_identity_v2"] != alignment["claim_alignment_identity_v2"]:
        errors.append("signal_alignment_identity_mismatch")
    if errors:
        status = "rejected"
    elif alignment["alignment_status"] != "aligned":
        status, errors = "blocked_alignment", ["alignment_not_aligned"]
    elif not (
        signal["signal_status"] == "validated"
        and signal["signal_structure_valid"]
        and signal.get("signal_schema_valid", True)
        and signal.get("signal_validator_valid", True)
        and signal.get("signal_provenance_complete", bool(signal.get("provenance")))
    ):
        status, errors = "blocked_signal", ["signal_qualification_input_ineligible"]
    elif not generation_policy_identity:
        status, errors = "insufficient_information", ["generation_policy_identity_missing"]
    else:
        status = "qualified"
    basis = {
        "candidate_id": candidate["candidate_id"],
        "legacy_candidate_identity": candidate["conflict_candidate_identity"],
        "observation_a_id": candidate["observation_a_id"],
        "observation_b_id": candidate["observation_b_id"],
        "endpoint_claim_identity_a": candidate["claim_a_identity"],
        "endpoint_claim_identity_b": candidate["claim_b_identity"],
        "proposition_core_identity_a": alignment["proposition_core_identity_a"],
        "proposition_core_identity_b": alignment["proposition_core_identity_b"],
        "claim_alignment_v2_identity": alignment["claim_alignment_identity_v2"],
        "claim_alignment_status": alignment["alignment_status"],
        "contradiction_signal_v2_identity": signal["contradiction_signal_identity_v2"],
        "contradiction_signal_status": signal["signal_status"],
        "contradiction_signal_structure_valid": signal["signal_structure_valid"],
        "contradiction_signal_schema_valid": signal.get("signal_schema_valid", True),
        "contradiction_signal_validator_valid": signal.get("signal_validator_valid", True),
        "contradiction_signal_provenance_complete": signal.get("signal_provenance_complete", bool(signal.get("provenance"))),
        "candidate_generation_policy_identity": generation_policy_identity,
        "qualification_contract_identity": contract_identity,
        "qualification_validator_identity": VALIDATOR_IDENTITY,
        "scientific_candidate_pair_identity": pair.scientific_candidate_pair_identity,
        "source_lineage": {"legacy_candidate_read_only": True, "endpoint_order_preserved": True},
        "provenance": {"provider_effect_used": False, "comparability_consumed": False,
                       "divergence_explanation_consumed": False},
        "observation_context_readiness_a": context_a,
        "observation_context_readiness_b": context_b,
        "qualification_status": status,
        "qualification_error_codes": errors,
        "qualified_for_l4": status == "qualified",
    }
    record = ConflictCandidateQualificationV1(
        **basis, qualification_identity=qualification_identity(basis)
    )
    validation_errors = validate_qualification(record)
    if validation_errors:
        raise ValueError(",".join(validation_errors))
    return record


def build_authority_sidecar(record: ConflictCandidateQualificationV1) -> QualifiedCandidateAuthoritySidecarV1:
    basis = {
        "candidate_id": record.candidate_id,
        "legacy_candidate_identity": record.legacy_candidate_identity,
        "qualification_identity": record.qualification_identity,
        "authority_status": record.qualification_status,
        "authority_scope": "future_standard" if record.qualified_for_l4 else "legacy_only",
        "lineage_status": "complete",
        "qualified_for_l4": record.qualified_for_l4,
        "source_pair_set_unchanged": True,
        "legacy_identity_preserved": True,
        "scientific_pair_identity": record.scientific_candidate_pair_identity,
    }
    return QualifiedCandidateAuthoritySidecarV1(
        **basis, identity=authority_sidecar_identity(basis)
    )

