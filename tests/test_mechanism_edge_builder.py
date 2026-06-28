import unittest

from code_engine.mechanism.edge_builder import build_mechanism_edges_from_observations


def observation(**updates):
    value = {"triple_id": "o1", "subject": "A", "object": "B", "subject_canonical_id": "CHEM:A", "object_canonical_id": "GENE:B", "normalized_subject": "A", "normalized_object": "B", "relation_raw": "increases expression", "relation_sign": 1, "source_asset": "P1", "evidence_id": "EV1", "belief_weight": 0.8, "allow_high_confidence_graph_use": True, "normalization_quality": "resolved_or_acceptable", "subject_normalization_status": "resolved", "object_normalization_status": "resolved", "context": {"species": "mouse"}}
    value.update(updates)
    return value


class MechanismEdgeBuilderTests(unittest.TestCase):
    def test_observation_builds_grounded_edge(self):
        edge = build_mechanism_edges_from_observations([observation()])[0]
        self.assertEqual(edge.relation_type, "expression_increase")
        self.assertEqual(edge.observation_ids, ["o1"])
        self.assertEqual(edge.evidence_ids, ["EV1"])
        self.assertEqual(edge.paper_ids, ["P1"])

    def test_low_confidence_filter_and_explicit_include(self):
        low = observation(allow_high_confidence_graph_use=False, subject_normalization_status="ambiguous")
        self.assertEqual(build_mechanism_edges_from_observations([low]), [])
        edge = build_mechanism_edges_from_observations([low], include_low_confidence=True)[0]
        self.assertFalse(edge.allow_high_confidence_graph_use)
        self.assertEqual(edge.normalization_quality, "low_confidence")

    def test_seed_triple_is_excluded(self):
        self.assertEqual(build_mechanism_edges_from_observations([observation(is_evidence=False, source="llm_semantic_intake")]), [])


if __name__ == "__main__": unittest.main()
