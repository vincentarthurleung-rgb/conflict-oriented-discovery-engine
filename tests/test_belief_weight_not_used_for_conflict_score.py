import unittest

from code_engine.graph.conflict_discovery import build_conflict_graph


def observation(eid, sign, belief):
    return {"evidence_id": eid, "triple_id": eid, "subject": "A", "object": "B",
            "normalized_subject": "A", "normalized_object": "B", "relation_sign": sign,
            "source_asset": "P" + eid, "doi": "", "article_title": "", "evidence_sentence": "x",
            "context": {}, "belief_weight": belief, "confidence": 0.4,
            "allow_high_confidence_graph_use": True, "normalization_quality": "resolved_or_acceptable"}


class ConflictBeliefWeightTests(unittest.TestCase):
    def test_belief_weight_not_used_for_conflict_score(self):
        first = [observation("1", 1, 0.1), observation("2", -1, 0.1)]
        second = [observation("1", 1, 0.99), observation("2", -1, 0.99)]
        graph_a, edges_a, _, _ = build_conflict_graph(first, latent_pool=[])
        graph_b, edges_b, _, _ = build_conflict_graph(second, latent_pool=[])
        self.assertEqual(edges_a, edges_b)
        self.assertEqual(graph_a[0]["mean_edge_confidence"], graph_b[0]["mean_edge_confidence"])


if __name__ == "__main__": unittest.main()
