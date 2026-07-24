from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from ..layer_identity import layer_identity
from .comparability.models import FactorComparabilityAssessment
from .divergence_explanation.models import FactorDivergenceExplanation


class FactorAttributionBundle(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        title="Factor Attribution Bundle v1",
        json_schema_extra={
            "$id": "https://conflict-oriented-discovery-engine.local/schemas/factor_attribution_bundle_v1"
        },
    )

    schema_version: Literal[
        "factor_attribution_bundle_v1"
    ] = "factor_attribution_bundle_v1"
    pair_id: str
    context_difference_identity: str
    comparability_assessment_ids: list[str]
    divergence_explanation_ids: list[str]
    pending_factor_ids: list[str]
    rejected_factor_ids: list[str]
    insufficient_factor_ids: list[str]
    all_comparability_assessed: bool
    all_explanations_assessed: bool
    policy_identities: list[str]
    adjudication_identities: list[str]
    comparability_assessment_bundle_identity: str
    divergence_explanation_bundle_identity: str
    bundle_identity: str
    provenance: dict[str, Any]
    validation_status: Literal["validated", "rejected"]


def _branch_identity(kind: str, identities: list[str]) -> str:
    return layer_identity(
        kind, f"{kind}_identity_v1", {"artifact_identities": identities}
    )


def factor_attribution_bundle_identity(payload: dict[str, Any]) -> str:
    return layer_identity(
        "factor_attribution_bundle",
        "factor_attribution_bundle_identity_v1",
        {
            key: payload[key]
            for key in (
                "pair_id",
                "context_difference_identity",
                "comparability_assessment_ids",
                "divergence_explanation_ids",
                "pending_factor_ids",
                "rejected_factor_ids",
                "insufficient_factor_ids",
                "all_comparability_assessed",
                "all_explanations_assessed",
                "policy_identities",
                "adjudication_identities",
                "comparability_assessment_bundle_identity",
                "divergence_explanation_bundle_identity",
            )
        },
    )


def build_factor_attribution_bundle(
    *,
    pair_id: str,
    context_difference_identity: str,
    comparability: list[FactorComparabilityAssessment],
    explanations: list[FactorDivergenceExplanation],
) -> FactorAttributionBundle:
    comp_ids = [item.factor_comparability_identity for item in comparability]
    exp_ids = [
        item.factor_divergence_explanation_identity for item in explanations
    ]
    comp_by_factor = {item.factor_id: item for item in comparability}
    exp_by_factor = {item.factor_id: item for item in explanations}
    factors = list(dict.fromkeys([*comp_by_factor, *exp_by_factor]))
    pending = [
        factor
        for factor in factors
        if (
            comp_by_factor.get(factor) is None
            or comp_by_factor[factor].assessment_status
            in {"not_assessed", "pending_policy", "pending_human_adjudication"}
            or exp_by_factor.get(factor) is None
            or exp_by_factor[factor].assessment_status
            in {"not_assessed", "pending_policy", "pending_human_adjudication"}
        )
    ]
    rejected = [
        factor
        for factor in factors
        if (
            comp_by_factor.get(factor)
            and comp_by_factor[factor].assessment_status == "rejected"
        )
        or (
            exp_by_factor.get(factor)
            and exp_by_factor[factor].assessment_status == "rejected"
        )
    ]
    insufficient = [
        factor
        for factor in factors
        if (
            comp_by_factor.get(factor)
            and comp_by_factor[factor].assessment_status
            == "insufficient_information"
        )
        or (
            exp_by_factor.get(factor)
            and exp_by_factor[factor].assessment_status
            == "insufficient_information"
        )
    ]
    policy_ids = sorted(
        {
            value
            for item in comparability
            for value in [item.comparability_policy_identity]
            if value
        }
        | {
            value
            for item in explanations
            for value in [item.explanation_policy_identity]
            if value
        }
    )
    adjudication_ids = sorted(
        {
            value
            for item in [*comparability, *explanations]
            for value in [item.adjudication_identity]
            if value
        }
    )
    payload = {
        "schema_version": "factor_attribution_bundle_v1",
        "pair_id": pair_id,
        "context_difference_identity": context_difference_identity,
        "comparability_assessment_ids": comp_ids,
        "divergence_explanation_ids": exp_ids,
        "pending_factor_ids": pending,
        "rejected_factor_ids": rejected,
        "insufficient_factor_ids": insufficient,
        "all_comparability_assessed": bool(comparability)
        and all(
            item.assessment_status == "validated"
            and item.validation_status == "validated"
            for item in comparability
        ),
        "all_explanations_assessed": bool(explanations)
        and all(
            item.assessment_status == "assessed"
            and item.validation_status == "validated"
            for item in explanations
        ),
        "policy_identities": policy_ids,
        "adjudication_identities": adjudication_ids,
        "comparability_assessment_bundle_identity": _branch_identity(
            "comparability_assessment_bundle", comp_ids
        ),
        "divergence_explanation_bundle_identity": _branch_identity(
            "divergence_explanation_bundle", exp_ids
        ),
        "provenance": {
            "scientific_aggregation_performed": False,
            "max_severity_computed": False,
            "aggregate_explanatory_score_computed": False,
            "automatic_pair_class_computed": False,
        },
        "validation_status": "validated",
    }
    payload["bundle_identity"] = factor_attribution_bundle_identity(payload)
    return FactorAttributionBundle.model_validate(payload)


def validate_factor_attribution_bundle(
    bundle: FactorAttributionBundle,
    *,
    comparability: list[FactorComparabilityAssessment],
    explanations: list[FactorDivergenceExplanation],
) -> list[str]:
    errors: list[str] = []
    if bundle.comparability_assessment_ids != [
        item.factor_comparability_identity for item in comparability
    ]:
        errors.append("comparability_bundle_identity_drift")
    if bundle.divergence_explanation_ids != [
        item.factor_divergence_explanation_identity for item in explanations
    ]:
        errors.append("explanation_bundle_identity_drift")
    if bundle.bundle_identity != factor_attribution_bundle_identity(
        bundle.model_dump()
    ):
        errors.append("factor_attribution_bundle_identity_mismatch")
    return errors
