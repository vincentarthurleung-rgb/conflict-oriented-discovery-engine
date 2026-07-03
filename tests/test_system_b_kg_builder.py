import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from code_engine.system_b.kg import KGBuilder, KGStore


class KGBuilderTests(unittest.TestCase):
    def test_builds_case_validator_and_entities_without_network(self):
        with tempfile.TemporaryDirectory() as td, patch("urllib.request.urlopen", side_effect=AssertionError("network call")):
            output = Path(td) / "kg"
            summary = KGBuilder("case_bundles", output).build()
            nodes, edges, evidence = KGStore(output).load()
            ids = {item["id"] for item in nodes}
            self.assertEqual(summary["case_count_indexed"], 1)
            self.assertIn("case:metformin_ampk_cancer", ids)
            self.assertIn("validator:lincs_l1000", ids)
            self.assertIn("entity:ampk", ids)
            self.assertEqual(len(evidence), 3)
            self.assertTrue(any(item["edge_type"] == "claim_relation" for item in edges))

    def test_malformed_observation_is_skipped_with_warning(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); bundle = root / "bundles" / "case"
            shutil.copytree("case_bundles/metformin_ampk_cancer", bundle)
            with (bundle / "core_observations.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"subject_name": "incomplete"}) + "\n")
            output = root / "kg"; summary = KGBuilder(root / "bundles", output).build()
            warnings = [json.loads(line) for line in (output / "kg_build_warnings.jsonl").read_text().splitlines()]
            self.assertEqual(summary["skipped_record_count"], 1)
            self.assertEqual(warnings[0]["reason"], "missing_subject_predicate_object")


if __name__ == "__main__": unittest.main()
