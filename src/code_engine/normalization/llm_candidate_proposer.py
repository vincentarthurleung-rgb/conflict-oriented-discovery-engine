"""Disabled dry-run interface for unvalidated normalization suggestions."""

from __future__ import annotations

from code_engine.normalization.models import NormalizationCandidate


class LLMCandidateProposer:
    enabled = False

    def propose(self, raw_text: str) -> list[NormalizationCandidate]:
        """Return no candidates by default; no API client exists in this stub."""

        if not self.enabled:
            return []
        return [
            NormalizationCandidate(
                canonical_id=f"SUGGESTION:{raw_text.strip().upper()}",
                canonical_name=raw_text.strip(),
                entity_type="unknown",
                semantic_level="unvalidated_suggestion",
                aliases=[raw_text.strip()],
                score=0.0,
                source="llm_candidate_proposer_stub",
                match_type="llm_suggestion_unvalidated",
                warnings=["requires_deterministic_validation"],
            )
        ]
