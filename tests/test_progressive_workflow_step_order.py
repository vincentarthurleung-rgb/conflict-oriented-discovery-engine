import unittest

from code_engine.workflow.models import STEP_ORDER


class ProgressiveWorkflowStepOrderTests(unittest.TestCase):
    def test_core_graph_and_fulltext_gates_are_ordered(self):
        expected = ["l2_abstract", "evidence_graph_core", "abstract_conflict_screening",
                    "fulltext_escalation", "fulltext_availability", "fulltext_acquisition",
                    "fulltext_l1", "l2_fulltext", "fulltext_conflict_confirmation", "hypothesis",
                    "conflict_timeline", "validation", "report"]
        positions = [STEP_ORDER.index(item) for item in expected]
        self.assertEqual(positions, sorted(positions))


if __name__ == "__main__": unittest.main()
