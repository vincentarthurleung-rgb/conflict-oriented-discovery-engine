import inspect,unittest
from code_engine.cli import replay_case_from_stage
class ReplayManifestTests(unittest.TestCase):
 def test_manifest_contract_is_written(self):
  source=inspect.getsource(replay_case_from_stage);self.assertIn("case_stage_replay_v1",source);self.assertIn("reused_artifacts",source);self.assertIn("upstream_artifacts_reused",source)
if __name__=="__main__":unittest.main()
