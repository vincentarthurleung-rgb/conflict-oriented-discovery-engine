import unittest
from pathlib import Path
class ZeroClaimVisualizationTests(unittest.TestCase):
 def test_frontend_explains_zero_claim(self):
  source=Path("src/code_engine/system_b/dashboard/static/app.js").read_text();self.assertIn("Execution passed, but no core observations survived",source);self.assertIn("no biological claim edges",source)
if __name__=="__main__":unittest.main()
