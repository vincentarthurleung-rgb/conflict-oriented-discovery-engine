import tempfile
import unittest

from code_engine.acquisition.literature_search import execute_acquisition_plan
from code_engine.query.intent import parse_research_intent
from code_engine.query.search_planner import build_literature_search_plan


class Client:
    def search(self, *args, **kwargs): return [{"paper_id": "1", "pmid": "1"}]
    def fetch(self, record, source):
        return "<PubmedArticle><PMID>1</PMID><ArticleTitle>T</ArticleTitle><Abstract><AbstractText>A</AbstractText></Abstract></PubmedArticle>"


class AcquisitionCountTaxonomyTests(unittest.TestCase):
    def test_explicit_esearch_efetch_and_effective_counts(self):
        plan = build_literature_search_plan(parse_research_intent("metformin AMPK cancer"))
        plan.pubmed_queries = plan.pubmed_queries[:1]
        with tempfile.TemporaryDirectory() as tmp:
            report = execute_acquisition_plan(plan, repository_root=tmp, execute=True, network=True, client=Client())
        self.assertEqual(report["pubmed_esearch_returned_id_count"], 1)
        self.assertEqual(report["pubmed_efetch_attempted_count"], 1)
        self.assertEqual(report["pubmed_efetch_returned_record_count"], 1)
        self.assertEqual(report["pubmed_new_raw_record_count"], 1)
        self.assertEqual(report["effective_acquisition_count"], 1)


if __name__ == "__main__": unittest.main()
