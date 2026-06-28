import unittest

from code_engine.validation.anchors import (
    build_validation_anchors_from_conflicts, build_validation_anchors_from_hypotheses,
    build_validation_anchors_from_mechanism_graph, build_validation_anchors_from_observations,
)


class ValidationAnchorTests(unittest.TestCase):
    def test_hypothesis_triple_gap_and_clinical_provenance(self):
        anchors=build_validation_anchors_from_hypotheses([{"hypothesis_id":"H1","seed_pair":"drug -> disease","relation_family":"clinical_outcome","evidence_ids":["E1"],"predicted_missing_links":[{"source":"A","target":"B","relation_family":"pathway_mechanism"}]}])
        types={item.anchor_type for item in anchors}
        self.assertTrue({"hypothesis_anchor","triple_anchor","clinical_context_anchor","mechanism_gap_anchor"}.issubset(types))
        self.assertTrue(all("H1" in item.linked_hypothesis_ids for item in anchors))
        self.assertTrue(any("exploratory_anchor_entity_missing_canonical_id" in item.warnings for item in anchors))

    def test_conflict_mechanism_and_gene_set(self):
        conflict=build_validation_anchors_from_conflicts([{"candidate_id":"C1","subject_canonical_id":"A","object_canonical_id":"B","relation_family":"gene_expression","linked_evidence_ids":["E1"]}])[0]
        self.assertEqual(conflict.anchor_type,"conflict_anchor")
        graph=build_validation_anchors_from_mechanism_graph({"paths":[{"path_id":"P1","node_ids":["A","B"]}],"edges":[{"edge_id":"M1","relation_type":"unknown_mechanism_relation","subject_name":"A","object_name":"B"}]})
        self.assertEqual({item.anchor_type for item in graph},{"mechanism_path_anchor","mechanism_gap_anchor"})
        observations=[{"subject_canonical_id":"G1","subject":"G1","subject_entity_type":"gene","object_canonical_id":"G2","object":"G2","object_entity_type":"gene","allow_high_confidence_graph_use":True}]
        self.assertIn("gene_set_anchor",{item.anchor_type for item in build_validation_anchors_from_observations(observations)})


if __name__ == "__main__": unittest.main()
