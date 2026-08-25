from __future__ import annotations

from typing import Any, Literal, Sequence
from pydantic import BaseModel, ConfigDict
from code_engine.extraction_assets.scientific_entity_integrity import (
    ScientificEntityIntegrityGateResultV1, require_scientific_entity_integrity,
)
from ..layer_identity import layer_identity
from ..observation_semantics.models import PropositionCoreView
from .granularity import GranularityBridgeAssessment


class CoreDimensionComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dimension_id: str
    value_a: str | None
    value_b: str | None
    status: Literal["match", "mismatch", "unresolved"]
    basis: str


class ClaimAlignmentRecordV2(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["claim_alignment_record_v2"] = "claim_alignment_record_v2"
    alignment_record_id: str
    observation_a_id: str
    observation_b_id: str
    proposition_core_identity_a: str
    proposition_core_identity_b: str
    proposition_core_signature_a: dict[str, Any]
    proposition_core_signature_b: dict[str, Any]
    core_dimension_comparisons: list[CoreDimensionComparison]
    granularity_bridge_assessments: list[GranularityBridgeAssessment]
    alignment_status: Literal["aligned","partially_aligned","unaligned","insufficient_information"]
    alignment_basis: list[str]
    blocking_core_dimensions: list[str]
    unresolved_core_dimensions: list[str]
    unresolved_bridge_dimensions: list[str]
    excluded_context_dimensions: list[str]
    excluded_contradiction_dimensions: list[str]
    legacy_claim_alignment_identity_v1: str
    role_taxonomy_identity: str
    validator_version: Literal["claim_alignment_validator_v2"] = "claim_alignment_validator_v2"
    claim_alignment_identity_v2: str
    provenance: dict[str, Any]


def align_semantic_views(*, observation_a_id: str, observation_b_id: str,
                         core_a: PropositionCoreView, core_b: PropositionCoreView,
                         bridges: list[GranularityBridgeAssessment], legacy_identity: str,
                         role_taxonomy_identity: str,
                         entity_integrity_decisions: Sequence[ScientificEntityIntegrityGateResultV1] | None = None,
                         ) -> ClaimAlignmentRecordV2:
    require_scientific_entity_integrity("claim_alignment", entity_integrity_decisions)
    keys = ("canonical_subject_identity","canonical_relation_family",
            "canonical_endpoint_identity","outcome_variable_identity")
    comparisons = []
    for key in keys:
        a, b = getattr(core_a,key), getattr(core_b,key)
        if key == "outcome_variable_identity" and a is None and b is None:
            state, basis = "match", "optional dimension absent on both observations"
        elif a is None or b is None:
            state, basis = "unresolved", "required normalized core identity unavailable"
        elif a == b:
            state, basis = "match", "exact normalized core value match"
        else:
            state, basis = "mismatch", "normalized core values differ"
        comparisons.append({"dimension_id":key,"value_a":a,"value_b":b,"status":state,"basis":basis})
    blocking = [x["dimension_id"] for x in comparisons if x["status"] == "mismatch"]
    unresolved = [x["dimension_id"] for x in comparisons if x["status"] == "unresolved"
                  and x["dimension_id"] != "outcome_variable_identity"]
    unresolved_bridges = [x.dimension_id for x in bridges if x.bridge_status in {"unresolved","partially_compatible"}]
    incompatible = [x.dimension_id for x in bridges if x.bridge_status == "incompatible"]
    status = ("unaligned" if blocking or incompatible else
              "insufficient_information" if unresolved else
              "partially_aligned" if unresolved_bridges else "aligned")
    signature_keys = ("canonical_subject_identity","canonical_relation_family",
                      "canonical_endpoint_identity","outcome_variable_identity",
                      "proposition_core_dimensions","unresolved_core_dimensions","normalization_identities")
    payload = {
        "schema_version":"claim_alignment_record_v2",
        "alignment_record_id":layer_identity("alignment_record","alignment_record_id_v2",
                                             {"observation_a_id":observation_a_id,"observation_b_id":observation_b_id}),
        "observation_a_id":observation_a_id,"observation_b_id":observation_b_id,
        "proposition_core_identity_a":core_a.proposition_core_identity,
        "proposition_core_identity_b":core_b.proposition_core_identity,
        "proposition_core_signature_a":{k:getattr(core_a,k) for k in signature_keys},
        "proposition_core_signature_b":{k:getattr(core_b,k) for k in signature_keys},
        "core_dimension_comparisons":comparisons,
        "granularity_bridge_assessments":[x.model_dump() for x in bridges],
        "alignment_status":status,
        "alignment_basis":["direction and context dimensions excluded from proposition alignment",
                           "nonexact granularity requires explicit versioned policy"],
        "blocking_core_dimensions":blocking+incompatible,"unresolved_core_dimensions":unresolved,
        "unresolved_bridge_dimensions":unresolved_bridges,
        "excluded_context_dimensions":["measurement_method","assay","dose","duration","species",
                                       "temporal_context","intervention_context"],
        "excluded_contradiction_dimensions":["direction","sign","polarity","qualitative_outcome",
                                             "quantitative_effect","result_category"],
        "legacy_claim_alignment_identity_v1":legacy_identity,"role_taxonomy_identity":role_taxonomy_identity,
        "validator_version":"claim_alignment_validator_v2",
        "provenance":{"pairwise_record":True,"legacy_alignment_modified":False,
                      "automatic_granularity_equivalence":False}}
    payload["claim_alignment_identity_v2"] = layer_identity(
        "claim_alignment","claim_alignment_identity_v2",
        {k:payload[k] for k in ("proposition_core_identity_a","proposition_core_identity_b",
                                "core_dimension_comparisons","granularity_bridge_assessments",
                                "alignment_status","blocking_core_dimensions","unresolved_core_dimensions",
                                "unresolved_bridge_dimensions","role_taxonomy_identity","validator_version")})
    return ClaimAlignmentRecordV2.model_validate(payload)


def validate_claim_alignment_v2(record: ClaimAlignmentRecordV2) -> list[str]:
    if record.alignment_status == "aligned" and (
        record.blocking_core_dimensions or record.unresolved_core_dimensions or record.unresolved_bridge_dimensions):
        return ["aligned_record_has_unresolved_gate"]
    return []
