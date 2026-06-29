import unittest
from datetime import datetime, timezone
from code_engine.corpus.identity import normalize_doi, resolve_paper_identity
from code_engine.corpus.models import BibliographicMetadata, PaperRegistryRecord


def record(payload):
    identity = resolve_paper_identity(payload, [])
    now = datetime.now(timezone.utc).isoformat()
    return PaperRegistryRecord(canonical_paper_id=identity.canonical_paper_id, canonical_paper_key=identity.canonical_paper_key, identity=identity, bibliographic=BibliographicMetadata(canonical_paper_id=identity.canonical_paper_id, title=payload.get("title"), doi=payload.get("doi"), pmid=payload.get("pmid"), pmcid=payload.get("pmcid")), created_at=now, updated_at=now)


class PaperIdentityTests(unittest.TestCase):
    def test_identifier_priority_and_normalization(self):
        self.assertEqual(normalize_doi("https://doi.org/10.1/ABC."), "10.1/abc")
        for field, value, method in (("doi", "10.1/x", "doi_exact"), ("pmid", "123", "pmid_exact"), ("pmcid", "PMC9", "pmcid_exact")):
            base = record({field: value, "title": "A"})
            result = resolve_paper_identity({field: value, "title": "Different"}, [base])
            self.assertEqual(result.duplicate_resolution_method, method)
            self.assertEqual(result.canonical_paper_id, base.canonical_paper_id)

    def test_title_author_merge_but_title_only_is_possible_duplicate(self):
        base = record({"paper_id": "A", "title": "A study: of MTOR", "year": 2024, "first_author": "Li"})
        match = resolve_paper_identity({"paper_id": "B", "title": "A study of MTOR", "year": 2024, "first_author": "Li"}, [base])
        self.assertEqual(match.duplicate_resolution_method, "title_year_first_author_exact")
        possible = resolve_paper_identity({"paper_id": "C", "title": "A study of MTOR"}, [base])
        self.assertNotEqual(possible.canonical_paper_id, base.canonical_paper_id)
        self.assertTrue(any("possible_duplicate" in warning for warning in possible.warnings))

    def test_missing_doi_has_stable_canonical_id(self):
        left = resolve_paper_identity({"pmid": "42", "title": "x"}, [])
        right = resolve_paper_identity({"pmid": "PMID: 42", "title": "x"}, [])
        self.assertEqual(left.canonical_paper_id, right.canonical_paper_id)


if __name__ == "__main__": unittest.main()
