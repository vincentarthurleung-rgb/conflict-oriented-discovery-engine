import inspect
import unittest

from code_engine.system_b import batch_ingest, case_card, quality_classifier


class SystemBGeneralizationTests(unittest.TestCase):
    def test_case_roles_are_not_selected_by_known_case_ids(self):
        source = "\n".join(inspect.getsource(module) for module in (batch_ingest, case_card, quality_classifier))
        self.assertNotIn('case_id == "metformin_ampk_cancer"', source)
        self.assertNotIn('case_id == "autophagy_cancer_chemoresistance"', source)


if __name__ == "__main__":
    unittest.main()
