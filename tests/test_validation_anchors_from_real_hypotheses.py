import unittest
from code_engine.validation.anchors import build_validation_anchors_from_hypotheses


class ValidationAnchorsFromHypothesesTests(unittest.TestCase):
    def test_requirements_become_hypothesis_anchor_intents(self):
        hypotheses = [{"hypothesis_id": "H", "entities": [{"canonical_id": "S", "name": "s"}, {"canonical_id": "O", "name": "o"}], "linked_conflict_ids": ["C"], "linked_mechanism_path_ids": ["P"], "validation_requirements": [{"requirement_type": "expression_direction_check"}, {"requirement_type": "pathway_membership_check"}]}]
        anchors = build_validation_anchors_from_hypotheses(hypotheses)
        hypothesis_anchors = [item for item in anchors if item.anchor_type == "hypothesis_anchor"]
        self.assertEqual({item.validation_intent for item in hypothesis_anchors}, {"expression_direction_check", "pathway_membership_check"})
        self.assertEqual(hypothesis_anchors[0].linked_hypothesis_ids, ["H"])


if __name__ == "__main__": unittest.main()
