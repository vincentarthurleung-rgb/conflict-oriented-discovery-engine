import tempfile
import unittest
from pathlib import Path

from code_engine.acquisition.fulltext_availability import (
    acquire_selected_fulltexts, build_fulltext_escalation_candidates,
    resolve_fulltext_availability,
)


class FulltextClient:
    def __init__(self): self.ids = []
    def fetch(self, record, source):
        self.ids.append(record["canonical_paper_id"])
        return "Ketamine increased BDNF in human cells."


class ConflictGatedFulltextTests(unittest.TestCase):
    def test_only_conflict_selected_available_paper_is_downloaded(self):
        papers = [
            {"paper_id": "P1", "canonical_paper_id": "P1", "pmid": "1", "pmcid": "PMC1"},
            {"paper_id": "P2", "canonical_paper_id": "P2", "pmid": "2"},
            {"paper_id": "P3", "canonical_paper_id": "P3", "pmid": "3", "pmcid": "PMC3"},
        ]
        selected = build_fulltext_escalation_candidates(
            [{"candidate_id": "C", "paper_ids": ["P1", "P2"]}], [], [], papers,
            triple_id="T", query_hash="Q",
        )
        self.assertEqual({item["canonical_paper_id"] for item in selected}, {"P1", "P2"})
        self.assertNotIn("P3", {item["canonical_paper_id"] for item in selected})
        available = resolve_fulltext_availability(selected)
        client = FulltextClient()
        with tempfile.TemporaryDirectory() as tmp:
            records, calls = acquire_selected_fulltexts(available, repository_root=Path(tmp),
                                                        execute=True, network=True, client=client)
        self.assertEqual(calls, 1)
        self.assertEqual(client.ids, ["P1"])
        unavailable = next(item for item in records if item["canonical_paper_id"] == "P2")
        self.assertEqual(unavailable["acquisition_status"], "skipped")
        self.assertTrue(unavailable["reason"])


if __name__ == "__main__": unittest.main()
