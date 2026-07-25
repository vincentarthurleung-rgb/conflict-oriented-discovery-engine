"""Read-only adapters for legacy candidate inputs.

This module intentionally contains no discovery or provider integration.
"""

def candidate_generation_policy_identity(candidate: dict) -> str:
    return candidate.get("candidate_generation_version", "")

