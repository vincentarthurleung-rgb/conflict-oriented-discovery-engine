import unittest
from code_engine.hypothesis.hyperedge_builder import build_hypothesis_hyperedge
from code_engine.hypothesis.reasoning import build_reasoning_record


class HypothesisReasoningIntegrationTests(unittest.TestCase):
    def test_abstract_limit_and_mechanism_context_explanations(self):
        edge = build_hypothesis_hyperedge({"hypothesis_id": "H", "candidate_type": "context_partition_hypothesis", "source_scope": "abstract", "hypothesis_text": "contexts separate directions", "mechanism_path": ["A", "M", "B"], "linked_mechanism_path_ids": ["P"], "context_variables": ["species"], "linked_evidence_ids": ["E"]})
        record = build_reasoning_record(edge)
        self.assertEqual(record.input_evidence, ["E"])
        self.assertIn("A -> M -> B", record.mechanism_bridge)
        self.assertIn("species", record.context_partition)
        self.assertTrue(any("abstract" in item.lower() for item in record.limitations))


if __name__ == "__main__": unittest.main()
