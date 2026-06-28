import json
import unittest
from pathlib import Path

from code_engine.hypothesis.hyperedge_builder import build_hypothesis_hyperedge
from code_engine.hypothesis.reasoning import build_reasoning_record


FIXTURE = json.loads((Path(__file__).parent / "fixtures/v42_minimal.json").read_text())


class ReasoningRecordTests(unittest.TestCase):
    def test_reasoning_uses_grounded_hyperedge_fields(self):
        hyperedge = build_hypothesis_hyperedge(FIXTURE["hypothesis"], conflict_edges=[FIXTURE["conflict_edge"]])
        record = build_reasoning_record(hyperedge)
        self.assertIn("KETAMINE->BDNF", record.bottleneck)
        self.assertIn("NMDAR", record.mechanism)


if __name__ == "__main__": unittest.main()
