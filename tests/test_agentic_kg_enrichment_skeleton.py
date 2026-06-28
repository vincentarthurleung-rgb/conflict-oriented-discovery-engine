import json
import unittest
from pathlib import Path

from code_engine.agents.kg_enrichment_agents import (
    ConflictReviewAgent, CoveragePlanningAgent, DomainRoutingAgent,
    EntityNormalizationAgent, HypothesisCriticAgent, RelationExtractionAgent,
    SchemaAlignmentAgent,
)


FIXTURE = json.loads((Path(__file__).parent / "fixtures/v42_minimal.json").read_text())


class AgenticKGEnrichmentTests(unittest.TestCase):
    def test_all_agents_only_return_validatable_suggestions(self):
        agents = [DomainRoutingAgent(), EntityNormalizationAgent(), RelationExtractionAgent(), SchemaAlignmentAgent(), ConflictReviewAgent(), CoveragePlanningAgent(), HypothesisCriticAgent()]
        for agent in agents:
            with self.subTest(agent=agent.__class__.__name__):
                result = agent.suggest(FIXTURE["hypothesis"])
                self.assertTrue(result.suggestion)
                self.assertTrue(result.requires_deterministic_validation)


if __name__ == "__main__": unittest.main()
