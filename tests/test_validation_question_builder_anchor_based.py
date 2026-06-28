import unittest

from code_engine.schemas.validation import ValidationAnchor
from code_engine.validation.question_builder import build_validation_questions_from_anchors


class AnchorQuestionBuilderTests(unittest.TestCase):
    def test_intents_remain_semantic_and_offline(self):
        intents=("expression_direction_check","binding_activity_check","pathway_membership_check","protein_interaction_check","clinical_context_check")
        anchors=[ValidationAnchor(anchor_id=f"A{i}",anchor_type="triple_anchor",entities=[{"canonical_id":"X","name":"x"}],validation_intent=intent) for i,intent in enumerate(intents)]
        questions=build_validation_questions_from_anchors(anchors,{"domain_id":"general_biomedical"})
        self.assertEqual([item.validator_intent for item in questions],list(intents))
        self.assertTrue(all(item.anchor_id for item in questions))


if __name__ == "__main__": unittest.main()
