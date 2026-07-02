import tempfile
import unittest

from code_engine.acquisition.literature_search import execute_acquisition_plan
from code_engine.query.intent import parse_research_intent
from code_engine.query.search_planner import build_literature_search_plan


class Client:
    def __init__(self): self.search_caps = []
    def search(self, query, source, max_results, year_from=None, year_to=None):
        self.search_caps.append(max_results)
        index = len(self.search_caps)
        return [{"paper_id": f"{index}{item}", "pmid": f"{index}{item}"} for item in range(max_results)]
    def fetch(self, record, source):
        return f"<PubmedArticle><PMID>{record['pmid']}</PMID><ArticleTitle>T{record['pmid']}</ArticleTitle><Abstract><AbstractText>A</AbstractText></Abstract></PubmedArticle>"


class DiversifiedAcquisitionEvenSplitTests(unittest.TestCase):
    def test_all_queries_are_attempted_with_even_caps(self):
        plan = build_literature_search_plan(parse_research_intent("metformin AMPK cancer"))
        client = Client()
        with tempfile.TemporaryDirectory() as tmp:
            report = execute_acquisition_plan(plan, repository_root=tmp, execute=True, network=True,
                                              max_papers=10, client=client, diversify_acquisition=True)
        self.assertEqual(len(client.search_caps), len(plan.pubmed_queries))
        self.assertEqual(sum(client.search_caps), 10)
        self.assertLessEqual(max(client.search_caps) - min(client.search_caps), 1)
        self.assertEqual(report["pubmed_query_skipped_count"], 0)


if __name__ == "__main__": unittest.main()
