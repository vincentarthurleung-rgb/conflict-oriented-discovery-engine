import unittest
from code_engine.corpus.artifact_provenance import attach_bibliographic_summary, attach_linked_paper_provenance
from code_engine.corpus.models import BibliographicMetadata


class BibliographicProvenanceTests(unittest.TestCase):
    def test_single_and_multi_paper_provenance(self):
        bibliography = BibliographicMetadata(canonical_paper_id="P", title="Title", journal="J", publication_year=2024, doi="10/x")
        claim = attach_bibliographic_summary({"paper_id": "old"}, bibliography)
        self.assertEqual((claim["canonical_paper_id"], claim["journal"]), ("P", "J"))
        conflict = attach_linked_paper_provenance({}, [claim])
        self.assertEqual(conflict["linked_dois"], ["10/x"])
        self.assertEqual(conflict["publication_year_range"], {"min": 2024, "max": 2024})
        missing = attach_bibliographic_summary({}, None)
        self.assertIn("bibliographic_metadata_unavailable", missing["warnings"])


if __name__ == "__main__": unittest.main()
