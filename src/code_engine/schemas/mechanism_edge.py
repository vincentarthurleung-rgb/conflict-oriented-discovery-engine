"""Typed mechanism edges that preserve biological distinctions."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator

from code_engine.schemas.models import CODEBaseModel


EdgeType = Literal[
    "causal_positive", "causal_negative", "regulatory", "conditioned_by",
    "supported_by", "validated_by", "unresolved_by", "subunit_of",
    "metabolite_of", "salt_form_of", "explains", "addresses_bottleneck",
    "introduces_tradeoff", "compares_with",
]


class MechanismEdge(CODEBaseModel):
    edge_id: str
    source: str
    source_type: str = "unknown"
    target: str
    target_type: str = "unknown"
    edge_type: EdgeType
    direct_relation_sign: int = 0
    relation_raw: str = ""
    relation_family: str = "unknown"
    context: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    positive_count: int = 0
    negative_count: int = 0
    conflict_entropy: float = 0.0
    conflict_state: str = "unresolved"
    probabilistic_state: dict[str, Any] = Field(default_factory=dict)
    normalization_warnings: list[str] = Field(default_factory=list)

    @field_validator("direct_relation_sign")
    @classmethod
    def validate_sign(cls, value: int) -> int:
        if value not in (-1, 0, 1):
            raise ValueError("direct_relation_sign must be -1, 0, or 1")
        return value

    @classmethod
    def from_legacy_pair(cls, pair: dict[str, Any]) -> "MechanismEdge":
        sign = int(pair.get("relation_sign", pair.get("direct_relation_sign", 0)))
        edge_type = "causal_positive" if sign > 0 else "causal_negative" if sign < 0 else "regulatory"
        evidence_ids = list(pair.get("evidence_ids") or pair.get("supporting_triples", []))
        evidence_ids.extend(item for item in pair.get("contradicting_triples", []) if item not in evidence_ids)
        source, target = str(pair.get("source") or pair.get("subject") or ""), str(pair.get("target") or pair.get("object") or "")
        return cls(
            edge_id=str(pair.get("edge_id") or f"{source}->{target}"),
            source=source,
            source_type=str(pair.get("source_type") or "unknown"),
            target=target,
            target_type=str(pair.get("target_type") or "unknown"),
            edge_type=edge_type,
            direct_relation_sign=sign,
            relation_raw=str(pair.get("relation_raw") or ""),
            relation_family=str(pair.get("relation_family") or "legacy_causal_pair"),
            context=dict(pair.get("context") or {}),
            evidence_ids=evidence_ids,
            evidence_count=int(pair.get("evidence_count") or len(evidence_ids)),
            positive_count=int(pair.get("positive_count", 0)),
            negative_count=int(pair.get("negative_count", 0)),
            conflict_entropy=float(pair.get("entropy", pair.get("conflict_entropy", 0.0))),
            conflict_state=str(pair.get("conflict_type") or pair.get("conflict_state") or "unresolved"),
            normalization_warnings=list(pair.get("normalization_warnings", [])),
        )

