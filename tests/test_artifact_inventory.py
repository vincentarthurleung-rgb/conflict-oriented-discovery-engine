import json
import tempfile
import unittest
from pathlib import Path

from src.query.parser import parse_research_query
from src.storage.artifact_inventory import build_artifact_inventory, find_unprocessed_papers_for_query


class ArtifactInventoryTests(unittest.TestCase):
    def test_paper_state_and_unprocessed_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data/metadata").mkdir(parents=True)
            (root / "data/raw/xml").mkdir(parents=True)
            (root / "data/interim/weighted_payloads").mkdir(parents=True)
            (root / "data/processed/l1").mkdir(parents=True)
            manifest = {
                "papers": {
                    "PMC1": {"title": "Ketamine BDNF study"},
                    "PMC2": {"title": "Ketamine BDNF follow-up"},
                }
            }
            (root / "data/metadata/global_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (root / "data/raw/xml/PMC1.xml").write_text("<article/>", encoding="utf-8")
            (root / "data/raw/xml/PMC2.xml").write_text("<article/>", encoding="utf-8")
            (root / "data/interim/weighted_payloads/PMC1_payload.json").write_text(
                json.dumps({"chunks": ["a", "b"]}), encoding="utf-8"
            )
            (root / "data/processed/l1/PMC1_extracted.json").write_text("{}", encoding="utf-8")

            inventory = build_artifact_inventory(root)
            indexed = {paper["paper_id"]: paper for paper in inventory["papers"]}
            self.assertTrue(indexed["PMC1"]["l1_extracted"])
            self.assertFalse(indexed["PMC2"]["l1_extracted"])
            query = parse_research_query("ketamine -> BDNF")
            pending = find_unprocessed_papers_for_query(query, inventory)
            self.assertEqual([paper["paper_id"] for paper in pending], ["PMC1", "PMC2"])


if __name__ == "__main__":
    unittest.main()
