import unittest
from pydantic import ValidationError

from code_engine.encoder.models import DomainRoutingDecision, SemanticIntakeResult, SemanticResearchIntent, SemanticSeedTriple


class SemanticIntakeModelTests(unittest.TestCase):
    def test_round_trip_and_seed_boundary(self):
        routing = DomainRoutingDecision(confidence=0.8)
        result = SemanticIntakeResult(research_intent=SemanticResearchIntent(raw_user_input="A -> B", domain_routing=routing, confidence=0.8), domain_routing=routing, seed_triples=[SemanticSeedTriple(triple_id="s", subject="A", relation="affects", object="B", is_evidence=True, confidence=0.7)])
        loaded = SemanticIntakeResult.model_validate_json(result.model_dump_json())
        self.assertFalse(loaded.seed_triples[0].is_evidence)

    def test_confidence_bounds(self):
        with self.assertRaises(ValidationError):
            DomainRoutingDecision(confidence=1.1)


if __name__ == "__main__": unittest.main()
