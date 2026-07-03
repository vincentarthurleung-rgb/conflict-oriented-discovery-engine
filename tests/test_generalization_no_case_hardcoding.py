import unittest

from code_engine.cli.generalization_audit import audit


class GeneralizationAuditTests(unittest.TestCase):
    def test_generic_source_has_no_problematic_literals(self):
        report = audit("src/code_engine", "configs", "tests")
        self.assertEqual(0, report["counts"]["problematic_source_hardcode_findings"], report["findings"])
        self.assertIn(report["decision"], {"GENERALIZATION_AUDIT_PASS", "GENERALIZATION_AUDIT_PASS_WITH_WARNINGS"})


if __name__ == "__main__":
    unittest.main()
