import tempfile
import unittest
from pathlib import Path

from code_engine.acquisition.literature_search import execute_acquisition_plan, parse_pubmed_xml
from code_engine.domain.router import default_domain_router
from code_engine.extraction.abstract_screening import run_abstract_l1_screening
from code_engine.query.intake import parse_research_intake
from code_engine.query.search_planner import build_literature_search_plan
from code_engine.workflow.steps import run_abstract_l1_step


XML = """<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1</PMID><Article>
<ArticleTitle>Metformin AMPK study</ArticleTitle><Abstract>
<AbstractText Label="BACKGROUND">Metformin affects AMPK.</AbstractText>
<AbstractText Label="RESULTS">AMPK decreased in cancer cells.</AbstractText></Abstract>
<Journal><Title>Journal</Title><JournalIssue><PubDate><Year>2024</Year></PubDate></JournalIssue></Journal>
</Article></MedlineCitation><PubmedData><ArticleIdList><ArticleId IdType="doi">10.1/x</ArticleId>
</ArticleIdList></PubmedData></PubmedArticle></PubmedArticleSet>"""


class FakePubMedClient:
    def __init__(self): self.search_sources = []; self.fetch_sources = []
    def search(self, query, source, max_results, year_from=None, year_to=None):
        self.search_sources.append(source)
        return [{"paper_id": "1", "pmid": "1"}]
    def fetch(self, record, source):
        self.fetch_sources.append(source)
        return XML


class AbstractRetrievalPubMedFirstTests(unittest.TestCase):
    def test_pubmed_only_xml_is_parsed_and_consumed(self):
        intake = parse_research_intake("metformin AMPK cancer", execute=False, use_api=False)
        profile = default_domain_router().get_or_default(intake.research_intent.domain_id)
        plan = build_literature_search_plan(intake.research_intent, seed_triples=intake.seed_triples,
                                            domain_profile=profile, semantic_intake=intake.semantic_intake)
        self.assertTrue(all("open access[filter]" not in item.query_string.casefold() for item in plan.pubmed_queries))
        client = FakePubMedClient()
        with tempfile.TemporaryDirectory() as tmp:
            report = execute_acquisition_plan(plan, repository_root=tmp, execute=True, network=True,
                                              max_papers=1, client=client)
            self.assertEqual(client.search_sources, ["pubmed"])
            self.assertEqual(client.fetch_sources, ["pubmed"])
            self.assertEqual(report["initial_fulltext_download_count"], 0)
            paper = report["downloaded_papers"][0]
            self.assertTrue(paper["abstract_available"])
            self.assertIn("Metformin affects AMPK", paper["abstract_text"])
            output = run_abstract_l1_screening([paper], {}, Path(tmp) / "artifacts")
            self.assertEqual(output["summary"]["abstract_available_count"], 1)
            self.assertGreater(output["summary"]["planned_l1_call_count"], 0)
            run = Path(tmp) / "run"; artifacts = run / "artifacts"; artifacts.mkdir(parents=True)
            (artifacts / "acquisition_report.json").write_text(__import__("json").dumps(report))
            (artifacts / "domain_profile.json").write_text("{}")
            (artifacts / "run_paper_manifest.jsonl").write_text("{}\n")
            step = run_abstract_l1_step(run_dir=run, execute=False, api=False, max_papers=None,
                                        l1_mode="abstract_screening", repository_root=Path(tmp),
                                        l1_task_cache_enabled=False)
            self.assertGreater(step.summary["planned_l1_call_count"], 0)

    def test_parser_merges_labeled_abstract_sections(self):
        parsed = parse_pubmed_xml(XML)
        self.assertEqual(len(parsed["abstract_sections"]), 2)
        self.assertIn("BACKGROUND:", parsed["abstract_text"])


if __name__ == "__main__": unittest.main()
