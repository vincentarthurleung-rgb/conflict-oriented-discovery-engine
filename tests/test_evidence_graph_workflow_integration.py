import unittest

from code_engine.workflow.models import STEP_ORDER


class WorkflowIntegrationTests(unittest.TestCase):
    def test_graph_step_is_after_timeline_before_validation(self):
        self.assertLess(STEP_ORDER.index("conflict_timeline"), STEP_ORDER.index("evidence_graph"))
        self.assertLess(STEP_ORDER.index("evidence_graph"), STEP_ORDER.index("validation"))


if __name__ == "__main__": unittest.main()
