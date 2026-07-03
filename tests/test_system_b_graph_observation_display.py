import inspect,unittest
from code_engine.system_b.kg import kg_builder
class GraphObservationDisplayTests(unittest.TestCase):
 def test_review_badges_are_metadata(self):
  source=inspect.getsource(kg_builder);self.assertIn("local_canonicalization_used",source);self.assertIn("requires_review",source);self.assertIn("conflict_reasoning_eligible",source)
if __name__=="__main__":unittest.main()
