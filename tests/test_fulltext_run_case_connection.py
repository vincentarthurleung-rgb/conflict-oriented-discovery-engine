import unittest
from pathlib import Path
class ConnectionTests(unittest.TestCase):
 def test_live_path_has_no_old_placeholder(self):
  source=Path("src/code_engine/fulltext/stage.py").read_text(); self.assertNotIn("fulltext_l1_extractor_not_connected_in_run_case",source); self.assertIn("run_fulltext_l1_v2_extraction",source)
