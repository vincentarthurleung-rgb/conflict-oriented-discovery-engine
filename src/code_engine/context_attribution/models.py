from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

EXTRACTION_SCHEMA_VERSION = "observation_context_extraction_v5"
EXTRACTION_SCHEMA_VERSION_V6 = "observation_context_extraction_v6"
PAIR_SCHEMA_VERSION = "context_pair_attribution_v2"

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class RawComponent(StrictModel):
    chain_node_id: str
    field_path: str
    surface: str = Field(min_length=1)
    evidence_anchor_ids: list[str] = Field(min_length=1)

class ExplicitSpan(StrictModel):
    evidence_anchor_id: str
    start_token_id: str
    end_token_id: str


class ProviderContextFactorV6(StrictModel):
    """Provider-owned v6 fields.

    Factor-level anchors and every hydrated/composed/normalized field are
    deliberately absent.  They are deterministic system authority.
    """

    factor_id: str
    status: Literal["explicit", "inferred_from_local_chain", "unknown", "conflicting"]
    explicit_span: ExplicitSpan | None = None
    source_chain_node_ids: list[str] = Field(default_factory=list)
    inference_rule: str | None = None
    raw_components: list[RawComponent] = Field(default_factory=list)
    normalized_candidate: str | None = None
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def status_contract(self):
        if self.status == "explicit":
            if self.explicit_span is None:
                raise ValueError("explicit_factor_requires_token_span")
            if self.raw_components or self.source_chain_node_ids or self.inference_rule:
                raise ValueError("explicit_factor_must_not_have_chain_components")
        elif self.status == "inferred_from_local_chain":
            if self.explicit_span is not None:
                raise ValueError("inferred_factor_explicit_span_forbidden")
            if not self.raw_components:
                raise ValueError("inferred_factor_requires_raw_components")
            if not self.source_chain_node_ids or not self.inference_rule:
                raise ValueError("inferred_factor_requires_chain_nodes_and_rule")
            component_nodes = list(dict.fromkeys(x.chain_node_id for x in self.raw_components))
            if self.source_chain_node_ids != component_nodes:
                raise ValueError("inferred_factor_nodes_must_match_components")
        elif self.status == "unknown":
            if any((
                self.explicit_span, self.source_chain_node_ids, self.inference_rule,
                self.raw_components, self.normalized_candidate,
            )):
                raise ValueError("unknown_factor_must_be_empty")
        return self


class ProviderContextExtractionV6(StrictModel):
    schema_version: Literal["observation_context_extraction_v6"] = EXTRACTION_SCHEMA_VERSION_V6
    observation_id: str
    domain_profiles: list[str] = Field(min_length=1)
    input_mode: Literal["abstract_sentence_only", "fulltext_evidence_chain"]
    context_factors: list[ProviderContextFactorV6]
    missing_critical_information: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

class ContextFactor(StrictModel):
    factor_id: str
    raw_value: str | None = None
    normalized_value: str | None = None
    status: Literal["explicit", "inferred_from_local_chain", "unknown", "conflicting"]
    evidence_anchor_ids: list[str] = Field(default_factory=list)
    source_chain_node_ids: list[str] = Field(default_factory=list)
    inference_rule: str | None = None
    raw_components: list[RawComponent] = Field(default_factory=list)
    explicit_span: ExplicitSpan | None = None
    raw_value_source: Literal["explicit_token_span"] | None = None
    explicit_span_resolution: dict[str, Any] = Field(default_factory=dict)
    composed_value: str | None = None
    composition_rule: str | None = None
    composition_provenance: list[dict[str, Any]] = Field(default_factory=list)
    normalized_candidate: str | None = None
    normalization_status: Literal[
        "not_requested", "resolved_identity", "resolved_controlled",
        "resolved_supplied", "unresolved_candidate", "not_applicable",
    ] = "not_requested"
    normalization_provenance: dict = Field(default_factory=dict)
    evidence_text: str | None = None
    authoritative_evidence: list[dict] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    legacy_unverifiable: bool = False

    @model_validator(mode="after")
    def status_contract(self):
        if self.status == "explicit":
            legacy = self.legacy_unverifiable and self.raw_value
            if not legacy and (self.explicit_span is None or not self.evidence_anchor_ids):
                raise ValueError("explicit_factor_requires_token_span_and_anchor")
            if self.raw_value is not None and not self.raw_value_source and not legacy:
                raise ValueError("provider_explicit_raw_value_must_be_null")
            if self.raw_components or self.source_chain_node_ids or self.inference_rule:
                raise ValueError("explicit_factor_must_not_have_chain_components")
        elif self.status == "inferred_from_local_chain":
            if self.raw_value is not None:
                raise ValueError("inferred_factor_raw_value_must_be_null")
            if not self.raw_components and not self.legacy_unverifiable:
                raise ValueError("inferred_factor_requires_raw_components")
            if not self.source_chain_node_ids or not self.inference_rule:
                raise ValueError("inferred_factor_requires_chain_nodes_and_rule")
            if self.explicit_span is not None:
                raise ValueError("inferred_factor_explicit_span_forbidden")
            component_nodes = list(dict.fromkeys(x.chain_node_id for x in self.raw_components))
            if self.raw_components and self.source_chain_node_ids != component_nodes:
                raise ValueError("inferred_factor_nodes_must_match_components")
        elif self.status == "unknown":
            legacy_unknown = self.legacy_unverifiable and self.raw_value == "unknown"
            if self.raw_value is not None and not legacy_unknown:
                raise ValueError("unknown_factor_raw_value_must_be_null")
            if any((
                self.normalized_candidate, self.normalized_value, self.evidence_anchor_ids,
                self.source_chain_node_ids, self.raw_components, self.inference_rule,
                self.composed_value, self.composition_rule, self.composition_provenance,
                self.explicit_span, self.raw_value_source, self.explicit_span_resolution,
            )):
                raise ValueError("unknown_factor_must_be_empty")
        return self

class ContextExtraction(StrictModel):
    schema_version: Literal["observation_context_extraction_v5"] = EXTRACTION_SCHEMA_VERSION
    observation_id: str
    domain_profiles: list[str] = Field(min_length=1)
    input_mode: Literal["abstract_sentence_only", "fulltext_evidence_chain"]
    context_factors: list[ContextFactor]
    missing_critical_information: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provenance: dict = Field(default_factory=dict)
    extraction_identity: str | None = None
    validation_status: Literal["unvalidated", "validated", "rejected", "reviewable"] = "unvalidated"

    @model_validator(mode="before")
    @classmethod
    def read_legacy_artifacts(cls, value):
        if isinstance(value, dict) and value.get("schema_version") in {
            "observation_context_extraction_v2", "observation_context_extraction_v3",
            "observation_context_extraction_v4",
        }:
            original = value["schema_version"]
            factors = []
            for factor in value.get("context_factors", []):
                converted = {**factor, "legacy_unverifiable": True}
                if converted.get("status") == "inferred_from_local_chain":
                    converted["raw_value"] = None
                factors.append(converted)
            value = {
                **value,
                "schema_version": EXTRACTION_SCHEMA_VERSION,
                "context_factors": factors,
                "provenance": {
                    **(value.get("provenance") or {}),
                    "compatibility_read": {
                        "original_schema_version": original,
                        "legacy_components_synthesized": False,
                    },
                },
            }
        return value

    @model_validator(mode="after")
    def provider_fields_are_unhydrated(self):
        compatibility_read = bool(self.provenance.get("compatibility_read"))
        if self.validation_status == "unvalidated" and not compatibility_read:
            for factor in self.context_factors:
                if factor.normalized_value is not None:
                    raise ValueError("provider_normalized_value_must_be_null")
                if factor.status == "explicit" and factor.raw_value is not None:
                    raise ValueError("provider_explicit_raw_value_must_be_null")
                if factor.raw_value_source or factor.explicit_span_resolution:
                    raise ValueError("provider_explicit_hydration_fields_forbidden")
                if factor.composed_value or factor.composition_rule or factor.composition_provenance:
                    raise ValueError("provider_composition_fields_forbidden")
        return self

class FactorComparison(StrictModel):
    factor_id: str
    claim_a_value: str
    claim_b_value: str
    status: Literal["same", "equivalent", "different", "missing_a", "missing_b", "missing_both", "conflicting"]
    comparability_effect: Literal["none", "minor", "major", "blocking", "unknown"]
    explanatory_strength: Literal["none", "low", "medium", "high", "unknown"]
    claim_a_anchor_ids: list[str] = Field(default_factory=list)
    claim_b_anchor_ids: list[str] = Field(default_factory=list)
    reason: str

class ContextPairAttribution(StrictModel):
    schema_version: Literal["context_pair_attribution_v2"] = PAIR_SCHEMA_VERSION
    pair_id: str
    claim_a_observation_id: str
    claim_b_observation_id: str
    comparability: Literal["comparable", "conditionally_comparable", "non_comparable", "insufficient_information"]
    factor_comparisons: list[FactorComparison]
    primary_explanatory_factors: list[str] = Field(default_factory=list)
    missing_critical_information: list[str] = Field(default_factory=list)
    reasoning_summary: str
    confidence: float = Field(ge=0, le=1)
    comparison_identity: str | None = None
    validation_status: Literal["unvalidated", "validated", "rejected", "reviewable"] = "unvalidated"
