"""Create evidence-bearing annotation tasks; never execute or accept annotations."""
from __future__ import annotations

from typing import Any

from .identities import core_identity

QUESTIONS = {
    "comparator": "该Observed Result明确相对于哪个Comparator、Control或Baseline报告？",
    "factor_application": "以下哪些Experimental Factors明确适用于该Measurement？",
    "measurement_method": "该Measurement使用了什么测量方法？",
}
LABELS = {
    "comparator": ["factor_id", "multiple_comparators", "no_comparator_reported", "source_insufficient", "cannot_determine"],
    "factor_application": ["one_or_more_factor_ids", "all_listed_factors", "none", "source_insufficient", "cannot_determine"],
    "measurement_method": ["specific_method_text", "assay_family_only", "method_not_reported", "source_insufficient", "cannot_determine"],
}


def build_annotation_target(
    *,
    task_type: str,
    observation_identity: str,
    result_identity: str | None,
    measurement_identity: str | None,
    factor_candidate_ids: list[str],
    experiment_scope_identity: str | None,
    envelope: dict[str, Any],
    candidate_answers: list[str],
    ambiguity_reason: str,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    if not envelope.get("primary_result_sentence"):
        raise ValueError("annotation target requires primary source evidence")
    competing = len(candidate_answers)
    difficulty = (
        "hard" if competing > 2
        else "medium" if competing == 2 or envelope.get("methods_text_refs")
        else "easy"
    )
    payload = {
        "annotation_target_id": "",
        "task_type": task_type,
        "observation_identity": observation_identity,
        "result_identity": result_identity,
        "measurement_identity": measurement_identity,
        "factor_candidate_ids": sorted(factor_candidate_ids),
        "experiment_scope_identity": experiment_scope_identity,
        "source_resolution_envelope_identity": envelope["identity"],
        "primary_text": envelope["primary_result_sentence"],
        "supporting_text_refs": sorted(
            envelope.get("preceding_sentence_refs", []) + envelope.get("following_sentence_refs", [])
        ),
        "methods_refs": envelope.get("methods_text_refs", []),
        "caption_refs": sorted(
            envelope.get("figure_caption_refs", []) + envelope.get("table_caption_refs", [])
        ),
        "evidence_refs": envelope.get("evidence_chain_refs", []),
        "context_refs": envelope.get("context_field_evidence_refs", []),
        "candidate_answers": sorted(candidate_answers),
        "candidate_answer_evidence": [],
        "candidate_answers_authoritative": False,
        "competing_candidate_count": competing,
        "ambiguity_reason": ambiguity_reason,
        "question_text": QUESTIONS[task_type],
        "allowed_labels": LABELS[task_type],
        "abstain_allowed": True,
        "annotation_priority": "core" if task_type != "measurement_method" else "enrichment",
        "expected_difficulty": difficulty,
        "disagreement_risk": "high" if difficulty == "hard" else "medium" if difficulty == "medium" else "low",
        "gold_eligibility_status": (
            "needs_domain_expert" if difficulty == "hard"
            else "eligible_for_double_annotation"
        ),
        "scientific_link_created": False,
        "annotation_executed": False,
        "human_gold": False,
        "provenance": provenance,
        "schema_version": (
            "measurement_method_annotation_target_v1"
            if task_type == "measurement_method"
            else "experimental_linkage_annotation_target_v1"
        ),
    }
    identity = core_identity(payload["schema_version"], {k: v for k, v in payload.items() if k != "provenance"})
    payload["annotation_target_id"] = identity
    payload["identity"] = identity
    return payload
