"""Build report blueprints from ranked hypothesis dictionaries."""

from __future__ import annotations

from typing import Any, Dict, List


ANCHOR_FIELD_PRIORITY = [
    "omics_anchor_gene",
    "registry_anchor_gene",
    "anchor_gene",
    "target_gene",  # legacy field retained for backward compatibility
    "lincs_target_gene_matched",  # legacy field retained for backward compatibility
]


def resolve_anchor_gene(hypothesis: Dict[str, Any]) -> Dict[str, str]:
    """Resolve the display anchor gene using new fields before legacy fields."""

    for field in ANCHOR_FIELD_PRIORITY:
        value = str(hypothesis.get(field, "")).strip()
        if value and value.upper() not in {"UNKNOWN", "UNSPECIFIED", "N/A", "NONE"}:
            source = "legacy" if field in {"target_gene", "lincs_target_gene_matched"} else "current"
            return {"anchor_gene": value, "anchor_gene_source": field, "anchor_gene_semantics": source}
    return {"anchor_gene": "UNSPECIFIED", "anchor_gene_source": "none", "anchor_gene_semantics": "unresolved"}


def build_intervention_blueprint(anchor_gene: str, relation_sign: int, seed_pair: str = "") -> Dict[str, str]:
    """Create conservative experiment guidance from an anchor gene and polarity."""

    clean_anchor = str(anchor_gene).strip().upper()
    if clean_anchor in {"UNKNOWN", "UNSPECIFIED", "N/A", "NONE", "GLUTAMATE"}:
        if "GLUTAMATE" in str(seed_pair).upper() or clean_anchor == "GLUTAMATE":
            clean_anchor = "SLC17A7 (VGLUT1 / vesicular glutamate transporter 1)"
        else:
            clean_anchor = "GRIA1 (AMPA Receptor Subunit 1 / systematic fallback anchor)"

    if relation_sign > 0:
        return {
            "paradigm": "Gain-of-function / positive perturbation assay",
            "method": f"Overexpression or positive perturbation design targeting {clean_anchor}.",
            "guideline": "Measure downstream synaptic or transcriptional response with matched controls.",
        }
    return {
        "paradigm": "Loss-of-function / negative perturbation assay",
        "method": f"Knockdown, knockout, or negative perturbation design targeting {clean_anchor}.",
        "guideline": "Confirm perturbation efficiency before downstream phenotyping.",
    }


def build_report_blueprints(ranked_hypotheses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert ranked hypotheses into markdown-ready report objects."""

    blueprints = []
    for rank, hypothesis in enumerate(ranked_hypotheses, start=1):
        anchor = resolve_anchor_gene(hypothesis)
        first_sign = hypothesis.get("whitebox_traceability", [{}])[0].get("relation_sign", 1)
        validation_result = hypothesis.get("validation_result", {})
        validation_status = hypothesis.get("validation_status") or validation_result.get("status") or "Pending"
        blueprints.append(
            {
                "rank": rank,
                "hypothesis_id": hypothesis.get("hypothesis_id", "UNKNOWN"),
                "seed_pair": hypothesis.get("seed_pair", ""),
                "anchor_gene": anchor["anchor_gene"],
                "anchor_gene_source": anchor["anchor_gene_source"],
                "anchor_gene_semantics": anchor["anchor_gene_semantics"],
                "global_ranking_score": hypothesis.get("global_ranking_score", 0.0),
                "minimal_augmented_context_set": hypothesis.get("minimal_augmented_context_set", []),
                "separating_contexts": hypothesis.get("separating_contexts", []),
                "whitebox_traceability": hypothesis.get("whitebox_traceability", []),
                "metrics_breakdown": hypothesis.get("metrics_breakdown", {}),
                "intervention_blueprint": build_intervention_blueprint(anchor["anchor_gene"], first_sign, hypothesis.get("seed_pair", "")),
                "loss_ci_95": hypothesis.get("loss_ci_95", [0.0, 0.0]),
                "validation_status": validation_status,
                "validation_score": validation_result.get("score"),
                "validation_limitations": validation_result.get("limitations", []),
            }
        )
    return blueprints
