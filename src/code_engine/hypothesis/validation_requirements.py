"""Rule-derived validation requirements; these are requests, not results."""

from __future__ import annotations


REQUIREMENTS = {
    "mechanism_conflict_hypothesis": ["expression_direction_check", "pathway_membership_check", "context_specific_omics_check"],
    "context_partition_hypothesis": ["context_specific_literature_check", "cell_type_or_species_specific_omics_check"],
    "mechanism_gap_hypothesis": ["pathway_bridge_check", "protein_interaction_check", "target_binding_check"],
    "target_mediated_hypothesis": ["binding_activity_check", "drug_target_identity_check"],
    "pathway_bridge_hypothesis": ["reactome_pathway_check", "stringdb_interaction_check", "uniprot_function_check"],
    "abstract_conflict_followup_hypothesis": ["fulltext_confirmation_required", "manual_review_required"],
    "coverage_gap_hypothesis": ["fulltext_confirmation_required", "manual_review_required"],
    "legacy_conflict_hypothesis": ["fulltext_confirmation_required", "context_specific_literature_check"],
}


def build_validation_requirements_for_hypothesis(hypothesis: dict) -> list[dict]:
    kind = str(hypothesis.get("hypothesis_type") or hypothesis.get("candidate_type") or "")
    names = list(REQUIREMENTS.get(kind, ["manual_review_required"]))
    domain = str(hypothesis.get("domain_id") or "").casefold()
    if kind == "context_partition_hypothesis" and "clinical" in domain:
        names.append("clinical_context_check")
    priority = str(hypothesis.get("validation_priority") or ("low" if kind in {"coverage_gap_hypothesis", "abstract_conflict_followup_hypothesis"} else "medium"))
    return [
        {
            "requirement_id": f"{hypothesis.get('candidate_id') or hypothesis.get('hypothesis_id')}:{name}",
            "hypothesis_id": hypothesis.get("hypothesis_id") or hypothesis.get("candidate_id"),
            "requirement_type": name,
            "priority": priority,
            "status": "not_run",
        }
        for name in dict.fromkeys(names)
    ]


__all__ = ["build_validation_requirements_for_hypothesis"]
