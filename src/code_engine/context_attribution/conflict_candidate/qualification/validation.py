from __future__ import annotations

from .models import ConflictCandidateQualificationV1

VALIDATOR_IDENTITY = "conflict_candidate_qualification_validator_v1"


def validate_qualification(record: ConflictCandidateQualificationV1) -> list[str]:
    errors: list[str] = []
    if not record.legacy_candidate_identity:
        errors.append("legacy_candidate_identity_missing")
    if not record.scientific_candidate_pair_identity:
        errors.append("scientific_pair_identity_missing")
    if record.qualification_status == "qualified":
        if record.claim_alignment_status != "aligned":
            errors.append("alignment_not_eligible")
        if record.contradiction_signal_status != "validated":
            errors.append("signal_not_validated")
        if not all((
            record.contradiction_signal_structure_valid,
            record.contradiction_signal_schema_valid,
            record.contradiction_signal_validator_valid,
            record.contradiction_signal_provenance_complete,
        )):
            errors.append("signal_input_incomplete")
    return errors

