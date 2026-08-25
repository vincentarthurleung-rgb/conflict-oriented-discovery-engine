from __future__ import annotations
from typing import Any, Literal, Sequence
from pydantic import BaseModel, ConfigDict
from code_engine.extraction_assets.scientific_entity_integrity import (
    ScientificEntityIntegrityGateResultV1, require_scientific_entity_integrity,
)
from ..claim_alignment.v2 import ClaimAlignmentRecordV2
from ..layer_identity import layer_identity
from ..observation_semantics.models import ContradictionResultView


class ResultDimensionComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dimension_id: str
    value_a: str | None
    value_b: str | None
    comparison: Literal["opposed","same","different","unresolved"]


def compare_result_directions_v2(
    direction_a: str | None,
    direction_b: str | None,
) -> Literal["opposed", "same", "unresolved"]:
    """Apply the deterministic v2 direction policy without creating a signal.

    Proposition compatibility is intentionally outside this helper.  Callers
    must establish it before using direction to assess contradiction.
    """
    supported = {"positive", "negative"}
    if direction_a not in supported or direction_b not in supported:
        return "unresolved"
    return "same" if direction_a == direction_b else "opposed"


class ContradictionSignalV2(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["contradiction_signal_v2"] = "contradiction_signal_v2"
    contradiction_signal_id: str
    alignment_record_identity_v2: str
    alignment_status: str
    observation_a_id: str
    observation_b_id: str
    result_identity_a: str
    result_identity_b: str
    signal_type: Literal["opposite_direction","incompatible_outcome","quantitative_disagreement","unresolved_disagreement"]
    signal_status: Literal["validated","candidate","rejected","insufficient_information"]
    signal_structure_valid: bool
    signal_schema_valid: bool = True
    signal_validator_valid: bool = True
    signal_provenance_complete: bool = True
    alignment_eligible: bool = False
    candidate_qualification_status: str | None = None
    candidate_qualification_identity: str | None = None
    downstream_candidate_authority: bool = False
    result_dimension_comparisons: list[ResultDimensionComparison]
    signal_basis: list[str]
    candidate_authority_scope: Literal["future_standard","legacy_preserved","diagnostic_only"]
    formal_adjudication_eligible: bool
    deprecated_ambiguous_metric: bool = True
    validator_version: Literal["contradiction_signal_validator_v2"] = "contradiction_signal_validator_v2"
    contradiction_signal_identity_v2: str
    provenance: dict[str, Any]


def build_contradiction_signal_v2(*, alignment: ClaimAlignmentRecordV2,
                                  result_a: ContradictionResultView,
                                  result_b: ContradictionResultView,
                                  historical_candidate: bool,
                                  entity_integrity_decisions: Sequence[ScientificEntityIntegrityGateResultV1] | None = None,
                                  ) -> ContradictionSignalV2:
    require_scientific_entity_integrity("contradiction_signal", entity_integrity_decisions)
    a, b = result_a.direction, result_b.direction
    direction_relation = compare_result_directions_v2(a, b)
    opposed = direction_relation == "opposed"
    structural = bool(opposed)
    scope = ("legacy_preserved" if historical_candidate
             else "future_standard" if alignment.alignment_status == "aligned" and structural
             else "diagnostic_only")
    eligible = (not historical_candidate) and alignment.alignment_status == "aligned" and structural
    payload = {
        "schema_version":"contradiction_signal_v2",
        "contradiction_signal_id":layer_identity("contradiction_signal_record","contradiction_signal_record_id_v2",
                                                 {"alignment":alignment.claim_alignment_identity_v2}),
        "alignment_record_identity_v2":alignment.claim_alignment_identity_v2,
        "alignment_status":alignment.alignment_status,
        "observation_a_id":alignment.observation_a_id,"observation_b_id":alignment.observation_b_id,
        "result_identity_a":result_a.contradiction_result_identity,
        "result_identity_b":result_b.contradiction_result_identity,
        "signal_type":"opposite_direction" if opposed else "unresolved_disagreement",
        "signal_status":"validated" if opposed else "insufficient_information",
        "signal_structure_valid":structural,
        "signal_schema_valid":True,
        "signal_validator_valid":True,
        "signal_provenance_complete":True,
        "alignment_eligible":alignment.alignment_status == "aligned",
        "candidate_qualification_status":None,
        "candidate_qualification_identity":None,
        "downstream_candidate_authority":False,
        "result_dimension_comparisons":[{"dimension_id":"direction","value_a":a,"value_b":b,
                                         "comparison":"opposed" if opposed else "unresolved"}],
        "signal_basis":["result views compared independently of proposition core",
                        "structural validity does not confer formal authority"],
        "candidate_authority_scope":scope,"formal_adjudication_eligible":eligible,
        "deprecated_ambiguous_metric":True,
        "validator_version":"contradiction_signal_validator_v2",
        "provenance":{"result_view_only":True,"context_effect_consumed":False,
                      "alignment_gate_bypassed":False}}
    payload["contradiction_signal_identity_v2"] = layer_identity(
        "contradiction_signal","contradiction_signal_identity_v2",
        {k:payload[k] for k in ("alignment_record_identity_v2","alignment_status","result_identity_a",
                                "result_identity_b","signal_type","signal_status","signal_structure_valid",
                                "result_dimension_comparisons","candidate_authority_scope",
                                "formal_adjudication_eligible","validator_version")})
    return ContradictionSignalV2.model_validate(payload)


def validate_contradiction_signal_v2(signal: ContradictionSignalV2,
                                     alignment: ClaimAlignmentRecordV2) -> list[str]:
    errors = []
    if signal.alignment_record_identity_v2 != alignment.claim_alignment_identity_v2:
        errors.append("alignment_identity_mismatch")
    if signal.formal_adjudication_eligible and alignment.alignment_status != "aligned":
        errors.append("formal_eligibility_bypasses_alignment")
    return errors
