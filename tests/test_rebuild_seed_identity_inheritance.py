import json, tempfile, unittest
from tests.rebuild_test_support import TRIPLE, make_rebuild

class RebuildSeedTests(unittest.TestCase):
    def test_seed_is_inherited_without_planners(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, output = make_rebuild(tmp)
            value = json.loads((output / "artifacts/runtime_provenance_report.json").read_text())
        policy = value["seed_identity_rebuild_policy"]
        self.assertEqual(policy["mode"], "inherit_from_source_run")
        self.assertEqual(policy["rebuilt_triple_id"], TRIPLE)
        self.assertFalse(policy["semantic_intake_called"])
        self.assertFalse(policy["llm_search_intent_called"])
        self.assertFalse(policy["triple_id_changed"])

if __name__ == "__main__": unittest.main()
