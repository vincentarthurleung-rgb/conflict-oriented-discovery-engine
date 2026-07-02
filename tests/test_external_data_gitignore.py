import unittest
from pathlib import Path
class GitignoreTests(unittest.TestCase):
 def test_external_data_is_ignored(self): self.assertIn("data/external/",Path(".gitignore").read_text().splitlines())
if __name__=="__main__": unittest.main()
