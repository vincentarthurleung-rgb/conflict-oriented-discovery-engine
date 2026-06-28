import unittest

from code_engine.normalization.candidates import EntityCandidate, EntityResolutionRequest, EntityResolutionResult


class EntityCandidateModelTests(unittest.TestCase):
    def test_models_serialize_and_llm_boundary(self):
        request = EntityResolutionRequest(surface="sirolimus")
        candidate = EntityCandidate(surface="sirolimus", normalized_surface="sirolimus", source="llm", provider_name="fake", is_llm_suggested=True, is_grounded=True, overall_score=0.9)
        result = EntityResolutionResult(request=request, candidates=[candidate], normalization_status="llm_suggestion_ungrounded", confidence=0.4, decision_reason="test")
        loaded = EntityResolutionResult.model_validate_json(result.model_dump_json())
        self.assertFalse(loaded.candidates[0].is_grounded)
        self.assertTrue(loaded.candidates[0].requires_external_grounding)


if __name__ == "__main__": unittest.main()
