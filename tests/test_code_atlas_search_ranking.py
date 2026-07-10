import tempfile
import unittest
from pathlib import Path

from code_engine.system_b.explorer.explorer_api import ExplorerAPI
from tests.test_system_b_knowledge_explorer import KnowledgeExplorerTests, write_jsonl


class AtlasSearchRankingTests(unittest.TestCase):
    def test_exact_entity_beats_generic_contains_and_reports_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            KnowledgeExplorerTests().fixture(root)
            entities = [
                {"entity_id": "generic", "label": "Generic A Hub", "display_label": "Generic A Hub", "aliases": [], "entity_type": "unknown_biomedical_entity", "degree": 999, "evidence_count": 999, "display_priority_score": 999, "source_case_ids": ["case"]},
                {"entity_id": "exact", "label": "A", "display_label": "A", "aliases": ["Alpha"], "entity_type": "gene", "degree": 1, "evidence_count": 1, "display_priority_score": 1, "source_case_ids": ["case"]},
                {"entity_id": "e2", "label": "B", "display_label": "B", "aliases": [], "entity_type": "biological_process", "degree": 1, "evidence_count": 1, "display_priority_score": 1, "source_case_ids": ["case"]},
            ]
            write_jsonl(root / "display_entities_v2.jsonl", entities)
            data = ExplorerAPI(root, root / "missing").dispatch("/api/search", {"q": ["A"]})[1]
            self.assertEqual(data["entities"][0]["entity_id"], "exact")
            self.assertEqual(data["entities"][0]["match_reason"], "exact")

    def test_pmid_exact_search_prioritizes_paper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            KnowledgeExplorerTests().fixture(root)
            write_jsonl(root / "triple_evidence_links.jsonl", [
                {"triple_id": "t1", "case_id": "case", "source_scope": "fulltext", "paper_title": "A study", "pmid": "12345", "evidence_sentence": "A promotes B."}
            ])
            data = ExplorerAPI(root, root / "missing").dispatch("/api/search", {"q": ["12345"]})[1]
            self.assertEqual(data["papers"][0]["pmid"], "12345")
            self.assertEqual(data["papers"][0]["match_reason"], "identifier_exact")


if __name__ == "__main__":
    unittest.main()
