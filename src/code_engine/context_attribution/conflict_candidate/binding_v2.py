from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict
from ..layer_identity import layer_identity


class CandidateAlignmentSignalBindingV2(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["candidate_alignment_signal_binding_v2"] = "candidate_alignment_signal_binding_v2"
    candidate_id: str
    legacy_candidate_identity: str
    claim_alignment_identity_v1: str
    claim_alignment_identity_v2: str
    contradiction_signal_identity_v1: str
    contradiction_signal_identity_v2: str
    candidate_authority_scope: Literal["future_standard","legacy_preserved","diagnostic_only"]
    alignment_gate_passed: bool
    formal_adjudication_eligible: bool
    migration_status: Literal["migrated_read_only"]
    candidate_alignment_signal_binding_identity_v2: str


def bind_candidate_v2(**values: object) -> CandidateAlignmentSignalBindingV2:
    payload = {"schema_version":"candidate_alignment_signal_binding_v2", **values,
               "migration_status":"migrated_read_only"}
    payload["candidate_alignment_signal_binding_identity_v2"] = layer_identity(
        "candidate_alignment_signal_binding","candidate_alignment_signal_binding_identity_v2",
        {k:payload[k] for k in ("legacy_candidate_identity","claim_alignment_identity_v1",
                                "claim_alignment_identity_v2","contradiction_signal_identity_v1",
                                "contradiction_signal_identity_v2","candidate_authority_scope",
                                "alignment_gate_passed","formal_adjudication_eligible","migration_status")})
    return CandidateAlignmentSignalBindingV2.model_validate(payload)
