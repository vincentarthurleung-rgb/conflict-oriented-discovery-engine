import inspect,unittest
from code_engine.cli import replay_case_from_stage
class ReplayIsolationTests(unittest.TestCase):
 def test_replay_has_no_l1_or_network_call(self):
  source=inspect.getsource(replay_case_from_stage.replay);self.assertNotIn("urlopen(",source);self.assertNotIn("build_l1_client",source);self.assertIn('network=False,api=False',source.replace(" ",""))
if __name__=="__main__":unittest.main()
