"""Formal graph relation registry and normalization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FormalRelation:
    relation: str
    family: str
    sign: int
    direction: str
    formal_graph_eligible: bool = True
    conflict_eligible: bool = True
    measurement_dimension: str | None = None
    semantic_kind: str = "causal"
    formal_conflict_eligible: bool | None = None
    formal_hypothesis_eligible: bool | None = None

    def __post_init__(self) -> None:
        if self.formal_conflict_eligible is None:
            object.__setattr__(self, "formal_conflict_eligible", self.conflict_eligible)
        if self.formal_hypothesis_eligible is None:
            object.__setattr__(self, "formal_hypothesis_eligible", self.conflict_eligible)


RELATION_REGISTRY: dict[str, FormalRelation] = {
    "activation": FormalRelation("activation", "positive_regulation", 1, "positive"),
    "activates": FormalRelation("activates", "positive_regulation", 1, "positive"),
    "increases": FormalRelation("increases", "positive_regulation", 1, "positive"),
    "increase": FormalRelation("increase", "positive_regulation", 1, "positive"),
    "pathway_regulation": FormalRelation("pathway_regulation", "regulation", 1, "positive"),
    "expression_regulation": FormalRelation("expression_regulation", "regulation", 1, "positive", conflict_eligible=False, measurement_dimension="expression"),
    "phosphorylation_regulation": FormalRelation("phosphorylation_regulation", "regulation", 1, "positive", conflict_eligible=False, measurement_dimension="phosphorylation"),
    "inhibition": FormalRelation("inhibition", "negative_regulation", -1, "negative"),
    "inhibits": FormalRelation("inhibits", "negative_regulation", -1, "negative"),
    "decreases": FormalRelation("decreases", "negative_regulation", -1, "negative"),
    "decrease": FormalRelation("decrease", "negative_regulation", -1, "negative"),
    "increases_expression_of": FormalRelation("increases_expression_of", "positive_regulation", 1, "positive", measurement_dimension="expression"),
    "decreases_expression_of": FormalRelation("decreases_expression_of", "negative_regulation", -1, "negative", measurement_dimension="expression"),
    "increases_abundance_of": FormalRelation("increases_abundance_of", "positive_regulation", 1, "positive", measurement_dimension="abundance"),
    "decreases_abundance_of": FormalRelation("decreases_abundance_of", "negative_regulation", -1, "negative", measurement_dimension="abundance"),
    "increases_phosphorylation_of": FormalRelation("increases_phosphorylation_of", "positive_regulation", 1, "positive", measurement_dimension="phosphorylation"),
    "decreases_phosphorylation_of": FormalRelation("decreases_phosphorylation_of", "negative_regulation", -1, "negative", measurement_dimension="phosphorylation"),
    "increases_activity_of": FormalRelation("increases_activity_of", "positive_regulation", 1, "positive", measurement_dimension="activity"),
    "decreases_activity_of": FormalRelation("decreases_activity_of", "negative_regulation", -1, "negative", measurement_dimension="activity"),
    "promotes_nuclear_localization_of": FormalRelation("promotes_nuclear_localization_of", "positive_regulation", 1, "positive", measurement_dimension="localization"),
    "reduces_nuclear_localization_of": FormalRelation("reduces_nuclear_localization_of", "negative_regulation", -1, "negative", measurement_dimension="localization"),
    "higher_expression_in": FormalRelation("higher_expression_in", "differential_expression", 1, "positive", conflict_eligible=False, measurement_dimension="expression", semantic_kind="association", formal_conflict_eligible=False, formal_hypothesis_eligible=False),
    "lower_expression_in": FormalRelation("lower_expression_in", "differential_expression", -1, "negative", conflict_eligible=False, measurement_dimension="expression", semantic_kind="association", formal_conflict_eligible=False, formal_hypothesis_eligible=False),
    "differentially_expressed_in": FormalRelation("differentially_expressed_in", "differential_expression", 0, "unknown", formal_graph_eligible=False, conflict_eligible=False, measurement_dimension="expression", semantic_kind="association", formal_conflict_eligible=False, formal_hypothesis_eligible=False),
    "associated_with": FormalRelation("associated_with", "association", 0, "unknown", formal_graph_eligible=False, conflict_eligible=False, semantic_kind="association", formal_conflict_eligible=False, formal_hypothesis_eligible=False),
    "observed_decrease_after": FormalRelation("observed_decrease_after", "intervention_event", -1, "negative", formal_graph_eligible=False, conflict_eligible=False, semantic_kind="intervention_event", formal_conflict_eligible=False, formal_hypothesis_eligible=False),
    "observed_increase_after": FormalRelation("observed_increase_after", "intervention_event", 1, "positive", formal_graph_eligible=False, conflict_eligible=False, semantic_kind="intervention_event", formal_conflict_eligible=False, formal_hypothesis_eligible=False),
    "rescues": FormalRelation("rescues", "rescue", 1, "positive", formal_graph_eligible=False, conflict_eligible=False, semantic_kind="intervention_event", formal_conflict_eligible=False, formal_hypothesis_eligible=False),
    "reverses_effect_of": FormalRelation("reverses_effect_of", "rescue", 1, "positive", formal_graph_eligible=False, conflict_eligible=False, semantic_kind="intervention_event", formal_conflict_eligible=False, formal_hypothesis_eligible=False),
    "measured_in": FormalRelation("measured_in", "measurement", 0, "unknown", formal_graph_eligible=False, conflict_eligible=False, semantic_kind="measurement", formal_conflict_eligible=False, formal_hypothesis_eligible=False),
    "present_in_sample": FormalRelation("present_in_sample", "context", 0, "unknown", formal_graph_eligible=False, conflict_eligible=False, semantic_kind="context", formal_conflict_eligible=False, formal_hypothesis_eligible=False),
}


def normalize_formal_relation(observation: dict[str, Any]) -> FormalRelation | None:
    if observation.get("core_projection_relation"):
        return RELATION_REGISTRY.get(str(observation.get("core_projection_relation")))
    derived_sign = observation.get("derived_causal_sign")
    if derived_sign in (1, "+1", "1", "positive"):
        return RELATION_REGISTRY["increases"]
    if derived_sign in (-1, "-1", "negative"):
        return RELATION_REGISTRY["decreases"]
    relation = str(
        observation.get("relation_family")
        or observation.get("relation_raw")
        or ""
    ).strip()
    if relation in RELATION_REGISTRY:
        return RELATION_REGISTRY[relation]
    direction = str(observation.get("direction") or "").casefold()
    if direction in {"positive", "increase", "activate"}:
        return RELATION_REGISTRY["increases"]
    if direction in {"negative", "decrease", "inhibit"}:
        return RELATION_REGISTRY["decreases"]
    return None


__all__ = ["FormalRelation", "RELATION_REGISTRY", "normalize_formal_relation"]
