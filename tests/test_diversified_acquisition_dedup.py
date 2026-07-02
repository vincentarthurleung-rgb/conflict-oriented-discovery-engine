import tempfile
import unittest

from code_engine.acquisition.literature_search import execute_acquisition_plan
from code_engine.query.intent import parse_research_intent
from code_engine.query.search_planner import build_literature_search_plan


class DuplicateClient:
    def search(self, *args, **kwargs): return [{"paper_id": "1", "pmid": "1"}]
    def fetch(self, record, source):
        return "<PubmedArticle><PMID>1</PMID><ArticleTitle>Same</ArticleTitle><Abstract><AbstractText>A</AbstractText></Abstract></PubmedArticle>"


class DiversifiedAcquisitionDedupTests(unittest.TestCase):
    def test_duplicate_tracks_all_queries(self):
        plan = build_literature_search_plan(parse_research_intent("metformin AMPK cancer"))
        with tempfile.TemporaryDirectory() as tmp:
            report = execute_acquisition_plan(plan, repository_root=tmp, execute=True, network=True,
                                              max_papers=10, client=DuplicateClient(), diversify_acquisition=True)
        self.assertEqual(len(report["candidate_papers"]), 1)
        self.assertEqual(report["candidate_papers"][0]["matched_query_ids"], [q.query_id for q in plan.pubmed_queries])
        self.assertEqual(report["pubmed_dedup_removed_count"], len(plan.pubmed_queries) - 1)


if __name__ == "__main__": unittest.main()
