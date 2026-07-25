"""Machine reuse is a candidate gate, never Human Gold or conflict authority."""
from __future__ import annotations


def evaluate_readiness(
    *, observation_type: str, integrity_status: str,
    has_claim_evidence: bool, raw_layers_separate: bool = True,
) -> tuple[str, list[str]]:
    if observation_type == "non_experimental_claim":
        return "non_experimental_claim", []
    if integrity_status == "structurally_complete" and raw_layers_separate:
        return "machine_reusable_candidate", []
    if integrity_status == "structurally_complete_with_limitations":
        return "usable_with_major_limitations", [integrity_status]
    if has_claim_evidence and integrity_status in {
        "incomplete_missing_factor", "incomplete_missing_measurement",
        "incomplete_missing_result", "incomplete_missing_linkage", "unresolved",
    }:
        return "text_evidence_only", [integrity_status]
    if integrity_status == "unresolved":
        return "unassessed", ["observation_type_unresolved"]
    return "unusable", [integrity_status]

