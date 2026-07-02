import tempfile, unittest
from pathlib import Path
from code_engine.tools.audit_core_observations import render_core_audit
from tests.whitebox_test_support import make_whitebox

class CoreAuditCliTests(unittest.TestCase):
    def test_output_contains_only_core_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); make_whitebox(root, 5, 20); output=render_core_audit(root)
        self.assertIn("CORE OBSERVATIONS: 5", output)
        self.assertEqual(output.count("\n["), 5)
        for layer in ("mechanism_layer", "context_layer", "review_layer", "excluded"):
            self.assertNotIn(layer, output)

if __name__ == "__main__": unittest.main()
