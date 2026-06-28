"""Heuristic policy-guided mechanism path scoring; no RL training is used."""

from __future__ import annotations

import hashlib
from typing import Any

from pydantic import Field

from code_engine.schemas.models import CODEBaseModel


POLICY_WEIGHTS = {
    "evidence_strength": 0.25,
    "conflict_information_gain": 0.20,
    "context_separability": 0.20,
    "validation_coverage": 0.15,
    "novelty": 0.10,
    "feasibility": 0.10,
}


class MechanismPathPolicyScore(CODEBaseModel):
    path_id: str
    nodes: list[str] = Field(default_factory=list)
    edges: list[str] = Field(default_factory=list)
    evidence_strength: float = 0.0
    conflict_information_gain: float = 0.0
    context_separability: float = 0.0
    validation_coverage: float = 0.0
    novelty: float = 0.0
    feasibility: float = 0.0
    total_score: float = 0.0
    warnings: list[str] = Field(default_factory=list)


def score_mechanism_path(path: dict[str, Any]) -> MechanismPathPolicyScore:
    """Apply fixed deterministic weights to caller-provided normalized features."""

    def bounded(name: str) -> float:
        return max(0.0, min(1.0, float(path.get(name, 0.0))))

    features = {name: bounded(name) for name in POLICY_WEIGHTS}
    score = round(sum(features[name] * weight for name, weight in POLICY_WEIGHTS.items()), 6)
    nodes = [str(item) for item in path.get("nodes", [])]
    edges = [str(item) for item in path.get("edges", [])]
    path_id = str(path.get("path_id") or hashlib.sha256("|".join(nodes + edges).encode()).hexdigest()[:16])
    warnings = ["heuristic_policy_score_not_reinforcement_learning"]
    if not edges:
        warnings.append("path_has_no_typed_edges")
    return MechanismPathPolicyScore(path_id=path_id, nodes=nodes, edges=edges, total_score=score, warnings=warnings, **features)


def rank_mechanism_paths(paths: list[dict[str, Any]]) -> list[MechanismPathPolicyScore]:
    return sorted((score_mechanism_path(path) for path in paths), key=lambda item: (-item.total_score, item.path_id))

