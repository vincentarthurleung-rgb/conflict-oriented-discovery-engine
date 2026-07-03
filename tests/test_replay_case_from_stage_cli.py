import tempfile,unittest
from pathlib import Path
from tests.replay_test_support import fixture
from code_engine.cli.replay_case_from_stage import replay
class ReplayCLITests(unittest.TestCase):
 def test_l2_replay_creates_new_run_and_graph_lane(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);profile,plan,source=fixture(root);result=replay(profile,plan,source,"l2",root/"runs","replay","r2",bundle_root=root/"bundles")
   new=Path(result["new_run"]);self.assertNotEqual(source.resolve(),new);self.assertTrue((new/"artifacts/l2_graph_observations.jsonl").is_file());self.assertEqual(1,result["raw_l1_claims_reused"])
if __name__=="__main__":unittest.main()
