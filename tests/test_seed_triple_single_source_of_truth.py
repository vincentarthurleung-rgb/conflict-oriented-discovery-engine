import json
import tempfile
import unittest
from pathlib import Path

from code_engine.workflow.orchestrator import run_workflow


class SeedTripleSourceOfTruthTests(unittest.TestCase):
    def test_weak_seed_and_identity_are_consistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_workflow("metformin AMPK cancer", run_dir=root, until="report",
                         l1_mode="abstract_screening", allow_uncertain_intake=True,
                         merge_knowledge_store=False)
            intake = json.loads((root / "artifacts/intake.json").read_text())
            search = json.loads((root / "artifacts/search_plan.json").read_text())
            card = json.loads((root / "triple_card.json").read_text())
            manifest = json.loads((root / "triple_run_manifest.json").read_text())
            provenance = json.loads((root / "artifacts/runtime_provenance_report.json").read_text())
            final = json.loads((root / "artifacts/final_report.json").read_text())
            seed = intake["unified_seed_triple"]
            self.assertEqual((seed["subject"]["name"], seed["object"]["name"]), ("metformin", "AMPK"))
            self.assertEqual(seed["context"]["context_terms"], ["cancer"])
            self.assertEqual(seed["relation"]["name"], "unspecified_association")
            ids = {seed["triple_id"], search["seed_triple"]["triple_id"], card["triple_id"],
                   manifest["triple_id"], provenance["triple_id"], final["triple_id"]}
            self.assertEqual(len(ids), 1)
            self.assertTrue(provenance["triple_id_consistent_across_artifacts"])


if __name__ == "__main__": unittest.main()
