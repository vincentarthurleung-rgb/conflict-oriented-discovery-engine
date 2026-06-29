import unittest

from code_engine.hypothesis.candidate_builder import build_hypothesis_candidates_from_run_artifacts


class HypothesisCandidateBuilderTests(unittest.TestCase):
    def build(self, confirmations=(), abstracts=(), mechanism=None, legacy=()):
        return list(build_hypothesis_candidates_from_run_artifacts(mechanism, iter(confirmations), iter(abstracts), iter(()), iter(legacy), iter(())))

    def test_fulltext_status_mapping(self):
        abstract = {"candidate_id": "C1", "subject_canonical_id": "S", "object_canonical_id": "O", "abstract_entropy": 1.0}
        statuses = {
            "confirmed_conflict": "mechanism_conflict_hypothesis",
            "context_resolved_conflict": "context_partition_hypothesis",
            "false_conflict_due_to_abstract_loss": "abstract_conflict_followup_hypothesis",
            "insufficient_fulltext_coverage": "coverage_gap_hypothesis",
        }
        for status, expected in statuses.items():
            with self.subTest(status=status):
                item = self.build([{"candidate_id": "confirmation_C1", "abstract_conflict_candidate_id": "C1", "confirmation_status": status}], [abstract])[0]
                self.assertEqual(item["candidate_type"], expected)
                if status not in {"confirmed_conflict", "context_resolved_conflict"}:
                    self.assertFalse(item["high_confidence"])

    def test_mechanism_path_gap_abstract_and_legacy(self):
        graph = {"nodes": [{"node_id": "A", "canonical_id": "A"}, {"node_id": "B", "canonical_id": "B"}], "paths": [{"path_id": "P", "node_ids": ["A", "B"], "edge_ids": ["E"], "start_node_id": "A", "end_node_id": "B", "mechanistic_completeness": .5}], "edges": [{"edge_id": "E", "source_node_id": "A", "target_node_id": "B", "relation_type": "unknown_mechanism_relation"}]}
        items = self.build(abstracts=[{"candidate_id": "C", "subject_canonical_id": "A", "object_canonical_id": "B"}], mechanism=graph)
        kinds = {item["candidate_type"] for item in items}
        self.assertTrue({"pathway_bridge_hypothesis", "mechanism_gap_hypothesis", "abstract_conflict_followup_hypothesis"}.issubset(kinds))
        abstract = next(item for item in items if item["candidate_type"] == "abstract_conflict_followup_hypothesis")
        self.assertTrue(abstract["requires_fulltext_confirmation"])
        self.assertEqual(self.build(legacy=[{"edge_id": "L", "source": "A", "target": "B"}])[0]["candidate_type"], "legacy_conflict_hypothesis")

    def test_confirmed_conflict_links_matching_mechanism_path(self):
        graph = {"nodes": [{"node_id": "A", "canonical_id": "S"}, {"node_id": "B", "canonical_id": "O"}], "edges": [], "paths": [{"path_id": "P", "node_ids": ["A", "B"], "edge_ids": ["E"], "start_node_id": "A", "end_node_id": "B", "mechanistic_completeness": .8}]}
        confirmation = {"candidate_id": "confirmation_C", "abstract_conflict_candidate_id": "C", "confirmation_status": "confirmed_conflict", "fulltext_entropy": 1.0}
        item = self.build([confirmation], [{"candidate_id": "C", "subject_canonical_id": "S", "object_canonical_id": "O"}], graph)[0]
        self.assertEqual(item["linked_mechanism_path_ids"], ["P"])
        self.assertEqual(item["linked_mechanism_edge_ids"], ["E"])


if __name__ == "__main__": unittest.main()
