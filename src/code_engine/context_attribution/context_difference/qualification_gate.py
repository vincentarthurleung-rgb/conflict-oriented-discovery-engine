"""Authority gate for future-standard L4 Context Difference creation."""
from __future__ import annotations

from ..conflict_candidate.qualification.models import ConflictCandidateQualificationV1


def require_qualified_candidate(
    qualification: ConflictCandidateQualificationV1,
) -> None:
    """Fail closed before creating a new authoritative L4 artifact."""
    if qualification.qualification_status != "qualified" or not qualification.qualified_for_l4:
        raise PermissionError(
            f"candidate_not_qualified_for_l4:{qualification.qualification_status}"
        )

