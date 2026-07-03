import tempfile,unittest
from pathlib import Path
from tests.replay_test_support import fixture
from code_engine.cli.replay_case_from_stage import replay
class ReplayBundleTests(unittest.TestCase):
 def test_bundle_suffix_does_not_overwrite_base(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);profile,plan,source=fixture(root);base=root/"bundles/synthetic_replay";base.mkdir(parents=True);(base/"marker").write_text("v1")
   result=replay(profile,plan,source,"bundle",root/"runs","replay","replay_l2_v2",bundle_root=root/"bundles")
   self.assertEqual("v1",(base/"marker").read_text());self.assertIn("__replay_l2_v2",result["bundle"]);self.assertEqual("v2_replay_bundle",result["case_version"])
if __name__=="__main__":unittest.main()
