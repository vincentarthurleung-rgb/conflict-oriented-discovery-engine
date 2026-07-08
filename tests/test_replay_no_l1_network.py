import inspect,unittest
from code_engine.cli import replay_case_from_stage
class ReplayIsolationTests(unittest.TestCase):
 def test_replay_has_no_l1_or_network_call(self):
  source=inspect.getsource(replay_case_from_stage.replay);self.assertNotIn("urlopen(",source);self.assertNotIn("build_l1_client",source)
 def test_replay_defaults_to_network_disabled(self):
  """replay() signature must default to network=False for safe offline replay."""
  sig=inspect.signature(replay_case_from_stage.replay)
  self.assertFalse(sig.parameters["network"].default)
  self.assertFalse(sig.parameters["api"].default)
  self.assertFalse(sig.parameters["entity_network_lookup"].default)
 def test_cli_supports_network_flag(self):
  source=inspect.getsource(replay_case_from_stage.main)
  self.assertIn("--network",source)
  self.assertIn("--api",source)
  self.assertIn("--entity-network-lookup",source)
 def test_entity_network_lookup_defaults_false(self):
  """--entity-network-lookup must default to False for conservative replay."""
  sig=inspect.signature(replay_case_from_stage.replay)
  self.assertFalse(sig.parameters["entity_network_lookup"].default,
                   "entity_network_lookup must default to False in replay signature")
if __name__=="__main__":unittest.main()
