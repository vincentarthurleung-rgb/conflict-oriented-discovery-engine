from __future__ import annotations

from typing import Any

SCIENTIFIC_STATUS_PRIORITY = (
    "incomplete",
    "all_extractions_rejected",
    "partial_validation_failure",
    "no_pairs_attributed",
    "validated_complete",
    "validated_partial",
)


def calculate_scientific_status(
    *,
    purpose: str,
    selected_extraction_count: int,
    validated_extraction_count: int,
    rejected_extraction_count: int,
    selected_pair_count: int,
    validated_pair_count: int,
    blocked_pair_count: int,
    pending_pair_count: int,
    transport_complete: bool,
    planned_coverage_complete: bool,
) -> str:
    """Apply a fixed, order-independent scientific status precedence."""
    if (
        not transport_complete
        or pending_pair_count > 0
        or validated_extraction_count + rejected_extraction_count < selected_extraction_count
    ):
        return "incomplete"
    if selected_extraction_count > 0 and validated_extraction_count == 0 and rejected_extraction_count > 0:
        return "all_extractions_rejected"
    if rejected_extraction_count > 0 or blocked_pair_count > 0:
        return "partial_validation_failure" if validated_extraction_count or validated_pair_count else "all_extractions_rejected"
    if validated_extraction_count > 0 and selected_pair_count > 0 and validated_pair_count == 0:
        return "no_pairs_attributed"
    if (
        purpose == "complete"
        and planned_coverage_complete
        and validated_extraction_count == selected_extraction_count
        and validated_pair_count == selected_pair_count
    ):
        return "validated_complete"
    if (
        purpose == "smoke"
        and validated_extraction_count == selected_extraction_count
        and validated_pair_count == selected_pair_count
    ):
        return "validated_partial"
    return "incomplete"


def scientific_readiness(summary: dict[str, Any]) -> dict[str, Any]:
    status = summary.get("scientific_status")
    validated_pairs = int(summary.get("validated_pair_count") or 0)
    ready = status in {"validated_complete", "validated_partial"} and validated_pairs > 0
    return {
        "scientifically_ready": ready,
        "handoff_allowed": ready,
        "scientific_status": status,
        "validated_pair_count": validated_pairs,
        "coverage_complete": bool(summary.get("coverage_complete")),
        "publication_ready": ready and status == "validated_complete",
        "atlas_activation_allowed": False,
        "reason": (
            "validated_pair_attribution_available"
            if ready else "scientific_status_or_validated_pair_count_blocks_handoff"
        ),
    }


__all__ = [
    "SCIENTIFIC_STATUS_PRIORITY", "calculate_scientific_status",
    "scientific_readiness",
]
