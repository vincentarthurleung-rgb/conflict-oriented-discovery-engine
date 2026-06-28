import unittest

from code_engine.normalization.adjudicator import adjudicate_entity_candidates
from code_engine.normalization.candidates import EntityCandidate, EntityResolutionRequest


def candidate(cid="X:1", score=.9, *, curated=False, grounded=True, provider="external", llm=False):
    return EntityCandidate(surface="x", normalized_surface="x", candidate_id=cid, canonical_id=None if llm else cid, canonical_name=None if llm else cid, entity_type="gene", source=provider, provider_name=provider, match_score=score, source_reliability=score, overall_score=score, is_curated=curated, is_grounded=grounded, is_llm_suggested=llm)


class AdjudicatorTests(unittest.TestCase):
    def setUp(self): self.request = EntityResolutionRequest(surface="x")

    def test_resolution_states(self):
        self.assertEqual(adjudicate_entity_candidates(self.request, [candidate(curated=True)]).normalization_status, "resolved_curated")
        self.assertEqual(adjudicate_entity_candidates(self.request, [candidate()]).normalization_status, "resolved_external_grounded")
        self.assertEqual(adjudicate_entity_candidates(self.request, [candidate("X:1"), candidate("X:2", .88)]).normalization_status, "ambiguous")
        self.assertEqual(adjudicate_entity_candidates(self.request, [candidate(llm=True, grounded=False, score=.4)]).normalization_status, "llm_suggestion_ungrounded")
        self.assertEqual(adjudicate_entity_candidates(self.request, []).normalization_status, "unresolved")
        self.assertEqual(adjudicate_entity_candidates(self.request, [candidate(score=.6)]).normalization_status, "manual_review_required")


if __name__ == "__main__": unittest.main()
